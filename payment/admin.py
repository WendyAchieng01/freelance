import secrets
from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'user_display',
        'job',
        'amount',
        'verified',
        'email',
        'date_created'
    )
    list_filter = ('verified', 'date_created')
    search_fields = ('user__username', 'job__title', 'email', 'ref')
    readonly_fields = ('ref', 'verified', 'date_created',
                       'amount_value_display', 'extra_data')
    ordering = ('-date_created',)

    fieldsets = (
        (None, {
            'fields': (
                'user',
                'job',
                'amount',
                'amount_value_display',
                'email',
                'ref',
                'verified',
                'extra_data',
                'date_created'
            )
        }),
    )

    def user_display(self, obj):
        return obj.user.username if obj.user else "Anonymous"
    user_display.short_description = "User"

    def amount_value_display(self, obj):
        return f"{obj.amount_value()} (subunit)"
    amount_value_display.short_description = "Amount in Subunit"

    def save_model(self, request, obj, form, change):
        # Ensure unique ref is generated if not set
        if not obj.ref:
            while True:
                ref = secrets.token_urlsafe(50)
                if not Payment.objects.filter(ref=ref).exists():
                    obj.ref = ref
                    break
        super().save_model(request, obj, form, change)
