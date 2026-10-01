from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('organizer/', views.organizer_analytics, name='organizer_analytics'),
    path('admin/', views.admin_analytics, name='admin_analytics'),
]