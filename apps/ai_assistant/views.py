from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator

from .models import AISearchQuery, AIRecommendation
from apps.chat.models import AIConversation, AIMessage
from .utils import chat_with_ai_assistant, search_products_with_ai, generate_ai_product_description
from apps.products.models import Product, Category
from apps.user_activities.models import UserActivity
import json
import uuid


@login_required
def create_conversation(request):
    if request.method == 'POST':
        # Создаем новый диалог
        conversation = AIConversation.objects.create(user=request.user)

        # Приветственное сообщение от AI
        AIMessage.objects.create(
            conversation=conversation,
            role='ai',
            content='Привет! Я AISha, персональный ассистент этого маркетплейса. Чем я могу помочь вам сегодня?'
        )

        return JsonResponse({
            'status': 'success',
            'conversation_id': conversation.id
        })

    return JsonResponse({'status': 'error', 'message': 'Метод не поддерживается'}, status=405)


@login_required
def get_conversation_history(request, conversation_id):
    try:
        # Используем модель AIConversation из apps.chat.models
        from apps.chat.models import AIConversation

        conversation = AIConversation.objects.get(id=conversation_id, user=request.user)
        messages = conversation.messages.all().order_by('created_at')

        return JsonResponse({
            'status': 'success',
            'messages': [
                {
                    'id': message.id,
                    'role': message.role,
                    'content': message.content,
                    'created_at': message.created_at.isoformat()
                }
                for message in messages
            ]
        })
    except AIConversation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Диалог не найден'}, status=404)


@login_required
def search_products(request):
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({'status': 'error', 'message': 'Запрос не может быть пустым'}, status=400)

    # Сохранение поискового запроса
    AISearchQuery.objects.create(user=request.user, query=query)

    # Используем ИИ для анализа запроса
    search_params = search_products_with_ai(query, request.user)

    # Базовый запрос
    products = Product.objects.filter(status='active')

    # Применяем категории
    if search_params.get('categories'):
        categories = Category.objects.filter(name__in=search_params['categories'])
        if categories.exists():
            products = products.filter(category__in=categories)

    # Применяем ключевые слова
    if search_params.get('keywords'):
        q_objects = Q()
        for keyword in search_params['keywords']:
            q_objects |= Q(name__icontains=keyword) | Q(description__icontains=keyword)
        products = products.filter(q_objects)

    # Применяем ценовой диапазон
    price_range = search_params.get('price_range', {})
    if price_range.get('min') is not None:
        products = products.filter(price__gte=price_range['min'])
    if price_range.get('max') is not None:
        products = products.filter(price__lte=price_range['max'])

    # Формируем результаты
    results = [
        {
            'id': product.id,
            'name': product.name,
            'url': product.get_absolute_url(),
            'price': str(product.price),
            'image': product.images.first().image.url if product.images.exists() else None,
        }
        for product in products
    ]

    return JsonResponse({
        'status': 'success',
        'results': results
    })


@login_required
def get_recommendations(request):
    # Создание рекомендаций на основе активности пользователя
    user_activities = UserActivity.objects.filter(user=request.user).order_by('-view_time', '-view_count')[:10]

    if not user_activities.exists():
        # Если нет активности, рекомендуем популярные товары
        recommended_products = Product.objects.filter(status='active').order_by('-reviews__rating')[:12]
        reason = "Популярные товары"
    else:
        # Получаем категории, которые интересуют пользователя
        category_ids = [activity.product.category_id for activity in user_activities]

        # Находим похожие товары
        recommended_products = Product.objects.filter(
            status='active',
            category_id__in=category_ids
        ).exclude(
            id__in=[activity.product_id for activity in user_activities]
        ).order_by('?')[:12]

        reason = "Основано на ваших интересах"

    # Сохраняем рекомендации
    if recommended_products.exists():
        recommendation = AIRecommendation.objects.create(
            user=request.user,
            reason=reason
        )
        recommendation.products.set(recommended_products)

    # Формируем результаты
    results = []
    for product in recommended_products:
        results.append({
            'id': product.id,
            'name': product.name,
            'slug': product.slug,
            'price': str(product.price),
            'old_price': str(product.old_price) if product.old_price else None,
            'image': product.images.first().image.url if product.images.exists() else None,
            'rating': product.rating,
            'reviews_count': product.reviews.count(),
            'url': product.get_absolute_url()
        })

    return JsonResponse({
        'status': 'success',
        'results': results,
        'reason': reason
    })


@login_required
def generate_description(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_name = data.get('name', '')
            attributes = data.get('attributes', {})

            if not product_name:
                return JsonResponse({'status': 'error', 'message': 'Название товара обязательно'}, status=400)

            description = generate_ai_product_description(product_name, attributes)

            return JsonResponse({
                'status': 'success',
                'description': description
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Метод не поддерживается'}, status=405)