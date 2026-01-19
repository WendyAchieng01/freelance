from django.contrib import admin, messages
from django.urls import reverse, path, re_path
from django.shortcuts import redirect, get_object_or_404
from django.utils.html import format_html

from wallet.models import (
    WalletTransaction,PaymentBatch,
    PaymentPeriod,PayoutLog,Rate,
)
from django.contrib.admin import SimpleListFilter

from wallet.services.batch_discovery import auto_discover_batches
from wallet.admin_views import (
    single_pay_view,
    retry_pay_view,list_periods_for_batching_view,
    period_payout_detail_view,
)


class UserTypeFilter(SimpleListFilter):
    title = "User Type"
    parameter_name = "user_type"

    def lookups(self, request, model_admin):
        return (
            ("freelancer", "Freelancer"),
            ("client", "Client"),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user__profile__user_type=self.value())
        return queryset


class HasJobFilter(SimpleListFilter):
    title = "Has Job"
    parameter_name = "has_job"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(job__isnull=False)
        if self.value() == "no":
            return queryset.filter(job__isnull=True)
        return queryset


class BatchStatusFilter(SimpleListFilter):
    title = "Batch Status"
    parameter_name = "batch_status"

    def lookups(self, request, model_admin):
        return (
            ("batched", "Assigned to Batch"),
            ("unbatched", "Not Batched"),
        )

    def queryset(self, request, queryset):
        if self.value() == "batched":
            return queryset.filter(batch__isnull=False)
        if self.value() == "unbatched":
            return queryset.filter(batch__isnull=True)
        return queryset


class PayoutLogInline(admin.TabularInline):
    model = PayoutLog
    extra = 0
    readonly_fields = (
        "created_at",
        "provider",
        "endpoint",
        "idempotency_key",
        "status_code",
        "short_request",
        "short_response",
    )

    def short_request(self, obj):
        return format_html("<pre>{}</pre>", obj.request_payload or "-")

    def short_response(self, obj):
        return format_html("<pre>{}</pre>", obj.response_payload or "-")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    date_hierarchy = "timestamp"

    list_display = (
        "user",
        "user_type",
        "transaction_type",
        "payment_type",
        "gross_amount",
        "fee_amount",
        "amount",
        "status",
        "payment_period",
        "batch",
        "provider_reference",
        "single_pay_button",
        "retry_button",
        "timestamp",
    )

    list_filter = (
        "transaction_type",
        "payment_type",
        "status",
        "payment_period",
        UserTypeFilter,
        HasJobFilter,
        BatchStatusFilter,
    )

    search_fields = (
        "transaction_id",
        "provider_reference",
        "user__username",
        "user__email",
    )

    readonly_fields = (
        "gross_amount",
        "fee_amount",
        "amount",
        "provider_reference",
        "timestamp",
    )

    inlines = [PayoutLogInline]

    list_select_related = (
        "user",
        "job",
        "payment_period",
        "batch",
        "rate",
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user__profile")

    def get_urls(self):
        custom = [
            re_path(
                r"^single-pay/(?P<pk>[-\w]+)/$",
                self.admin_site.admin_view(single_pay_view),
                name="wallet_single_pay",
            ),
            re_path(
                r"^retry-pay/(?P<pk>[-\w]+)/$",
                self.admin_site.admin_view(retry_pay_view),
                name="wallet_retry_pay",
            ),
        ]
        return custom + super().get_urls()

    @admin.display(description="User Type")
    def user_type(self, obj):
        return getattr(obj.user.profile, "user_type", "-")

    # -------------------------
    # PAY / RETRY BUTTON RULES
    # -------------------------

    def _can_trigger_payment(self, obj):
        return (
            obj.transaction_type == "payment_processing"
            and obj.status in ("failed", "cancelled")
        )

    @admin.display(description="Pay")
    def single_pay_button(self, obj):
        if not self._can_trigger_payment(obj):
            return "-"
        url = reverse("admin:wallet_single_pay", args=[obj.id])
        return format_html(
            '<a class="button" style="background:#28a745;color:white;padding:4px 8px;border-radius:4px;" href="{}">Pay</a>',
            url,
        )

    @admin.display(description="Retry")
    def retry_button(self, obj):
        if not self._can_trigger_payment(obj):
            return "-"
        url = reverse("admin:wallet_retry_pay", args=[obj.id])
        return format_html(
            '<a class="button" style="background:#f0ad4e;color:white;padding:4px 8px;border-radius:4px;" href="{}">Retry</a>',
            url,
        )



@admin.register(PaymentPeriod)
class PaymentPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "batch_payouts_button")
    search_fields = ("name",)

    def get_urls(self):
        custom_urls = [
            path(
                "batch-payouts-v2/",
                self.admin_site.admin_view(list_periods_for_batching_view),
                name="wallet_period_payout_list",
            ),
            path(
                "batch-payouts-v2/<int:period_id>/",  # <-- FIXED: int instead of uuid
                self.admin_site.admin_view(period_payout_detail_view),
                name="wallet_paymentperiod_batch_payouts",
            ),
        ]
        return custom_urls + super().get_urls()

    @admin.display(description="Batch Payouts")
    def batch_payouts_button(self, obj):
        url = reverse(
            "admin:wallet_paymentperiod_batch_payouts",
            kwargs={"period_id": obj.id},  # integer now works
        )
        return format_html(
            '<a class="button" style="background:#28a745;color:white;padding:5px 10px;border-radius:4px;" href="{}">View / Run Payouts</a>',
            url
        )


@admin.register(PaymentBatch)
class PaymentBatchAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "provider",
        "period",
        "total_amount",
        "status",
        "run_button",
    )
    list_filter = ("provider", "status", "period")

    def changelist_view(self, request, extra_context=None):
        auto_discover_batches()
        return super().changelist_view(request, extra_context)

    def run_button(self, obj):
        if obj.status != "pending":
            return "-"
        return format_html(
            '<a class="button" href="run/{}/">Run Now</a>', obj.pk
        )

    run_button.short_description = "Payout"

    def get_urls(self):
        custom_urls = [
            path(
                "run/<uuid:batch_id>/",
                self.admin_site.admin_view(self.run_now),
                name="wallet_run_batch_now",
            ),
        ]
        return custom_urls + super().get_urls()

    def run_now(self, request, batch_id):
        batch = get_object_or_404(PaymentBatch, pk=batch_id)

        try:
            from wallet.payouts.manager import PayoutManager
            PayoutManager.execute_batch(batch, async_run=False)
            messages.success(
                request, f"Batch {batch.reference} executed successfully."
            )
        except Exception as exc:
            messages.error(request, str(exc))

        return redirect("..")


@admin.register(Rate)
class RateAdmin(admin.ModelAdmin):
    list_display = ("rate_amount", "effective_from")
    readonly_fields = ("effective_from",)

# ----------------------------
# PAYOUT LOG ADMIN
# ----------------------------


@admin.register(PayoutLog)
class PayoutLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "provider",
        "wallet_transaction",
        "batch",
        "status_readable",
        "has_error",
    )

    list_filter = ("provider", "endpoint", "batch")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)

    def status_readable(self, obj):
        if obj.status_code is None:
            return "Unknown"
        return "Successful" if 200 <= obj.status_code < 300 else "Failed"

    def has_error(self, obj):
        return bool(obj.error)

    has_error.boolean = True
