
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
import django_filters
from core.models import Job, Response as JobResponse
from datetime import datetime


class JobFilter(django_filters.FilterSet):
    price__gte = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price__lte = django_filters.NumberFilter(field_name='price', lookup_expr='lte')

    deadline_before = django_filters.DateFilter(field_name='deadline_date', lookup_expr='lte')
    deadline_after = django_filters.DateFilter(field_name='deadline_date', lookup_expr='gte')

    posted_before = django_filters.DateFilter(field_name='posted_date', lookup_expr='lte')
    posted_after = django_filters.DateFilter(field_name='posted_date', lookup_expr='gte')

    # Filter by category name
    category = django_filters.CharFilter(field_name='category__name', lookup_expr='iexact')

    # NEW: Filter by category slug
    category_slug = django_filters.CharFilter(field_name='category__slug', lookup_expr='iexact')

    class Meta:
        model = Job
        fields = ['status', 'category', 'category_slug']


class AdvancedJobFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(
        field_name="price", lookup_expr='gte')
    max_price = django_filters.NumberFilter(
        field_name="price", lookup_expr='lte')
    category = django_filters.CharFilter(
        field_name="category", lookup_expr='iexact')
    status = django_filters.CharFilter(
        field_name="status", lookup_expr='iexact')
    level = django_filters.CharFilter(
        field_name="preferred_freelancer_level", lookup_expr='iexact')
    deadline_days = django_filters.NumberFilter(method='filter_deadline')

    def filter_deadline(self, queryset, name, value):
        try:
            cutoff = timezone.now().date() + timedelta(days=int(value))
            return queryset.filter(deadline_date__lte=cutoff)
        except Exception:
            return queryset.none()

    class Meta:
        model = Job
        fields = ['category', 'status', 'level',
                'min_price', 'max_price', 'deadline_days']


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
