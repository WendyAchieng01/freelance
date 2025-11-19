# analytics/management/commands/seed_payments_and_wallet.py

import random
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum, Q
from django.contrib.auth import get_user_model

from accounts.models import ClientProfile
from core.models import Job
from payment.models import Payment
from wallet.models import WalletTransaction, Rate, PaymentPeriod

User = get_user_model()


class Command(BaseCommand):
    help = "Fix missing payments + fund all jobs with REAL Paystack/M-Pesa simulation"

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Delete ALL payments & wallet tx first')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be created')
        parser.add_argument('--only-missing', action='store_true',
                            help='Only fix jobs with payment_verified=True but no Payment record')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        clear_first = options['clear']
        only_missing = options['only_missing']

        if clear_first:
            self.stdout.write(
                "Clearing ALL payments and wallet transactions...")
            Payment.objects.all().delete()
            WalletTransaction.objects.all().delete()
            Job.objects.update(payment_verified=False)
            self.stdout.write(self.style.SUCCESS("Cleared!"))

        # Auto-load current rate
        try:
            rate_obj = Rate.objects.latest('effective_from')
            rate_value = rate_obj.rate_amount
            self.stdout.write(self.style.SUCCESS(
                f"Using platform fee: {rate_value}%"))
        except Rate.DoesNotExist:
            rate_obj = Rate.objects.create(rate_amount=Decimal('8.00'))
            rate_value = rate_obj.rate_amount
            self.stdout.write(self.style.WARNING(
                "No rate found → created 8.00%"))

        # Auto-load or create current payment period
        today = timezone.now().date()
        period = PaymentPeriod.get_period_for_date(today)
        if not period:
            from dateutil.relativedelta import relativedelta
            start = today.replace(day=1)
            end = (start + relativedelta(months=1)) - timedelta(days=1)
            period = PaymentPeriod.objects.create(
                name=f"{today.strftime('%B %Y')} - Full Month",
                start_date=start,
                end_date=end
            )
            self.stdout.write(self.style.SUCCESS(
                f"Created payment period: {period}"))

        # Build query: either only missing, or all unpaid + missing
        base_jobs = Job.objects.select_related('client__user')

        if only_missing:
            jobs = base_jobs.filter(payment_verified=True).exclude(
                payment__isnull=False)
            self.stdout.write(
                f"Found {jobs.count()} jobs marked as paid but missing Payment record → fixing...")
        else:
            jobs = base_jobs.filter(
                Q(payment_verified=False) | Q(
                    payment_verified=True, payment__isnull=True)
            ).distinct()
            self.stdout.write(
                f"Found {jobs.count()} jobs needing payment simulation (unpaid + missing records)")

        if not jobs.exists():
            self.stdout.write(self.style.SUCCESS(
                "All jobs already have proper payment records!"))
            return

        created = 0
        for job in jobs:
            client_user = job.client.user
            amount = job.price

            ref = f"PAY_{uuid.uuid4().hex[:28].upper()}"
            paid_at = job.posted_date + \
                timedelta(minutes=random.randint(5, 600))
            if paid_at > timezone.now():
                paid_at = timezone.now() - timedelta(minutes=random.randint(1, 180))

            channel = random.choice(["mobile_money", "card"])
            extra_data = {
                "id": random.randint(5000000000, 9999999999),
                "domain": "live",
                "status": "success",
                "reference": ref,
                "amount": int(amount * 100),
                "currency": "KES",
                "channel": channel,
                "gateway_response": "Approved",
                "paid_at": paid_at.isoformat() + "Z",
                "created_at": (paid_at - timedelta(seconds=random.randint(15, 120))).isoformat() + "Z",
                "customer": {"email": client_user.email},
                "authorization": {
                    "bank": "M-PESA" if channel == "mobile_money" else "KCB",
                    "brand": "M-pesa" if channel == "mobile_money" else "Visa",
                    "last4": "0000",
                    "mobile_money_number": f"07{random.randint(10000000, 99999999)}" if channel == "mobile_money" else None
                }
            }

            if dry_run:
                status = "MISSING" if job.payment_verified else "UNPAID"
                self.stdout.write(
                    f"[DRY] [{status}] Job #{job.id} ← {amount:,.0f} KES | Ref: {ref}")
                created += 1
                continue

            # Create Payment (only if not exists)
            payment, created_payment = Payment.objects.get_or_create(
                job=job,
                defaults={
                    'user': client_user,
                    'amount': amount,
                    'ref': ref,
                    'email': client_user.email,
                    'verified': True,
                    'date_created': paid_at,
                    'extra_data': extra_data,
                }
            )

            # Always mark job as paid
            job.payment_verified = True
            job.save(update_fields=['payment_verified'])

            # Create Wallet Transaction
            WalletTransaction.objects.update_or_create(
                transaction_id=ref,
                defaults={
                    'user': client_user,
                    'transaction_type': 'payment_received',
                    'rate': rate_value,
                    'payment_type': 'paystack',
                    'amount': amount,
                    'status': 'completed',
                    'job': job,
                    'payment_period': period,
                    'completed': True,
                    'extra_data': {
                        "gateway": "paystack",
                        "channel": channel,
                        "note": "Client funded job budget"
                    }
                }
            )

            status = "FIXED" if job.payment_verified and not created_payment else "FUNDED"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{status} → Job #{job.id} | {amount:,.0f} KES | {ref[:35]}")
            )
            created += 1

        # Final Summary
        total = Payment.objects.aggregate(t=Sum('amount'))[
            't'] or Decimal('0.00')
        self.stdout.write("\n" + "═" * 85)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f" DRY RUN: Would fix/fund {created} jobs "))
        else:
            self.stdout.write(self.style.SUCCESS(
                f" SUCCESS: {created} jobs now have real payments & wallet entries "))
            self.stdout.write(self.style.SUCCESS(
                f" Total money in system: {total:,.2f} KES "))
            self.stdout.write(self.style.SUCCESS(
                f" Platform fee: {rate_value}% | Period: {period} "))
        self.stdout.write("═" * 85)
