from celery import shared_task
from django.db.models import Count, Avg
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import AIRecommendation
from apps.products.models import Product
from apps.user_activities.models import UserActivity
import random

User = get_user_model()

@shared_task
def generate_daily_recommendations():
    """Создание ежедневных рекомендаций для активных пользователей"""
    # Получаем всех активных пользователей
    active_users = User.objects.filter(is_active=True)
    
    for user in active_users:
        # Проверяем, есть ли уже созданные сегодня рекомендации
        if not AIRecommendation.objects.filter(user=user).filter(
            created_at__date=timezone.now().date()
        ).exists():
            # Получаем активность пользователя
            user_activities = UserActivity.objects.filter(user=user).order_by('-view_time', '-view_count')[:10]
            
            if user_activities.exists():
                # Получаем категории, которые интересуют пользователя
                category_ids = [activity.product.category_id for activity in user_activities]
                
                # Находим похожие товары
                recommended_products = Product.objects.filter(
                    status='active',
                    category_id__in=category_ids
                ).exclude(
                    id__in=[activity.product_id for activity in user_activities]
                ).order_by('?')[:8]
                
                reason = "Основано на ваших интересах"
            else:
                # Если нет активности, рекомендуем популярные товары
                recommended_products = Product.objects.filter(status='active').annotate(
                    avg_rating=Avg('reviews__rating'),
                    order_count=Count('order_items')
                ).order_by('-avg_rating', '-order_count')[:8]
                
                reason = "Популярные товары, которые могут вам понравиться"
            
            # Сохраняем рекомендации
            if recommended_products.exists():
                recommendation = AIRecommendation.objects.create(
                    user=user,
                    reason=reason
                )
                recommendation.products.set(recommended_products)

@shared_task
def process_search_query(user_id, query):
    """Обработка поискового запроса и анализ интересов пользователя"""
    from .utils import search_products_with_ai
    
    user = User.objects.get(id=user_id)
    search_params = search_products_with_ai(query, user)
    
    # Анализируем запрос для улучшения будущих рекомендаций
    # Здесь может быть более сложная логика анализа и сохранения предпочтений пользователя
    
    return search_params
