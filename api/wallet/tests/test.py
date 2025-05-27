import uuid
import json
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from payment.models import Payment
from payments.models import PaypalPayments
from core.models import Job, JobAssignment
from accounts.models import Profile
from wallet.models import WalletTransaction
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
import logging

logger = logging.getLogger(__name__)


class WalletAPITest(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        # Clear all relevant models
        ContentType.objects.all().delete()
        Permission.objects.all().delete()
        WalletTransaction.objects.all().delete()
        JobAssignment.objects.all().delete()
        Job.objects.all().delete()
        Profile.objects.all().delete()
        User.objects.all().delete()
        Payment.objects.all().delete()
        PaypalPayments.objects.all().delete()

        # Unique usernames
        self.freelancer_username = f'freelancer_{str(uuid.uuid4())[:8]}'
        self.client_username = f'client_{str(uuid.uuid4())[:8]}'

        # Create freelancer
        self.freelancer_user = User.objects.create_user(
            username=self.freelancer_username,
            password='testpass'
        )
        self.freelancer_profile, _ = Profile.objects.get_or_create(
            user=self.freelancer_user,
            defaults={'user_type': 'freelancer'}
        )
        self.freelancer_profile.user_type = 'freelancer'
        self.freelancer_profile.save()

        # Create client
        self.client_user = User.objects.create_user(
            username=self.client_username,
            password='testpass'
        )
        self.client_profile, _ = Profile.objects.get_or_create(
            user=self.client_user,
            defaults={'user_type': 'client'}
        )
        self.client_profile.user_type = 'client'
        self.client_profile.save()

        # Create job
        self.job = Job.objects.create(
            title='Test Job',
            category='data_entry',
            description='Test description',
            price=100.00,
            deadline_date='2025-12-31',
            client=self.client_profile,
            status='open'
        )
        # Assign freelancer to job
        self.assignment = JobAssignment.objects.create(
            job=self.job,
            freelancer=self.freelancer_profile
        )
        # Get JWT token for freelancer
        refresh = RefreshToken.for_user(self.freelancer_user)
        self.freelancer_token = str(refresh.access_token)

    def tearDown(self):
        # Clear all relevant models
        ContentType.objects.all().delete()
        Permission.objects.all().delete()
        WalletTransaction.objects.all().delete()
        JobAssignment.objects.all().delete()
        Job.objects.all().delete()
        Profile.objects.all().delete()
        User.objects.all().delete()
        Payment.objects.all().delete()
        PaypalPayments.objects.all().delete()

    def test_job_picked_creates_pending_transaction(self):
        wallet_tx = WalletTransaction.objects.get(
            user=self.freelancer_user,
            job=self.job,
            transaction_type='job_picked'
        )
        self.assertEqual(wallet_tx.status, 'pending')
        self.assertEqual(
            wallet_tx.extra_data['assignment_id'], self.assignment.id)
        self.assertIsNone(wallet_tx.amount)
        self.assertIsNone(wallet_tx.payment_type)
        self.assertIsNone(wallet_tx.transaction_id)

    def test_paystack_payment_updates_to_payment_received(self):
        payment = Payment.objects.create(
            user=self.client_user,
            amount=100,
            ref=f'paystack_ref_{str(uuid.uuid4())[:8]}',
            email='client@example.com',
            job=self.job,
            verified=True
        )
        wallet_tx = WalletTransaction.objects.get(
            user=self.freelancer_user,
            job=self.job,
            transaction_type='payment_received'
        )
        self.assertEqual(wallet_tx.payment_type, 'paystack')
        self.assertEqual(wallet_tx.transaction_id, payment.ref)
        self.assertEqual(wallet_tx.amount, 100)
        self.assertEqual(wallet_tx.status, 'completed')
        self.assertEqual(wallet_tx.extra_data['payment_id'], payment.id)
        self.assertEqual(
            wallet_tx.extra_data['original_assignment_id'], self.assignment.id)

    def test_paypal_payment_updates_to_payment_received(self):
        paypal_payment = PaypalPayments.objects.create(
            job=self.job,
            invoice=f'paypal_invoice_{str(uuid.uuid4())[:8]}',
            amount=100.00,
            email='client@example.com',
            user=self.client_user,
            status='completed'
        )
        wallet_tx = WalletTransaction.objects.get(
            user=self.freelancer_user,
            job=self.job,
            transaction_type='payment_received'
        )
        self.assertEqual(wallet_tx.payment_type, 'paypal')
        self.assertEqual(wallet_tx.transaction_id, paypal_payment.invoice)
        self.assertEqual(wallet_tx.amount, 100.00)
        self.assertEqual(wallet_tx.status, 'completed')
        self.assertEqual(wallet_tx.extra_data['payment_id'], paypal_payment.id)
        self.assertEqual(
            wallet_tx.extra_data['original_assignment_id'], self.assignment.id)

    def test_wallet_api_lists_transactions(self):
        payment = Payment.objects.create(
            user=self.client_user,
            amount=100,
            ref=f'ref_{str(uuid.uuid4())[:8]}',
            email='client@example.com',
            job=self.job,
            verified=True
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.freelancer_token}')
        response = self.client.get(reverse('wallet-list'))
        self.assertEqual(response.status_code, 200)
        logger.debug(f"API response transactions: {len(response.data)}")
        logger.debug(
            f"Raw response data: {json.dumps(response.data, indent=2)}")
        if isinstance(response.data, list):
            for tx in response.data:
                if isinstance(tx, dict):
                    logger.debug(
                        f"API response tx: id={tx.get('id', 'N/A')}, user={tx.get('user', 'N/A')}, type={tx.get('transaction_type', 'N/A')}, job={tx.get('job', 'N/A')}")
                else:
                    logger.debug(f"Unexpected response item: {tx}")
        else:
            logger.debug(
                f"Unexpected response data type: {type(response.data)}")
        self.assertEqual(len(response.data), 1)  # Only payment_received
        tx = response.data[0]
        self.assertEqual(tx['user'], self.freelancer_username)
        self.assertEqual(tx['transaction_type'], 'payment_received')
        self.assertEqual(tx['payment_type'], 'paystack')
        self.assertEqual(tx['transaction_id'], payment.ref)
        self.assertEqual(float(tx['amount']), 100.00)
        self.assertEqual(tx['status'], 'completed')

    def test_wallet_api_only_own_transactions(self):
        # Clear job and assignment to ensure no transactions for freelancer
        JobAssignment.objects.all().delete()
        Job.objects.all().delete()
        WalletTransaction.objects.all().delete()

        # Recreate client
        self.client_user = User.objects.create_user(
            username=f'client_{str(uuid.uuid4())[:8]}',
            password='testpass'
        )
        self.client_profile, _ = Profile.objects.get_or_create(
            user=self.client_user,
            defaults={'user_type': 'client'}
        )
        self.client_profile.user_type = 'client'
        self.client_profile.save()

        # Create other freelancer
        other_freelancer_username = f'other_freelancer_{str(uuid.uuid4())[:8]}'
        other_freelancer_user = User.objects.create_user(
            username=other_freelancer_username,
            password='otherpass'
        )
        other_freelancer_profile, _ = Profile.objects.get_or_create(
            user=other_freelancer_user,
            defaults={'user_type': 'freelancer'}
        )
        other_freelancer_profile.user_type = 'freelancer'
        other_freelancer_profile.save()

        # Create other job
        other_job = Job.objects.create(
            title='Other Job',
            category='writing',
            description='Other description',
            price=50.00,
            deadline_date='2025-12-31',
            client=self.client_profile,
            status='open'
        )
        # Assign other freelancer
        other_assignment = JobAssignment.objects.create(
            job=other_job,
            freelancer=other_freelancer_profile
        )
        # Create payment for other freelancer
        payment = Payment.objects.create(
            user=self.client_user,
            amount=50,
            ref=f'other_ref_{str(uuid.uuid4())[:8]}',
            email='client@example.com',
            job=other_job,
            verified=True
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.freelancer_token}')
        response = self.client.get(reverse('wallet-list'))
        self.assertEqual(response.status_code, 200)
        logger.debug(
            f"API response transactions for freelancer: {len(response.data)}")
        logger.debug(
            f"Raw response data: {json.dumps(response.data, indent=2)}")
        if isinstance(response.data, list):
            for tx in response.data:
                if isinstance(tx, dict):
                    logger.debug(
                        f"API response tx: id={tx.get('id', 'N/A')}, user={tx.get('user', 'N/A')}, type={tx.get('transaction_type', 'N/A')}, job={tx.get('job', 'N/A')}")
                else:
                    logger.debug(f"Unexpected response item: {tx}")
        else:
            logger.debug(
                f"Unexpected response data type: {type(response.data)}")
        # No transactions for this freelancer
        self.assertEqual(len(response.data), 0)

    def test_wallet_api_unauthenticated(self):
        response = self.client.get(reverse('wallet-list'))
        self.assertEqual(response.status_code, 401)
