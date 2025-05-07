from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Conversation(models.Model):
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='buyer_conversations')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller_conversations')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='conversations', null=True, blank=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)
    
    class Meta:
        verbose_name = _('Чат')
        verbose_name_plural = _('Чаты')
        unique_together = ('buyer', 'seller', 'product')
    
    def __str__(self):
        return f"Чат между {self.buyer.username} и {self.seller.username}"

class Message(models.Model):
    MESSAGE_TYPE_CHOICES = (
        ('text', _('Текст')),
        ('ai', _('ИИ')),
        ('system', _('Системное')),
    )
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    message_type = models.CharField(_('Тип сообщения'), max_length=10, choices=MESSAGE_TYPE_CHOICES, default='text')
    content = models.TextField(_('Содержание'))
    is_read = models.BooleanField(_('Прочитано'), default=False)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Сообщение')
        verbose_name_plural = _('Сообщения')
        ordering = ['created_at']
    
    def __str__(self):
        return f"Сообщение от {self.sender.username} в {self.conversation}"

class AIConversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_conversations')
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)
    
    class Meta:
        verbose_name = _('Диалог с ИИ')
        verbose_name_plural = _('Диалоги с ИИ')
    
    def __str__(self):
        return f"Диалог с ИИ пользователя {self.user.username}"

class AIMessage(models.Model):
    ROLE_CHOICES = (
        ('user', _('Пользователь')),
        ('ai', _('ИИ')),
    )
    
    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(_('Роль'), max_length=10, choices=ROLE_CHOICES)
    content = models.TextField(_('Содержание'))
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Сообщение ИИ')
        verbose_name_plural = _('Сообщения ИИ')
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}"