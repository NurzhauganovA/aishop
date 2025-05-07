from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import Message
from apps.notifications.models import Notification

@receiver(post_save, sender=Message)
def create_message_notification(sender, instance, created, **kwargs):
    """Создание уведомления при получении нового сообщения"""
    if created and instance.message_type != 'system':
        conversation = instance.conversation
        
        # Определяем получателя уведомления
        if instance.sender == conversation.buyer:
            recipient = conversation.seller
        else:
            recipient = conversation.buyer
        
        # Формируем заголовок и текст уведомления
        if instance.message_type == 'ai':
            title = 'Новое сообщение от ИИ-ассистента'
            message = 'AISha ответила на ваш вопрос.'
        else:
            title = f'Новое сообщение от {instance.sender.username}'
            message = instance.content[:50] + ('...' if len(instance.content) > 50 else '')
        
        # Создаем уведомление
        Notification.objects.create(
            user=recipient,
            notification_type='chat_message',
            title=title,
            message=message,
            link=reverse('chat_detail', args=[conversation.id])
        )