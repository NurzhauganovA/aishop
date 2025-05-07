from django import forms
from .models import EmailNotificationSettings

class EmailNotificationSettingsForm(forms.ModelForm):
    class Meta:
        model = EmailNotificationSettings
        fields = ['order_updates', 'new_messages', 'product_updates', 'promotions']
        labels = {
            'order_updates': 'Обновления статуса заказов',
            'new_messages': 'Новые сообщения',
            'product_updates': 'Обновления отслеживаемых товаров',
            'promotions': 'Акции и специальные предложения'
        }