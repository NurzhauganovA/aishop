from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils.text import slugify
from django.urls import reverse

class Category(models.Model):
    name = models.CharField(_('Название'), max_length=100)
    slug = models.SlugField(_('Слаг'), max_length=100, unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, related_name='children', 
                               null=True, blank=True, verbose_name=_('Родительская категория'))
    image = models.ImageField(_('Изображение'), upload_to='categories/', blank=True, null=True)
    
    class Meta:
        verbose_name = _('Категория')
        verbose_name_plural = _('Категории')
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Product(models.Model):
    STATUS_CHOICES = (
        ('active', _('Активен')),
        ('archive', _('Архив')),
        ('out_of_stock', _('Нет в наличии')),
    )
    
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                              related_name='products', verbose_name=_('Продавец'))
    category = models.ForeignKey(Category, on_delete=models.CASCADE, 
                                related_name='products', verbose_name=_('Категория'))
    name = models.CharField(_('Название'), max_length=200)
    slug = models.SlugField(_('Слаг'), max_length=200, unique=True)
    description = models.TextField(_('Описание'))
    price = models.DecimalField(_('Цена'), max_digits=10, decimal_places=2)
    old_price = models.DecimalField(_('Старая цена'), max_digits=10, decimal_places=2, blank=True, null=True)
    stock = models.PositiveIntegerField(_('Количество'))
    status = models.CharField(_('Статус'), max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)
    
    class Meta:
        verbose_name = _('Товар')
        verbose_name_plural = _('Товары')
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('product_detail', kwargs={'slug': self.slug})
    
    @property
    def rating(self):
        reviews = self.reviews.all()
        if reviews:
            return sum(review.rating for review in reviews) / len(reviews)
        return 0
    
    @property
    def discount_percentage(self):
        if self.old_price:
            return int(100 - (self.price * 100 / self.old_price))
        return 0

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(_('Изображение'), upload_to='products/')
    is_main = models.BooleanField(_('Основное изображение'), default=False)
    
    class Meta:
        verbose_name = _('Изображение товара')
        verbose_name_plural = _('Изображения товаров')
    
    def __str__(self):
        return f"Изображение для {self.product.name}"

class ProductVideo(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='videos')
    video = models.FileField(_('Видео'), upload_to='products/videos/')
    
    class Meta:
        verbose_name = _('Видео товара')
        verbose_name_plural = _('Видео товаров')
    
    def __str__(self):
        return f"Видео для {self.product.name}"

class ProductAttribute(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attributes')
    name = models.CharField(_('Название'), max_length=100)
    value = models.CharField(_('Значение'), max_length=255)
    
    class Meta:
        verbose_name = _('Атрибут товара')
        verbose_name_plural = _('Атрибуты товаров')
        unique_together = ('product', 'name')
    
    def __str__(self):
        return f"{self.name}: {self.value}"

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(_('Рейтинг'), choices=[(i, i) for i in range(1, 6)])
    text = models.TextField(_('Текст отзыва'))
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Отзыв')
        verbose_name_plural = _('Отзывы')
        unique_together = ('product', 'user')
    
    def __str__(self):
        return f"Отзыв от {self.user.username} на {self.product.name}"

class ReviewImage(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(_('Изображение'), upload_to='reviews/')
    
    class Meta:
        verbose_name = _('Изображение отзыва')
        verbose_name_plural = _('Изображения отзывов')
    
    def __str__(self):
        return f"Изображение для отзыва {self.review.id}"

class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)
    
    class Meta:
        verbose_name = _('Корзина')
        verbose_name_plural = _('Корзины')
    
    def __str__(self):
        return f"Корзина {self.user.username}"
    
    @property
    def total_price(self):
        return sum(item.subtotal for item in self.items.all())
    
    @property
    def item_count(self):
        return self.items.count()

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(_('Количество'), default=1)
    
    class Meta:
        verbose_name = _('Элемент корзины')
        verbose_name_plural = _('Элементы корзины')
        unique_together = ('cart', 'product')
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    @property
    def subtotal(self):
        return self.product.price * self.quantity

class Wishlist(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist')
    products = models.ManyToManyField(Product, related_name='wishlists')
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Список желаний')
        verbose_name_plural = _('Списки желаний')
    
    def __str__(self):
        return f"Список желаний {self.user.username}"

class ProductTracking(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tracked_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='tracking_users')
    track_price = models.BooleanField(_('Отслеживать цену'), default=True)
    track_stock = models.BooleanField(_('Отслеживать наличие'), default=True)
    track_discount = models.BooleanField(_('Отслеживать скидки'), default=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Отслеживание товара')
        verbose_name_plural = _('Отслеживания товаров')
        unique_together = ('user', 'product')
    
    def __str__(self):
        return f"{self.user.username} отслеживает {self.product.name}"