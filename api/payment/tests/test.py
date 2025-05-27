from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from accounts.models import Profile
from core.models import Job
from payment.models import Payment
from unittest.mock import patch, Mock
from datetime import date, timedelta
import uuid

User = get_user_model()


class PaymentAPITest(APITestCase):
    def setUp(self):
        """Set up test data: a verified user, a client profile, and a job."""
        # Create a test user (client)
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        # Use get_or_create to avoid UNIQUE constraint violation
        self.profile, _ = Profile.objects.get_or_create(
            user=self.user,
            defaults={'user_type': 'client'}
        )
        # Activate the user (simulate email verification)
        self.user.is_active = True
        self.user.save()

        # Create a job owned by the client
        self.job = Job.objects.create(
            client=self.profile,
            title='Test Job',
            category='data_entry',
            description='Test Description',
            price=100.00,  # Use Decimal for price
            deadline_date=date.today() + timedelta(days=30),
            status='open',
            max_freelancers=1,
            preferred_freelancer_level='intermediate'
        )

    @patch('api.payment.paystack.Paystack')
    def test_initiate_payment_success(self, MockPaystack):
        """Test successful payment initiation for a job owned by the user."""
        # Configure the mock instance
        mock_paystack_instance = MockPaystack.return_value
        mock_paystack_instance.initialize_transaction = Mock(
            return_value=(
                True, {'authorization_url': 'https://paystack.com/authorization'})
        )

        # Authenticate the user
        self.client.force_authenticate(user=self.user)

        # Prepare payment data
        data = {
            'amount': 100,  # Integer as per PaymentInitiateSerializer
            'email': 'test@example.com',
            'job_id': self.job.id,
            'extra_data': {'response_id': 1}
        }

        # Send POST request to initiate payment
        response = self.client.post(
            reverse('api_initiate_payment'), data, format='json')

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('authorization_url', response.data)
        self.assertIn('reference', response.data)

        # Check that a Payment object was created
        payment = Payment.objects.get(ref=response.data['reference'])
        self.assertEqual(payment.amount, 100)
        self.assertEqual(payment.email, 'test@example.com')
        self.assertEqual(payment.job, self.job)
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.extra_data, {'response_id': 1})
        self.assertFalse(payment.verified)

    def test_initiate_payment_unauthenticated(self):
        """Test payment initiation fails if user is not authenticated."""
        # Prepare payment data
        data = {
            'amount': 100,
            'email': 'test@example.com',
            'job_id': self.job.id
        }

        # Send POST request without authentication
        response = self.client.post(
            reverse('api_initiate_payment'), data, format='json')

        # Verify unauthorized response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('api.payment.paystack.Paystack')
    def test_initiate_payment_wrong_job(self, MockPaystack):
        """Test payment initiation fails if job does not belong to the user."""
        # Configure the mock instance
        mock_paystack_instance = MockPaystack.return_value
        mock_paystack_instance.initialize_transaction = Mock(
            return_value=(
                True, {'authorization_url': 'https://paystack.com/authorization'})
        )

        # Create another user and profile
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='password123'
        )
        other_profile, _ = Profile.objects.get_or_create(
            user=other_user,
            defaults={'user_type': 'client'}
        )

        # Create a job owned by the other user
        other_job = Job.objects.create(
            client=other_profile,
            title='Other Job',
            category='data_entry',
            description='Other Description',
            price=200.00,
            deadline_date=date.today() + timedelta(days=30),
            status='open',
            max_freelancers=1,
            preferred_freelancer_level='intermediate'
        )

        # Authenticate the original user
        self.client.force_authenticate(user=self.user)

        # Try to initiate payment for the other user's job
        data = {
            'amount': 200,
            'email': 'test@example.com',
            'job_id': other_job.id
        }

        # Send POST request
        response = self.client.post(
            reverse('api_initiate_payment'), data, format='json')

        # Verify 404 response (job not found for this user)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # Ensure initialize_transaction was not called
        mock_paystack_instance.initialize_transaction.assert_not_called()

    @patch('payment.paystack.Paystack.verify_payment')
    def test_payment_callback_success(self, mock_verify):
        """Test successful payment verification callback."""
        # Create a payment instance
        payment = Payment.objects.create(
            user=self.user,
            job=self.job,
            amount=100,
            email='test@example.com',
            ref=uuid.uuid4().hex
        )

        # Mock Paystack's verify_payment response
        mock_verify.return_value = (True, {
            'status': 'success',
            'amount': 10000  # Paystack returns amount in kobo (100 * 100)
        })

        # Simulate callback GET request
        response = self.client.get(
            reverse('api_payment_callback') + f'?reference={payment.ref}',
            follow=False
        )

        # Verify redirect response
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response['Location'],
                         'https://frontend.com/payment/success')

        # Refresh payment from database
        payment.refresh_from_db()
        self.assertTrue(payment.verified)

    @patch('payment.paystack.Paystack.verify_payment')
    def test_payment_callback_invalid_reference(self, mock_verify):
        """Test callback with an invalid payment reference."""
        # Mock Paystack's verify_payment (though it won't be called)
        mock_verify.return_value = (False, 'Verification failed')

        # Simulate callback with an invalid reference
        response = self.client.get(
            reverse('api_payment_callback') + '?reference=invalid_ref',
            follow=False
        )

        # Verify 404 response (get_object_or_404 behavior)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('payment.paystack.Paystack.verify_payment')
    def test_payment_callback_failed_verification(self, mock_verify):
        """Test callback with a failed payment verification."""
        # Create a payment instance
        payment = Payment.objects.create(
            user=self.user,
            job=self.job,
            amount=100,
            email='test@example.com',
            ref=uuid.uuid4().hex
        )

        # Mock Paystack's verify_payment response
        mock_verify.return_value = (False, 'Verification failed')

        # Simulate callback GET request
        response = self.client.get(
            reverse('api_payment_callback') + f'?reference={payment.ref}',
            follow=False
        )

        # Verify redirect response
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response['Location'],
                         'https://frontend.com/payment/failure')

        # Refresh payment from database
        payment.refresh_from_db()
        self.assertFalse(payment.verified)
