import time
from functools import wraps

import openai
import google.generativeai as genai
from django.conf import settings
from django.db.models import Q

from .models import AISearchQuery
import json
import logging

from ..products.models import Product, Category

# Настройка логирования
logger = logging.getLogger(__name__)

# Инициализация Gemini API
genai.configure(api_key=settings.OPENAI_API_KEY)


class RateLimiter:
    def __init__(self, max_calls=20, period=60):
        self.max_calls = max_calls  # Максимальное количество вызовов
        self.period = period  # Период в секундах
        self.calls = []  # История вызовов

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()

            # Очистка истории вызовов старше периода
            self.calls = [call_time for call_time in self.calls if now - call_time < self.period]

            # Проверка лимита
            if len(self.calls) >= self.max_calls:
                wait_time = self.period - (now - self.calls[0])
                if wait_time > 0:
                    raise Exception(f"Превышен лимит запросов. Попробуйте снова через {int(wait_time)} секунд.")

            # Добавление текущего вызова
            self.calls.append(now)
            return func(*args, **kwargs)

        return wrapper


@RateLimiter(max_calls=15, period=60)
def generate_ai_product_description(product_name, attributes):
    """Генерация описания товара с помощью ИИ"""
    try:
        # Создание запроса к модели
        prompt = f"""
        Создай подробное и привлекательное описание для товара "{product_name}" на основе следующих характеристик:

        {json.dumps(attributes, indent=2, ensure_ascii=False)}

        Описание должно быть привлекательным для покупателей, подчеркивать преимущества товара 
        и включать информацию о характеристиках. Используй маркетинговый стиль, 
        но будь честным и точным. Пиши на русском языке, 3-4 абзаца текста.
        """

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты - опытный копирайтер, специализирующийся на описаниях товаров"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800,
        )
        # Получение текста ответа
        result_text = response.choices[0].message.content.strip()
        return result_text
    except Exception as e:
        logger.error(f"Ошибка при генерации описания: {str(e)}")
        return f"Ошибка при генерации описания: {str(e)}"


@RateLimiter(max_calls=15, period=60)
def chat_with_ai_assistant(user, message, conversation_history=None):
    """Взаимодействие с ИИ-ассистентом AISha"""
    try:
        # Сохранение запроса пользователя
        AISearchQuery.objects.create(user=user, query=message)

        # Подготовка сообщений для OpenAI
        messages = [
            {"role": "system", "content": """
            Ты AISha - умный ассистент маркетплейса. Твоя задача - помогать пользователям находить нужные товары,
            отвечать на их вопросы и давать рекомендации. Говори на русском языке, будь дружелюбной,
            полезной и информативной. 

            ВАЖНО: Когда пользователь просит найти товар или информацию о товаре, НЕ ВЫДУМЫВАЙ ТОВАРЫ. 
            Вместо этого, возвращай запрос для поиска в базе данных в следующем формате JSON:

            {
                "search_request": true,
                "keywords": ["ключевое слово1", "ключевое слово2"],
                "categories": ["категория1", "категория2"],
                "price_range": {"min": минимальная_цена, "max": максимальная_цена},
                "filters": {"параметр1": "значение1", "параметр2": "значение2"}
            }

            НЕ добавляй объяснений до или после JSON. Если пользователь не запрашивает поиск товара, 
            отвечай обычным текстом без JSON.
            """}
        ]

        # Добавляем историю сообщений
        if conversation_history:
            for msg in conversation_history:
                role = "user" if msg.role == "user" else "assistant"
                messages.append({"role": role, "content": msg.content})

        # Добавляем текущее сообщение пользователя
        messages.append({"role": "user", "content": message})

        logger.info(f"Запрос к OpenAI: {messages[-1]}")

        # Отправляем запрос к модели
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=800,
        )

        # Получение текста ответа
        response_text = response.choices[0].message.content.strip()
        logger.info(f"Ответ от OpenAI: {response_text}")

        # Проверяем, есть ли в ответе полноценный JSON объект
        try:
            # Ищем начало и конец JSON (фигурные скобки)
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                # Извлекаем строку, которая может быть JSON
                json_str = response_text[start_idx:end_idx]

                # Пытаемся распарсить JSON
                json_data = json.loads(json_str)

                # Проверяем, что это действительно объект для поиска
                if isinstance(json_data, dict) and json_data.get('search_request') == True:
                    # Выполняем поиск в базе данных, используя параметры из JSON
                    search_results = perform_actual_search(json_data, user)

                    # Возвращаем результаты поиска в формате, который будет полезен пользователю
                    if search_results:
                        return format_search_results(search_results)
                    else:
                        return "К сожалению, товары по вашему запросу не найдены. Попробуйте изменить критерии поиска."

                # Если JSON не для поиска или не содержит 'search_request', просто возвращаем текстовый ответ
                return response_text
        except json.JSONDecodeError:
            # Если не удалось распарсить, просто возвращаем текстовый ответ
            logger.warning(f"Не удалось распарсить JSON из ответа: {response_text}")
            return response_text

        # Если мы дошли до этой точки, просто возвращаем текстовый ответ
        return response_text

    except Exception as e:
        logger.error(f"Ошибка в чате с ИИ: {str(e)}")
        return f"Извините, произошла ошибка: {str(e)}"


