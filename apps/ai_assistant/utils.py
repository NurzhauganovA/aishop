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

logger = logging.getLogger(__name__)

# ── Model priority list ───────────────────────────────────────────────────────
# Each model is tried in order; first successful API response wins.
CANDIDATE_MODELS = [
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash',
    'gemini-1.5-flash-8b',
    'gemini-1.5-pro',
    'gemini-pro',
]
EMBEDDING_MODEL_NAME = "models/embedding-001"

_configured = False


def _configure_genai():
    """Configure Gemini once. Returns True when a valid API key is present."""
    global _configured
    if _configured:
        return True
    key = (getattr(settings, 'GEMINI_API_KEY', '') or '').strip()
    if not key or key.startswith('ЗАМЕНИ') or len(key) < 15:
        logger.warning("GEMINI_API_KEY not set – falling back to keyword search")
        return False
    genai.configure(api_key=key)
    _configured = True
    return True


# ── Russian → English product aliases ────────────────────────────────────────
# Used by the keyword fallback so "Айфоны" finds "iPhone" products.
RU_ALIASES: dict[str, str] = {
    # Phones
    'айфон': 'iPhone', 'айфоны': 'iPhone',
    'iphone': 'iPhone',
    'самсунг': 'Samsung', 'samsung': 'Samsung',
    'галакси': 'Galaxy',
    'сяоми': 'Xiaomi', 'ксяоми': 'Xiaomi', 'xiaomi': 'Xiaomi',
    'редми': 'Redmi',
    'хуавей': 'Huawei',
    'пиксель': 'Pixel', 'гугл': 'Google',
    'реалми': 'Realme',
    'виво': 'Vivo',
    'оппо': 'Oppo',
    'нокиа': 'Nokia',
    'моторола': 'Motorola',
    # Laptops
    'макбук': 'MacBook', 'macbook': 'MacBook',
    'thinkpad': 'ThinkPad', 'тинкпад': 'ThinkPad',
    'asus': 'ASUS',
    'асус': 'ASUS',
    'рог': 'ROG',
    'зефирус': 'Zephyrus',
    'делл': 'Dell', 'dell': 'Dell',
    'хп': 'HP', 'спектр': 'Spectre',
    'леново': 'Lenovo', 'lenovo': 'Lenovo',
    'мси': 'MSI',
    # Headphones
    'аирподс': 'AirPods', 'airpods': 'AirPods',
    'сони': 'Sony',
    'босе': 'Bose', 'bose': 'Bose',
    'джбл': 'JBL', 'jbl': 'JBL',
    # Watches
    'аппл вотч': 'Apple Watch',
    'гармин': 'Garmin',
    # Tablets
    'айпад': 'iPad', 'ipad': 'iPad',
    'планшет': None,   # no translation → category search
    # Cameras
    'альфа': 'Alpha', 'canon': 'Canon', 'nikon': 'Nikon', 'никон': 'Nikon',
    # Shoes
    'найк': 'Nike', 'nike': 'Nike',
    'адидас': 'Adidas', 'adidas': 'Adidas',
    'нью беланс': 'New Balance', 'new balance': 'New Balance',
    'аскикс': 'ASICS',
    # Categories (no translation – triggers category search)
    'ноутбук': None, 'ноутбуки': None, 'лэптоп': None, 'лаптоп': None,
    'смартфон': None, 'смартфоны': None, 'телефон': None, 'телефоны': None,
    'наушники': None, 'наушник': None,
    'часы': None, 'умные часы': None,
    'планшеты': None,
    'фотоаппарат': None, 'камера': None, 'фотик': None,
    'кроссовки': None, 'кроссовок': None,
    'рюкзак': None, 'сумка': None,
}

# Category name keyword map for fallback
CATEGORY_ALIASES: dict[str, str] = {
    'смартфон':    'Смартфоны',
    'телефон':     'Смартфоны',
    'айфон':       'Смартфоны',
    'ноутбук':     'Ноутбуки',
    'лэптоп':      'Ноутбуки',
    'лаптоп':      'Ноутбуки',
    'наушник':     'Наушники',
    'часы':        'Умные часы',
    'планшет':     'Планшеты',
    'фотоаппарат': 'Фотоаппараты',
    'камера':      'Фотоаппараты',
    'кроссовк':    'Кроссовки',
    'рюкзак':      'Рюкзаки и сумки',
    'сумк':        'Рюкзаки и сумки',
}


class RateLimiter:
    def __init__(self, max_calls=20, period=60):
        self.max_calls = max_calls
        self.period = period
        self.calls: list[float] = []

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            self.calls = [t for t in self.calls if now - t < self.period]
            if len(self.calls) >= self.max_calls:
                wait = self.period - (now - self.calls[0])
                if wait > 0:
                    raise Exception(f"Превышен лимит запросов. Подождите {int(wait)} сек.")
            self.calls.append(now)
            return func(*args, **kwargs)
        return wrapper


