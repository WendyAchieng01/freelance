import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count

from core.models import Job, Response, Chat


class Command(BaseCommand):
    help = (
        "Assign freelancers trying to meet required_freelancers count.\n"
        "Will try to assign exactly required_freelancers freelancers per job when possible.\n"
        "--assign-per-job acts as a soft maximum (for testing / limiting)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--num-jobs',
            type=int,
            default=20,
            help='Max number of jobs to process (default: 20)',
        )
        parser.add_argument(
            '--assign-per-job',
            type=int,
            default=999,  # high default → effectively disabled unless set
            help='Maximum freelancers to assign per job (soft cap). Default: no limit (tries required_freelancers)',
        )
        parser.add_argument(
            '--complete',
            type=int,
            help='Try to mark the first N in-progress jobs as completed',
        )
        parser.add_argument(
            '--force-complete',
            action='store_true',
            help='Allow completing jobs even if freelancer count requirement is not met',
        )
        parser.add_argument(
            '--unassign',
            action='store_true',
            help='Clear ALL current assignments before doing anything else',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate without saving changes',
        )
        parser.add_argument(
            '--only',
            type=int,
            nargs='*',
            help='Only process these job IDs',
        )

    def handle(self, *args, **options):
        num_jobs = max(1, options['num_jobs'])
        max_per_job = max(1, options['assign_per_job'])
        dry_run = options['dry_run']
        force_complete = options['force_complete']

        if options['unassign']:
            self.stdout.write("Clearing all assignments...")
            Job.objects.update(assigned_at=None, status='open')
            Job.selected_freelancers.through.objects.all().delete()
            Chat.objects.filter(freelancer__isnull=False).delete()
            Response.objects.update(status='submitted')
            self.stdout.write(self.style.SUCCESS("All assignments cleared."))

        if options['complete']:
            self.complete_jobs(
                count=options['complete'],
                dry_run=dry_run,
                force=force_complete
            )
            # Only continue to assignment if num-jobs was explicitly changed
            if options.get('num_jobs') == 20 and not options.get('only'):
                return

        self.assign_jobs(
            max_jobs=num_jobs,
            max_per_job=max_per_job,
            dry_run=dry_run,
            only_ids=options.get('only'),
        )

    def complete_jobs(self, count: int, dry_run: bool, force: bool):
        jobs = Job.objects.filter(
            status='in_progress').order_by('assigned_at')[:count]

        if not jobs.exists():
            self.stdout.write(self.style.WARNING("No in-progress jobs found."))
            return

        self.stdout.write(f"Processing {jobs.count()} in-progress jobs...")

        completed = 0
        for job in jobs:
            if dry_run:
                self.stdout.write(
                    f"[DRY] Would complete #{job.id} — {job.title[:60]}")
                completed += 1
                continue

            can_complete = job.mark_as_completed(force=force)

            if can_complete:
                Response.objects.filter(
                    job=job, status='accepted').update(status='completed')
                Chat.objects.filter(job=job).update(active=False)
                self.stdout.write(self.style.SUCCESS(
                    f"COMPLETED → #{job.id} {job.title[:55]}"))
                completed += 1
            else:
                reasons = []
                if job.status != 'in_progress':
                    reasons.append(f"status is '{job.status}'")
                if not job.payment_verified:
                    reasons.append("payment not verified")
                current = job.selected_freelancers.count()
                req = job.required_freelancers
                if current < req:
                    reasons.append(
                        f"only {current}/{req} freelancers assigned")
                reason_str = "; ".join(reasons) or "unknown"
                self.stdout.write(self.style.WARNING(
                    f"Skipped #{job.id} — {reason_str}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nCompleted: {completed}/{jobs.count()} jobs"))

    def assign_jobs(self, max_jobs: int, max_per_job: int, dry_run: bool, only_ids: list | None = None):
        qs = Job.objects.filter(
            status='open',
            payment_verified=True,
        ).annotate(
            resp_count=Count('responses')
        ).filter(
            resp_count__gt=0
        ).order_by('posted_date')

        if only_ids:
            qs = qs.filter(id__in=only_ids)

        jobs = list(qs[:max_jobs * 4])

        if not jobs:
            self.stdout.write(self.style.WARNING("No eligible jobs found."))
            return

        self.stdout.write(
            f"Found {len(jobs)} eligible jobs. Trying to assign freelancers...")

        total_hired = 0

        for job in jobs:
            already_hired = job.selected_freelancers.count()
            required = job.required_freelancers
            still_needed = required - already_hired

            if still_needed <= 0:
                continue

            # Try to reach required number, but respect soft cap if set
            target_this_job = min(still_needed, max_per_job)

            self.stdout.write(self.style.HTTP_INFO(
                f"Job #{job.id} ({job.title[:50]}…): "
                f"{already_hired}/{required} — trying to assign up to {target_this_job} more"
            ))

            hired_this_job = 0
            ranked = self.get_ranked_responses(job)

            if len(ranked) < target_this_job:
                self.stdout.write(self.style.WARNING(
                    f"  Warning: only {len(ranked)} suitable applicants available "
                    f"(wanted {target_this_job} more for job #{job.id})"
                ))

            for response in ranked:
                if hired_this_job >= target_this_job:
                    break

                freelancer = response.user

                if job.selected_freelancers.filter(id=freelancer.id).exists():
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  [DRY] Would hire {freelancer.username} → #{job.id}")
                    hired_this_job += 1
                    total_hired += 1
                    continue

                # Assign
                job.selected_freelancers.add(freelancer)
                if not job.assigned_at:
                    job.assigned_at = timezone.now()
                if job.status != 'in_progress':
                    job.status = 'in_progress'
                job.save(update_fields=['assigned_at', 'status'])

                # Accept response
                response.status = 'accepted'
                extra = response.extra_data or {}
                extra.update({
                    'hired_at': timezone.now().isoformat(),
                    'note': 'Selected for the job!',
                })
                response.extra_data = extra
                response.save(update_fields=['status', 'extra_data'])

                # Chat
                Chat.objects.get_or_create(
                    job=job,
                    client=job.client,
                    freelancer=freelancer.profile,
                    defaults={'active': True}
                )

                hired_this_job += 1
                total_hired += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  HIRED {freelancer.username} → #{job.id}"
                ))

            if hired_this_job > 0 and not dry_run:
                job.refresh_from_db()
                current = job.selected_freelancers.count()
                msg = f"now has {current}/{required}"
                if current < required:
                    msg += f"  (not enough suitable applicants)"
                self.stdout.write(self.style.SUCCESS(
                    f"  → Job #{job.id} {msg}"))

        self.stdout.write("\n" + "═" * 80)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN: Would have hired {total_hired} freelancers"))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Hired {total_hired} freelancers in total"))
            in_progress = Job.objects.filter(status='in_progress').count()
            self.stdout.write(self.style.SUCCESS(
                f"Jobs now in progress: {in_progress}"))
        self.stdout.write("═" * 80)

    def get_ranked_responses(self, job: Job) -> list[Response]:
        responses = job.responses.select_related(
            'user__profile__freelancer_profile'
        ).filter(
            status='submitted',
            user__profile__freelancer_profile__isnull=False
        )

        if not responses.exists():
            return []

        scored = []
        required_skills_set = set(
            job.skills_required.values_list('id', flat=True))

        for r in responses:
            fp = r.user.profile.freelancer_profile
            score = 0

            # Skills
            freelancer_skills = set(fp.skills.values_list('id', flat=True))
            matched = len(required_skills_set & freelancer_skills)
            score += matched * 25

            # Experience
            score += (fp.experience_years or 0) * 8

            # Rate fit
            if r.extra_data and 'proposed_rate' in r.extra_data:
                try:
                    prop = float(r.extra_data['proposed_rate'])
                    base = float(fp.hourly_rate or 45)
                    if prop <= base * 1.4:
                        score += 40
                except:
                    pass

            # Random tie breaker
            score += random.randint(0, 15)

            scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored]
