# accounts/filters.py

import django_filters
from accounts.models import FreelancerProfile,ClientProfile


class FreelancerProfileFilter(django_filters.FilterSet):
    hourly_rate__gte = django_filters.NumberFilter(
        field_name="hourly_rate", lookup_expr='gte')
    hourly_rate__lte = django_filters.NumberFilter(
        field_name="hourly_rate", lookup_expr='lte')
    experience_years__gte = django_filters.NumberFilter(
        field_name="experience_years", lookup_expr='gte')
    experience_years__lte = django_filters.NumberFilter(
        field_name="experience_years", lookup_expr='lte')

    class Meta:
        model = FreelancerProfile
        fields = [
            'languages__name',
            'skills__name',
            'profile__location',
            'availability',
            'is_visible',
        ]


class ClientProfileFilter(django_filters.FilterSet):
    project_budget__gte = django_filters.NumberFilter(
        field_name='project_budget', lookup_expr='gte')
    project_budget__lte = django_filters.NumberFilter(
        field_name='project_budget', lookup_expr='lte')
    profile__location = django_filters.CharFilter(
        field_name='profile__location', lookup_expr='icontains')

    class Meta:
        model = ClientProfile
        fields = [
            'industry',
            'preferred_freelancer_level',
            'is_verified',
            'languages__name',
        ]
