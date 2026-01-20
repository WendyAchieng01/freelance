from django.contrib import admin
from .models import PaypalPayments
from django.utils.html import format_html
from django.urls import reverse


@admin.register(PaypalPayments)
class PaypalPaymentsAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "user_display",
        "job_link",
        "amount",
        "email",
        "status",
        "verified",
        "created_at",
    )
    list_filter = ("status", "verified")
    search_fields = ("invoice", "user__username", "job__title", "email")
    ordering = ("-created_at",)

    readonly_fields = (
        "invoice",
        "verified",
        "amount",
        "extra_data",
        "job_link",
        "status",
        "user_display",
        "created_at",
    )

    fieldsets = (
        (None, {
            "fields": (
                "user_display",
                "job_link",
                "amount",
                "email",
                "invoice",
                "status",
                "verified",
                "extra_data",
                "created_at",
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

    def get_readonly_fields(self, request, obj=None):
        if obj and (obj.verified or obj.status in ("completed", "failed", "cancelled")):
            # Lock the record if verified or finalized
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields
