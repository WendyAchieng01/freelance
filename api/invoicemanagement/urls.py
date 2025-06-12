from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import InvoiceViewSet,InvoiceDownloadView

router = DefaultRouter()
router.register(r'', InvoiceViewSet, basename='invoice')

urlpatterns = [
    #path('<int:invoice_id>/download/',InvoiceDownloadView.as_view(), name='invoice-download'),
]

urlpatterns += router.urls
