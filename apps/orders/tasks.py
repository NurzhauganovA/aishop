from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from .models import Order

User = get_user_model()

@shared_task
def send_weekly_sales_report():
    """Отправка еженедельного отчета о продажах продавцам"""
    # Получаем всех продавцов
    sellers = User.objects.filter(role='seller')
    
    # Определяем период отчета (прошлая неделя)
    end_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=7)
    
    for seller in sellers:
        # Получаем заказы продавца за прошлую неделю
        orders = Order.objects.filter(
            seller=seller,
            created_at__gte=start_date,
            created_at__lt=end_date
        )
        
        # Если нет заказов, пропускаем
        if not orders.exists():
            continue
        
        # Вычисляем статистику
        total_revenue = sum(order.total_price for order in orders)
        completed_orders = orders.filter(status='completed').count()
        new_orders = orders.filter(status='new').count()
        processing_orders = orders.filter(status='processing').count()
        
        # Получаем топ-5 товаров по продажам
        top_products = []
        # Здесь должна быть логика получения топ-продуктов
        
        # Формируем контекст для шаблона письма
        context = {
            'seller_name': seller.get_full_name() or seller.username,
            'start_date': start_date.strftime('%d.%m.%Y'),
            'end_date': (end_date - timedelta(days=1)).strftime('%d.%m.%Y'),
            'total_orders': orders.count(),
            'total_revenue': total_revenue,
            'completed_orders': completed_orders,
            'new_orders': new_orders,
            'processing_orders': processing_orders,
            'top_products': top_products,
        }
        
        # Рендерим шаблон письма
        subject = f'Отчет о продажах за неделю {start_date.strftime("%d.%m.%Y")} - {(end_date - timedelta(days=1)).strftime("%d.%m.%Y")}'
        html_message = render_to_string('emails/sales_report.html', context)
        plain_message = render_to_string('emails/sales_report.txt', context)
        
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
def send_order_reminder():
    """Отправка напоминаний о необработанных заказах"""
    # Получаем все заказы, которые не обрабатывались более 24 часов
    yesterday = timezone.now() - timedelta(hours=24)
    orders = Order.objects.filter(
        status='new',
        created_at__lt=yesterday
    )
    
    for order in orders:
        # Формируем контекст для шаблона письма
        context = {
            'seller_name': order.seller.get_full_name() or order.seller.username,
            'order_id': order.id,
            'created_at': order.created_at.strftime('%d.%m.%Y %H:%M'),
            'total_price': order.total_price,
        }
        
        # Рендерим шаблон письма
        subject = f'Напоминание о необработанном заказе #{order.id}'
        html_message = render_to_string('emails/order_reminder.html', context)
        plain_message = render_to_string('emails/order_reminder.txt', context)
        
        # Отправляем письмо
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [order.seller.email],
            html_message=html_message,
            fail_silently=False,
        )