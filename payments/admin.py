from django.contrib import admin
from .models import PaypalPayments


@admin.register(PaypalPayments)
class PaypalPaymentsAdmin(admin.ModelAdmin):
    list_display = (
        'invoice',
        'user_display',
        'job',
        'amount',
        'email',
        'status',
        'verified'
    )
    list_filter = ('status', 'verified')
    search_fields = ('invoice', 'user__username', 'job__title', 'email')
    readonly_fields = ('invoice', 'verified', 'extra_data')
    ordering = ('-id',)

    fieldsets = (
        (None, {
            'fields': (
                'job',
                'invoice',
                'amount',
                'email',
                'user',
                'status',
                'verified',
                'extra_data'
            )
        }),
    )

    def user_display(self, obj):
        return obj.user.username if obj.user else "Anonymous"
    user_display.short_description = "User"
