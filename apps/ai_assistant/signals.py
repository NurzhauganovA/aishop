from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AIRecommendation
from apps.notifications.models import Notification
from django.urls import reverse

@receiver(post_save, sender=AIRecommendation)
def create_recommendation_notification(sender, instance, created, **kwargs):
    """Создание уведомления о новых рекомендациях"""
    if created:
        # Создаем уведомление для пользователя
        Notification.objects.create(
            user=instance.user,
            notification_type='system',
            title='Новые рекомендации для вас',
            message=f'AISha подобрала для вас товары: {instance.reason}',
            link=reverse('ai_recommendations')
        )