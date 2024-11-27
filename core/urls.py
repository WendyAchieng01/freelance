from django.urls import path

from . import views


app_name = 'core' 

urlpatterns = [
    path('', views.freelancer_index, name='index'),
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
    path('mark_response_as_done/', views.mark_response_as_done, name='mark_response_as_done'),
    path('delete-job/<int:job_id>/', views.delete_job, name='delete_job'),
]