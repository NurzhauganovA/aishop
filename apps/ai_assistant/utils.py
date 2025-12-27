import math
import time
import json
import logging
from functools import wraps

import google.generativeai as genai
from django.conf import settings
from django.db.models import Q

from .models import AISearchQuery, ProductEmbedding
from ..products.models import Product, Category

# Настройка логирования
logger = logging.getLogger(__name__)

# Инициализация Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

# Модель, которую requested пользователь
MODEL_NAME = 'gemini-3-flash-preview'  # Если эта модель не доступна, библиотека может выдать ошибку.
# В таком случае замените на 'gemini-1.5-flash' или 'gemini-2.0-flash-exp'
EMBEDDING_MODEL_NAME = "models/embedding-001"


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
    """Генерация описания товара с помощью Google Gemini"""
    try:
        model = genai.GenerativeModel(MODEL_NAME)

        prompt = f"""
        Создай подробное и привлекательное описание для товара "{product_name}" на основе следующих характеристик:

        {json.dumps(attributes, indent=2, ensure_ascii=False)}

        Описание должно быть привлекательным для покупателей, подчеркивать преимущества товара 
        и включать информацию о характеристиках. Используй маркетинговый стиль, 
        но будь честным и точным. Пиши на русском языке, 3-4 абзаца текста.
        """

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=800,
            )
        )

        return response.text.strip()
    except Exception as e:
        logger.error(f"Ошибка при генерации описания: {str(e)}")
        # Fallback на стабильную модель если экспериментальная недоступна
        if "404" in str(e) or "not found" in str(e).lower():
            try:
                logger.info("Попытка использовать запасную модель gemini-1.5-flash")
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as e2:
                logger.error(f"Ошибка и с запасной моделью: {str(e2)}")

        return f"Ошибка при генерации описания: {str(e)}"


@RateLimiter(max_calls=15, period=60)
def chat_with_ai_assistant(user, message, conversation_history=None):
    """Взаимодействие с ИИ-ассистентом AISha через Google Gemini"""
    try:
        # Сохранение запроса пользователя
        AISearchQuery.objects.create(user=user, query=message)

        system_instruction = """
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
        """

        model = genai.GenerativeModel(MODEL_NAME)

        # Формирование истории чата для Gemini. Для старых версий SDK добавляем системную инструкцию как первый элемент истории.
        chat_history = [{"role": "user", "parts": [system_instruction]}]
        if conversation_history:
            for msg in conversation_history:
                role = "user" if msg.role == "user" else "model"
                chat_history.append({"role": role, "parts": [msg.content]})

        # Запуск чата
        chat = model.start_chat(history=chat_history)

        logger.info(f"Запрос к Gemini: {message}")

        response = chat.send_message(
            message,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=800,
            )
        )

        response_text = response.text.strip()
        logger.info(f"Ответ от Gemini: {response_text}")

        # Проверяем JSON
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                json_data = json.loads(json_str)

                if isinstance(json_data, dict) and json_data.get('search_request') == True:
                    search_results = list(perform_actual_search(json_data, user))
                    vector_hits = semantic_vector_search(message, max_results=5)
                    combined_results = merge_product_lists(vector_hits, search_results)

                    if combined_results:
                        return format_search_results(combined_results)
                    return "К сожалению, товары по вашему запросу не найдены. Попробуйте изменить критерии поиска."
                else:
                    # Если ИИ не вернул search_request, попробуем семантический поиск напрямую
                    vector_hits = semantic_vector_search(message, max_results=5)
                    if vector_hits:
                        return format_search_results(vector_hits)
                    return response_text
        except json.JSONDecodeError:
            logger.warning(f"Не удалось распарсить JSON из ответа: {response_text}")
            vector_hits = semantic_vector_search(message, max_results=5)
            if vector_hits:
                return format_search_results(vector_hits)
            return response_text

        return response_text

    except Exception as e:
        logger.error(f"Ошибка в чате с ИИ: {str(e)}")
        # Fallback
        if "404" in str(e) or "not found" in str(e).lower():
            return "Извините, выбранная модель ИИ сейчас недоступна. Попробуйте позже."
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
    # Принимаем как QuerySet, так и обычный список
    if hasattr(products, 'exists'):
        products = list(products)

    if not products:
        return "К сожалению, товары по вашему запросу не найдены."

    total_count = len(products)
    products = products[:max_results]
    result = "Вот что я нашла по вашему запросу:\n\n"

    for i, product in enumerate(products, 1):
        result += f"{i}. {product.name}\n"
        result += f"   Цена: {product.price} ₸\n"  # Исправил валюту на Тенге
        if product.old_price and product.old_price > product.price:
            discount = round(100 - (product.price / product.old_price * 100))
            result += f"   Скидка: {discount}% (было {product.old_price} ₸)\n"
        if product.description:
            desc = product.description[:100] + "..." if len(product.description) > 100 else product.description
            result += f"   {desc}\n"
        result += f"   Ссылка: {product.get_absolute_url()}\n\n"

    if total_count > max_results:
        result += f"И еще {total_count - max_results} товаров. Уточните запрос, чтобы получить более точные результаты."

    return result


