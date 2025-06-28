from django.urls import path
from .views import ( 
                    JobViewSet, ApplyToJobView,UnapplyFromJobView,
                    ResponseListForJobView, AcceptFreelancerView, RejectFreelancerView,
                    JobsWithResponsesView,AdvancedJobSearchAPIView,FreelancerJobStatusView,ClientJobStatusView,NotificationSummaryView,JobDashboardSummaryView,ClientJobListView
                    
)


job_list = JobViewSet.as_view({'get': 'list'})
job_create = JobViewSet.as_view({'post': 'create'})
job_detail = JobViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})
job_matches = JobViewSet.as_view({'get': 'matches'})
job_complete = JobViewSet.as_view({'post': 'mark_completed'})



urlpatterns = [
    
    #path('search/', AdvancedJobSearchAPIView.as_view(), name='job-search'),
    path('freelancer/<str:status_filter>/',FreelancerJobStatusView.as_view(), name='freelancer-job-status'),
    path('client/<str:status_filter>/',ClientJobStatusView.as_view(), name='client-job-status'),

    #path('client/<str:status_filter>/', ClientJobListView.as_view(), name='client-job-filtered'),

    path('notifications/summary/', NotificationSummaryView.as_view(), name='notification-summary'),

    path('dashboard/summary/', JobDashboardSummaryView.as_view(), name='dashboard-summary'),
    path('list/', job_list, name='job-list'),
    path('create/', job_create, name='job-create'),
    path('<slug:slug>/', job_detail, name='job-detail-slug'),
    path('<slug:slug>/', job_matches, name='job-matches'),
    path('<slug:slug>/', job_complete, name='job-complete'),
    
    path('<slug:slug>/apply/', ApplyToJobView.as_view(), name='job-apply'),
    path('<slug:slug>/unapply/', UnapplyFromJobView.as_view(), name='job-unapply'),
    
    #path('aplications/', JobsWithResponsesView.as_view(), name='job-applications-list'),
    path('<slug:slug>/aplications/', ResponseListForJobView.as_view(), name='job-applications'),
    path('<slug:slug>/accept/<str:freelancer_username>/', AcceptFreelancerView.as_view(), name='accept-freelancer'),
    path('<slug:slug>/reject/<str:freelancer_username>/', RejectFreelancerView.as_view(), name='reject-freelancer'),
    
    

]
