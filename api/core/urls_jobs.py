from django.urls import path
from .views import JobViewSet, ResponseViewSet

job_list = JobViewSet.as_view({'get': 'list', 'post': 'create'})
job_detail = JobViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})
job_matches = JobViewSet.as_view({'get': 'matches'})
job_complete = JobViewSet.as_view({'post': 'mark_completed'})

response_list = ResponseViewSet.as_view({'get': 'list', 'post': 'create'})
response_detail = ResponseViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})
response_accept = ResponseViewSet.as_view({'patch': 'accept'})
response_reject = ResponseViewSet.as_view({'post': 'reject'})


urlpatterns = [
    path('list/', job_list, name='job-list'),
    path('<slug:slug>/', job_detail, name='job-detail-slug'),
    path('<int:id>/', job_detail, name='job-detail-id'),
    path('<slug:slug>/matches/', job_matches, name='job-matches'),
    path('<slug:slug>/complete/', job_complete, name='job-complete'),

    path('response/', response_list, name='response-list'),
    path('response/<slug:slug>/', response_detail, name='response-detail'),
    path('response/<slug:slug>/accept/', response_accept, name='response-accept'),
    path('response/<slug:slug>/reject/', response_reject, name='response-reject'),
]
