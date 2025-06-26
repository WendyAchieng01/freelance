from django.urls import path
from .views import ClientWriteViewSet,ClientListView

client_write = ClientWriteViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'update',
    'delete': 'destroy',
})

client_create = ClientWriteViewSet.as_view({
    'post': 'create',
})

client_list = ClientListView.as_view()

urlpatterns = [
    path('<str:client_profile_slug>/',client_write, name='client-manage'),
    path('', client_create, name='client-create'),
    path('list/', client_list, name='client-list'),
]
