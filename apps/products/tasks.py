from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from .models import Product
from apps.notifications.models import Notification

@shared_task
def notify_low_stock_products():
    """Уведомление продавцов о товарах, которых мало в наличии"""
    # Получаем товары с малым количеством остатка (меньше 5)
    low_stock_products = Product.objects.filter(status='active', stock__gt=0, stock__lt=5)
    
    # Группируем товары по продавцам
    products_by_seller = {}
    for product in low_stock_products:
        if product.seller not in products_by_seller:
            products_by_seller[product.seller] = []
        products_by_seller[product.seller].append(product)
    
    # Отправляем уведомления каждому продавцу
    for seller, products in products_by_seller.items():
        # Создаем уведомление в системе
        product_list = ", ".join([f"{product.name} ({product.stock} шт.)" for product in products])
        Notification.objects.create(
            user=seller,
            notification_type='system',
            title='Товары с низким остатком',
            message=f'У вас есть товары с низким остатком на складе: {product_list}',
            link='/seller/products/?status=active'
        )
        
        # Формируем контекст для шаблона письма
        context = {
            'seller_name': seller.get_full_name() or seller.username,
            'products': products,
            'date': timezone.now().strftime('%d.%m.%Y'),
        }
        
        # Рендерим шаблон письма
        subject = f'Товары с низким остатком на {timezone.now().strftime("%d.%m.%Y")}'
        html_message = render_to_string('emails/low_stock_notification.html', context)
        plain_message = render_to_string('emails/low_stock_notification.txt', context)
        
        # Отправляем письмо
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [seller.email],
            html_message=html_message,
            fail_silently=False,
        )

@shared_task
def process_product_images(product_id):
    """Обработка изображений товара (оптимизация, создание миниатюр)"""
    from PIL import Image
    import os
    
    try:
        product = Product.objects.get(id=product_id)
        
        for image in product.images.all():
            # Путь к файлу изображения
            file_path = os.path.join(settings.MEDIA_ROOT, image.image.name)
            
            # Открываем изображение
            img = Image.open(file_path)
            
            # Оптимизируем изображение
            img = img.convert('RGB')
            img.save(file_path, optimize=True, quality=85)
            
            # Создаем миниатюру
            thumbnail_size = (300, 300)
            img.thumbnail(thumbnail_size)
            
            # Путь для миниатюры
            thumbnail_path = os.path.join(
                os.path.dirname(file_path),
                f"thumb_{os.path.basename(file_path)}"
            )
            
            # Сохраняем миниатюру
            img.save(thumbnail_path, optimize=True, quality=85)
    except Product.DoesNotExist:
        pass
    except Exception as e:
        # Обработка ошибок
        print(f"Error processing images for product {product_id}: {e}")
