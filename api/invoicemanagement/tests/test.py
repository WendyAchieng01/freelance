from django.test import TransactionTestCase
from rest_framework.test import APIClient
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from invoicemgmt.models import Invoice, InvoiceLineItem
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.management import call_command
import io
from PyPDF2 import PdfReader
from unittest.mock import patch
from rest_framework import status

User = get_user_model()

class InvoiceAPITests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api_client = APIClient()

    def create_verified_user(self, username, email, password, user_type, is_staff=False):
        """
        Helper method to create a user, simulate email verification, and return the user and JWT token.
        """
        # Register user
        register_data = {
            'username': username,
            'email': email,
            'password1': password,
            'password2': password,
            'user_type': user_type
        }
        print(f"Register request data: {register_data}")
        # Clear any existing credentials to ensure no auth headers
        self.api_client.credentials()
        # Use explicit URL to avoid reverse issues
        response = self.api_client.post('/api/v1/accounts/auth/register/', register_data, format='json')
        print(f"Register response: {response.status_code}, {response.data}")
        print(f"Register response headers: {response.headers}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED,
                         f"Registration failed: {response.data}")
        user = User.objects.get(username=username)
        user.is_staff = is_staff
        user.save()
        self.assertFalse(user.is_active)  # User should be inactive until verified

        # Generate verification token and uid
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Simulate email verification
        verify_url = f'/api/v1/accounts/auth/verify-email/{uid}/{token}/'
        response = self.api_client.get(verify_url)
        print(f"Verify email response: {response.status_code}, {response.data}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_active)  # User should now be active

        # Extract access token
        access_token = response.data.get('access')
        self.assertIsNotNone(access_token, "No access token returned from verify-email")
        return user, access_token

    def setUp(self):
        """
        Set up test data: users, tokens, invoices, and line items.
        """
        # Explicitly flush the database to reset id sequences
        call_command('flush', verbosity=0, interactive=False)

        # Create unique users with tokens, inspired by client1 (ID 19)
        self.staff_user, self.staff_token = self.create_verified_user(
            f'client1_test_{self.id()}', f'client1_test_{self.id()}@example.com', 'Pass123!', 'client', is_staff=True
        )
        self.user, self.user_token = self.create_verified_user(
            f'user_test_{self.id()}', f'user_test_{self.id()}@example.com', 'Pass123!', 'client', is_staff=False
        )

        # Create sample invoices with line items
        self.invoice1 = Invoice.objects.create(
            client=self.staff_user,
            invoice_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            status='draft',
            notes='Test invoice 1'
        )
        InvoiceLineItem.objects.create(
            invoice=self.invoice1,
            description='Service 1',
            quantity=2,
            rate=Decimal('50.00')
        )

        self.invoice2 = Invoice.objects.create(
            client=self.user,
            invoice_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=15),
            status='sent',
            notes='Test invoice 2'
        )
        InvoiceLineItem.objects.create(
            invoice=self.invoice2,
            description='Service 2',
            quantity=1,
            rate=Decimal('100.00')
        )

    def test_unauthenticated_user_cannot_access_list_create(self):
        """Test that unauthenticated users cannot access the invoice list endpoint."""
        url = reverse('invoice-list-create')
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_non_staff_user_cannot_access_list_create(self):
        """Test that non-staff users cannot access the invoice list endpoint."""
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        url = reverse('invoice-list-create')
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_staff_user_can_list_invoices(self):
        """Test that a staff user can list all invoices."""
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.staff_token}')
        url = reverse('invoice-list-create')
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 200)
        if 'results' in response.data:  # Handle pagination
            invoices = response.data['results']
        else:
            invoices = response.data
        self.assertEqual(len(invoices), 2)  # Should return both invoices
        self.assertEqual(invoices[0]['notes'], 'Test invoice 1')

    def test_staff_user_can_create_invoice(self):
        """Test that a staff user can create an invoice with line items."""
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.staff_token}')
        url = reverse('invoice-list-create')
        data = {
            'client': self.staff_user.id,
            'invoice_date': timezone.now().date().isoformat(),
            'due_date': (timezone.now().date() + timedelta(days=30)).isoformat(),
            'status': 'draft',
            'notes': 'New invoice',
            'line_items': [
                {'description': 'Service 3', 'quantity': 3, 'rate': '25.00'},
                {'description': 'Service 4', 'quantity': 1, 'rate': '75.00'}
            ]
        }
        response = self.api_client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        invoice = Invoice.objects.get(notes='New invoice')
        self.assertEqual(invoice.line_items.count(), 2)
        self.assertEqual(invoice.line_items.first().description, 'Service 3')

    def test_unauthenticated_user_cannot_access_detail(self):
        """Test that unauthenticated users cannot access the invoice detail endpoint."""
        url = reverse('invoice-detail', kwargs={'pk': self.invoice1.id})
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_non_staff_user_cannot_access_detail(self):
        """Test that non-staff users cannot access the invoice detail endpoint."""
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        url = reverse('invoice-detail', kwargs={'pk': self.invoice1.id})
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_staff_user_can_retrieve_invoice(self):
        """Test that a staff user can retrieve an invoice."""
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.staff_token}')
        url = reverse('invoice-detail', kwargs={'pk': self.invoice1.id})
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['notes'], 'Test invoice 1')
        self.assertEqual(len(response.data['line_items']), 1)

    def test_staff_user_can_update_invoice(self):
        """Test that a staff user can update an invoice and its line items."""
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.staff_token}')
        url = reverse('invoice-detail', kwargs={'pk': self.invoice1.id})
        data = {
            'client': self.staff_user.id,
            'invoice_date': timezone.now().date().isoformat(),
            'due_date': (timezone.now().date() + timedelta(days=45)).isoformat(),
            'status': 'sent',
            'notes': 'Updated invoice',
            'line_items': [
                {'description': 'Updated Service', 'quantity': 4, 'rate': '30.00'}
            ]
        }
        response = self.api_client.put(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.invoice1.refresh_from_db()
        self.assertEqual(self.invoice1.notes, 'Updated invoice')
        self.assertEqual(self.invoice1.line_items.count(), 1)
        self.assertEqual(self.invoice1.line_items.first().description, 'Updated Service')

    def test_staff_user_can_delete_invoice(self):
        """Test that a staff user can delete an invoice."""
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.staff_token}')
        url = reverse('invoice-detail', kwargs={'pk': self.invoice1.id})
        response = self.api_client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Invoice.objects.filter(id=self.invoice1.id).exists())

    def test_unauthenticated_user_cannot_access_pdf(self):
        """Test that unauthenticated users cannot access the invoice PDF endpoint."""
        url = reverse('invoice-pdf', kwargs={'invoice_id': self.invoice1.id})
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_non_staff_user_cannot_access_pdf(self):
        """Test that non-staff users cannot access the invoice PDF endpoint."""
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        url = reverse('invoice-pdf', kwargs={'invoice_id': self.invoice1.id})
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_staff_user_can_generate_pdf(self):
        """Test that a staff user can generate an invoice PDF."""
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.staff_token}')
        url = reverse('invoice-pdf', kwargs={'invoice_id': self.invoice1.id})
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(f'invoice_{self.invoice1.invoice_number}.pdf', response['Content-Disposition'])
        pdf_reader = PdfReader(io.BytesIO(response.content))
        self.assertGreater(len(pdf_reader.pages), 0)