import logging
from decimal import Decimal
from django.db.models import Sum, Q
from django_q.tasks import async_task
from payments.tasks import process_batch
from django.utils.html import format_html
from django.contrib import admin, messages
from django.urls import reverse, path, re_path
from django.contrib.admin import SimpleListFilter
from django.shortcuts import redirect, get_object_or_404
from wallet.models import WalletTransaction, PaymentPeriod, PaymentBatch, PayoutLog, Rate
from api.wallet.gateways.batch_creator import create_batches_for_period
from wallet.admin_views import run_batch_view, single_pay_view, retry_pay_view,list_periods_for_batching_view, period_payout_detail_view

logger = logging.getLogger(__name__)



class BatchAssignedFilter(SimpleListFilter):
    title = 'Batch Assigned'
    parameter_name = 'batch_assigned'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Assigned'),
            ('no', 'Not Assigned'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(batch__isnull=False)
        if self.value() == 'no':
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
    fields = readonly_fields

    def short_request(self, obj):
        if not obj.request_payload:
            return "-"
        return format_html(
            "<pre style='max-width:420px; white-space:pre-wrap'>{}</pre>",
            obj.request_payload
        )

    def short_response(self, obj):
        if not obj.response_payload:
            return "-"
        return format_html(
            "<pre style='max-width:420px; white-space:pre-wrap'>{}</pre>",
            obj.response_payload
        )


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "transaction_type",
        "amount",
        "status",
        "payment_period",
        "batch",
        "single_pay_button",
        "retry_button",
    )

    list_filter = (
        "transaction_type",
        "payment_type",
        "status",
        "payment_period",
        "batch",
    )

    search_fields = ("transaction_id", "user__username")

    def get_urls(self):
        urls = super().get_urls()
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
        return custom + urls

    @admin.display(description="Pay")
    def single_pay_button(self, obj):
        url = reverse("admin:wallet_single_pay", args=[obj.id])
        return format_html("<a class='button' style='color:white;background:green;padding:4px 8px' href='{}'>Pay</a>", url)

    @admin.display(description="Retry")
    def retry_button(self, obj):
        url = reverse("admin:wallet_retry_pay", args=[obj.id])
        return format_html("<a class='button' style='color:white;background:orange;padding:4px 8px' href='{}'>Retry</a>", url)



@admin.register(PaymentPeriod)
class PaymentPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "create_batch_btn", "batch_payouts_v2_button")
    search_fields = ("name",)
    actions = ["create_batch_for_period_action"]

    def create_batch_btn(self, obj):
        url = reverse("admin:create_batch_for_period", args=[obj.id])
        return format_html(
            "<a class='button' style='background:#007bff; color:white; padding:5px 10px; border-radius:4px;' href='{}'>Create Batch</a>",
            url
        )
    create_batch_btn.short_description = "Batch"

    def batch_payouts_v2_button(self, obj):
        url = reverse('admin:wallet_period_payout_detail', args=[obj.id])
        return format_html(
            "<a class='button' style='background:#28a745; color:white; padding:5px 10px; border-radius:4px;' href='{}'>Batch Payouts V2</a>",
            url
        )
    batch_payouts_v2_button.short_description = "Batch Payouts (New)"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "create-batch/<int:period_id>/",
                self.admin_site.admin_view(self.create_batch_for_period),
                name="create_batch_for_period"
            ),
            path(
                "batch-payouts-v2/",
                self.admin_site.admin_view(list_periods_for_batching_view),
                name="wallet_period_payout_list"
            ),
            path(
                "batch-payouts-v2/<int:period_id>/",
                self.admin_site.admin_view(period_payout_detail_view),
                name="wallet_period_payout_detail"
            ),
        ]
        return custom + urls

    def create_batch_for_period(self, request, period_id):
        try:
            period = PaymentPeriod.objects.get(id=period_id)
        except PaymentPeriod.DoesNotExist:
            messages.error(request, "Payment period not found.")
            return redirect(request.META.get("HTTP_REFERER", "/admin/"))

        batches = create_batches_for_period(period)
        if not batches:
            messages.warning(
                request, "No pending completed-job payouts found for this period.")
            return redirect(request.META.get("HTTP_REFERER", "/admin/"))

        messages.success(
            request, f"Created {len(batches)} batch(es) for period {period.name}.")
        return redirect("/admin/wallet/paymentbatch/")

    def create_batch_for_period_action(self, request, queryset):
        total = 0
        for period in queryset:
            batches = create_batches_for_period(period)
            total += len(batches)
        messages.success(
            request, f"Created {total} batches across selected periods.")
    create_batch_for_period_action.short_description = "Create batch for selected payment periods"