# ── Multilingual system prompt ────────────────────────────────────────────────
SYSTEM_PROMPT = """You are AISha — the AI assistant of SmartShop marketplace.

YOUR TASK: Help users find products that exist on OUR website.

LANGUAGE RULE: Always reply in the SAME language the user writes in.
- Русский → отвечай по-русски
- Қазақша → қазақша жауап бер
- English → reply in English

PRODUCT SEARCH RULE:
When the user asks to find/show/search for a product, respond ONLY with valid JSON (no extra text):
{
  "search_request": true,
  "keywords": ["english_word1", "english_word2"],
  "categories": ["CategoryName"],
  "price_range": {"min": null, "max": null},
  "filters": {}
}

IMPORTANT: Put ENGLISH product names in "keywords" (e.g. "iPhone", not "Айфон").
For general questions/greetings — reply with friendly plain text, NO JSON.
Never invent products. Never link to external sites."""


@RateLimiter(max_calls=15, period=60)
def chat_with_ai_assistant(user, message, conversation_history=None):
    """Main chat entry point. Tries Gemini AI; falls back to keyword search."""
    try:
        AISearchQuery.objects.create(user=user, query=message)
    except Exception:
        pass

    # Try Gemini
    if _configure_genai():
        response_text = _call_gemini(message, conversation_history)
        if response_text is not None:
            return _process_ai_response(response_text, message)

    # Fallback: keyword DB search
    logger.info("Using keyword fallback for: %s", message)
    return _keyword_fallback(message)


# ── Gemini call (retries every candidate model) ───────────────────────────────

def _call_gemini(message: str, conversation_history) -> str | None:
    """Try each candidate model until one returns a response. Returns text or None."""
    # Build the first-turn content with system prompt embedded
    first_content = f"{SYSTEM_PROMPT}\n\n---\nUser: {message}"

    # Build alternating user/model history (last 5 exchanges)
    history = []
    if conversation_history:
        pairs: list[tuple] = []
        msgs = list(conversation_history)
        i = 0
        while i < len(msgs) - 1:
            if msgs[i].role == 'user' and msgs[i + 1].role == 'ai':
                pairs.append((msgs[i], msgs[i + 1]))
                i += 2
            else:
                i += 1
        for u_msg, a_msg in pairs[-5:]:
            history.append({"role": "user",  "parts": [u_msg.content]})
            history.append({"role": "model", "parts": [a_msg.content]})

    gen_cfg = genai.types.GenerationConfig(
        temperature=0.4,
        max_output_tokens=800,
    )

    for model_name in CANDIDATE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            if history:
                chat = model.start_chat(history=history)
                resp = chat.send_message(first_content, generation_config=gen_cfg)
            else:
                resp = model.generate_content(first_content, generation_config=gen_cfg)

            text = (resp.text or "").strip()
            if text:
                logger.info("Gemini (%s) OK: %s", model_name, text[:120])
                return text
        except Exception as e:
            logger.warning("Gemini model %s failed: %s — trying next", model_name, e)
            continue

    logger.error("All Gemini models failed")
    return None


# ── Process AI response ───────────────────────────────────────────────────────

def _process_ai_response(text: str, original_message: str) -> str:
    """Parse Gemini output — handle JSON search or plain text reply."""
    # Try to extract JSON block
    try:
        start = text.find('{')
        end   = text.rfind('}') + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            if isinstance(data, dict) and data.get('search_request'):
                keywords  = data.get('keywords', [])
                results   = list(perform_actual_search(data))
                # Also try semantic vector search
                vector_hits: list = []
                try:
                    vector_hits = semantic_vector_search(original_message, max_results=5)
                except Exception:
                    pass
                combined = merge_product_lists(results, vector_hits)
                if combined:
                    return format_search_results(combined, search_keywords=keywords)
                # No results → offer catalog link
                from urllib.parse import quote_plus
                q = quote_plus(' '.join(keywords)) if keywords else ''
                return (
                    f"К сожалению, товары по вашему запросу не найдены.\n\n"
                    f"👉 [Открыть каталог](/products/?q={q})"
                )
    except (json.JSONDecodeError, ValueError):
        pass

    # Plain-text reply — run vector search if message looks like a product query
    product_words = ['найди', 'покажи', 'хочу', 'ищу', 'есть ли', 'find', 'show',
                     'тауып', 'табу', 'көрсет', 'бар ма']
    if any(w in original_message.lower() for w in product_words):
        try:
            hits = semantic_vector_search(original_message, max_results=5)
            if hits:
                return format_search_results(hits)
        except Exception:
            pass

    return text


