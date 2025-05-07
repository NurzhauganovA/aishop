from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import CustomUser

class Profile:
    def __init__(self, user):
        self.user = user

# Добавление атрибута profile к модели CustomUser
CustomUser.profile = property(lambda user: Profile(user))

@receiver(post_save, sender=CustomUser)
def update_user_online_status(sender, instance, **kwargs):
    """Обновляем статус 'в сети' пользователя"""
    if hasattr(instance, 'last_activity'):
        # Если последняя активность была менее 5 минут назад, считаем пользователя онлайн
        if instance.last_activity and (timezone.now() - instance.last_activity < timedelta(minutes=5)):
            instance.is_online = True
        else:
            instance.is_online = False
        
        # Если статус изменился, сохраняем модель (без вызова сигнала)
        # Здесь используем хак с _original_is_online чтобы избежать рекурсии
        if not hasattr(instance, '_original_is_online'):
            instance._original_is_online = instance.is_online
        
        if instance.is_online != instance._original_is_online:
            post_save.disconnect(update_user_online_status, sender=CustomUser)
            instance.save(update_fields=['is_online'])
            post_save.connect(update_user_online_status, sender=CustomUser)
