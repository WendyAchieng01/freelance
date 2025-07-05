from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import ReviewViewSet,UserReviewSummaryView

router = DefaultRouter()
router.register(r'', ReviewViewSet, basename='review')

urlpatterns = [
    path('', include(router.urls)),
    path('<str:username>/summary/', UserReviewSummaryView.as_view(), name='user-review-summary'),
]
