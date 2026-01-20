import secrets
from django.contrib import admin
from .models import Payment


from django.utils.html import format_html
from django.urls import reverse


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user_display",
        "job_link",
        "amount",
        "amount_value_display",
        "verified",
        "email",
        "date_created",
    )
    list_filter = ("verified", "date_created")
    search_fields = ("user__username", "job__title", "email", "ref")
    ordering = ("-date_created",)

    readonly_fields = (
        "ref",
        "verified",
        'amount',
        "date_created",
        "extra_data",
        "job_link",
        "user_display",
    )

    fieldsets = (
        (None, {
            "fields": (
                "user_display",
                "job_link",
                "amount",
                "email",
                "ref",
                "verified",
                "extra_data",
                "date_created",
            )
        }),
    )

    @admin.display(description="User")
    def user_display(self, obj):
        return obj.user.username if obj.user else "Anonymous"

    @admin.display(description="Job")
    def job_link(self, obj):
        if not obj.job:
            return "-"
        url = reverse("admin:core_job_change", args=[obj.job.pk])
        return format_html('<a href="{}">{}</a>', url, obj.job.title)

    @admin.display(description="Amount in Subunit")
    def amount_value_display(self, obj):
        return f"{obj.amount_value()} (subunit)"

    def save_model(self, request, obj, form, change):
        # Ensure unique ref is generated if not set
        if not obj.ref:
            while True:
                ref = secrets.token_urlsafe(50)
                if not Payment.objects.filter(ref=ref).exists():
                    obj.ref = ref
                    break
        super().save_model(request, obj, form, change)
