from django.urls import path
from .views import analytics_dashboard
from analytics.api import AnalyticsDataAPI

urlpatterns = [
    path("", analytics_dashboard, name="admin-analytics"),
    path('api/data/', AnalyticsDataAPI.as_view(), name='analytics-data'),
]