# ── Keyword fallback (no AI) ──────────────────────────────────────────────────

def _keyword_fallback(message: str) -> str:
    """Pure DB keyword search when Gemini is unavailable or fails."""
    msg_lower = message.lower().strip()

    # 1. Translate Russian aliases → English / category names
    en_terms: list[str] = []
    cat_names: list[str] = []

    for ru, en in RU_ALIASES.items():
        if ru in msg_lower:
            if en:
                en_terms.append(en)
            else:
                # Look up category
                for cat_key, cat_name in CATEGORY_ALIASES.items():
                    if cat_key in ru or ru in cat_key:
                        cat_names.append(cat_name)
                        break

    # Also keep original non-stop words
    stop = {'найди', 'найти', 'покажи', 'хочу', 'ищу', 'все', 'мне', 'дай',
            'купить', 'есть', 'что', 'какой', 'какие', 'где', 'the', 'find',
            'show', 'me', 'all', 'some', 'good', 'best', 'и', 'в', 'на', 'с',
            'по', 'для', 'а', 'но'}
    words = [w for w in msg_lower.split() if len(w) > 2 and w not in stop]

    # 2. Combine: English aliases + original words
    search_terms = en_terms + words
    if not search_terms and not cat_names:
        return (
            "Привет! Я AISha — ИИ-ассистент SmartShop. "
            "Опишите, какой товар вы ищете.\n\n"
            "👉 [Открыть каталог](/products/)"
        )

    # 3. Search by category first (if we resolved one)
    if cat_names and not en_terms:
        cats = Category.objects.filter(name__in=cat_names)
        if cats.exists():
            # Include subcategories
            all_cat_ids = list(cats.values_list('id', flat=True))
            sub_ids = list(Category.objects.filter(parent__in=cats).values_list('id', flat=True))
            all_cat_ids += sub_ids
            products = list(
                Product.objects.filter(status='active', category_id__in=all_cat_ids)
                .select_related('category')[:10]
            )
            if products:
                return format_search_results(products, search_keywords=cat_names)

    # 4. Full-text search across name + description
    if search_terms:
        q_filter = Q()
        for term in search_terms:
            q_filter |= Q(name__icontains=term) | Q(description__icontains=term)

        # Also include category-filtered
        if cat_names:
            cats = Category.objects.filter(name__in=cat_names)
            if cats.exists():
                all_ids = list(cats.values_list('id', flat=True))
                all_ids += list(Category.objects.filter(parent__in=cats).values_list('id', flat=True))
                q_filter |= Q(category_id__in=all_ids)

        products = list(
            Product.objects.filter(status='active').filter(q_filter)
            .select_related('category').distinct()[:10]
        )
        if products:
            return format_search_results(products, search_keywords=search_terms)

    # 5. Nothing found
    from urllib.parse import quote_plus
    q = quote_plus(' '.join(search_terms[:3])) if search_terms else ''
    return (
        f"Товары по запросу **«{message}»** не найдены.\n\n"
        f"👉 [Посмотреть весь каталог](/products/?q={q})"
    )


# ── DB search helpers ─────────────────────────────────────────────────────────

def perform_actual_search(search_params: dict, user=None):
    products = Product.objects.filter(status='active').select_related('category')

    if search_params.get('categories'):
        cats = Category.objects.filter(name__in=search_params['categories'])
        if cats.exists():
            all_ids = list(cats.values_list('id', flat=True))
            all_ids += list(Category.objects.filter(parent__in=cats).values_list('id', flat=True))
            products = products.filter(category_id__in=all_ids)

    if search_params.get('keywords'):
        q = Q()
        for kw in search_params['keywords']:
            q |= Q(name__icontains=kw) | Q(description__icontains=kw)
        products = products.filter(q)

    pr = search_params.get('price_range') or {}
    if pr.get('min') is not None:
        products = products.filter(price__gte=pr['min'])
    if pr.get('max') is not None:
        products = products.filter(price__lte=pr['max'])

    for key, value in (search_params.get('filters') or {}).items():
        products = products.filter(
            attributes__name__icontains=key,
            attributes__value__icontains=str(value)
        )

    return products.distinct()


