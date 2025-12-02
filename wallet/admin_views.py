import csv
import logging
from decimal import Decimal
from django.db import models
from django.urls import reverse
from django.http import HttpResponse
from django_q.tasks import async_task
from django.contrib import admin, messages

from django.shortcuts import render, redirect, get_object_or_404


from wallet.payouts.manager import PayoutManager
from wallet.models import PaymentPeriod, WalletTransaction, PaymentBatch


logger = logging.getLogger(__name__)


def single_pay_view(request, pk):
    tx = get_object_or_404(WalletTransaction, pk=pk)
    logger.warning(
        "SINGLE PAY INITIATED for TX %s (user=%s)", tx.id, tx.user)

    try:
        result = PayoutManager.execute_single(tx)
    except Exception as exc:
        logger.exception(
            "Unhandled error while running single pay for tx %s", tx.id)
        messages.error(request, f"Unexpected error: {exc}")
        return redirect(request.META.get("HTTP_REFERER", "/admin/"))

    if result.get("success"):
        messages.success(request, f"Payment sent for tx {tx.id}.")
    else:
        messages.error(request, "Payment failed: " +
                       (result.get("error") or "unknown"))
    return redirect(request.META.get("HTTP_REFERER", "/admin/"))


def run_batch_view(request, batch_id):
    batch = get_object_or_404(PaymentBatch, pk=batch_id)
    # schedule async run using django-q
    try:
        PayoutManager.execute_batch(batch, async_run=True)
        messages.success(
            request, f"Batch {batch.reference} scheduled for processing.")
    except Exception:
        logger.exception("Error scheduling batch %s", batch_id)
        messages.error(request, "Failed to schedule batch processing.")
    return redirect(request.META.get("HTTP_REFERER", "/admin/"))


def retry_pay_view(request, pk):
    tx = get_object_or_404(WalletTransaction, pk=pk)

    from wallet.tasks import retry_failed_payouts

    retry_failed_payouts()

    messages.success(request, "Retry queued/executed.")
    return redirect("/admin/wallet/wallettransaction/")


def list_periods_for_batching_view(request):
    """
    Admin view to list all payment periods and show which ones have pending payouts.
    """
    periods = PaymentPeriod.objects.annotate(
        pending_payouts=models.Count(
            'transactions',
            filter=models.Q(
                transactions__status='pending',
                transactions__batch__isnull=True
            )
        )
    ).order_by('-start_date')

    context = {
        **admin.site.each_context(request),
        'title': 'Payment Periods for Batch Payout',
        'periods': periods,
    }
    return render(request, 'admin/wallet/paymentperiod/list_periods_for_batching.html', context)


def period_payout_detail_view(request, period_id):
    """
    Admin view to show all transactions for a specific payment period,
    with search, filtering, CSV export, and batch creation capabilities.
    """
    period = get_object_or_404(PaymentPeriod, id=period_id)

    # --- Filtering and Searching ---
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    all_transactions = WalletTransaction.objects.filter(
        payment_period=period,
        user__profile__user_type='freelancer'
    ).select_related('user', 'job').order_by('-timestamp')


    if search_query:
        all_transactions = all_transactions.filter(
            models.Q(user__username__icontains=search_query) |
            models.Q(job__title__icontains=search_query)
        )

    if status_filter in ['completed', 'failed', 'pending']:
        all_transactions = all_transactions.filter(status=status_filter)

    # --- CSV Export ---
    if 'download_csv' in request.GET:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="payouts_{period.name}_{period.id}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Transaction ID', 'Freelancer', 'Job Title', 'Gross Amount (KES)', 'Fee Amount (KES)',
            'Net Amount (KES)', 'Status', 'Payment Type', 'Timestamp'
        ])
        for tx in all_transactions:
            writer.writerow([
                tx.transaction_id, tx.user.username, tx.job.title if tx.job else 'N/A',
                tx.gross_amount, tx.fee_amount, tx.amount, tx.get_status_display(),
                tx.payment_type, tx.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            ])
        return response

    # --- Batch Creation (POST) ---
    pending_transactions = all_transactions.filter(
        status='pending',
        batch__isnull=True
    )

    if request.method == 'POST':
        if not pending_transactions.exists():
            messages.warning(
                request, "There are no pending transactions to batch for this period.")
            return redirect(request.get_full_path())

        transactions_by_user = {}
        for tx in pending_transactions:
            provider = tx.payment_type or 'paystack'
            key = (tx.user.id, provider)
            if key not in transactions_by_user:
                transactions_by_user[key] = []
            transactions_by_user[key].append(tx)

        batches_created = []
        for (user_id, provider), tx_list in transactions_by_user.items():
            total_amount = sum(tx.amount for tx in tx_list if tx.amount)
            batch = PaymentBatch.objects.create(
                period=period, user_id=user_id, provider=provider,
                total_amount=total_amount, status='pending'
            )
            batches_created.append(batch)
            WalletTransaction.objects.filter(
                id__in=[tx.id for tx in tx_list]).update(batch=batch)
            async_task('wallet.tasks_v2.process_batch_payment_v2', batch.id)

        if batches_created:
            messages.success(
                request, f"Successfully created and initiated {len(batches_created)} payment batch(es).")
        else:
            messages.warning(request, "No batches were created.")

        return redirect(reverse('admin:wallet_paymentbatch_changelist'))

    context = {
        **admin.site.each_context(request),
        'title': f'Payouts for {period.name}',
        'period': period,
        'transactions': all_transactions,
        'pending_count': pending_transactions.count(),
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'admin/wallet/paymentperiod/period_payout_detail.html', context)
