from django.urls import path
from .views import ( 
                    JobViewSet, JobCategoryListCreateView,JobCategoryRetrieveUpdateDeleteView,
                    ApplyToJobView,UnapplyFromJobView,JobDiscoveryView,UpdateResponseFilesView,
                    ResponseListForJobView, AcceptFreelancerView, RejectFreelancerView,
                    JobsWithResponsesView,AdvancedJobSearchAPIView,FreelancerJobStatusView,
                    ClientJobStatusView,NotificationSummaryView,JobDashboardSummaryView
                    
)


job_list = JobViewSet.as_view({'get': 'list'})
job_create = JobViewSet.as_view({'post': 'create'})
job_detail = JobViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})
job_matches = JobViewSet.as_view({'get': 'matches'})
job_complete = JobViewSet.as_view({'post': 'mark_completed'})



urlpatterns = [
    
    path('search/', AdvancedJobSearchAPIView.as_view(), name='job-search'),
    
    path('discover/', JobDiscoveryView.as_view(), name='job-discovery-default'),
    
    #status
    path('freelancer/',FreelancerJobStatusView.as_view(), name='freelancer-job-status'),
    path('by-client/',ClientJobStatusView.as_view(), name='client-job-status'),
    
    
    #notification
    path('notifications/summary/', NotificationSummaryView.as_view(), name='notification-summary'),
    
    #dashboard
    path('dashboard/summary/', JobDashboardSummaryView.as_view(), name='dashboard-summary'),
    
    #job categories
    path('categories/', JobCategoryListCreateView.as_view(), name='jobcategory-list-create'),
    path('categories/<slug:slug>/', JobCategoryRetrieveUpdateDeleteView.as_view(), name='jobcategory-detail'),
    
    
    #Job list,detail,create
    path('list/', job_list, name='job-list'),
    path('create/', job_create, name='job-create'),
    path('<slug:slug>/', job_detail, name='job-detail-slug'),
    path('<slug:slug>/', job_matches, name='job-matches'),
    path('<slug:slug>/', job_complete, name='job-complete'),
    
    #apply and unapply
    path('<slug:slug>/apply/', ApplyToJobView.as_view(), name='job-apply'),
    path('<slug:slug>/unapply/', UnapplyFromJobView.as_view(), name='job-unapply'),
    path('<slug:slug>/update-files/', UpdateResponseFilesView.as_view(), name='update-response-files'),

    
    #path('aplications/', JobsWithResponsesView.as_view(), name='job-applications-list'),
    path('<slug:slug>/aplications/', ResponseListForJobView.as_view(), name='job-applications'),
    path('<slug:slug>/accept/<str:identifier>/', AcceptFreelancerView.as_view(), name='accept-freelancer'),
    path('<slug:slug>/reject/<str:identifier>/', RejectFreelancerView.as_view(), name='reject-freelancer'),
    
    path('discover/<str:status_filter>/', JobDiscoveryView.as_view(), name='job-discovery'),
    
    

]