def format_search_results(products, max_results: int = 5, search_keywords=None) -> str:
    from urllib.parse import quote_plus

    if hasattr(products, 'exists'):
        products = list(products)
    if not products:
        return "К сожалению, товары по вашему запросу не найдены."

    total = len(products)
    shown = products[:max_results]
    result = f"Нашла **{total}** товар(ов):\n\n"

    for i, p in enumerate(shown, 1):
        url = p.get_absolute_url()
        result += f"**{i}. [{p.name}]({url})**\n"
        result += f"   💰 {p.price} ₸"
        if p.old_price and p.old_price > p.price:
            disc = round(100 - float(p.price) / float(p.old_price) * 100)
            result += f"  ~~{p.old_price} ₸~~ (-{disc}%)"
        result += "\n"
        if p.description:
            desc = p.description[:100] + "…" if len(p.description) > 100 else p.description
            result += f"   _{desc}_\n"
        result += f"   🔗 [Смотреть товар]({url})\n\n"

    if total > max_results:
        q = quote_plus(' '.join(str(k) for k in search_keywords)) if search_keywords else ''
        catalog_url = f"/products/?q={q}" if q else "/products/"
        result += f"_…ещё {total - max_results} товаров_\n"
        result += f"👉 [Все результаты в каталоге]({catalog_url})"

    return result


# ── AI description generator ──────────────────────────────────────────────────

@RateLimiter(max_calls=15, period=60)
def generate_ai_product_description(product_name: str, attributes: dict) -> str:
    if not _configure_genai():
        return f"Описание для «{product_name}»: качественный товар с отличными характеристиками."

    prompt = (
        f"Создай привлекательное описание для товара \"{product_name}\" "
        f"на основе характеристик:\n{json.dumps(attributes, indent=2, ensure_ascii=False)}\n"
        "Пиши на русском, 2-3 абзаца, маркетинговый стиль."
    )
    for model_name in CANDIDATE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7, max_output_tokens=600
                )
            )
            return (resp.text or "").strip()
        except Exception as e:
            logger.warning("generate_ai_product_description: model %s failed: %s", model_name, e)
            continue

    return f"Описание для «{product_name}»: качественный товар с отличными характеристиками."


# ── REST search endpoint ──────────────────────────────────────────────────────

def search_products_with_ai(query: str, user=None) -> dict:
    default = {"categories": [], "keywords": query.split(),
                "price_range": {"min": None, "max": None}, "filters": {}}
    if not _configure_genai():
        return default

    prompt = (
        f'Analyse this search query: "{query}"\n'
        'Return ONLY valid JSON:\n'
        '{"categories":[],"keywords":[],"price_range":{"min":null,"max":null},"filters":{}}'
    )
    for model_name in CANDIDATE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            return json.loads((resp.text or "").strip())
        except Exception as e:
            logger.warning("search_products_with_ai: %s failed: %s", model_name, e)
            continue

    return default


# ── Semantic / vector search ──────────────────────────────────────────────────

def cosine_similarity(a, b) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def build_product_text(product) -> str:
    parts = [product.name or "", product.description or ""]
    if product.category:
        parts.append(product.category.name)
    if hasattr(product, "attributes"):
        parts.extend(f"{a.name}: {a.value}" for a in product.attributes.all())
    return "\n".join(p for p in parts if p)


def embed_text(text: str, task_type: str = "retrieval_document"):
    if not _configure_genai():
        return None
    try:
        resp = genai.embed_content(
            model=EMBEDDING_MODEL_NAME,
            content=text,
            task_type=task_type,
        )
        return resp["embedding"]
    except Exception as e:
        logger.error("embed_text error: %s", e)
        return None


def ensure_product_embedding(product):
    embedding_obj, _ = ProductEmbedding.objects.get_or_create(
        product=product,
        defaults={"vector": [], "source_model": EMBEDDING_MODEL_NAME, "dim": 0},
    )
    needs_refresh = not embedding_obj.vector or embedding_obj.updated_at < product.updated_at
    if needs_refresh:
        vector = embed_text(build_product_text(product))
        if vector:
            embedding_obj.vector = vector
            embedding_obj.dim = len(vector)
            embedding_obj.source_model = EMBEDDING_MODEL_NAME
            embedding_obj.save(update_fields=["vector", "dim", "source_model", "updated_at"])
    return embedding_obj.vector


def semantic_vector_search(query_text: str, max_results: int = 5) -> list:
    query_vector = embed_text(query_text, task_type="retrieval_query")
    if not query_vector:
        return []

    candidates = (Product.objects.filter(status="active")
                  .select_related("category")
                  .prefetch_related("attributes"))
    scored = []
    for product in candidates:
        pv = ensure_product_embedding(product)
        if not pv:
            continue
        scored.append((cosine_similarity(query_vector, pv), product))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for score, p in scored[:max_results] if score > 0.1]


def merge_product_lists(primary, secondary) -> list:
    seen: set = set()
    merged: list = []
    for p in list(primary) + list(secondary):
        if p.id not in seen:
            seen.add(p.id)
            merged.append(p)
    return merged
