from django import forms
from .models import Review, ReviewImage, Product, ProductImage, ProductVideo, ProductAttribute

class ReviewForm(forms.ModelForm):
    # Удалим атрибут multiple из виджета
    images = forms.FileField(required=False, widget=forms.ClearableFileInput())
    
    class Meta:
        model = Review
        fields = ['rating', 'text']

class ProductForm(forms.ModelForm):
    images = forms.FileField(required=False, widget=forms.ClearableFileInput())
    videos = forms.FileField(required=False, widget=forms.ClearableFileInput())
    
    class Meta:
        model = Product
        fields = ['category', 'name', 'description', 'price', 'old_price', 'stock', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }

class ProductAttributeForm(forms.ModelForm):
    class Meta:
        model = ProductAttribute
        fields = ['name', 'value']

# Здесь была ошибка, используем ProductAttributeForm вместо ProductAttributeFormSet
ProductAttributeFormSet = forms.inlineformset_factory(
    Product, ProductAttribute, 
    form=ProductAttributeForm,  # Используем ProductAttributeForm вместо ProductAttributeFormSet
    extra=3, can_delete=True
)