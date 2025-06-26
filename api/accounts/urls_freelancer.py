from django.urls import path, include
from.views import FreelancerReadOnlyViewSet, FreelancerWriteViewSet,ListFreelancersView

# View mappings
freelancer_read = FreelancerReadOnlyViewSet.as_view({
    'get': 'retrieve',
})

freelancer_write = FreelancerWriteViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'delete': 'destroy',
})

freelancer_create = FreelancerWriteViewSet.as_view({
    'post': 'create',
})


urlpatterns = [
    #create
    path('create/', freelancer_create, name='freelancer-create'),
    path('list/', ListFreelancersView.as_view(),name='list-freelancers'),

    # portfolio detail view
    path('portfolio/<str:username>/', freelancer_read, name='freelancer-portfolio'),

    # Owner Write View
    path('<str:freelance_profile_slug>/',freelancer_write, name='freelancer-manage'),
]