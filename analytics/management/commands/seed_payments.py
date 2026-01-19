import random
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum, Q
from django.contrib.auth import get_user_model

from accounts.models import ClientProfile, Profile
from core.models import Job
from payment.models import Payment
from wallet.models import WalletTransaction, Rate, PaymentPeriod

User = get_user_model()


class Command(BaseCommand):
    help = "Seed/fix client payments for jobs. Use --freelancers to also simulate freelancer payouts"

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete ALL payments & wallet transactions first (VERY DANGEROUS!)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually saving anything',
        )
        parser.add_argument(
            '--only-missing',
            action='store_true',
            help='Only fix jobs that have payment_verified=True but no Payment record',
        )
        parser.add_argument(
            '--freelancers',
            action='store_true',
            help='Also create simulated freelancer payout/withdrawal records',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        clear_first = options['clear']
        only_missing = options['only_missing']
        include_freelancers = options['freelancers']

        # 1. Optional dangerous full clear
        if clear_first:
            self.stdout.write(self.style.WARNING(
                "DANGER: Clearing ALL payments, wallet transactions and resetting job payment status..."
            ))
            if not dry_run:
                Payment.objects.all().delete()
                WalletTransaction.objects.all().delete()
                Job.objects.update(payment_verified=False)
                self.stdout.write(self.style.SUCCESS("Everything cleared."))
            else:
                self.stdout.write(self.style.WARNING(
                    "[DRY-RUN] Would have cleared all data."))
            self.stdout.write("")

        # 2. Get or create platform fee rate
        rate_obj = Rate.objects.order_by('-effective_from').first()
        if rate_obj is None:
            if dry_run:
                rate_value = Decimal('10.00')
                self.stdout.write("[DRY] Using default platform rate: 10.00%")
            else:
                rate_obj = Rate.objects.create(
                    rate_amount=Decimal('10.00'),
                    effective_from=timezone.now(),
                )
                rate_value = rate_obj.rate_amount
                self.stdout.write(self.style.SUCCESS(
                    f"Created default rate: {rate_value}%"))
        else:
            rate_value = rate_obj.rate_amount
            self.stdout.write(self.style.SUCCESS(
                f"Using platform fee rate: {rate_value}% (effective from {rate_obj.effective_from.date()})"
            ))

        # 3. Get or create current payment period
        today = timezone.now().date()
        period = PaymentPeriod.get_period_for_date(today)

        if not period and not dry_run:
            from dateutil.relativedelta import relativedelta
            start = today.replace(day=1)
            end = (start + relativedelta(months=1)) - timedelta(days=1)
            period = PaymentPeriod.objects.create(
                name=f"{today.strftime('%B %Y')} - Full Month",
                start_date=start,
                end_date=end,
            )
            self.stdout.write(self.style.SUCCESS(
                f"Created payment period: {period.name}"))

        # 4. Select jobs to process (only client related fields!)
        base_qs = Job.objects.select_related('client__user')

        if only_missing:
            jobs = base_qs.filter(
                payment_verified=True,
                payment__isnull=True,
            )
            msg = f"Found {jobs.count()} jobs with payment_verified=True but missing Payment record"
        else:
            jobs = base_qs.filter(
                Q(payment_verified=False) | Q(
                    payment_verified=True, payment__isnull=True)
            ).distinct()
            msg = f"Found {jobs.count()} jobs needing payment simulation / fix"

        self.stdout.write(msg)

        if not jobs.exists():
            self.stdout.write(self.style.SUCCESS(
                "Nothing to do — all relevant jobs already look funded."))
            return

        created_payments = 0
        created_payouts = 0

        for job in jobs.iterator():
            if not job.client:
                self.stdout.write(self.style.WARNING(
                    f"Skipping job #{job.id} — no client"))
                continue

            client_user = job.client.user
            amount = job.price

            ref = f"PAY_{uuid.uuid4().hex[:28].upper()}"
            paid_at = job.posted_date + \
                timedelta(minutes=random.randint(5, 600))
            if paid_at > timezone.now():
                paid_at = timezone.now() - timedelta(minutes=random.randint(1, 180))

            channel = random.choice(["mobile_money", "card"])

            extra_data = {
                "reference": ref,
                "amount": int(amount * 100),
                "currency": "KES",
                "channel": channel,
                "status": "success",
                "gateway_response": "Approved",
                "paid_at": paid_at.isoformat() + "Z",
            }

            if dry_run:
                self.stdout.write(
                    f"[DRY] Job #{job.id} | Client funding {amount:,.0f} KES | Ref: {ref}"
                )
                created_payments += 1
            else:
                # Create or get client payment record
                payment, created = Payment.objects.get_or_create(
                    job=job,
                    defaults={
                        'user': client_user,
                        # assuming your Payment.amount is IntegerField
                        'amount': int(amount),
                        'ref': ref,
                        'email': client_user.email,
                        'verified': True,
                        'date_created': paid_at,
                        'extra_data': extra_data,
                    }
                )

                # Mark job as verified if needed
                if not job.payment_verified:
                    job.payment_verified = True
                    job.save(update_fields=['payment_verified'])

                # Record in wallet (client → platform)
                WalletTransaction.objects.update_or_create(
                    transaction_id=ref,
                    defaults={
                        'user': client_user,
                        'transaction_type': 'payment_received',
                        'rate': rate_obj,
                        'payment_type': 'paystack',
                        'gross_amount': amount,
                        # client side doesn't pay fee here
                        'fee_amount': Decimal('0.00'),
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
                created_payments += 1

                status = "CREATED" if created else "ALREADY_EXISTED"
                self.stdout.write(self.style.SUCCESS(
                    f"Client payment {status} → Job #{job.id} | {amount:,.0f} KES | {ref[:35]}..."
                ))

            # ── FREELANCER PAYOUTS ──────────────────────────────────────────────
            if not include_freelancers:
                continue

            if job.status not in ['completed', 'delivered', 'approved']:
                continue

            freelancers = job.selected_freelancers.all()
            if not freelancers.exists():
                continue

            platform_fee = amount * (rate_value / Decimal('100'))
            net_total = amount - platform_fee

            count = freelancers.count()
            if count == 0:
                continue

            split_amount = (
                net_total / count).quantize(Decimal('0.01'), rounding='ROUND_DOWN')
            remainder = net_total - (split_amount * count)

            for idx, freelancer_user in enumerate(freelancers):
                payout = split_amount
                if idx == 0:  # give remainder to first freelancer
                    payout += remainder

                payout_ref = f"PAYOUT_{uuid.uuid4().hex[:28].upper()}"
                payout_date = paid_at + timedelta(days=random.randint(1, 45))

                if dry_run:
                    self.stdout.write(
                        f"[DRY] Job #{job.id} → Freelancer {freelancer_user.username} "
                        f"→ {payout:,.0f} KES"
                    )
                    created_payouts += 1
                    continue

                # Create freelancer incoming transaction (most systems use 'payment_received')
                WalletTransaction.objects.update_or_create(
                    transaction_id=payout_ref,
                    defaults={
                        'user': freelancer_user,
                        'transaction_type': 'payment_received',
                        'rate': rate_obj,
                        'gross_amount': amount / count,
                        'fee_amount': platform_fee / count,
                        'amount': payout,
                        'status': 'completed',
                        'job': job,
                        'payment_period': period,
                        'completed': True,
                        'extra_data': {
                            "type": "job_completion_payout",
                            "client_ref": ref,
                            "split_count": count,
                            "note": "Payout after job completion"
                        }
                    }
                )
                created_payouts += 1

        # ── Final summary ─────────────────────────────────────────────────────
        self.stdout.write("\n" + "═" * 85)

        if dry_run:
            msg = f"DRY RUN COMPLETE — Would have created {created_payments} client payments"
            if include_freelancers:
                msg += f" + {created_payouts} freelancer payouts"
            self.stdout.write(self.style.WARNING(msg))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Processed {created_payments} client payments"))
            if include_freelancers and created_payouts > 0:
                self.stdout.write(self.style.SUCCESS(
                    f"Also created {created_payouts} freelancer payouts"))

        total_funded = Payment.objects.aggregate(
            t=Sum('amount'))['t'] or Decimal('0.00')
        self.stdout.write(
            f"Total client-funded amount in system: {total_funded:,.2f} KES")
        self.stdout.write("═" * 85)
