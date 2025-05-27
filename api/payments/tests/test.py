from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounts.models import Profile
from core.models import Job, Response as CoreResponse, Chat, JobAssignment
from payments.models import PaypalPayments
from paypal.standard.ipn.models import PayPalIPN
from paypal.standard.models import ST_PP_COMPLETED
# Import for manual trigger
from paypal.standard.ipn.signals import valid_ipn_received

User = get_user_model()


class PaymentsAPITest(APITestCase):
    def setUp(self):
        """Set up test data: users, profiles, job, response, and job assignment."""
        # Create client and freelancer users
        self.client_user = User.objects.create_user(
            username='client',
            password='password',
            email='client@example.com',
            is_active=True
        )
        self.freelancer_user = User.objects.create_user(
            username='freelancer',
            password='password',
            email='freelancer@example.com',
            is_active=True
        )

        # Create or get profiles
        self.client_profile, created = Profile.objects.get_or_create(
            user=self.client_user,
            defaults={'user_type': 'client'}
        )
        if not created:
            self.client_profile.user_type = 'client'
            self.client_profile.save()

        self.freelancer_profile, created = Profile.objects.get_or_create(
            user=self.freelancer_user,
            defaults={'user_type': 'freelancer'}
        )
        if not created:
            self.freelancer_profile.user_type = 'freelancer'
            self.freelancer_profile.save()

        # Create a job
        self.job = Job.objects.create(
            title='Test Job',
            category='data_entry',
            description='Test description',
            price=100.00,
            deadline_date='2024-12-31',
            client=self.client_profile,
            max_freelancers=1,
            preferred_freelancer_level='intermediate'
        )

        # Create a response to the job
        self.response = CoreResponse.objects.create(
            job=self.job,
            user=self.freelancer_user
        )

        # Create a job assignment
        self.job_assignment = JobAssignment.objects.create(
            job=self.job,
            freelancer=self.freelancer_profile,
            status='pending'
        )

    def test_initiate_payment_not_client(self):
        """Test that a non-client user cannot initiate a payment."""
        client = APIClient()
        client.force_authenticate(user=self.freelancer_user)
        url = reverse('initiate_payment')
        data = {
            'job_id': self.job.id,
            'response_id': self.response.id
        }
        response = client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_initiate_payment_as_client(self):
        """Test that the job client can initiate a payment successfully."""
        client = APIClient()
        client.force_authenticate(user=self.client_user)
        url = reverse('initiate_payment')
        data = {
            'job_id': self.job.id,
            'response_id': self.response.id
        }
        response = client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('payment_id', response.data)
        self.assertIn('paypal_form', response.data)

        # Verify payment creation
        payment = PaypalPayments.objects.get(id=response.data['payment_id'])
        self.assertEqual(payment.job, self.job)
        self.assertEqual(
            payment.invoice, f"response-{self.job.id}-{self.response.id}")
        self.assertEqual(payment.amount, self.job.price)
        self.assertEqual(payment.user, self.client_user)
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(
            payment.extra_data['response_id'], str(self.response.id))

    def test_initiate_payment_already_processed(self):
        """Test that initiating a payment for an already processed payment fails."""
        payment = self._create_payment()
        payment.status = 'completed'
        payment.save()

        client = APIClient()
        client.force_authenticate(user=self.client_user)
        url = reverse('initiate_payment')
        data = {
            'job_id': self.job.id,
            'response_id': self.response.id
        }
        response = client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], "Payment already processed.")

    def test_initiate_payment_invalid_job(self):
        """Test initiating payment with an invalid job ID."""
        client = APIClient()
        client.force_authenticate(user=self.client_user)
        url = reverse('initiate_payment')
        data = {
            'job_id': 9999,  # Non-existent job
            'response_id': self.response.id
        }
        response = client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('job_id', response.data)

    def test_initiate_payment_response_not_for_job(self):
        """Test initiating payment with a response not associated with the job."""
        another_job = Job.objects.create(
            title='Another Job',
            category='translation',
            description='Another description',
            price=200.00,
            deadline_date='2024-12-31',
            client=self.client_profile
        )
        another_response = CoreResponse.objects.create(
            job=another_job,
            user=self.freelancer_user
        )
        client = APIClient()
        client.force_authenticate(user=self.client_user)
        url = reverse('initiate_payment')
        data = {
            'job_id': self.job.id,
            'response_id': another_response.id
        }
        response = client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('response_id', response.data)

    def test_invalid_invoice(self):
        """Test that an IPN with an invalid invoice format does not affect payments."""
        ipn_obj = PayPalIPN(
            payment_status=ST_PP_COMPLETED,
            invoice='invalid-invoice',
            payer_email=self.client_user.email,
            txn_id='TEST_INVALID',
            payment_date='2025-05-25T12:00:00Z',
            flag=False,
            ipaddress='127.0.0.1'
        )
        ipn_obj.save()

        payments = PaypalPayments.objects.filter(status='completed')
        self.assertEqual(payments.count(), 0)

    def test_payment_failed(self):
        """Test that a failed IPN updates the payment status to 'failed'."""
        payment = self._create_payment()
        ipn_obj = PayPalIPN(
            payment_status='Failed',
            invoice=payment.invoice,
            payer_email=self.client_user.email,
            custom=str(self.response.id),
            txn_id=f'TEST_{payment.id}',
            payment_date='2025-05-25T12:00:00Z',
            flag=False,
            ipaddress='127.0.0.1',
            mc_gross=str(payment.amount),
            mc_currency='USD'
        )
        ipn_obj.save()
        valid_ipn_received.send(sender=ipn_obj)  # Manually trigger the signal

        payment.refresh_from_db()
        self.assertEqual(payment.status, 'failed')

    def test_payment_status_not_owner(self):
        """Test that a user cannot view another user's payment status."""
        payment = self._create_payment()
        client = APIClient()
        client.force_authenticate(user=self.freelancer_user)
        url = reverse('payment_status', kwargs={'payment_id': payment.id})
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_payment_status_as_owner(self):
        """Test that the payment owner can view the payment status."""
        payment = self._create_payment()
        client = APIClient()
        client.force_authenticate(user=self.client_user)
        url = reverse('payment_status', kwargs={'payment_id': payment.id})
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], payment.id)
        self.assertEqual(response.data['status'], 'pending')

    def test_payment_successful(self):
        """Test that a successful IPN updates payment and job status."""
        payment = self._create_payment()
        ipn_obj = PayPalIPN(
            payment_status=ST_PP_COMPLETED,
            invoice=payment.invoice,
            payer_email=self.client_user.email,
            custom=str(self.response.id),
            txn_id=f'TEST_{payment.id}',
            payment_date='2025-05-25T12:00:00Z',
            flag=False,
            ipaddress='127.0.0.1',
            mc_gross=str(payment.amount),
            mc_currency='USD'
        )
        ipn_obj.save()
        valid_ipn_received.send(sender=ipn_obj)  # Manually trigger the signal

        payment.refresh_from_db()
        self.job.refresh_from_db()

        self.assertEqual(payment.status, 'completed')
        self.assertTrue(payment.verified)
        self.assertEqual(self.job.status, 'in_progress')
        self.assertEqual(self.job.selected_freelancer, self.response.user)

        chat = Chat.objects.get(job=self.job)
        self.assertEqual(chat.client, self.job.client)
        self.assertEqual(chat.freelancer, self.response.user.profile)

    def _create_payment(self):
        """Helper method to create a payment with a job assignment."""
        payment = PaypalPayments.objects.create(
            job=self.job,
            invoice=f"response-{self.job.id}-{self.response.id}",
            amount=self.job.price,
            user=self.client_user,
            email=self.client_user.email,
            status='pending',
            extra_data={'response_id': str(self.response.id)}
        )
        return payment
