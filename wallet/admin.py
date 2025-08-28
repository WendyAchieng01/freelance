from .models import WalletTransaction, PaymentPeriod, Rate
from django.contrib import admin
from wallet.models import WalletTransaction,Rate


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'transaction_type', 'amount', 'status',
        'job', 'payment_period', 'timestamp'
    )
    list_filter = (
        'status', 'transaction_type', 'payment_type', 'payment_period'
    )
    search_fields = ('user__username', 'transaction_id')
    autocomplete_fields = ('user', 'job', 'payment_period')

    readonly_fields = (
        'user',
        'transaction_type',
        'rate',
        'transaction_id',
        'amount',
        'job',
        'timestamp',
        'completed',
        'extra_data',
    )
    list_select_related = ('user', 'job', 'payment_period')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'job', 'payment_period')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser:
            # Non-superusers can only toggle status & assign payment period
            return True
        # Superusers may override more fields if needed
        return True

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        """
        Make most fields read-only.
        For superusers, allow overriding almost everything if needed.
        """
        if request.user.is_superuser:
            return ('timestamp', 'extra_data') 
        return self.readonly_fields


@admin.register(PaymentPeriod)
class PaymentPeriodAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = ('name',)
    ordering = ('-start_date',)
    actions = ['mark_transactions_as_paid']

    @admin.action(description="Mark all transactions in this period as paid")
    def mark_transactions_as_paid(self, request, queryset):
        for period in queryset:
            transactions = period.transactions.filter(
                status__in=['in_progress', 'pending'])
            updated = transactions.update(status='completed', completed=True)
            self.message_user(
                request, f"{updated} transactions marked as paid in {period.name}")


@admin.register(Rate)
class RateAdmin(admin.ModelAdmin):
    list_display = ('rate_amount', 'effective_from')
    ordering = ('-effective_from',)



