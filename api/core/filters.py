
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
import django_filters
from core.models import Job, Response as JobResponse


class JobFilter(django_filters.FilterSet):
    budget__gte = django_filters.NumberFilter(
        field_name='budget', lookup_expr='gte')
    budget__lte = django_filters.NumberFilter(
        field_name='budget', lookup_expr='lte')
    deadline__gte = django_filters.DateFilter(
        field_name='deadline', lookup_expr='gte')
    deadline__lte = django_filters.DateFilter(
        field_name='deadline', lookup_expr='lte')
    created__gte = django_filters.DateFilter(
        field_name='created', lookup_expr='gte')
    created__lte = django_filters.DateFilter(
        field_name='created', lookup_expr='lte')
    client_location = django_filters.CharFilter(
        field_name='client__profile__location', lookup_expr='icontains')

    class Meta:
        model = Job
        fields = [
            'status',  
            'category', 
        ]


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
