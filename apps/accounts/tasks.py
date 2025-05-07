from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()

@shared_task
def update_online_status():
    """Обновление статуса 'в сети' пользователей"""
    # Получаем временную метку для 5 минут назад
    five_minutes_ago = timezone.now() - timedelta(minutes=5)
    
    # Пользователи, которые были активны в последние 5 минут
    active_users = User.objects.filter(last_activity__gte=five_minutes_ago, is_online=False)
    active_users.update(is_online=True)
    
    # Пользователи, которые не были активны в последние 5 минут
    inactive_users = User.objects.filter(last_activity__lt=five_minutes_ago, is_online=True)
    inactive_users.update(is_online=False)

@shared_task
def send_verification_reminder():
    """Отправка напоминаний о верификации email и телефона"""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    
    # Получаем временную метку для 3 дней назад
    three_days_ago = timezone.now() - timedelta(days=3)
    
    # Пользователи, которые зарегистрировались более 3 дней назад, но не верифицировали email
    unverified_users = User.objects.filter(
        date_joined__lt=three_days_ago,
        profile__email_verified=False
    )
    
    for user in unverified_users:
        # Генерируем новый токен верификации
        token = get_random_string(64)
        user.profile.email_verification_token = token
        user.profile.email_verification_sent = timezone.now()
        user.profile.save()
        
        # Формируем URL для верификации
        verification_url = f"{settings.SITE_URL}/accounts/verify-email/{token}/"
        
        # Формируем контекст для шаблона письма
        context = {
            'user_name': user.get_full_name() or user.username,
            'verification_url': verification_url,
        }
        
        # Рендерим шаблон письма
        subject = 'Напоминание о подтверждении email'
        html_message = render_to_string('emails/verification_reminder.html', context)
        plain_message = render_to_string('emails/verification_reminder.txt', context)
        
        # Отправляем письмо
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )