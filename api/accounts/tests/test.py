from rest_framework.test import APITestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from accounts.models import Profile, FreelancerProfile, ClientProfile, Skill, Language
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator

User = get_user_model()


class AccountsAPITest(APITestCase):
    def setUp(self):
        self.base_url = '/api/v1/accounts/'
        self.users = [
            {
                'username': f'user{i}',
                'email': f'user{i}@example.com',
                'password1': 'testpass123',
                'password2': 'testpass123',
                'user_type': 'freelancer'
            } for i in range(1, 6)
        ]
        self.created_users = []
        # Create sample skills and languages for freelancer/client forms
        self.skill1 = Skill.objects.create(name='Python')
        self.skill2 = Skill.objects.create(name='Django')
        self.language1 = Language.objects.create(name='English')
        self.language2 = Language.objects.create(name='Swahili')

    def test_register_users(self):
        """Test registering 5 users."""
        for user_data in self.users:
            response = self.client.post(
                f'{self.base_url}auth/register/',
                {
                    'username': user_data['username'],
                    'email': user_data['email'],
                    'password1': user_data['password1'],
                    'password2': user_data['password2'],
                    'user_type': user_data['user_type']
                },
                format='json'
            )
            self.assertEqual(response.status_code, 201,
                             f"Failed to register {user_data['username']}: {response.data}")
            self.assertEqual(
                response.data['message'], "User created, verification email sent.")
            self.created_users.append(
                User.objects.get(username=user_data['username']))

    def test_verify_email(self):
        """Test email verification for 5 users."""
        self.test_register_users()
        for user in self.created_users:
            token = default_token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            response = self.client.get(
                f'{self.base_url}verify-email/{uidb64}/{token}/'
            )
            self.assertEqual(response.status_code, 200,
                             f"Email verification failed for {user.username}: {response.data}")
            user.refresh_from_db()
            self.assertTrue(user.is_active, f"{user.username} not activated")
            self.assertIn('access', response.data,
                          f"No access token for {user.username}")

    def test_resend_verification(self):
        """Test resending verification email for 5 users."""
        self.test_register_users()
        mail.outbox.clear()  # Clear emails from registration
        for user in self.created_users:
            response = self.client.post(
                f'{self.base_url}auth/resend-verification/{user.id}/'
            )
            self.assertEqual(response.status_code, 200,
                             f"Resend verification failed for {user.username}: {response.data}")
            self.assertEqual(len(mail.outbox), 1,
                             f"No email sent for {user.username}")
            self.assertIn(
                user.email, mail.outbox[0].to, f"Email not sent to {user.email}")
            self.assertIn(
                'Verify Your Email', mail.outbox[0].subject, f"Incorrect email subject for {user.username}")
            mail.outbox.clear()

    def test_login_users(self):
        """Test logging in with 5 users."""
        self.test_register_users()
        for user, user_data in zip(self.created_users, self.users):
            user.is_active = True  # Simulate email verification
            user.save()
            response = self.client.post(
                f'{self.base_url}auth/login/',
                {'identifier': user_data['email'],
                    'password': user_data['password1']},
                format='json'
            )
            self.assertEqual(response.status_code, 200,
                             f"Login failed for {user.username}: {response.data}")
            self.assertIn('access', response.data,
                          f"No access token for {user.username}")
            self.assertIn('refresh', response.data,
                          f"No refresh token for {user.username}")
            self.assertEqual(
                response.data['user_type'], 'freelancer', f"Wrong user_type for {user.username}")

    def test_logout_users(self):
        """Test logging out with 5 users."""
        self.test_register_users()
        for user, user_data in zip(self.created_users, self.users):
            user.is_active = True
            user.save()
            login_response = self.client.post(
                f'{self.base_url}auth/login/',
                {'identifier': user_data['email'],
                    'password': user_data['password1']},
                format='json'
            )
            refresh_token = login_response.data['refresh']
            self.client.credentials(
                HTTP_AUTHORIZATION=f'Bearer {login_response.data["access"]}')
            response = self.client.post(
                f'{self.base_url}auth/logout/',
                {'refresh': refresh_token},
                format='json'
            )
            self.assertEqual(response.status_code, 205,
                             f"Logout failed for {user.username}: {response.data}")

    def test_password_change(self):
        """Test password change for 5 users."""
        self.test_register_users()
        for user, user_data in zip(self.created_users, self.users):
            user.is_active = True
            user.save()
            login_response = self.client.post(
                f'{self.base_url}auth/login/',
                {'identifier': user_data['email'],
                    'password': user_data['password1']},
                format='json'
            )
            token = login_response.data['access']
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            response = self.client.post(
                f'{self.base_url}auth/password-change/',
                {'new_password1': 'newpass123', 'new_password2': 'newpass123'},
                format='json'
            )
            self.assertEqual(response.status_code, 200,
                             f"Password change failed for {user.username}: {response.data}")

    def test_password_reset(self):
        """Test password reset request and confirmation for 5 users."""
        self.test_register_users()
        mail.outbox.clear()  # Clear emails from registration
        for user in self.created_users:
            user.is_active = True
            user.save()
            response = self.client.post(
                f'{self.base_url}auth/password-reset/',
                {'email': user.email},
                format='json'
            )
            self.assertEqual(response.status_code, 200,
                             f"Password reset request failed for {user.username}: {response.data}")
            self.assertEqual(len(mail.outbox), 1,
                             f"No email sent for {user.username}")
            token = default_token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            response = self.client.post(
                f'{self.base_url}auth/password-reset-confirm/{uidb64}/{token}/',
                {'new_password': 'resetpass123'},
                format='json'
            )
            self.assertEqual(response.status_code, 200,
                             f"Password reset confirmation failed for {user.username}: {response.data}")
            mail.outbox.clear()

    def test_freelancer_form(self):
        """Test freelancer form submission for 5 users."""
        self.test_register_users()
        for user in self.created_users:
            user.is_active = True
            user.save()
            # Use get_or_create to avoid duplicate Profile
            profile, created = Profile.objects.get_or_create(
                user=user, defaults={'user_type': 'freelancer'})
            if not created and profile.user_type != 'freelancer':
                profile.user_type = 'freelancer'
                profile.save()
            login_response = self.client.post(
                f'{self.base_url}auth/login/',
                {'identifier': user.email, 'password': 'testpass123'},
                format='json'
            )
            token = login_response.data['access']
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            response = self.client.post(
                f'{self.base_url}freelancer-form/',
                {
                    'name': user.username,
                    'email': user.email,
                    'phone_number': '+1234567890',
                    'experience_years': 3,
                    'hourly_rate': 50.00,
                    'languages': [self.language1.id, self.language2.id],
                    'pay_id_no': '123456',
                    'skills': [self.skill1.id, self.skill2.id],
                    'portfolio_link': 'https://example.com/portfolio',
                    'availability': 'full_time'
                },
                format='json'
            )
            self.assertEqual(response.status_code, 200,
                             f"Freelancer form failed for {user.username}: {response.data}")

    def test_client_form(self):
        """Test client form submission for 5 users."""
        self.test_register_users()
        for user in self.created_users:
            user.is_active = True
            user.save()
            # Use get_or_create to avoid duplicate Profile
            profile, created = Profile.objects.get_or_create(
                user=user, defaults={'user_type': 'client'})
            if not created and profile.user_type != 'client':
                profile.user_type = 'client'
                profile.save()
            login_response = self.client.post(
                f'{self.base_url}auth/login/',
                {'identifier': user.email, 'password': 'testpass123'},
                format='json'
            )
            token = login_response.data['access']
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            response = self.client.post(
                f'{self.base_url}client-form/',
                {
                    'company_name': f'{user.username} Corp',
                    'email': user.email,
                    'phone_number': '+1234567890',
                    'industry': 'technology',  
                    'languages': [self.language1.id, self.language2.id],
                    'pay_id_no': '123456',
                    'company_website': 'https://example.com',
                    'project_budget': 5000.00,
                    'preferred_freelancer_level': 'intermediate'
                },
                format='json'
            )
            self.assertEqual(response.status_code, 200,
                             f"Client form failed for {user.username}: {response.data}")
