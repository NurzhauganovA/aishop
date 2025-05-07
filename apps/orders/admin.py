from django.contrib import admin
from .models import Order, OrderItem, OrderStatus

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    readonly_fields = ('product', 'price', 'quantity', 'subtotal')
    extra = 0

class OrderStatusInline(admin.TabularInline):
    model = OrderStatus
    readonly_fields = ('created_at', 'created_by')
    extra = 1

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'seller', 'status', 'total_price', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('buyer__username', 'seller__username', 'full_name', 'phone', 'email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [OrderItemInline, OrderStatusInline]
    fieldsets = (
        ('Основная информация', {
            'fields': ('buyer', 'seller', 'status', 'total_price')
        }),
        ('Контактная информация', {
            'fields': ('full_name', 'phone', 'email')
        }),
        ('Адрес доставки', {
            'fields': ('address', 'city', 'postal_code')
        }),
        ('Дополнительная информация', {
            'fields': ('comment', 'tracking_number', 'created_at', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """При изменении статуса заказа в админке создаем запись о статусе"""
        if change and 'status' in form.changed_data:
            old_obj = Order.objects.get(pk=obj.pk)
            if old_obj.status != obj.status:
                OrderStatus.objects.create(
                    order=obj,
                    status=obj.status,
                    comment=f'Статус изменен через админ-панель',
                    created_by=request.user
                )
        super().save_model(request, obj, form, change)

admin.site.register(Order, OrderAdmin)
