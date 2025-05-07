from django import forms
from .models import Order
from apps.accounts.models import Address

class OrderForm(forms.Form):
    address_choices = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        required=False,
        label='Выберите адрес из сохраненных'
    )
    full_name = forms.CharField(max_length=100, label='Полное имя')
    email = forms.EmailField(label='Email')
    phone = forms.CharField(max_length=15, label='Телефон')
    address_line = forms.CharField(max_length=255, label='Адрес')
    city = forms.CharField(max_length=100, label='Город')
    postal_code = forms.CharField(max_length=20, required=False, label='Почтовый индекс')
    comment = forms.CharField(widget=forms.Textarea, required=False, label='Комментарий к заказу')
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(OrderForm, self).__init__(*args, **kwargs)
        
        if user and user.is_authenticated:
            self.fields['address_choices'].queryset = Address.objects.filter(user=user)
