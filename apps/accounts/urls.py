from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/addresses/', views.address_list, name='address_list'),
    path('profile/addresses/add/', views.add_address, name='add_address'),
    path('profile/addresses/<int:pk>/edit/', views.edit_address, name='edit_address'),
    path('profile/addresses/<int:pk>/delete/', views.delete_address, name='delete_address'),
    path('profile/addresses/<int:pk>/set-default/', views.set_default_address, name='set_default_address'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('verify-phone/', views.verify_phone, name='verify_phone'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    path('reset-password/', views.reset_password_request, name='reset_password_request'),
    path('reset-password/<str:token>/', views.reset_password, name='reset_password'),
]