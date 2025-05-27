from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import User, Profile, FreelancerProfile
from core.models import Job, Response, Chat, Message, MessageAttachment, Review
import json
import os


class APITestBase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        # Create users
        self.client_user = User.objects.create_user(
            username='client', password='testpass')
        self.freelancer_user = User.objects.create_user(
            username='freelancer', password='testpass')
        self.other_user = User.objects.create_user(
            username='other', password='testpass')
        # Create profiles
        self.client_profile = Profile.objects.create(
            user=self.client_user, user_type='client')
        self.freelancer_profile = Profile.objects.create(
            user=self.freelancer_user, user_type='freelancer')
        self.other_profile = Profile.objects.create(
            user=self.other_user, user_type='client')
        FreelancerProfile.objects.create(profile=self.freelancer_profile)
        # Get tokens
        self.client_token = str(RefreshToken.for_user(
            self.client_user).access_token)
        self.freelancer_token = str(RefreshToken.for_user(
            self.freelancer_user).access_token)
        self.other_token = str(RefreshToken.for_user(
            self.other_user).access_token)
        # Create a job
        self.job = Job.objects.create(
            title='Test Job',
            category='web_dev',
            description='Test description',
            price=100.00,
            deadline_date='2025-12-31',
            client=self.client_profile,
            max_freelancers=1,
            preferred_freelancer_level='intermediate'
        )

    def authenticate_client(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.client_token}')

    def authenticate_freelancer(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.freelancer_token}')

    def authenticate_other(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.other_token}')

    def tearDown(self):
        # Clean up files created during tests
        for response in Response.objects.all():
            if response.extra_data and 'sample_work' in response.extra_data:
                file_path = response.extra_data['sample_work'].get('path')
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    os.rmdir(os.path.dirname(file_path))


class JobViewSetTest(APITestBase):
    def test_create_job_as_client(self):
        self.authenticate_client()
        url = reverse('job-list')
        data = {
            'title': 'New Job',
            'category': 'web_dev',
            'description': 'New description',
            'price': 200.00,
            'deadline_date': '2025-12-31',
            'max_freelancers': 2,
            'preferred_freelancer_level': 'expert'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Job.objects.count(), 2)

    def test_create_job_as_freelancer(self):
        self.authenticate_freelancer()
        url = reverse('job-list')
        data = {
            'title': 'New Job',
            'category': 'web_dev',
            'description': 'New description',
            'price': 200.00,
            'deadline_date': '2025-12-31',
            'max_freelancers': 2,
            'preferred_freelancer_level': 'expert'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 403)

    def test_update_job_as_owner(self):
        self.authenticate_client()
        url = reverse('job-detail', kwargs={'pk': self.job.id})
        data = {'title': 'Updated Job'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, 'Updated Job')

    def test_update_job_as_non_owner(self):
        self.authenticate_other()
        url = reverse('job-detail', kwargs={'pk': self.job.id})
        data = {'title': 'Unauthorized Update'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, 403)

    def test_mark_completed_as_owner(self):
        self.job.status = 'in_progress'
        self.job.selected_freelancer = self.freelancer_user
        self.job.save()
        self.authenticate_client()
        url = reverse('job-mark-completed', kwargs={'pk': self.job.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'completed')


class ResponseViewSetTest(APITestBase):
    def test_create_response_as_freelancer(self):
        self.authenticate_freelancer()
        url = reverse('response-list')
        data = {
            'job': self.job.id,
            'extra_data': json.dumps({'message': 'I can do this'})
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)

    def test_create_response_with_file(self):
        self.authenticate_freelancer()
        url = reverse('response-list')
        sample_file = SimpleUploadedFile(
            'sample.txt', b'file_content', content_type='text/plain')
        data = {
            'job': self.job.id,
            'extra_data': json.dumps({'message': 'With file'}),
            'sample_work_file': sample_file
        }
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, 201)
        resp_obj = Response.objects.get(id=response.data['id'])
        self.assertIn('sample_work', resp_obj.extra_data)
        self.assertEqual(
            resp_obj.extra_data['sample_work']['filename'], 'sample.txt')

    def test_create_response_as_client(self):
        self.authenticate_client()
        url = reverse('response-list')
        data = {
            'job': self.job.id,
            'extra_data': json.dumps({'message': 'I am a client'})
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 403)

    def test_accept_response_as_job_owner(self):
        self.authenticate_freelancer()
        url = reverse('response-list')
        data = {
            'job': self.job.id,
            'extra_data': json.dumps({'message': 'Please accept'})
        }
        response = self.client.post(url, data, format='json')
        response_id = response.data['id']

        self.authenticate_client()
        accept_url = reverse('response-accept', kwargs={'pk': response_id})
        accept_response = self.client.patch(accept_url)
        self.assertEqual(accept_response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'in_progress')
        self.assertEqual(self.job.selected_freelancer, self.freelancer_user)
        self.assertTrue(Chat.objects.filter(job=self.job).exists())

    def test_accept_response_as_non_owner(self):
        self.authenticate_freelancer()
        url = reverse('response-list')
        data = {
            'job': self.job.id,
            'extra_data': json.dumps({'message': 'Please accept'})
        }
        response = self.client.post(url, data, format='json')
        response_id = response.data['id']

        self.authenticate_other()
        accept_url = reverse('response-accept', kwargs={'pk': response_id})
        accept_response = self.client.patch(accept_url)
        self.assertEqual(accept_response.status_code, 403)