def perform_actual_search(search_params, user):
    """Выполняет фактический поиск товаров в базе данных"""
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
    if price_range and price_range.get('min') is not None:
        products = products.filter(price__gte=price_range['min'])
    if price_range and price_range.get('max') is not None:
        products = products.filter(price__lte=price_range['max'])

    # Применяем дополнительные фильтры (если есть)
    filters = search_params.get('filters', {})
    for key, value in filters.items():
        if hasattr(Product, key):
            filter_param = {key: value}
            products = products.filter(**filter_param)

    return products


def format_search_results(products, max_results=5):
    """Форматирует результаты поиска для отображения пользователю"""
    if not products.exists():
        return "К сожалению, товары по вашему запросу не найдены."

    # Ограничиваем количество результатов
    products = products[:max_results]

    # Формируем текстовый ответ с результатами
    result = "Вот что я нашла по вашему запросу:\n\n"

    for i, product in enumerate(products, 1):
        result += f"{i}. {product.name}\n"
        result += f"   Цена: {product.price} руб.\n"
        if product.old_price and product.old_price > product.price:
            discount = round(100 - (product.price / product.old_price * 100))
            result += f"   Скидка: {discount}% (было {product.old_price} руб.)\n"
        if product.description:
            result += f"   {product.description}\n"
        result += f"   Ссылка: {product.get_absolute_url()}\n\n"

    # Если есть больше результатов, чем показали
    if products.count() > max_results:
        result += f"И еще {products.count() - max_results} товаров. Уточните запрос, чтобы получить более точные результаты."

    return result


def search_products_with_ai(query, user=None):
    """Поиск товаров с помощью ИИ"""
    try:
        # Если есть пользователь, сохраняем запрос
        if user and user.is_authenticated:
            AISearchQuery.objects.create(user=user, query=query)

        # Создание запроса к модели для анализа поискового запроса
        prompt = f"""
        Проанализируй поисковый запрос пользователя: "{query}"

        Определи:
        1. Категории товаров, которые могут подойти
        2. Ключевые слова для поиска
        3. Возможный ценовой диапазон (если указан)
        4. Другие важные параметры для фильтрации

        Ответ дай строго в формате JSON без дополнительного текста:
        {{
            "categories": ["категория1", "категория2"],
            "keywords": ["ключевое_слово1", "ключевое_слово2"],
            "price_range": {{"min": минимальная_цена, "max": максимальная_цена}},
            "filters": {{"параметр1": "значение1", "параметр2": "значение2"}}
        }}
        """

        # Отправка запроса к OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system",
                 "content": "Ты - аналитическая система для маркетплейса. Твоя задача - распознавать категории и ключевые слова в запросах. Отвечай только в формате JSON без дополнительного текста."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500,
        )

        # Получение текста ответа
        result_text = response.choices[0].message.content.strip()
        logger.info(f"Ответ от search_products_with_ai: {result_text}")

        # Проверяем, содержит ли ответ валидный JSON
        try:
            # Удаляем все что не JSON (текст до { и после })
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = result_text[start_idx:end_idx]
                search_params = json.loads(json_str)
                return search_params
            else:
                # Если не удалось найти JSON в ответе, создаем базовый ответ
                logger.warning(f"Не найден JSON формат в ответе: {result_text}")
                return {
                    "categories": [],
                    "keywords": query.split(),
                    "price_range": {"min": None, "max": None},
                    "filters": {}
                }
        except json.JSONDecodeError as e:
            logger.error(f"Не удалось распарсить JSON из ответа: {result_text}. Ошибка: {str(e)}")
            return {
                "categories": [],
                "keywords": query.split(),
                "price_range": {"min": None, "max": None},
                "filters": {}
            }
    except Exception as e:
        logger.error(f"Ошибка при поиске товаров с ИИ: {str(e)}")
        return {
            "categories": [],
            "keywords": query.split(),
            "price_range": {"min": None, "max": None},
            "filters": {}
        }