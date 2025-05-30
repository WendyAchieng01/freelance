from django.urls import path
from .views import ReviewViewSet

review_list = ReviewViewSet.as_view({'get': 'list', 'post': 'create'})
review_detail = ReviewViewSet.as_view(
    {'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})


urlpatterns = [
    path('reviews/', review_list),
    path('reviews/<int:pk>/', review_detail),
]
