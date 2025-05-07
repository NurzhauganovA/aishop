from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/aisha/<int:conversation_id>/', consumers.AIAssistantConsumer.as_asgi()),
]