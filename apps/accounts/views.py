from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils import timezone
from datetime import timedelta
import json
import re

from .models import CustomUser, Address
from .forms import LoginForm, RegisterForm, ProfileForm, AddressForm

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next', 'home')
                return redirect(next_url)
            else:
                messages.error(request, 'Неверное имя пользователя или пароль.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Будет активирован после подтверждения email
            user.save()
            
            # Генерация токена верификации
            token = get_random_string(64)
            
            # Здесь была ошибка - user.profile это не модель Django, не имеет метода save()
            # Вместо этого, мы можем сохранить токен и время в сессии или создать отдельную запись
            # в базе данных для хранения токенов, например через модель VerificationToken
            
            # Временное решение - сохраняем токен в сессии
            request.session['email_verification_token'] = token
            request.session['email_verification_email'] = user.email
            request.session['email_verification_sent'] = timezone.now().isoformat()
            
            # Отправка письма для подтверждения
            verification_url = f"{request.scheme}://{request.get_host()}/accounts/verify-email/{token}/"
            send_mail(
                'Подтверждение регистрации',
                f'Для завершения регистрации перейдите по ссылке: {verification_url}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            messages.success(request, 'Вы успешно зарегистрировались! Проверьте вашу почту для подтверждения аккаунта.')
            return redirect('login')
    else:
        form = RegisterForm()
    
    return render(request, 'accounts/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

def verify_email(request, token):
    # Получаем токен и email из сессии
    stored_token = request.session.get('email_verification_token')
    email = request.session.get('email_verification_email')
    sent_time_str = request.session.get('email_verification_sent')
    
    if not stored_token or stored_token != token:
        messages.error(request, 'Недействительная ссылка подтверждения.')
        return redirect('login')
    
    try:
        # Находим пользователя по email
        user = CustomUser.objects.get(email=email)
        
        # Проверка срока действия токена (24 часа)
        if sent_time_str:
            from datetime import datetime
            sent_time = datetime.fromisoformat(sent_time_str)
            # Преобразуем sent_time и timezone.now() к UTC для корректного сравнения
            if timezone.now() - sent_time > timedelta(hours=24):
                messages.error(request, 'Срок действия ссылки истек. Запросите новую ссылку.')
                return redirect('resend_verification')
        
        # Активируем пользователя
        user.is_active = True
        user.save()
        
        # Очищаем данные верификации из сессии
        if 'email_verification_token' in request.session:
            del request.session['email_verification_token']
        if 'email_verification_email' in request.session:
            del request.session['email_verification_email']
        if 'email_verification_sent' in request.session:
            del request.session['email_verification_sent']
        
        messages.success(request, 'Ваш email успешно подтвержден! Теперь вы можете войти в систему.')
        return redirect('login')
    
    except CustomUser.DoesNotExist:
        messages.error(request, 'Пользователь с таким email не найден.')
        return redirect('login')

def verify_phone(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        user = request.user
        
        if user.profile.phone_verification_code == code:
            # Проверка срока действия кода (10 минут)
            if timezone.now() - user.profile.phone_verification_sent > timedelta(minutes=10):
                messages.error(request, 'Срок действия кода истек. Запросите новый код.')
                return redirect('profile')
            
            user.profile.phone_verified = True
            user.profile.phone_verification_code = ''
            user.profile.save()
            
            messages.success(request, 'Ваш номер телефона успешно подтвержден!')
            return redirect('profile')
        else:
            messages.error(request, 'Неверный код подтверждения.')
    
    return render(request, 'accounts/verify_phone.html')

def resend_verification(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = CustomUser.objects.get(email=email)
            
            if user.profile.email_verified:
                messages.info(request, 'Этот email уже подтвержден. Вы можете войти в систему.')
                return redirect('login')
            
            # Генерация нового токена
            token = get_random_string(64)
            user.profile.email_verification_token = token
            user.profile.email_verification_sent = timezone.now()
            user.profile.save()
            
            # Отправка письма для подтверждения
            verification_url = f"{request.scheme}://{request.get_host()}/accounts/verify-email/{token}/"
            send_mail(
                'Подтверждение регистрации',
                f'Для завершения регистрации перейдите по ссылке: {verification_url}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            messages.success(request, 'Новая ссылка для подтверждения отправлена на ваш email.')
            return redirect('login')
        
        except CustomUser.DoesNotExist:
            messages.error(request, 'Пользователь с таким email не найден.')
    
    return render(request, 'accounts/resend_verification.html')

def reset_password_request(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = CustomUser.objects.get(email=email)
            
            # Генерация токена для сброса пароля
            token = get_random_string(64)
            user.profile.password_reset_token = token
            user.profile.password_reset_sent = timezone.now()
            user.profile.save()
            
            # Отправка письма для сброса пароля
            reset_url = f"{request.scheme}://{request.get_host()}/accounts/reset-password/{token}/"
            send_mail(
                'Сброс пароля',
                f'Для сброса пароля перейдите по ссылке: {reset_url}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            messages.success(request, 'Инструкции по сбросу пароля отправлены на ваш email.')
            return redirect('login')
        
        except CustomUser.DoesNotExist:
            messages.error(request, 'Пользователь с таким email не найден.')
    
    return render(request, 'accounts/reset_password_request.html')

def reset_password(request, token):
    try:
        profile = Profile.objects.get(password_reset_token=token)
        user = profile.user
        
        # Проверка срока действия токена (24 часа)
        if timezone.now() - profile.password_reset_sent > timedelta(hours=24):
            messages.error(request, 'Срок действия ссылки истек. Запросите новую ссылку.')
            return redirect('reset_password_request')
        
        if request.method == 'POST':
            password = request.POST.get('password')
            password_confirm = request.POST.get('password_confirm')
            
            if password != password_confirm:
                messages.error(request, 'Пароли не совпадают.')
                return render(request, 'accounts/reset_password.html')
            
            user.set_password(password)
            user.save()
            
            # Очистка токена
            profile.password_reset_token = ''
            profile.save()
            
            messages.success(request, 'Ваш пароль успешно изменен! Теперь вы можете войти в систему.')
            return redirect('login')
        
        return render(request, 'accounts/reset_password.html')
    
    except Profile.DoesNotExist:
        messages.error(request, 'Недействительная ссылка сброса пароля.')
        return redirect('login')

@login_required
def profile_view(request):
    addresses = Address.objects.filter(user=request.user)
    orders = request.user.orders.all().order_by('-created_at')
    
    context = {
        'user': request.user,
        'addresses': addresses,
        'orders': orders,
    }
    return render(request, 'accounts/profile.html', context)

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)
    
    return render(request, 'accounts/edit_profile.html', {'form': form})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Важно для сохранения сессии
            messages.success(request, 'Ваш пароль успешно изменен!')
            return redirect('profile')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})

@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user)
    return render(request, 'accounts/address_list.html', {'addresses': addresses})

@login_required
def add_address(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            
            # Если это первый адрес или установлен как по умолчанию
            if not Address.objects.filter(user=request.user).exists() or form.cleaned_data['is_default']:
                Address.objects.filter(user=request.user).update(is_default=False)
                address.is_default = True
            
            address.save()
            messages.success(request, 'Адрес успешно добавлен.')
            return redirect('address_list')
    else:
        form = AddressForm()
    
    return render(request, 'accounts/address_form.html', {'form': form, 'title': 'Добавить адрес'})

@login_required
def edit_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            address = form.save(commit=False)
            
            # Если установлен как по умолчанию
            if form.cleaned_data['is_default']:
                Address.objects.filter(user=request.user).update(is_default=False)
                address.is_default = True
            
            address.save()
            messages.success(request, 'Адрес успешно обновлен.')
            return redirect('address_list')
    else:
        form = AddressForm(instance=address)
    
    return render(request, 'accounts/address_form.html', {'form': form, 'title': 'Редактировать адрес'})

@login_required
def delete_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    if request.method == 'POST':
        is_default = address.is_default
        address.delete()
        
        # Если удаленный адрес был по умолчанию, устанавливаем новый
        if is_default:
            first_address = Address.objects.filter(user=request.user).first()
            if first_address:
                first_address.is_default = True
                first_address.save()
        
        messages.success(request, 'Адрес успешно удален.')
        return redirect('address_list')
    
    return render(request, 'accounts/delete_address.html', {'address': address})

@login_required
def set_default_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    
    # Снимаем флаг у всех адресов
    Address.objects.filter(user=request.user).update(is_default=False)
    
    # Устанавливаем новый адрес по умолчанию
    address.is_default = True
    address.save()
    
    messages.success(request, 'Адрес по умолчанию успешно изменен.')
    return redirect('address_list')