def search_products_with_ai(query, user=None):
    """Поиск товаров с помощью ИИ (анализ запроса)"""
    try:
        if user and user.is_authenticated:
            AISearchQuery.objects.create(user=user, query=query)

        model = genai.GenerativeModel(MODEL_NAME)

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
            "price_range": {{"min": null, "max": null}},
            "filters": {{"параметр1": "значение1"}}
        }}
        """

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )

        result_text = response.text.strip()
        logger.info(f"Ответ от search_products_with_ai: {result_text}")

        return json.loads(result_text)

    except Exception as e:
        logger.error(f"Ошибка при поиске товаров с ИИ: {str(e)}")
        # Fallback, если модель недоступна или ошибка парсинга
        return {
            "categories": [],
            "keywords": query.split(),
            "price_range": {"min": None, "max": None},
            "filters": {}
        }


def cosine_similarity(vec_a, vec_b):
    """Простая косинусная близость без numpy"""
    if not vec_a or not vec_b:
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def build_product_text(product):
    """Собираем текст для эмбеддинга товара"""
    parts = [product.name or "", product.description or ""]
    if product.category:
        parts.append(product.category.name)
    if hasattr(product, "attributes"):
        attrs = [f"{attr.name}: {attr.value}" for attr in product.attributes.all()]
        parts.extend(attrs)
    return "\n".join([p for p in parts if p])


def embed_text(text, task_type="retrieval_document"):
    """Получаем вектор через Gemini embeddings"""
    try:
        response = genai.embed_content(
            model=EMBEDDING_MODEL_NAME,
            content=text,
            task_type=task_type,
        )
        return response["embedding"]
    except Exception as e:
        logger.error(f"Ошибка при получении эмбеддинга: {str(e)}")
        return None


def ensure_product_embedding(product):
    """Создает или обновляет эмбеддинг товара, если это необходимо"""
    embedding_obj, _ = ProductEmbedding.objects.get_or_create(
        product=product,
        defaults={"vector": [], "source_model": EMBEDDING_MODEL_NAME, "dim": 0},
    )

    needs_refresh = not embedding_obj.vector or embedding_obj.updated_at < product.updated_at

    if needs_refresh:
        text = build_product_text(product)
        vector = embed_text(text, task_type="retrieval_document")
        if vector:
            embedding_obj.vector = vector
            embedding_obj.dim = len(vector)
            embedding_obj.source_model = EMBEDDING_MODEL_NAME
            embedding_obj.save(update_fields=["vector", "dim", "source_model", "updated_at"])
        else:
            logger.warning(f"Не удалось обновить эмбеддинг для товара {product.id}")

    return embedding_obj.vector


def semantic_vector_search(query_text, max_results=5):
    """
    Семантический поиск товаров по эмбеддингам.
    Возвращает список товаров, отсортированных по релевантности.
    """
    query_vector = embed_text(query_text, task_type="semantic_retrieval_query")
    if not query_vector:
        return []

    candidates = Product.objects.filter(status="active").select_related("category").prefetch_related("attributes")
    scored = []

    for product in candidates:
        product_vector = ensure_product_embedding(product)
        if not product_vector:
            continue
        score = cosine_similarity(query_vector, product_vector)
        scored.append((score, product))

    scored.sort(key=lambda item: item[0], reverse=True)
    top_products = [product for score, product in scored[:max_results] if score > 0]

    return top_products


def merge_product_lists(primary, secondary):
    """Объединение списков товаров с сохранением порядка и без дубликатов"""
    seen = set()
    merged = []

    for product in primary + secondary:
        if product.id in seen:
            continue
        seen.add(product.id)
        merged.append(product)

    return merged