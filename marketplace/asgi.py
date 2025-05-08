import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from apps.chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns
from apps.notifications.routing import websocket_urlpatterns as notifications_websocket_urlpatterns
from apps.ai_assistant.routing import websocket_urlpatterns as ai_assistant_websocket_urlpatterns

# Получение HTTP приложения
http_application = get_asgi_application()

# Комбинирование всех WebSocket URL-паттернов
combined_websocket_urlpatterns = (
    chat_websocket_urlpatterns +
    notifications_websocket_urlpatterns +
    ai_assistant_websocket_urlpatterns
)

application = ProtocolTypeRouter({
    'http': http_application,
    'websocket': AuthMiddlewareStack(
        URLRouter(
            combined_websocket_urlpatterns
        )
    )
})