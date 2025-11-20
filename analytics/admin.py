from django.contrib import admin
from django.utils import timezone
from .models import DailyAnalytics, GeographicAnalytics,PaymentMethodAnalytics,CategoryAnalytics,SkillsAnalytics,ComprehensiveAnalytics


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
        
        
@admin.register(GeographicAnalytics)
class GeographicAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'date', 'location', 'user_count',
        'freelancer_count', 'client_count', 'job_count'
    )
    list_filter = ('date', 'location')
    search_fields = ('location',)
    ordering = ('-date', 'location')
    readonly_fields = (
        'user_count', 'freelancer_count',
        'client_count', 'job_count'
    )

    actions = ['update_geographic_data_action']

    def update_geographic_data_action(self, request, queryset):
        """Admin action to force update geographic analytics for today."""
        date = timezone.now().date()
        GeographicAnalytics.update_geographic_data(date)
        self.message_user(request, f"Geographic analytics updated for {date}")
    update_geographic_data_action.short_description = (
        "Update geographic analytics for today"
    )


@admin.register(PaymentMethodAnalytics)
class PaymentMethodAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'date', 'payment_method',
        'transaction_count', 'successful_count', 'total_amount'
    )
    list_filter = ('date', 'payment_method')
    search_fields = ('payment_method',)
    ordering = ('-date', 'payment_method')
    readonly_fields = (
        'transaction_count', 'successful_count',
        'total_amount'
    )

    actions = ['update_payment_methods_action']

    def update_payment_methods_action(self, request, queryset):
        date = timezone.now().date()
        PaymentMethodAnalytics.update_payment_methods(date)
        self.message_user(
            request, f"Payment method analytics updated for {date}")
    update_payment_methods_action.short_description = (
        "Update payment method analytics for today"
    )


@admin.register(CategoryAnalytics)
class CategoryAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        'date', 'category', 'job_count',
        'application_count', 'completion_count', 'avg_price'
    )
    list_filter = ('date', 'category')
    search_fields = ('category__name',)
    ordering = ('-date', '-job_count')
    readonly_fields = (
        'job_count', 'application_count',
        'completion_count', 'avg_price'
    )

    actions = ['update_categories_action']

    def update_categories_action(self, request, queryset):
        date = timezone.now().date()
        CategoryAnalytics.update_categories(date)
        self.message_user(request, f"Category analytics updated for {date}")
    update_categories_action.short_description = (
        "Update category analytics for today"
    )


@admin.register(ComprehensiveAnalytics)
class ComprehensiveAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('date',)
    list_filter = ('date',)
    ordering = ('-date',)
    readonly_fields = ('date',)

    actions = ['update_all_analytics_action']

    def update_all_analytics_action(self, request, queryset):
        date = timezone.now().date()
        ComprehensiveAnalytics.update_all_analytics(date)
        self.message_user(
            request,
            f"All analytics updated and synchronized for {date}"
        )
    update_all_analytics_action.short_description = (
        "Run full analytics update for today"
    )
