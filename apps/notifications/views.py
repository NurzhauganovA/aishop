from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from .models import Notification, EmailNotificationSettings
from .forms import EmailNotificationSettingsForm

@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    
    return render(request, 'notifications/notification_list.html', {
        'notifications': notifications,
        'unread_count': unread_count
    })

@login_required
def mark_as_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    # Замена is_ajax() на проверку заголовка
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    # Редирект на страницу, указанную в уведомлении, или на список уведомлений
    if notification.link:
        return redirect(notification.link)
    return redirect('notification_list')

@login_required
def mark_all_as_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    # Вместо is_ajax() проверяем заголовок
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    messages.success(request, 'Все уведомления помечены как прочитанные')
    return redirect('notification_list')

@login_required
def clear_all_notifications(request):
    Notification.objects.filter(user=request.user).delete()
    
    # Замена is_ajax() на проверку заголовка
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    messages.success(request, 'Все уведомления удалены')
    return redirect('notification_list')

@login_required
def notification_settings(request):
    settings, created = EmailNotificationSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = EmailNotificationSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Настройки уведомлений обновлены')
            return redirect('notification_settings')
    else:
        form = EmailNotificationSettingsForm(instance=settings)
    
    return render(request, 'notifications/notification_settings.html', {'form': form})