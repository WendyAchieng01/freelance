from django.urls import path
from .views import ClientWriteViewSet,ClientProfileListView

client_write = ClientWriteViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'update',
    'delete': 'destroy',
})

client_create = ClientWriteViewSet.as_view({
    'post': 'create',
})


urlpatterns = [
    path('', client_create, name='client-create'),
    path('list/', ClientProfileListView.as_view(), name='client-list'),
    path('<str:client_profile_slug>/', client_write, name='client-manage'),

]
