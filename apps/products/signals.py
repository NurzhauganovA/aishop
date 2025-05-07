from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from .models import Product, ProductTracking
from apps.notifications.models import Notification
import random
import string

@receiver(pre_save, sender=Product)
def create_product_slug(sender, instance, **kwargs):
    """Автоматическое создание слага для товара"""
    if not instance.slug:
        # Создаем базовый слаг
        base_slug = slugify(instance.name)
        
        # Проверяем уникальность слага
        if not Product.objects.filter(slug=base_slug).exists():
            instance.slug = base_slug
        else:
            # Добавляем случайную строку к слагу
            random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            instance.slug = f"{base_slug}-{random_string}"

@receiver(post_save, sender=Product)
def product_update_notification(sender, instance, created, **kwargs):
    """Отправка уведомлений при обновлении товара"""
    if not created:
        # Получаем все отслеживания для данного товара
        trackings = ProductTracking.objects.filter(product=instance)
        
        # Проверяем изменения в товаре и отправляем уведомления
        for tracking in trackings:
            # Проверяем изменение цены
            if tracking.track_price and hasattr(instance, '_price_changed') and instance._price_changed:
                if instance.old_price and instance.price < instance.old_price:
                    # Снижение цены
                    Notification.objects.create(
                        user=tracking.user,
                        notification_type='product_change',
                        title=f'Снижение цены на {instance.name}',
                        message=f'Цена снизилась с {instance.old_price} ₸ до {instance.price} ₸',
                        link=instance.get_absolute_url()
                    )
                else:
                    # Обычное изменение цены
                    Notification.objects.create(
                        user=tracking.user,
                        notification_type='product_change',
                        title=f'Изменение цены на {instance.name}',
                        message=f'Новая цена: {instance.price} ₸',
                        link=instance.get_absolute_url()
                    )
            
            # Проверяем изменение наличия
            if tracking.track_stock and hasattr(instance, '_stock_changed') and instance._stock_changed:
                if instance.stock > 0 and hasattr(instance, '_was_out_of_stock') and instance._was_out_of_stock:
                    # Товар снова в наличии
                    Notification.objects.create(
                        user=tracking.user,
                        notification_type='product_change',
                        title=f'{instance.name} снова в наличии',
                        message=f'Товар появился в наличии. Количество: {instance.stock} шт.',
                        link=instance.get_absolute_url()
                    )
            
            # Проверяем появление скидки
            if tracking.track_discount and instance.old_price and hasattr(instance, '_discount_added') and instance._discount_added:
                discount_percentage = instance.discount_percentage
                Notification.objects.create(
                    user=tracking.user,
                    notification_type='product_change',
                    title=f'Скидка на {instance.name}',
                    message=f'Появилась скидка {discount_percentage}%. Новая цена: {instance.price} ₸',
                    link=instance.get_absolute_url()
                )

@receiver(pre_save, sender=Product)
def product_change_detection(sender, instance, **kwargs):
    """Обнаружение изменений в товаре для отправки уведомлений"""
    if instance.pk:
        # Получаем предыдущее состояние товара
        old_instance = Product.objects.get(pk=instance.pk)
        
        # Проверяем изменение цены
        if old_instance.price != instance.price:
            instance._price_changed = True
        
        # Проверяем изменение наличия
        if old_instance.stock != instance.stock:
            instance._stock_changed = True
            if old_instance.stock <= 0 and instance.stock > 0:
                instance._was_out_of_stock = True
        
        # Проверяем появление скидки
        if (not old_instance.old_price or old_instance.price == old_instance.old_price) and instance.old_price and instance.price < instance.old_price:
            instance._discount_added = True
