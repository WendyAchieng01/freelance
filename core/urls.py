from django.urls import path

from . import views


app_name = 'core' 

urlpatterns = [
    path('index/', views.freelancer_index, name='index'),
    path("jobs/", views.jobs, name="jobs"),
    path("job/<int:job_id>/", views.singlejob, name="singlejob"),
    path("job/", views.freelancer_jobs, name = "freelancer_jobs"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path('client/', views.client_index, name='client_index'),
    path("create_job/", views.create_job, name="create_job"),
    path('jobs/<int:job_id>/edit/', views.edit_job, name='edit_job'),
    path('client/responses/', views.client_responses, name='client_responses'),
    path('client/about/', views.client_about, name='client_about'),
    path('client/contact/', views.client_contact, name='client_contact'),
    path('client/posted_jobs/', views.client_posted_jobs, name='client_posted_jobs'),
    path("job_responses/<int:job_id>/", views.job_responses, name="job_responses"),
    path('delete-job/<int:job_id>/', views.delete_job, name='delete_job'),
    path('accept_response/<int:job_id>/<int:response_id>/', views.accept_response, name='accept_response'),
    path('reject_response/<int:job_id>/<int:response_id>/', views.reject_response, name='reject_response'),    path('my-chats/', views.my_chats, name='my_chats'),
    path('chat/<int:chat_id>/', views.chat_room, name='chat_room'),
    path('attachment/<int:attachment_id>/download/', views.download_attachment, name='download_attachment'),
    path('mark-job-completed/<int:job_id>/', views.mark_job_completed, name='mark_job_completed'),
    path('job/<int:job_id>/matches/', views.job_matches, name='job_matches'),
    path('responses/<int:response_id>/download/<str:filename>/', views.download_response_file, name='download_response_file'),
    path('user/<str:username>/reviews/', views.user_reviews, name='user_reviews'),
    path('user/<str:username>/review/', views.create_review, name='create_review'),
    path('review/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    path("index1/", views.index_gen, name="index1"),
    path("about1/", views.about_gen, name="about1"),
    path("contact1/", views.contact_gen, name="contact1"),
    
    path("", views.index_gen, name="index1"),
]