class ChatViewSetTest(APITestBase):
    def setUp(self):
        super().setUp()
        self.response = Response.objects.create(
            user=self.freelancer_user, job=self.job)
        self.job.selected_freelancer = self.freelancer_user
        self.job.status = 'in_progress'
        self.job.save()
        self.chat = Chat.objects.create(
            job=self.job,
            client=self.client_profile,
            freelancer=self.freelancer_profile
        )

    def test_view_chat_as_participant(self):
        self.authenticate_client()
        url = reverse('chat-detail', kwargs={'pk': self.chat.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_chat_as_non_participant(self):
        self.authenticate_other()
        url = reverse('chat-detail', kwargs={'pk': self.chat.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class MessageViewSetTest(APITestBase):
    def setUp(self):
        super().setUp()
        self.response = Response.objects.create(
            user=self.freelancer_user, job=self.job)
        self.job.selected_freelancer = self.freelancer_user
        self.job.status = 'in_progress'
        self.job.save()
        self.chat = Chat.objects.create(
            job=self.job,
            client=self.client_profile,
            freelancer=self.freelancer_profile
        )

    def test_send_message_as_participant(self):
        self.authenticate_freelancer()
        url = reverse('message-list')
        data = {'chat': self.chat.id, 'content': 'Hello client'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)

    def test_send_message_as_non_participant(self):
        self.authenticate_other()
        url = reverse('message-list')
        data = {'chat': self.chat.id, 'content': 'Unauthorized message'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 403)


class MessageAttachmentViewSetTest(APITestBase):
    def setUp(self):
        super().setUp()
        self.response = Response.objects.create(
            user=self.freelancer_user, job=self.job)
        self.job.selected_freelancer = self.freelancer_user
        self.job.status = 'in_progress'
        self.job.save()
        self.chat = Chat.objects.create(
            job=self.job,
            client=self.client_profile,
            freelancer=self.freelancer_profile
        )
        self.message = Message.objects.create(
            chat=self.chat,
            sender=self.freelancer_user,
            content='Test message'
        )

    def test_upload_attachment_as_participant(self):
        self.authenticate_freelancer()
        url = reverse('attachment-list')
        file = SimpleUploadedFile(
            'test.pdf', b'file_content', content_type='application/pdf')
        data = {'message': self.message.id, 'file': file}
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, 201)

    def test_download_attachment_as_participant(self):
        attachment = MessageAttachment.objects.create(
            message=self.message,
            file=SimpleUploadedFile(
                'test.pdf', b'file_content', content_type='application/pdf'),
            filename='test.pdf',
            file_size=12,
            content_type='application/pdf'
        )
        self.authenticate_client()
        url = reverse('attachment-download', kwargs={'pk': attachment.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'],
                         'attachment; filename="test.pdf"')

    def test_download_attachment_as_non_participant(self):
        attachment = MessageAttachment.objects.create(
            message=self.message,
            file=SimpleUploadedFile(
                'test.pdf', b'file_content', content_type='application/pdf'),
            filename='test.pdf',
            file_size=12,
            content_type='application/pdf'
        )
        self.authenticate_other()
        url = reverse('attachment-download', kwargs={'pk': attachment.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class ReviewViewSetTest(APITestBase):
    def test_create_review_after_job_completion(self):
        self.job.status = 'completed'
        self.job.selected_freelancer = self.freelancer_user
        self.job.save()
        self.authenticate_client()
        url = reverse('review-list')
        data = {
            'recipient': self.freelancer_user.id,
            'rating': 5,
            'comment': 'Great work!'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)

    def test_create_review_without_job_completion(self):
        self.authenticate_client()
        url = reverse('review-list')
        data = {
            'recipient': self.freelancer_user.id,
            'rating': 5,
            'comment': 'Great work!'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 403)


class FreelancerRecommendationsViewTest(APITestBase):
    def test_get_recommendations_as_freelancer(self):
        self.authenticate_freelancer()
        url = reverse('recommendations')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_get_recommendations_as_client(self):
        self.authenticate_client()
        url = reverse('recommendations')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
