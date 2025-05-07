from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order, OrderStatus
from apps.notifications.models import Notification
from django.urls import reverse

@receiver(post_save, sender=Order)
def create_order_notification(sender, instance, created, **kwargs):
    """Создание уведомления при создании заказа"""
    if created:
        # Уведомление для покупателя
        Notification.objects.create(
            user=instance.buyer,
            notification_type='order_status',
            title=f'Заказ #{instance.id} оформлен',
            message=f'Спасибо за заказ! Продавец скоро свяжется с вами.',
            link=reverse('order_detail', args=[instance.id])
        )
        
        # Уведомление для продавца
        Notification.objects.create(
            user=instance.seller,
            notification_type='order_status',
            title=f'Новый заказ #{instance.id}',
            message=f'Покупатель {instance.buyer.username} оформил новый заказ.',
            link=reverse('seller_order_detail', args=[instance.id])
        )

@receiver(post_save, sender=OrderStatus)
def order_status_notification(sender, instance, created, **kwargs):
    """Отправка уведомлений при изменении статуса заказа"""
    if created:
        order = instance.order
        
        # Определяем получателя уведомления
        if instance.created_by == order.buyer:
            recipient = order.seller
        else:
            recipient = order.buyer
        
        # Формируем текст уведомления в зависимости от статуса
        if instance.status == 'new':
            title = f'Заказ #{order.id} оформлен'
            message = 'Заказ успешно оформлен и ожидает обработки.'
        elif instance.status == 'processing':
            title = f'Заказ #{order.id} в обработке'
            message = 'Ваш заказ принят и находится в обработке.'
        elif instance.status == 'shipped':
            title = f'Заказ #{order.id} отправлен'
            message = f'Ваш заказ отправлен. {instance.comment if instance.comment else ""}'
        elif instance.status == 'completed':
            title = f'Заказ #{order.id} выполнен'
            message = 'Ваш заказ успешно выполнен. Спасибо за покупку!'
        elif instance.status == 'cancelled':
            title = f'Заказ #{order.id} отменён'
            message = f'Заказ был отменён. {instance.comment if instance.comment else ""}'
        else:
            title = f'Обновление статуса заказа #{order.id}'
            message = f'Статус заказа изменен на "{instance.status}".'
        
        # Создаем уведомление
        Notification.objects.create(
            user=recipient,
            notification_type='order_status',
            title=title,
            message=message,
            link=reverse('order_detail', args=[order.id]) if recipient == order.buyer else reverse('seller_order_detail', args=[order.id])
        )