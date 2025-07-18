import django_filters
from datetime import datetime
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from django.db.models import Count
from django_filters import rest_framework as filters
from core.models import Job, Response as JobResponse
from core.choices import JOB_STATUS_CHOICES


class JobFilter(filters.FilterSet):
    price__gte = filters.NumberFilter(field_name='price', lookup_expr='gte')
    price__lte = filters.NumberFilter(field_name='price', lookup_expr='lte')

    deadline_before = filters.DateFilter(
        field_name='deadline_date', lookup_expr='lte')
    deadline_after = filters.DateFilter(
        field_name='deadline_date', lookup_expr='gte')

    posted_before = filters.DateFilter(
        field_name='posted_date', lookup_expr='lte')
    posted_after = filters.DateFilter(
        field_name='posted_date', lookup_expr='gte')

    category = filters.CharFilter(
        field_name='category__name', lookup_expr='iexact')
    category_slug = filters.CharFilter(
        field_name='category__slug', lookup_expr='iexact')

    experience_level = filters.ChoiceFilter(
        field_name='preferred_freelancer_level',
        choices=Job._meta.get_field('preferred_freelancer_level').choices,
        lookup_expr='exact'
    )

    min_bids = filters.NumberFilter(method='filter_min_bids')
    max_bids = filters.NumberFilter(method='filter_max_bids')

    skills_required = filters.CharFilter(method='filter_skills_required')

    # Use ChoiceFilter for status to restrict to JOB_STATUS_CHOICES
    status = filters.ChoiceFilter(
        field_name='status',
        choices=JOB_STATUS_CHOICES,
        lookup_expr='exact'
    )

    def filter_min_bids(self, queryset, name, value):
        return queryset.annotate(bid_count=Count('responses')).filter(bid_count__gte=value)

    def filter_max_bids(self, queryset, name, value):
        return queryset.annotate(bid_count=Count('responses')).filter(bid_count__lte=value)

    def filter_skills_required(self, queryset, name, value):
        return queryset.filter(skills_required__name__icontains=value).distinct()

    class Meta:
        model = Job
        fields = [
            'status', 'category', 'category_slug', 'experience_level',
            'price__gte', 'price__lte',
            'deadline_before', 'deadline_after',
            'posted_before', 'posted_after',
            'min_bids', 'max_bids', 'skills_required',
        ]


class AdvancedJobFilter(filters.FilterSet):
    min_price = filters.NumberFilter(field_name="price", lookup_expr='gte')
    max_price = filters.NumberFilter(field_name="price", lookup_expr='lte')
    category = filters.CharFilter(field_name="category", lookup_expr='iexact')
    status = filters.CharFilter(field_name="status", lookup_expr='iexact')
    level = filters.CharFilter(
        field_name="preferred_freelancer_level", lookup_expr='iexact')
    deadline_days = filters.NumberFilter(method='filter_deadline')

    # Application count range filters
    min_applications = filters.NumberFilter(method='filter_min_applications')
    max_applications = filters.NumberFilter(method='filter_max_applications')

    # Skills required (ManyToMany lookup by skill name)
    skills_required = filters.CharFilter(method='filter_skills_required')

    def filter_deadline(self, queryset, name, value):
        try:
            cutoff = timezone.now().date() + timedelta(days=int(value))
            return queryset.filter(deadline_date__lte=cutoff)
        except Exception:
            return queryset.none()

    def filter_min_applications(self, queryset, name, value):
        queryset = queryset.annotate(application_count=Count('responses'))
        return queryset.filter(application_count__gte=value)

    def filter_max_applications(self, queryset, name, value):
        queryset = queryset.annotate(application_count=Count('responses'))
        return queryset.filter(application_count__lte=value)

    def filter_skills_required(self, queryset, name, value):
        return queryset.filter(skills_required__name__icontains=value).distinct()

    class Meta:
        model = Job
        fields = [
            'category', 'status', 'level',
            'min_price', 'max_price', 'deadline_days',
            'min_applications', 'max_applications', 'skills_required'
        ]


class JobDiscoveryFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(
        field_name='category', lookup_expr='iexact')
    preferred_freelancer_level = django_filters.CharFilter(
        field_name='preferred_freelancer_level', lookup_expr='iexact')

    class Meta:
        model = Job
        fields = ['category', 'preferred_freelancer_level']


def get_job_filters(request):
    filters = Q()

    category = request.query_params.get('category')
    if category:
        filters &= Q(category__name__iexact=category.strip())

    category_slug = request.query_params.get('category_slug')
    if category_slug:
        filters &= Q(category__slug__iexact=category_slug.strip())

    deadline_before = request.query_params.get('deadline_before')
    if deadline_before:
        try:
            parsed = datetime.strptime(deadline_before, '%Y-%m-%d').date()
            filters &= Q(deadline_date__date__lte=parsed)
        except ValueError:
            pass

    deadline_after = request.query_params.get('deadline_after')
    if deadline_after:
        try:
            parsed = datetime.strptime(deadline_after, '%Y-%m-%d').date()
            filters &= Q(deadline_date__date__gte=parsed)
        except ValueError:
            pass

    posted_before = request.query_params.get('posted_before')
    if posted_before:
        try:
            parsed = datetime.strptime(posted_before, '%Y-%m-%d').date()
            filters &= Q(posted_date__date__lte=parsed)
        except ValueError:
            pass

    posted_after = request.query_params.get('posted_after')
    if posted_after:
        try:
            parsed = datetime.strptime(posted_after, '%Y-%m-%d').date()
            filters &= Q(posted_date__date__gte=parsed)
        except ValueError:
            pass

    return filters
