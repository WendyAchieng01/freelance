from django.db.models import Q
from core.models import Job
from accounts.models import FreelancerProfile


def recommend_jobs_to_freelancer(freelancer_profile):
    # Filter open jobs, excluding those the freelancer has responded to
    jobs = Job.objects.filter(status='open').exclude(
        responses__user=freelancer_profile.profile.user)
    # Return Job objects (no need for tuples unless scoring is required)
    return jobs


def match_freelancers_to_job(job):
    """
    Match freelancers to a job based on job requirements.
    Returns a list of tuples (freelancer_profile, score).
    """
    freelancers = FreelancerProfile.objects.all()
    return [(f, 0.8) for f in freelancers]  # Example scoring
