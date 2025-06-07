from django.urls import path
from .views import JobViewSet, ApplyToJobView,UnapplyFromJobView,ResponseListForJobView, AcceptFreelancerView, RejectFreelancerView,JobsWithResponsesView


job_list = JobViewSet.as_view({'get': 'list', 'post': 'create'})
job_detail = JobViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})
job_matches = JobViewSet.as_view({'get': 'matches'})
job_complete = JobViewSet.as_view({'post': 'mark_completed'})



urlpatterns = [
    path('list/', job_list, name='job-list'),
    path('<slug:slug>/', job_detail, name='job-detail-slug'),
    #path('<int:id>/', job_detail, name='job-detail-id'),
    path('<slug:slug>/', job_matches, name='job-matches'),
    path('<slug:slug>/', job_complete, name='job-complete'),
    
    path('<slug:slug>/apply/', ApplyToJobView.as_view(), name='job-apply'),
    path('<slug:slug>/unapply/', UnapplyFromJobView.as_view(), name='job-unapply'),
    
    path('aplications/', JobsWithResponsesView.as_view(), name='job-applications-list'),
    path('<slug:slug>/aplications/', ResponseListForJobView.as_view(), name='job-applications'),
    path('<slug:slug>/accept/<str:identifier>/', AcceptFreelancerView.as_view(), name='accept-freelancer'),
    path('<slug:slug>/reject/<str:identifier>/', RejectFreelancerView.as_view(), name='reject-freelancer'),



]
