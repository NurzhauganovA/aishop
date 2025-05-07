from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Notification(models.Model):
    TYPE_CHOICES = (
        ('order_status', _('Статус заказа')),
        ('chat_message', _('Сообщение в чате')),
        ('product_change', _('Изменение товара')),
        ('system', _('Системное')),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(_('Тип уведомления'), max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(_('Заголовок'), max_length=255)
    message = models.TextField(_('Сообщение'))
    is_read = models.BooleanField(_('Прочитано'), default=False)
    link = models.CharField(_('Ссылка'), max_length=255, blank=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Уведомление')
        verbose_name_plural = _('Уведомления')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} для {self.user.username}"

class EmailNotificationSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_notification_settings')
    order_updates = models.BooleanField(_('Обновления заказов'), default=True)
    new_messages = models.BooleanField(_('Новые сообщения'), default=True)
    product_updates = models.BooleanField(_('Обновления товаров'), default=True)
    promotions = models.BooleanField(_('Акции и скидки'), default=True)
    
    class Meta:
        verbose_name = _('Настройки email-уведомлений')
        verbose_name_plural = _('Настройки email-уведомлений')
    
    def __str__(self):
        return f"Настройки уведомлений для {self.user.username}"