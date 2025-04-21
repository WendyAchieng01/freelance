from django.db.models import Q
from datetime import datetime

from accounts.models import FreelancerProfile
from core.models import Job

def match_freelancers_to_job(job, max_matches=5):
    """
    Matches only freelancers who have responded to the job.
    Returns a list of tuples: (freelancer_profile, score)
    """
    # Get users who have responded to this job
    responded_users = job.responses.values_list('user', flat=True)
    
    # Filter freelancer profiles to only those who responded
    freelancer_profiles = FreelancerProfile.objects.filter(
        profile__user_type='freelancer',
        profile__user__in=responded_users
    ).select_related('profile').prefetch_related('skills', 'languages')
    
    matched_freelancers = []
    
    for freelancer in freelancer_profiles:
        score = calculate_match_score(job, freelancer)
        if score > 0:
            matched_freelancers.append((freelancer, score))
    
    matched_freelancers.sort(key=lambda x: x[1], reverse=True)
    return matched_freelancers[:max_matches]

def calculate_match_score(job, freelancer):
    # This function remains unchanged from the previous corrected version
    score = 0.0
    max_score = 100.0
    
    weights = {
        'level': 25.0,
        'skills': 25.0,
        'availability': 20.0,
        'rate': 15.0,
        'languages': 10.0,
        'experience': 5.0
    }
    
    if job.preferred_freelancer_level == 'entry' and freelancer.experience_years <= 2:
        score += weights['level']
    elif job.preferred_freelancer_level == 'intermediate' and 2 < freelancer.experience_years <= 5:
        score += weights['level']
    elif job.preferred_freelancer_level == 'expert' and freelancer.experience_years > 5:
        score += weights['level']
    elif job.preferred_freelancer_level != 'entry':
        score += weights['level'] * 0.5
    
    job_skills = set(job.category.split(','))
    freelancer_skills = set(skill.name for skill in freelancer.skills.all())
    skill_overlap = len(job_skills.intersection(freelancer_skills))
    if skill_overlap > 0:
        skill_score = min(skill_overlap / len(job_skills), 1) * weights['skills']
        score += skill_score
    
    if freelancer.availability != 'not_available':
        if freelancer.availability == 'full_time':
            score += weights['availability']
        elif freelancer.availability in ['part_time', 'weekends']:
            score += weights['availability'] * 0.7
        else:
            score += weights['availability'] * 0.5
    
    client_budget = float(job.price)
    freelancer_rate = float(freelancer.hourly_rate)
    if freelancer_rate <= client_budget:
        rate_score = weights['rate'] * (1 - (freelancer_rate / client_budget))
        score += min(rate_score, weights['rate'])
    elif freelancer_rate <= client_budget * 1.2:
        score += weights['rate'] * 0.5
    
    job_languages = set()
    if hasattr(job.client, 'client_profile'):
        job_languages = set(job.client.client_profile.languages.all())

    freelancer_languages = set(freelancer.languages.all())
    if job_languages and freelancer_languages:
        lang_overlap = len(job_languages.intersection(freelancer_languages))
        if lang_overlap > 0:
            lang_score = min(lang_overlap / len(job_languages), 1) * weights['languages']
            score += lang_score
    
    experience_factor = min(freelancer.experience_years / 10, 1)
    score += experience_factor * weights['experience']
    
    return min(round(score), max_score)

# Usage example in a view
def find_freelancers_for_job(request, job_id):
    job = Job.objects.get(id=job_id)
    if job.status != 'open' or job.is_max_freelancers_reached:
        return "Job is not accepting applications"
    
    matches = match_freelancers_to_job(job)
    
    # Format results
    results = [
        {
            'freelancer': match[0].profile.user.username,
            'score': match[1],
            'skills': [skill.name for skill in match[0].skills.all()],
            'rate': float(match[0].hourly_rate),
            'availability': match[0].availability
        }
        for match in matches
    ]
    return results

# Additional helper function to recommend jobs to freelancers
def recommend_jobs_to_freelancer(freelancer_profile, max_recommendations=5):
    open_jobs = Job.objects.filter(
        status='open'
    ).exclude(
        responses__user=freelancer_profile.profile.user
    ).select_related('client__client_profile')

    
    job_matches = []
    for job in open_jobs:
        if not job.is_max_freelancers_reached:
            score = calculate_match_score(job, freelancer_profile)
            if score > 0:
                job_matches.append((job, score))
    
    job_matches.sort(key=lambda x: x[1], reverse=True)
    return job_matches[:max_recommendations]