from decimal import Decimal
from datetime import timedelta

from django.db.models import (
    Q, Count, F, FloatField, ExpressionWrapper, Case, When, Value
)
from django.db.models.functions import Abs, Cast
from django.utils import timezone

from core.models import Job,JobBookmark
from core.choices import EXPERIENCE_LEVEL


class JobMatcher:
    """
    Class for handling job matching and specialized filtering operations
    """
    @staticmethod
    def get_best_matches(user, queryset=None, min_skills=1):
        if queryset is None:
            queryset = Job.objects.all().prefetch_related('skills_required')

        if not user or not user.is_authenticated or not hasattr(user, 'profile'):
            return queryset.none()

        try:
            freelancer_profile = user.profile.freelancer_profile
        except AttributeError:
            return queryset.none()

        if getattr(user.profile, 'user_type', None) != 'freelancer':
            return queryset.none()

        # Normalize freelancer skills
        freelancer_skills = [
            s.strip().lower()
            for s in freelancer_profile.skills.values_list('name', flat=True)
            if s and s.strip()
        ]
        if not freelancer_skills:
            return queryset.none()

        # Experience mapping
        try:
            freelancer_experience_years = float(
                freelancer_profile.experience_years or 0)
        except (TypeError, ValueError):
            freelancer_experience_years = 0.0

        experience_ranges = {
            'entry': (0, 2),
            'intermediate': (2, 5),
            'advanced': (5, 8),
            'expert': (8, float('inf')),
        }
        levels = list(experience_ranges.keys())

        freelancer_level = 'entry'
        for level, (lo, hi) in experience_ranges.items():
            if lo <= freelancer_experience_years < hi:
                freelancer_level = level
                break

        idx = levels.index(freelancer_level)
        valid_levels = levels[max(0, idx - 1): min(len(levels), idx + 2)]

        # Build skill filter
        skill_q = Q()
        for sk in freelancer_skills:
            skill_q |= Q(skills_required__name__icontains=sk)

        # try with valid levels only
        qs = queryset.filter(
            status="open",
            preferred_freelancer_level__in=valid_levels
        ).filter(skill_q).distinct()

        # If no jobs found → fallback to skills only
        if not qs.exists():
            qs = queryset.filter(status="open").filter(skill_q).distinct()
            fallback_mode = True
        else:
            fallback_mode = False

        # Annotate scoring
        qs = qs.annotate(
            matching_skills=Count(
                "skills_required", filter=skill_q, distinct=True),
            total_skills=Count("skills_required", distinct=True),
        ).filter(matching_skills__gte=min_skills).annotate(
            skill_match_ratio=ExpressionWrapper(
                F("matching_skills") * 1.0 / F("total_skills"),
                output_field=FloatField()
            ),
            experience_match=Case(
                When(preferred_freelancer_level=freelancer_level, then=Value(1.0)),
                When(preferred_freelancer_level__in=valid_levels, then=Value(0.7)),
                default=Value(0.5 if fallback_mode else 0.0),
                output_field=FloatField()
            ),
            hourly_rate_match=ExpressionWrapper(
                1.0 / (
                    1.0 + Abs(Cast(F("price"), FloatField()) -
                            Value(float(freelancer_profile.hourly_rate or 10.0))) /
                    Value(float(freelancer_profile.hourly_rate or 10.0) or 1.0)
                ),
                output_field=FloatField()
            ),
            combined_score=ExpressionWrapper(
                F("skill_match_ratio") * 0.6 +
                F("experience_match") * 0.3 +
                F("hourly_rate_match") * 0.1,
                output_field=FloatField()
            )
        ).order_by("-combined_score", "-posted_date")

        return qs


    @staticmethod
    def get_most_recent(queryset=None, days=7):
        if queryset is None:
            queryset = Job.objects.all()
        cutoff_date = timezone.now() - timedelta(days=days)
        return queryset.filter(
            posted_date__gte=cutoff_date,
            status='open'
        ).order_by('-posted_date')

    @staticmethod
    def get_near_deadline(queryset=None, days=7):
        if queryset is None:
            queryset = Job.objects.all()
        cutoff = timezone.now() + timedelta(days=days)
        return queryset.filter(
            deadline_date__range=[timezone.now(), cutoff],
            status='open'
        ).order_by('deadline_date')

    @staticmethod
    def get_entry_level(queryset=None):
        if queryset is None:
            queryset = Job.objects.all()
        entry_level = [c[0]
                       for c in EXPERIENCE_LEVEL if 'entry' in c[1].lower()]
        if not entry_level:
            return queryset.none()
        return queryset.filter(
            preferred_freelancer_level__in=entry_level,
            status='open'
        ).order_by('-posted_date')
        
    @staticmethod
    def filter_by_skills(queryset, skills):
        """
        Filter jobs that require at least one of the given skills.
        Skills is a list of lowercase strings.
        """
        if not skills:
            return queryset

        skill_q = Q()
        for sk in skills:
            skill_q |= Q(skills_required__name__icontains=sk)

        return queryset.filter(skill_q).distinct()

    @staticmethod
    def get_jobs_for_freelancer(user, filter_type=None, queryset=None, min_skills=1):
        """
        Main method to get jobs based on filter type.
        Keeps your original behavior: only `best_match` needs the user; others work anonymously.
        """
        if queryset is None:
            queryset = Job.objects.all()

        valid = {'best_match', 'most_recent',
                 'near_deadline', 'entry_level', 'bookmarks'}
        if filter_type not in valid:
            return queryset

        if filter_type == 'best_match':
            return JobMatcher.get_best_matches(user, queryset, min_skills=min_skills)
        if filter_type == 'most_recent':
            return JobMatcher.get_most_recent(queryset)
        if filter_type == 'near_deadline':
            return JobMatcher.get_near_deadline(queryset)
        if filter_type == 'entry_level':
            return JobMatcher.get_entry_level(queryset)
        if filter_type == 'bookmarks':
            if not user or not user.is_authenticated:
                return Job.objects.none()
            job_ids = JobBookmark.objects.filter(
                user=user).values_list('job_id', flat=True)
            return Job.objects.filter(id__in=job_ids).order_by('-posted_date')
        return queryset
