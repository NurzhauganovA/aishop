import openai
from django.conf import settings
from .models import AISearchQuery
import json
import logging
import time
from functools import wraps

# Настройка логирования
logger = logging.getLogger(__name__)

# Инициализация OpenAI API
openai.api_key = settings.OPENAI_API_KEY


# Простой rate limiter
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


@RateLimiter(max_calls=15, period=60)  # Лимит 15 запросов в минуту
def generate_ai_product_description(product_name, attributes):
    """Генерация описания товара с помощью OpenAI"""
    try:
        # Создание запроса к модели
        prompt = f"""
        Создай подробное и привлекательное описание для товара "{product_name}" на основе следующих характеристик:

        {json.dumps(attributes, indent=2, ensure_ascii=False)}

        Описание должно быть привлекательным для покупателей, подчеркивать преимущества товара 
        и включать информацию о характеристиках. Используй маркетинговый стиль, 
        но будь честным и точным. Пиши на русском языке, 3-4 абзаца текста.
        """

        # Отправка запроса к OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - опытный копирайтер, специализирующийся на описаниях товаров"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800,
        )

        # Получение ответа
        description = response.choices[0].message.content.strip()
        return description
    except Exception as e:
        if "rate limit" in str(e).lower() or "quota" in str(e).lower():
            logger.error(f"Превышение квоты API: {str(e)}")
            raise Exception(
                "Превышен лимит запросов к API. Попробуйте позже или рассмотрите возможность обновления тарифа.")
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
            """}
        ]

        # Добавляем историю сообщений
        if conversation_history:
            for msg in conversation_history:
                role = "user" if msg.role == "user" else "assistant"
                messages.append({"role": role, "content": msg.content})

        # Добавляем текущее сообщение пользователя
        messages.append({"role": "user", "content": message})

        # Отправляем запрос к модели
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Можно заменить на gpt-3.5-turbo для экономии
            messages=messages,
            temperature=0.7,
            max_tokens=800,
        )

        # Получение ответа
        return response.choices[0].message.content.strip()
    except Exception as e:
        if "rate limit" in str(e).lower() or "quota" in str(e).lower():
            logger.error(f"Превышение квоты API: {str(e)}")
            raise Exception(
                "Превышен лимит запросов к API. Попробуйте позже или рассмотрите возможность обновления тарифа.")
        logger.error(f"Ошибка в чате с ИИ: {str(e)}")
        return f"Извините, произошла ошибка: {str(e)}"


@RateLimiter(max_calls=15, period=60)
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
        2. Ключевые характеристики, которые важны для пользователя
        3. Возможный ценовой диапазон (если указан)
        4. Другие важные параметры для фильтрации

        Ответ дай в формате JSON:
        {{
            "categories": ["категория1", "категория2"],
            "keywords": ["ключевое_слово1", "ключевое_слово2"],
            "price_range": {{"min": минимальная_цена, "max": максимальная_цена}},
            "filters": {{"параметр1": "значение1", "параметр2": "значение2"}}
        }}

        Если какой-то параметр не удалось определить, оставь его пустым или null.
        """

        # Отправка запроса к OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Можно заменить на gpt-3.5-turbo для экономии
            messages=[
                {"role": "system",
                 "content": "Ты - аналитическая система, которая помогает разбирать поисковые запросы для маркетплейса"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Нижкая температура для более предсказуемых ответов в JSON формате
            max_tokens=500,
        )

        result_text = response.choices[0].message.content.strip()

        try:
            # Ищем начало и конец JSON в ответе
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = result_text[start_idx:end_idx]
                # Пытаемся интерпретировать результат как JSON
                search_params = json.loads(json_str)
                return search_params
            else:
                # Если не удалось найти JSON, возвращаем базовый поиск
                return {
                    "categories": [],
                    "keywords": query.split(),
                    "price_range": {"min": None, "max": None},
                    "filters": {}
                }
        except Exception as json_error:
            logger.error(f"Ошибка при парсинге JSON: {str(json_error)}")
            # В случае ошибки разбора JSON, возвращаем базовый поиск по ключевым словам
            return {
                "categories": [],
                "keywords": query.split(),
                "price_range": {"min": None, "max": None},
                "filters": {}
            }
    except Exception as e:
        if "rate limit" in str(e).lower() or "quota" in str(e).lower():
            logger.error(f"Превышение квоты API: {str(e)}")
            raise Exception(
                "Превышен лимит запросов к API. Попробуйте позже или рассмотрите возможность обновления тарифа.")
        logger.error(f"Ошибка при поиске товаров с ИИ: {str(e)}")
        # В случае любой ошибки, возвращаем базовый поиск
        return {
            "categories": [],
            "keywords": query.split(),
            "price_range": {"min": None, "max": None},
            "filters": {}
        }