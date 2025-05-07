from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('buyer', _('Покупатель')),
        ('seller', _('Продавец')),
        ('admin', _('Администратор')),
    )
    
    email = models.EmailField(_('Email'), unique=True)
    phone_number = models.CharField(_('Номер телефона'), max_length=15, blank=True, null=True)
    role = models.CharField(_('Роль'), max_length=10, choices=ROLE_CHOICES, default='buyer')
    is_online = models.BooleanField(_('В сети'), default=False)
    last_activity = models.DateTimeField(_('Последняя активность'), default=timezone.now)
    
    def is_seller(self):
        return self.role == 'seller'
    
    def is_buyer(self):
        return self.role == 'buyer'
    
    def __str__(self):
        return self.username

class Address(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='addresses')
    title = models.CharField(_('Название'), max_length=100)
    full_name = models.CharField(_('Полное имя'), max_length=100)
    phone = models.CharField(_('Телефон'), max_length=15)
    city = models.CharField(_('Город'), max_length=100)
    postal_code = models.CharField(_('Почтовый индекс'), max_length=20, blank=True)
    address_line1 = models.CharField(_('Адрес'), max_length=255)
    address_line2 = models.CharField(_('Дополнительный адрес'), max_length=255, blank=True)
    is_default = models.BooleanField(_('По умолчанию'), default=False)
    
    class Meta:
        verbose_name = _('Адрес')
        verbose_name_plural = _('Адреса')
    
    def __str__(self):
        return f"{self.title} - {self.full_name}"

# Модель UserActivity перемещена в приложение user_activities