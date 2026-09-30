from django.urls import path
from . import views

app_name = 'recommendations'

urlpatterns = [
    path('', views.recommended_for_you, name='recommended_for_you'),
    path('trending/', views.trending_events, name='trending_events'),
]