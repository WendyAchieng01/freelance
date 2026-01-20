from django.urls import path, include

urlpatterns = [
    path('jobs/', include('api.core.urls_jobs')),
    path('messages/', include('api.core.urls_messages')),
    path('reviews/', include('api.core.urls_reviews')),
    path('bookmarks/', include('api.core.urls_bookmark')),
]
