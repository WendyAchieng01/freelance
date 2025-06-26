from django.urls import path
from .views import (
    JobBookmarkListView, AddBookmarkView, RemoveBookmarkView
)

urlpatterns = [
    path('', JobBookmarkListView.as_view(), name='bookmark-list'),
    path('<slug:slug>/add/',AddBookmarkView.as_view(), name='bookmark-add'),
    path('<slug:slug>/remove/',RemoveBookmarkView.as_view(), name='bookmark-remove'),
]
