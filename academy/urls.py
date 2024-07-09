from django.urls import include, path
from . import views

app_name = 'academy'

urlpatterns = [
    path("", views.academy_index, name="academy_index"), 
    path('trainings/<int:training_id>/', views.training, name='training'),
    path("client/academy", views.client_academy, name="client_academy"), 
    path('client/trainings/', views.client_trainings, name='client_trainings'),
    path('trainings/<int:training_id>/edit/', views.edit_training, name='edit_training'),
    path('trainings/<pk>/delete/', views.DeleteTrainingView.as_view(), name='delete_training'),
]

