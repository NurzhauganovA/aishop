from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Order(models.Model):
    STATUS_CHOICES = (
        ('new', _('Новый')),
        ('processing', _('В обработке')),
        ('shipped', _('Отправлен')),
        ('completed', _('Завершён')),
        ('cancelled', _('Отменён')),
    )
    
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller_orders')
    full_name = models.CharField(_('Полное имя'), max_length=100)
    phone = models.CharField(_('Телефон'), max_length=15)
    email = models.EmailField(_('Email'))
    address = models.CharField(_('Адрес'), max_length=255)
    city = models.CharField(_('Город'), max_length=100)
    postal_code = models.CharField(_('Почтовый индекс'), max_length=20, blank=True)
    status = models.CharField(_('Статус'), max_length=20, choices=STATUS_CHOICES, default='new')
    total_price = models.DecimalField(_('Общая сумма'), max_digits=10, decimal_places=2)
    comment = models.TextField(_('Комментарий к заказу'), blank=True)
    tracking_number = models.CharField(_('Номер отслеживания'), max_length=100, blank=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)
    
    class Meta:
        verbose_name = _('Заказ')
        verbose_name_plural = _('Заказы')
    
    def __str__(self):
        return f"Заказ #{self.id} от {self.buyer.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='order_items')
    price = models.DecimalField(_('Цена'), max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(_('Количество'), default=1)
    
    class Meta:
        verbose_name = _('Элемент заказа')
        verbose_name_plural = _('Элементы заказа')
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    @property
    def subtotal(self):
        return self.price * self.quantity

class OrderStatus(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_updates')
    status = models.CharField(_('Статус'), max_length=20, choices=Order.STATUS_CHOICES)
    comment = models.TextField(_('Комментарий'), blank=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='status_updates')
    
    class Meta:
        verbose_name = _('Статус заказа')
        verbose_name_plural = _('Статусы заказов')
    
    def __str__(self):
        return f"Статус {self.status} для заказа #{self.order.id}"