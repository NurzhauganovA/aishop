from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Max, Q

from .models import Conversation, Message
from apps.products.models import Product
from apps.accounts.models import CustomUser

@login_required
def chat_list(request):
    # Получаем все диалоги пользователя (как покупателя, так и продавца)
    user_conversations = Conversation.objects.filter(
        Q(buyer=request.user) | Q(seller=request.user)
    ).annotate(
        last_message_time=Max('messages__created_at')
    ).order_by('-last_message_time')
    
    # Разделяем по типу участия пользователя
    buyer_conversations = []
    seller_conversations = []
    
    for conversation in user_conversations:
        # Пропускаем диалоги без сообщений
        if not conversation.messages.exists():
            continue
            
        # Определяем непрочитанные сообщения
        unread_count = conversation.messages.filter(
            is_read=False
        ).exclude(sender=request.user).count()
        
        # Получаем последнее сообщение
        last_message = conversation.messages.order_by('-created_at').first()
        
        # Добавляем дополнительные атрибуты
        conversation.unread_count = unread_count
        conversation.last_message = last_message
        
        if conversation.buyer == request.user:
            buyer_conversations.append(conversation)
        else:
            seller_conversations.append(conversation)
    
    context = {
        'buyer_conversations': buyer_conversations,
        'seller_conversations': seller_conversations
    }
    return render(request, 'chat/chat_list.html', context)

@login_required
def chat_detail(request, conversation_id):
    # Проверяем, принадлежит ли чат пользователю
    queryset = Conversation.objects.filter(Q(buyer=request.user) | Q(seller=request.user))
    conversation = get_object_or_404(queryset, id=conversation_id)
    
    # Получаем сообщения без использования distinct() с id
    # Для PostgreSQL
    messages = conversation.messages.all().order_by('id', 'created_at').distinct('id')
    
    # Помечаем непрочитанные сообщения как прочитанные
    conversation.messages.filter(
        is_read=False
    ).exclude(sender=request.user).update(is_read=True)
    
    # Получаем информацию о собеседнике
    if conversation.buyer == request.user:
        interlocutor = conversation.seller
    else:
        interlocutor = conversation.buyer
    
    context = {
        'conversation': conversation,
        'messages': messages,
        'interlocutor': interlocutor
    }
    return render(request, 'chat/chat_detail.html', context)

@login_required
def start_chat(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        seller_id = request.POST.get('seller_id')
        message_text = request.POST.get('message')
        
        if not message_text:
            messages.error(request, 'Введите сообщение')
            return redirect('product_detail_by_id', product_id=product_id)  # Исправлено здесь
        
        # Проверяем, существует ли продукт и продавец
        product = get_object_or_404(Product, id=product_id)
        seller = get_object_or_404(CustomUser, id=seller_id, role='seller')
        
        # Если пользователь пытается написать сам себе
        if seller == request.user:
            messages.error(request, 'Вы не можете написать сообщение самому себе')
            return redirect('product_detail_by_id', product_id=product.id)  # Исправлено здесь
        
        # Проверяем, существует ли уже диалог
        conversation, created = Conversation.objects.get_or_create(
            buyer=request.user,
            seller=seller,
            product=product
        )
        
        # Создаем сообщение
        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            message_type='text',
            content=message_text
        )
        
        messages.success(request, 'Сообщение отправлено')
        return redirect('chat_detail', conversation_id=conversation.id)
    
    return redirect('home')