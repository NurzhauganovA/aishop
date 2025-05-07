from django.contrib import admin
from .models import Notification, EmailNotificationSettings

class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('created_at',)

class EmailNotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'order_updates', 'new_messages', 'product_updates', 'promotions')
    list_filter = ('order_updates', 'new_messages', 'product_updates', 'promotions')
    search_fields = ('user__username',)

admin.site.register(Notification, NotificationAdmin)
admin.site.register(EmailNotificationSettings, EmailNotificationSettingsAdmin)