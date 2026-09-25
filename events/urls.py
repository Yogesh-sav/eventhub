# events/urls.py
from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.event_list, name='event_list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create/', views.event_create, name='event_create'),
    path('<int:pk>/book/', views.event_book, name='event_book'),
    path('<int:pk>/save/', views.event_save_toggle, name='event_save_toggle'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('<int:pk>/edit/', views.event_edit, name='event_edit'),
    path('<int:pk>/delete/', views.event_delete, name='event_delete'),
    path('<int:pk>/', views.event_detail, name='event_detail'),
]