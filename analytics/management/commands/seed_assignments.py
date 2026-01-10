import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count

from core.models import Job, Response, Chat


class Command(BaseCommand):
    help = (
        "Assign ONE top freelancer to the first N eligible jobs (default: 20)\n"
        "OPTIONAL: Mark N in-progress jobs as completed using --complete N"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--num-jobs',
            type=int,
            default=20,
            help='Number of jobs to assign freelancers to (default: 20)',
        )
        parser.add_argument(
            '--complete',
            type=int,
            help='Mark the first N in-progress jobs as completed',
        )
        parser.add_argument(
            '--unassign',
            action='store_true',
            help='Remove ALL current assignments first',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would happen without saving',
        )
        parser.add_argument(
            '--only',
            type=int,
            nargs='*',
            help='Only process specific job IDs',
        )

    def handle(self, *args, **options):
        num_jobs = max(1, options['num_jobs'])
        dry_run = options['dry_run']

        # 1) Unassign everything
        if options['unassign']:
            self.stdout.write(
                "Unassigning all jobs & clearing chats/responses…")
            Job.objects.update(selected_freelancer=None,
                               assigned_at=None, status='open')
            Chat.objects.filter(freelancer__isnull=False).delete()
            Response.objects.update(status='submitted')
            self.stdout.write(self.style.SUCCESS("All assignments cleared!"))

        # 2) Mark N in-progress jobs as completed
        if options['complete']:
            self.complete_jobs(options['complete'], dry_run)
            return  # stop here, do NOT continue to assignment

        # 3) Assign freelancers to jobs
        self.assign_jobs(num_jobs, dry_run, options['only'])

    # PART A — COMPLETE JOBS
    def complete_jobs(self, n, dry_run):
        """
        Mark the first N in-progress jobs as completed.
        """
        # Get jobs that are in-progress
        jobs = Job.objects.filter(status='in_progress').order_by('assigned_at')[:n]

        if not jobs:
            self.stdout.write(self.style.WARNING(
                "No jobs are currently in progress."))
            return

        self.stdout.write(
            f"Found {len(jobs)} in-progress jobs → marking {len(jobs)} as completed")

        for job in jobs:
            if dry_run:
                self.stdout.write(
                    f"[DRY] Would COMPLETE job #{job.id} — {job.title[:50]}")
                continue

            # Update job status to completed
            job.status = 'completed'
            job.save(update_fields=['status'])

            # Update accepted response (if exists) to mark it as completed
            Response.objects.filter(
                job=job, status='accepted'
            ).update(status='completed')

            # Close chat
            Chat.objects.filter(job=job).update(active=False)

            self.stdout.write(self.style.SUCCESS(
                f"COMPLETED → #{job.id} {job.title[:55]}"
            ))

        self.stdout.write(self.style.SUCCESS("\nJobs completed successfully!"))

    # PART B — ASSIGN FREELANCERS
    def assign_jobs(self, num_jobs, dry_run, only_job_ids):
        # Build eligible jobs queryset
        eligible = Job.objects.filter(
            status='open',
            payment_verified=True,
            responses__isnull=False
        ).annotate(
            applicant_count=Count('responses')
        ).filter(
            applicant_count__gt=0,
            selected_freelancer__isnull=True
        ).order_by('posted_date')

        if only_job_ids:
            eligible = eligible.filter(id__in=only_job_ids)

        jobs = list(eligible[:num_jobs * 2])
        if not jobs:
            self.stdout.write(self.style.WARNING(
                "No eligible jobs found (need: open + paid + has applications)."
            ))
            return

        self.stdout.write(
            f"Found {len(jobs)} eligible jobs → assigning freelancers to up to {num_jobs}"
        )

        assigned = 0
        for job in jobs:
            if assigned >= num_jobs:
                break

            best_response = self.get_best_applicant(job)
            if not best_response:
                continue

            freelancer_user = best_response.user

            if dry_run:
                self.stdout.write(
                    f"[DRY] Would hire {freelancer_user.username} → Job #{job.id}"
                )
                assigned += 1
                continue

            # Assign job
            job.selected_freelancer = freelancer_user
            job.assigned_at = timezone.now()
            job.status = 'in_progress'
            job.save(update_fields=[
                     'selected_freelancer', 'assigned_at', 'status'])

            # Update response
            best_response.status = 'accepted'
            best_response.extra_data = best_response.extra_data or {}
            best_response.extra_data.update({
                "hired_at": timezone.now().isoformat(),
                "note": "You have been selected!",
            })
            best_response.save(update_fields=['status', 'extra_data'])

            # Create chat
            Chat.objects.get_or_create(
                job=job,
                client=job.client,
                freelancer=freelancer_user.profile,
                defaults={'active': True}
            )

            assigned += 1
            self.stdout.write(self.style.SUCCESS(
                f"HIRED → {freelancer_user.username:<18} → #{job.id} {job.title[:55]}"
            ))

        # Summary
        self.stdout.write("\n" + "═" * 90)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN: Would assign {assigned} freelancers"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"ASSIGNED: {assigned} jobs now have freelancers!"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"{Job.objects.filter(status='in_progress').count()} jobs IN PROGRESS"
            ))
        self.stdout.write("═" * 90)

    # PART C — CHOOSE BEST APPLICANT
    def get_best_applicant(self, job):
        responses = job.responses.select_related(
            'user__profile__freelancer_profile'
        )

        best = None
        best_score = -1

        for resp in responses:
            fp = resp.user.profile.freelancer_profile
            if not fp:
                continue

            score = 0

            # Skill match
            matched = set(fp.skills.values_list('id', flat=True)) & set(
                job.skills_required.values_list('id', flat=True)
            )
            score += len(matched) * 20

            # Experience
            score += (fp.experience_years or 0) * 5

            # Reasonable rate
            if resp.extra_data and resp.extra_data.get('proposed_rate'):
                rate = float(resp.extra_data['proposed_rate'])
                base = float(fp.hourly_rate or 50)
                if rate <= base * 1.3:
                    score += 30

            # Random noise
            score += random.randint(0, 10)

            if score > best_score:
                best_score = score
                best = resp

        return best
