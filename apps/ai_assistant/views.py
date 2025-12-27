from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator

from .models import AISearchQuery, AIRecommendation
from apps.chat.models import AIConversation, AIMessage
from .utils import (
    chat_with_ai_assistant,
    search_products_with_ai,
    generate_ai_product_description,
    semantic_vector_search,
)
from apps.products.models import Product, Category
from apps.user_activities.models import UserActivity
import json
import uuid
import logging

logger = logging.getLogger(__name__)


@login_required
def create_conversation(request):
    """Создание нового диалога с AI ассистентом"""
    if request.method == 'POST':
        try:
            # Создаем новый диалог
            conversation = AIConversation.objects.create(user=request.user)

            # Приветственное сообщение от AI
            AIMessage.objects.create(
                conversation=conversation,
                role='ai',
                content='Привет! Я AISha, персональный ассистент этого маркетплейса. Чем я могу помочь вам сегодня?'
            )

            logger.info(f"Создан новый AI диалог {conversation.id} для пользователя {request.user.username}")

            return JsonResponse({
                'status': 'success',
                'conversation_id': conversation.id
            })

        except Exception as e:
            logger.error(f"Ошибка при создании диалога: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Не удалось создать диалог'
            }, status=500)

    return JsonResponse({'status': 'error', 'message': 'Метод не поддерживается'}, status=405)


@login_required
def get_conversation_history(request, conversation_id):
    """Получение истории диалога с AI ассистентом"""
    try:
        # Используем модель AIConversation из apps.chat.models
        from apps.chat.models import AIConversation

        conversation = AIConversation.objects.get(id=conversation_id, user=request.user)
        messages = conversation.messages.all().order_by('created_at')

        logger.info(f"Загружена история диалога {conversation_id} для пользователя {request.user.username}")

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
        logger.warning(f"Диалог {conversation_id} не найден для пользователя {request.user.username}")
        return JsonResponse({'status': 'error', 'message': 'Диалог не найден'}, status=404)
    except Exception as e:
        logger.error(f"Ошибка при загрузке истории диалога: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Внутренняя ошибка сервера'}, status=500)


@login_required
def search_products(request):
    """Поиск товаров с помощью AI ассистента"""
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({'status': 'error', 'message': 'Запрос не может быть пустым'}, status=400)

    try:
        # Сохранение поискового запроса
        AISearchQuery.objects.create(user=request.user, query=query)

        # Используем ИИ для анализа запроса
        search_params = search_products_with_ai(query, request.user)

        # Базовый запрос
        products = Product.objects.filter(status='active')

        # Применяем категории
        categories_names = search_params.get('categories', [])
        if categories_names:
            categories = Category.objects.filter(
                Q(name__icontains=categories_names[0]) if categories_names else Q()
            )
            if categories.exists():
                products = products.filter(category__in=categories)

        # Применяем ключевые слова
        keywords = search_params.get('keywords', [])
        if keywords:
            q_objects = Q()
            for keyword in keywords:
                q_objects |= Q(name__icontains=keyword) | Q(description__icontains=keyword)
            products = products.filter(q_objects)

        # Применяем ценовой диапазон
        price_range = search_params.get('price_range', {})
        if price_range and price_range.get('min') is not None:
            products = products.filter(price__gte=price_range['min'])
        if price_range and price_range.get('max') is not None:
            products = products.filter(price__lte=price_range['max'])

        # Применяем дополнительные фильтры
        filters = search_params.get('filters', {})
        for param, value in filters.items():
            # Здесь можно добавить более сложную логику фильтрации
            if param and value:
                if hasattr(Product, param):
                    filter_kwargs = {param + '__icontains': value}
                    products = products.filter(**filter_kwargs)

        # Пагинация результатов
        paginator = Paginator(products, 12)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        # Если классический поиск ничего не нашел, пробуем семантический
        vector_hits = []
        used_vector = False

        if paginator.count == 0:
            vector_hits = semantic_vector_search(query, max_results=12)
            used_vector = True

        products_to_iterate = vector_hits if used_vector else page_obj
        total_count = len(vector_hits) if used_vector else paginator.count
        total_pages = 1 if used_vector else paginator.num_pages
        current_page = 1 if used_vector else page_obj.number

        # Формируем результаты
        results = []
        for product in products_to_iterate:
            # Безопасно получаем первое изображение
            first_image = product.images.first() if hasattr(product, 'images') else None
            image_url = first_image.image.url if first_image else None

            # Безопасно получаем количество отзывов
            reviews_count = 0
            if hasattr(product, 'reviews'):
                reviews_count = product.reviews.count()

            results.append({
                'id': product.id,
                'name': product.name,
                'slug': getattr(product, 'slug', ''),
                'price': str(product.price),
                'old_price': str(product.old_price) if product.old_price else None,
                'image': image_url,
                'rating': getattr(product, 'rating', None),
                'reviews_count': reviews_count,
                'url': getattr(product, 'get_absolute_url', lambda: f'/products/{product.id}/')()
            })

        logger.info(f"Поиск выполнен для запроса '{query}', найдено: {total_count} товаров (vector={used_vector})")

        return JsonResponse({
            'status': 'success',
            'results': results,
            'total': total_count,
            'pages': total_pages,
            'current_page': current_page,
            'used_vector': used_vector,
        })

    except Exception as e:
        logger.error(f"Ошибка при поиске товаров: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Ошибка при выполнении поиска'}, status=500)


@login_required
def get_recommendations(request):
    """Получение рекомендаций товаров для пользователя"""
    try:
        # Создание рекомендаций на основе активности пользователя
        user_activities = UserActivity.objects.filter(user=request.user).order_by('-view_time', '-view_count')[:10]

        if not user_activities.exists():
            # Если нет активности, рекомендуем популярные товары
            recommended_products = Product.objects.filter(status='active').order_by('-id')[:12]
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
            # Безопасно получаем первое изображение
            first_image = product.images.first() if hasattr(product, 'images') else None
            image_url = first_image.image.url if first_image else None

            # Безопасно получаем количество отзывов
            reviews_count = 0
            if hasattr(product, 'reviews'):
                reviews_count = product.reviews.count()

            results.append({
                'id': product.id,
                'name': product.name,
                'slug': getattr(product, 'slug', ''),
                'price': str(product.price),
                'old_price': str(product.old_price) if product.old_price else None,
                'image': image_url,
                'rating': getattr(product, 'rating', None),
                'reviews_count': reviews_count,
                'url': getattr(product, 'get_absolute_url', lambda: f'/products/{product.id}/')()
            })

        logger.info(f"Сгенерированы рекомендации для пользователя {request.user.username}")

        return JsonResponse({
            'status': 'success',
            'results': results,
            'reason': reason
        })

    except Exception as e:
        logger.error(f"Ошибка при генерации рекомендаций: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Ошибка при генерации рекомендаций'}, status=500)


@login_required
def generate_description(request):
    """Генерация описания товара с помощью AI"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_name = data.get('name', '')
            attributes = data.get('attributes', {})

            if not product_name:
                return JsonResponse({'status': 'error', 'message': 'Название товара обязательно'}, status=400)

            description = generate_ai_product_description(product_name, attributes)

            logger.info(f"Сгенерировано описание для товара '{product_name}' пользователем {request.user.username}")

            return JsonResponse({
                'status': 'success',
                'description': description
            })
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Некорректный JSON'}, status=400)
        except Exception as e:
            logger.error(f"Ошибка при генерации описания: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'Ошибка при генерации описания'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Метод не поддерживается'}, status=405)