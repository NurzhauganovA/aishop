from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class UserActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activities')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='user_activities')
    view_time = models.IntegerField(_('Время просмотра (сек)'), default=0)
    view_count = models.IntegerField(_('Количество просмотров'), default=1)
    last_viewed = models.DateTimeField(_('Последний просмотр'), auto_now=True)
    
    class Meta:
        verbose_name = _('Активность пользователя')
        verbose_name_plural = _('Активности пользователей')
        unique_together = ('user', 'product')