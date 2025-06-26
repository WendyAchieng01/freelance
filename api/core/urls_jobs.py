from django.urls import path
from .views import ( 
                    JobViewSet, ApplyToJobView,UnapplyFromJobView,
                    ResponseListForJobView, AcceptFreelancerView, RejectFreelancerView,
                    JobsWithResponsesView,AdvancedJobSearchAPIView,FreelancerAppliedJobsView,FreelancerActiveJobsView,
                    FreelancerCompletedJobsView,NotificationSummaryView,JobDashboardSummaryView,ClientJobListView
                    
)


job_list = JobViewSet.as_view({'get': 'list'})
job_create = JobViewSet.as_view({'post': 'create'})
job_detail = JobViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})
job_matches = JobViewSet.as_view({'get': 'matches'})
job_complete = JobViewSet.as_view({'post': 'mark_completed'})



urlpatterns = [
    path('list/', job_list, name='job-list'),
    path('create/', job_create, name='job-create'),
    path('<slug:job_slug>/', job_detail, name='job-detail-slug'),
    path('<slug:job_slug>/', job_matches, name='job-matches'),
    path('<slug:job_slug>/', job_complete, name='job-complete'),
    
    path('<slug:job_slug>/apply/', ApplyToJobView.as_view(), name='job-apply'),
    path('<slug:job_slug>/unapply/', UnapplyFromJobView.as_view(), name='job-unapply'),
    
    path('aplications/', JobsWithResponsesView.as_view(), name='job-applications-list'),
    path('<slug:job_slug>/aplications/', ResponseListForJobView.as_view(), name='job-applications'),
    path('<slug:job_slug>/accept/<str:freelancer_username>/', AcceptFreelancerView.as_view(), name='accept-freelancer'),
    path('<slug:job_slug>/reject/<str:freelancer_username>/', RejectFreelancerView.as_view(), name='reject-freelancer'),
    
    path('search/', AdvancedJobSearchAPIView.as_view(), name='job-search'),
    path('applied/', FreelancerAppliedJobsView.as_view(),name='freelancer-applied-jobs'),
    path('active/', FreelancerActiveJobsView.as_view(), name='freelancer-active-jobs'),
    path('completed/', FreelancerCompletedJobsView.as_view(), name='freelancer-completed-jobs'),
    
    path('client/<str:status_filter>/',ClientJobListView.as_view(), name='client-job-filtered'),

    path('notifications/summary/', NotificationSummaryView.as_view(),name='notification-summary'),

    path('dashboard/summary/', JobDashboardSummaryView.as_view(), name='dashboard-summary'),

]
