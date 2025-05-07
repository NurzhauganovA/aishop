from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_list, name='chat_list'),
    path('<int:conversation_id>/', views.chat_detail, name='chat_detail'),
    path('start/', views.start_chat, name='start_chat'),
]