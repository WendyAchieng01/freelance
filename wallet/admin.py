from .models import WalletTransaction, PaymentPeriod, Rate
from django.contrib import admin
from wallet.models import WalletTransaction,Rate


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'transaction_type', 'amount', 'status',
        'job', 'payment_period', 'timestamp'
    )
    list_filter = ('status', 'transaction_type',
                    'payment_type', 'payment_period')
    search_fields = ('user__username', 'transaction_id')
    autocomplete_fields = ('user', 'job', 'payment_period')

    readonly_fields = (
        'timestamp',
        'extra_data',
    )
    list_select_related = (
        'user',
        'job',
    )
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'job')

    def has_add_permission(self, request):
        # Prevent adding new transactions via admin to ensure they come from signals
        return False

    def has_change_permission(self, request, obj=None):
        # Allow editing for specific fields, but rely on signals for transaction_type changes
        return True

    def has_delete_permission(self, request, obj=None):
        # Allow deletion with caution, as transactions are financial records
        return True


@admin.register(PaymentPeriod)
class PaymentPeriodAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = ('name',)
    ordering = ('-start_date',)


@admin.register(Rate)
class RateAdmin(admin.ModelAdmin):
    list_display = ('rate_amount', 'effective_from')
    ordering = ('-effective_from',)



