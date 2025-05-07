from django.utils import timezone
from datetime import timedelta

class UserActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        if request.user.is_authenticated:
            # Обновляем время последней активности
            current_time = timezone.now()
            
            # Если последняя активность более 5 минут назад,
            # считаем пользователя вышедшим из сети и снова вошедшим
            if current_time - request.user.last_activity > timedelta(minutes=5):
                request.user.is_online = True
                
            request.user.last_activity = current_time
            request.user.save(update_fields=['last_activity', 'is_online'])
        
        return response