@admin.register(PaymentBatch)
class PaymentBatchAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "provider",
        "period",
        "user",
        "total_amount",
        "status",
        "created_at",
        "run_batch_button",
    )

    list_filter = ("provider", "status", "period")
    search_fields = ("reference", "user__username")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "run-batch/<uuid:pk>/",
                self.admin_site.admin_view(self.run_batch_view),
                name="wallet_run_batch",
            ),
        ]
        return custom + urls

    def run_batch_button(self, obj):
        url = reverse("admin:wallet_run_batch", args=[obj.id])
        return format_html(
            "<a class='button' style='padding:5px 10px;background:#007bff;color:white;' href='{}'>Run Batch</a>",
            url,
        )
    run_batch_button.short_description = "Run Batch"

    #  BATCH EXECUTION LOGIC

    def run_batch_view(self, request, pk):
        batch = get_object_or_404(PaymentBatch, pk=pk)

        txs = batch.transactions.filter(status="pending")

        if not txs.exists():
            messages.warning(request, "No pending transactions in this batch.")
            return redirect("admin:wallet_paymentbatch_changelist")

        # TODO: integrate gateway payout logic here


        messages.success(
            request, f"Batch executed for {txs.count()} payout(s)!")
        return redirect("admin:wallet_paymentbatch_changelist")
    
    #change_list_template = "admin/analytics_dashboard.html"

    def changelist_view(self, request, extra_context=None):
        stats = {
            "pending": PaymentBatch.objects.filter(status="pending").count(),
            "completed": PaymentBatch.objects.filter(status="completed").count(),
            "failed": PaymentBatch.objects.filter(status="failed").count(),
            "total_amount": PaymentBatch.objects.all().aggregate(Sum("total_amount"))["total_amount__sum"],
        }
        extra_context = extra_context or {}
        extra_context["stats"] = stats
        return super().changelist_view(request, extra_context)



@admin.register(Rate)
class RateAdmin(admin.ModelAdmin):
    list_display = ("rate_amount", "effective_from")
    readonly_fields = ("effective_from",)


@admin.register(PayoutLog)
class PayoutLogAdmin(admin.ModelAdmin):

    list_display = (
        "created_at","provider","wallet_transaction","batch",
        "status_readable","has_error",
    )

    list_filter = (
        "provider","endpoint","batch",
        ("created_at", admin.DateFieldListFilter),
    )

    date_hierarchy = "created_at"

    search_fields = (
        "provider","endpoint","idempotency_key","error",
    )

    readonly_fields = ("created_at",)

    fieldsets = (
        (None, {
            "fields": (
                "provider",
                "endpoint",
                "wallet_transaction",
                "batch",
                "status_code",
                "idempotency_key",
                "error",
            )
        }),
        ("Payloads", {
            "classes": ("collapse",),
            "fields": (
                "request_payload",
                "response_payload",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at",)
        }),
    )


    def status_readable(self, obj):
        """
        Make status human readable.
        200, 201, 204 → Successful
        >=400 → Failed
        None → Unknown
        """
        if obj.status_code is None:
            return "Unknown"
        if 200 <= obj.status_code < 300:
            return "Successful"
        return "Failed"

    status_readable.short_description = "Status"

    def has_error(self, obj):
        """
        Boolean flag for filtering.
        """
        return bool(obj.error)

    has_error.boolean = True 
    has_error.short_description = "Error?"

    def status_group(self, obj):
        """
        Used only for filtering.
        """
        if obj.status_code is None:
            return "Unknown"
        if 200 <= obj.status_code < 300:
            return "Successful"
        if obj.status_code >= 400:
            return "Failed"
        return "Other"

    status_group.short_description = "Status Category"

