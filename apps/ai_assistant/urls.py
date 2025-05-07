from django.urls import path
from . import views

urlpatterns = [
    path('create_conversation/', views.create_conversation, name='create_ai_conversation'),
    path('get_conversation_history/<int:conversation_id>/', views.get_conversation_history, name='get_ai_conversation_history'),
    path('search/', views.search_products, name='ai_search_products'),
    path('recommendations/', views.get_recommendations, name='ai_recommendations'),
    path('generate_description/', views.generate_description, name='ai_generate_description'),
]