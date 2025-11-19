from django.contrib import admin
from .models import DailyAnalytics


@admin.register(DailyAnalytics)
class DailyAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'new_users',
        'new_freelancers',
        'new_clients',
        'new_jobs',
        'new_applications',
        'new_hires',
        'revenue',
        'payouts',
        'platform_fees',
    )

    list_filter = ('date',)
    search_fields = ('date',)
    ordering = ('-date',)

    readonly_fields = (
        'new_users',
        'new_freelancers',
        'new_clients',
        'new_jobs',
        'new_applications',
        'new_hires',
        'revenue',
        'payouts',
        'platform_fees',
    )

    actions = ['update_today_stats']

    @admin.action(description="Update today's analytics")
    def update_today_stats(self, request, queryset):
        DailyAnalytics.update_today()
        self.message_user(
            request, "Today's analytics have been updated successfully.")
