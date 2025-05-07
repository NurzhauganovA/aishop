from django.urls import path
from . import views

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path('mark-as-read/<int:notification_id>/', views.mark_as_read, name='mark_notification_as_read'),
    path('mark-all-as-read/', views.mark_all_as_read, name='mark_all_notifications_as_read'),
    path('clear-all/', views.clear_all_notifications, name='clear_all_notifications'),
    path('settings/', views.notification_settings, name='notification_settings'),
]