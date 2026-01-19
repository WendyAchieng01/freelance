import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from wallet.models import WalletTransaction, PaymentPeriod
from core.models import Job

logger = logging.getLogger(__name__)


class PayoutIntentService:
    """
    Responsible for creating payout (payment_processing) wallet transactions
    when a Job is completed.

    This service is:
    - idempotent
    - safe to call multiple times
    - the ONLY place that creates payout intents
    """

    @classmethod
    @transaction.atomic
    def create_for_completed_job(cls, job: Job) -> int:
        """
        Creates payout intents for a completed job.
        Returns number of transactions created.
        """

        if job.status != "completed":
            logger.debug(
                "[PayoutIntentService] Job %s not completed, skipping", job.id
            )
            return 0

        freelancers = job.selected_freelancers.all()
        if not freelancers.exists():
            logger.warning(
                "[PayoutIntentService] Job %s has no selected freelancers", job.id
            )
            return 0

        # ---- Determine payment period ----
        period_date = (
            job.assigned_at.date()
            if job.assigned_at
            else timezone.now().date()
        )
        period = PaymentPeriod.get_period_for_date(period_date)

        # ---- Job helpers  ----
        gross_amount = Decimal(job.price or "0.00")
        fee_amount = job.total_platform_fee
        net_per_freelancer = job.net_per_freelancer

        rate_obj = None
        if job.wallet_transactions.exists():
            rate_obj = job.wallet_transactions.first().rate

        created_count = 0

        for user in freelancers:
            # ---- HARD idempotency guard ----
            exists = WalletTransaction.objects.filter(
                job=job,
                user=user,
                transaction_type="payment_processing",
                status__in=["pending", "in_progress"],
            ).exists()

            if exists:
                logger.info(
                    "[PayoutIntentService] Payout already exists | job=%s user=%s",
                    job.id,
                    user.id,
                )
                continue

            WalletTransaction.objects.create(
                user=user,
                job=job,
                transaction_type="payment_processing",
                status="pending",
                rate=rate_obj,
                gross_amount=gross_amount,
                fee_amount=fee_amount,
                amount=net_per_freelancer,
                payment_period=period,
            )

            created_count += 1
            logger.info(
                "[PayoutIntentService] Created payout intent | job=%s user=%s amount=%s",
                job.id,
                user.id,
                net_per_freelancer,
            )

        return created_count
