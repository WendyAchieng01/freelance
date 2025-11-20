from django.urls import path
from .views import analytics_dashboard
from analytics.api_views import AnalyticsAPIView

urlpatterns = [
    path("", analytics_dashboard, name="admin-analytics"),
    path('api/', AnalyticsAPIView.as_view(),name='admin-analytics-api'),
]
