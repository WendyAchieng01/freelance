from rest_framework.test import APITestCase, APIClient
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from accounts.models import Profile
from core.models import Job
from academy.models import Training
from decimal import Decimal
from datetime import date, timedelta

User = get_user_model()


class TrainingAPITests(APITestCase):
    def create_verified_user(self, username, email, password, user_type):
        """
        Helper method to create a user, simulate email verification, and return the user and JWT token.
        
        Args:
            username (str): The username for the new user.
            email (str): The email address for the new user.
            password (str): The password for the new user.
            user_type (str): The type of user ('client' or 'freelancer').
        
        Returns:
            tuple: (User instance, access token)
        """
        # Register user
        register_data = {
            'username': username,
            'email': email,
            'password1': password,
            'password2': password,
            'user_type': user_type
        }
        response = self.client.post(reverse('register'), register_data)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username=username)
        # User should be inactive until verified
        self.assertFalse(user.is_active)

        # Generate verification token and uid
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Simulate email verification
        verify_url = reverse(
            'verify-email', kwargs={'uidb64': uid, 'token': token})
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)  # User should now be active

        # Extract access token from verification response
        access_token = response.data['access']
        return user, access_token

    def setUp(self):
        """
        Set up test data: users, profiles, jobs, and trainings.
        Creates two verified users, their profiles, jobs with all required fields, and initial trainings.
        """
        self.client = APIClient()

        # Create two verified users: a client and a freelancer
        self.user1, self.token1 = self.create_verified_user(
            'client1', 'client1@example.com', 'pass123', 'client'
        )
        self.user2, self.token2 = self.create_verified_user(
            'freelancer1', 'freelancer1@example.com', 'pass123', 'freelancer'
        )

        # Retrieve profiles (created automatically during registration)
        self.profile1 = Profile.objects.get(user=self.user1)
        self.profile2 = Profile.objects.get(user=self.user2)

        # Create jobs with all required fields
        self.job1 = Job.objects.create(
            client=self.profile1,
            title='Job 1',
            category='data_entry',
            description='Test job 1 description',
            price=Decimal('100.00'),
            deadline_date=date.today() + timedelta(days=30)
        )
        self.job2 = Job.objects.create(
            client=self.profile2,
            title='Job 2',
            category='translation',
            description='Test job 2 description',
            price=Decimal('200.00'),
            deadline_date=date.today() + timedelta(days=60)
        )

        # Create initial trainings for each user with all required fields
        self.training1 = Training.objects.create(
            client=self.user1,
            job=self.job1,
            title='Training 1',
            texts='Training 1 texts'
        )
        self.training2 = Training.objects.create(
            client=self.user2,
            job=self.job2,
            title='Training 2',
            texts='Training 2 texts'
        )

    def test_unauthenticated_user_cannot_access(self):
        """Test that unauthenticated users cannot access the training list endpoint."""
        url = reverse('training-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_user_can_list_own_trainings(self):
        """Test that an authenticated user can list only their own trainings."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        url = reverse('training-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Handle paginated response
        if 'results' in response.data:
            trainings = response.data['results']
        else:
            trainings = response.data

        # Only user1's training should be returned
        self.assertEqual(len(trainings), 1)
        self.assertEqual(trainings[0]['title'], 'Training 1')

    def test_user_can_create_training_with_own_job(self):
        """Test that a user can create a training with their own job."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        url = reverse('training-list')
        data = {
            'job': self.job1.id,
            'title': 'New Training',
            'texts': 'New training texts'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Training.objects.filter(client=self.user1).count(), 2)
        new_training = Training.objects.get(title='New Training')
        self.assertEqual(new_training.client, self.user1)

    def test_user_cannot_create_training_with_others_job(self):
        """Test that a user cannot create a training with another user's job."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        url = reverse('training-list')
        data = {
            'job': self.job2.id,
            'title': 'Invalid Training',
            'texts': 'Invalid training texts'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)  # Validation error
        # Error should relate to the job field
        self.assertIn('job', response.data)

    def test_user_can_retrieve_own_training(self):
        """Test that a user can retrieve their own training."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        url = reverse('training-detail', kwargs={'pk': self.training1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Training 1')

    def test_user_cannot_retrieve_others_training(self):
        """Test that a user cannot retrieve another user's training."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        url = reverse('training-detail', kwargs={'pk': self.training2.id})
        response = self.client.get(url)
        # Not found due to queryset filtering
        self.assertEqual(response.status_code, 404)

    def test_user_can_update_own_training(self):
        """Test that a user can update their own training."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        url = reverse('training-detail', kwargs={'pk': self.training1.id})
        data = {'title': 'Updated Training'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.training1.refresh_from_db()
        self.assertEqual(self.training1.title, 'Updated Training')

    def test_user_cannot_update_others_training(self):
        """Test that a user cannot update another user's training."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        url = reverse('training-detail', kwargs={'pk': self.training2.id})
        data = {'title': 'Trying to Update'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, 404)

    def test_user_can_delete_own_training(self):
        """Test that a user can delete their own training."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        url = reverse('training-detail', kwargs={'pk': self.training1.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Training.objects.filter(
            id=self.training1.id).exists())

    def test_user_cannot_delete_others_training(self):
        """Test that a user cannot delete another user's training."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        url = reverse('training-detail', kwargs={'pk': self.training2.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 404)
