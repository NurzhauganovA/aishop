from django.urls import path, re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/aisha/(?P<conversation_id>\d+)/$', consumers.AIAssistantConsumer.as_asgi()),
]