from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class AISearchQuery(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_search_queries')
    query = models.TextField(_('Запрос'))
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Запрос к ИИ')
        verbose_name_plural = _('Запросы к ИИ')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Запрос от {self.user.username}: {self.query[:50]}"

class AIRecommendation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_recommendations')
    products = models.ManyToManyField('products.Product', related_name='ai_recommendations')
    reason = models.CharField(_('Причина рекомендации'), max_length=255)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    is_viewed = models.BooleanField(_('Просмотрено'), default=False)
    
    class Meta:
        verbose_name = _('ИИ-рекомендация')
        verbose_name_plural = _('ИИ-рекомендации')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Рекомендация для {self.user.username}: {self.reason}"