from django.contrib import admin
from wallet.models import WalletTransaction


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'transaction_type',
        'payment_type',
        'transaction_id',
        'amount',
        'status',
        'job',
        'timestamp',
    )
    list_filter = (
        'transaction_type',
        'payment_type',
        'status',
        'user',
    )
    search_fields = (
        'user__username',
        'transaction_id',
    )
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
