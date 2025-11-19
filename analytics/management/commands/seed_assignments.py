

import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q, Count, Avg,F

from accounts.models import FreelancerProfile
from core.models import Job, Response, Chat
from payment.models import Payment


class Command(BaseCommand):
    help = "Assign ONE top freelancer to the first N eligible jobs (default: 20)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--num-jobs',
            type=int,
            default=20,
            help='Number of jobs to assign a freelancer to (default: 20)'
        )
        parser.add_argument('--unassign', action='store_true',
                            help='Remove ALL current assignments first')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would happen without saving')
        parser.add_argument('--only', type=int, nargs='*',
                            help='Only process specific job IDs')

    def handle(self, *args, **options):
        num_jobs = max(1, options['num_jobs'])
        unassign_first = options['unassign']
        dry_run = options['dry_run']
        only_job_ids = options['only']

        if unassign_first:
            self.stdout.write(
                "Unassigning all freelancers and resetting jobs...")
            Job.objects.update(selected_freelancer=None,
                               assigned_at=None, status='open')
            Chat.objects.filter(freelancer__isnull=False).delete()
            Response.objects.update(status='submitted')
            self.stdout.write(self.style.SUCCESS("All assignments cleared!"))

        # Build query for eligible jobs
        eligible_jobs = Job.objects.filter(
            status='open',
            payment_verified=True,
            responses__isnull=False
        ).annotate(
            applicant_count=Count('responses')
        ).filter(
            applicant_count__gt=0,
            selected_freelancer__isnull=True  # Not already assigned
        ).order_by('posted_date')  # Oldest first (feels natural)

        if only_job_ids:
            eligible_jobs = eligible_jobs.filter(id__in=only_job_ids)

        # Get extra in case some fail
        jobs = list(eligible_jobs[:num_jobs * 2])
        if not jobs:
            self.stdout.write(self.style.WARNING(
                "No eligible jobs found! Need open + paid + has applications."))
            return

        self.stdout.write(
            f"Found {len(jobs)} eligible jobs → assigning 1 freelancer to up to {num_jobs} of them")

        assigned_count = 0
        for job in jobs:
            if assigned_count >= num_jobs:
                break

            # Get best applicant
            best_response = self.get_best_applicant(job)
            if not best_response:
                continue

            freelancer_user = best_response.user

            if dry_run:
                self.stdout.write(
                    f"[DRY] Hiring {freelancer_user.get_full_name() or freelancer_user.username} "
                    f"→ Job #{job.id}: \"{job.title[:50]}...\""
                )
                assigned_count += 1
                continue

            # === HIRE FREELANCER ===
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
                "note": "Congratulations! You have been selected for this job."
            })
            best_response.save(update_fields=['status', 'extra_data'])

            # Create chat
            Chat.objects.get_or_create(
                job=job,
                client=job.client,
                freelancer=freelancer_user.profile,
                defaults={'active': True}
            )

            assigned_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"HIRED → {freelancer_user.username:<18} → #{job.id} {job.title[:55]}"
                )
            )

        # Final Summary
        self.stdout.write("\n" + "═" * 90)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f" DRY RUN: Would assign {assigned_count} freelancers to {assigned_count} jobs"))
        else:
            self.stdout.write(self.style.SUCCESS(
                f" SUCCESS: {assigned_count} jobs now have a hired freelancer!"))
            self.stdout.write(self.style.SUCCESS(
                f" {Job.objects.filter(status='in_progress').count()} jobs IN PROGRESS"))
            self.stdout.write(self.style.SUCCESS(
                f" {Chat.objects.filter(active=True).count()} active client-freelancer chats"))
        self.stdout.write("═" * 90)
        self.stdout.write(self.style.SUCCESS(
            "Your platform looks REAL and ACTIVE!"))

    def get_best_applicant(self, job):
        """Return the single best Response for this job"""
        responses = job.responses.select_related(
            'user__profile__freelancer_profile').all()
        if not responses:
            return None

        best = None
        best_score = -1

        for resp in responses:
            fp = resp.user.profile.freelancer_profile
            if not fp:
                continue

            score = 0
            # Skill match
            matched = set(fp.skills.values_list('id', flat=True)) & set(
                job.skills_required.values_list('id', flat=True))
            score += len(matched) * 20

            # Experience
            score += (fp.experience_years or 0) * 5

            # Reasonable rate
            if resp.extra_data and resp.extra_data.get('proposed_rate'):
                rate = float(resp.extra_data['proposed_rate'])
                base = float(fp.hourly_rate or 50)
                if rate <= base * 1.3:
                    score += 30

            score += random.randint(0, 10)

            if score > best_score:
                best_score = score
                best = resp

        return best
