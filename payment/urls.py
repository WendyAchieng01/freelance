from django.urls import path
from . import views

app_name = 'payment' 

urlpatterns = [
    path('initiate-payment/', views.initiate_payment, name='initiate_payment'),
    path('initiate-payment/<int:job_id>/<int:response_id>/', views.initiate_response_payment, name='initiate_response_payment'),
    path('verify-payment/<str:ref>/', views.verify_payment, name='verify_payment'),
]