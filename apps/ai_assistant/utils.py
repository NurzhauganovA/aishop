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

# ── Model selection ───────────────────────────────────────────────────────────
# Tried in order until one works
CANDIDATE_MODELS = [
    'gemini-1.5-flash',
    'gemini-1.5-pro',
    'gemini-pro',
    'gemini-1.0-pro',
]
EMBEDDING_MODEL_NAME = "models/embedding-001"

_configured = False


def _configure_genai():
    """Configure Gemini once; returns True if key is present."""
    global _configured
    if _configured:
        return True
    key = getattr(settings, 'GEMINI_API_KEY', '') or ''
    if not key or key.startswith('ЗАМЕНИ') or len(key) < 10:
        logger.warning("GEMINI_API_KEY is not set — AI features will use keyword-only search")
        return False
    genai.configure(api_key=key)
    _configured = True
    return True


def _get_model(model_name=None):
    """Return the first working GenerativeModel."""
    candidates = [model_name] + CANDIDATE_MODELS if model_name else CANDIDATE_MODELS
    for name in candidates:
        if not name:
            continue
        try:
            m = genai.GenerativeModel(name)
            # Quick smoke-test: just constructing the object is enough
            return m, name
        except Exception:
            continue
    return None, None


class RateLimiter:
    def __init__(self, max_calls=20, period=60):
        self.max_calls = max_calls
        self.period = period
        self.calls = []

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


@RateLimiter(max_calls=15, period=60)
def generate_ai_product_description(product_name, attributes):
    """Generate product description with Gemini AI."""
    if not _configure_genai():
        return f"Описание для '{product_name}': качественный товар с отличными характеристиками."

    prompt = (
        f"Создай привлекательное описание для товара \"{product_name}\" "
        f"на основе характеристик:\n{json.dumps(attributes, indent=2, ensure_ascii=False)}\n"
        "Пиши на русском, 2-3 абзаца, маркетинговый стиль."
    )

    model, name = _get_model()
    if model is None:
        return f"Описание для '{product_name}': качественный товар."

    try:
        resp = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=600,
            )
        )
        return resp.text.strip()
    except Exception as e:
        logger.error(f"generate_ai_product_description error ({name}): {e}")
        return f"Ошибка при генерации описания: {e}"


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
  "keywords": ["word1", "word2"],
  "categories": ["CategoryName"],
  "price_range": {"min": null, "max": null},
  "filters": {"color": "black", "storage": "512"}
}

For general questions/greetings — reply with friendly plain text, NO JSON.
Never invent products. Never link to external sites."""


@RateLimiter(max_calls=15, period=60)
def chat_with_ai_assistant(user, message, conversation_history=None):
    """Main chat function — tries Gemini, falls back to keyword search."""
    try:
        AISearchQuery.objects.create(user=user, query=message)
    except Exception:
        pass

    # ── Try Gemini AI first ───────────────────────────────────────────────
    if _configure_genai():
        response_text = _call_gemini(message, conversation_history)
        if response_text is not None:
            return _process_ai_response(response_text, message)

    # ── Fallback: keyword-based DB search ────────────────────────────────
    logger.info("Falling back to keyword search for: %s", message)
    return _keyword_fallback(message)


def _call_gemini(message, conversation_history):
    """Call Gemini API. Returns text or None on failure."""
    model, model_name = _get_model()
    if model is None:
        logger.error("No working Gemini model found")
        return None

    # Build prompt: prepend system instructions to first user message
    # (v0.3.x does not support system_instruction parameter)
    first_user_content = f"{SYSTEM_PROMPT}\n\n---\nUser: {message}"

    # Build history with proper alternation (user → model → user → model …)
    history = []
    if conversation_history:
        msgs = list(conversation_history)
        # We need pairs (user, model). If odd count, drop the first one.
        paired = []
        i = 0
        while i < len(msgs):
            if msgs[i].role == 'user' and i + 1 < len(msgs) and msgs[i + 1].role == 'ai':
                paired.append((msgs[i], msgs[i + 1]))
                i += 2
            else:
                i += 1

        # Keep last 5 pairs to stay within token limit
        for u_msg, a_msg in paired[-5:]:
            history.append({"role": "user",  "parts": [u_msg.content]})
            history.append({"role": "model", "parts": [a_msg.content]})

    try:
        if history:
            # Start chat with history, then send current message with system prompt
            chat = model.start_chat(history=history)
            resp = chat.send_message(
                first_user_content,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.5,
                    max_output_tokens=800,
                )
            )
        else:
            # No history — use generate_content directly (simpler, more reliable)
            resp = model.generate_content(
                first_user_content,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.5,
                    max_output_tokens=800,
                )
            )

        text = resp.text.strip() if resp.text else ""
        logger.info("Gemini (%s) response: %s", model_name, text[:200])
        return text

    except Exception as e:
        logger.error("Gemini call failed (%s): %s", model_name, e)
        return None


def _process_ai_response(text, original_message):
    """Parse Gemini response — handle JSON search request or plain text."""
    # Try to extract JSON from the response
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = text[start:end]
            data = json.loads(json_str)
            if isinstance(data, dict) and data.get('search_request'):
                keywords = data.get('keywords', [])
                results = list(perform_actual_search(data, user=None))
                vector_hits = []
                try:
                    vector_hits = semantic_vector_search(original_message, max_results=5)
                except Exception:
                    pass
                combined = merge_product_lists(results, vector_hits)
                if combined:
                    return format_search_results(combined, search_keywords=keywords)
                # No results — suggest catalog search
                q = '+'.join(keywords) if keywords else ''
                return (
                    f"К сожалению, товары по вашему запросу не найдены на нашем сайте.\n\n"
                    f"👉 [Попробуйте поиск в каталоге](/products/?q={q})"
                )
    except (json.JSONDecodeError, ValueError):
        pass

    # Plain text response — still try vector search if it looks like a product query
    product_keywords = ['найди', 'покажи', 'хочу', 'ищу', 'есть ли', 'find', 'show',
                        'тауып', 'табу', 'көрсет', 'бар ма']
    is_search = any(kw in original_message.lower() for kw in product_keywords)
    if is_search:
        try:
            hits = semantic_vector_search(original_message, max_results=5)
            if hits:
                return format_search_results(hits)
        except Exception:
            pass

    return text


def _keyword_fallback(message):
    """Pure keyword search when Gemini is unavailable."""
    words = [w for w in message.split() if len(w) > 2]
    if not words:
        return (
            "Привет! Я AISha — ИИ-ассистент SmartShop. "
            "Опишите, какой товар вы ищете, и я найду его в нашем каталоге.\n\n"
            "👉 [Открыть каталог](/products/)"
        )

    q_filter = Q()
    for w in words:
        q_filter |= Q(name__icontains=w) | Q(description__icontains=w)

    products = list(Product.objects.filter(status='active').filter(q_filter)[:8])
    if products:
        return format_search_results(products, search_keywords=words)

    # Try category match
    for w in words:
        cats = Category.objects.filter(name__icontains=w)
        if cats.exists():
            products = list(Product.objects.filter(status='active', category__in=cats)[:6])
            if products:
                return format_search_results(products, search_keywords=words)

    q = '+'.join(words[:3])
    return (
        f"Товары по запросу **«{message}»** не найдены.\n\n"
        f"👉 [Посмотреть весь каталог](/products/?q={q})"
    )


# ── Search helpers ────────────────────────────────────────────────────────────

def perform_actual_search(search_params, user=None):
    """DB product search from AI-parsed params."""
    products = Product.objects.filter(status='active').select_related('category')

    if search_params.get('categories'):
        cats = Category.objects.filter(name__in=search_params['categories'])
        if cats.exists():
            products = products.filter(category__in=cats)

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

    # Apply extra filters (color, storage, etc.) via ProductAttribute
    for key, value in (search_params.get('filters') or {}).items():
        products = products.filter(
            attributes__name__icontains=key,
            attributes__value__icontains=str(value)
        )

    return products.distinct()


def format_search_results(products, max_results=5, search_keywords=None):
    """Format product list as markdown text with clickable links."""
    from urllib.parse import quote_plus

    if hasattr(products, 'exists'):
        products = list(products)
    if not products:
        return "К сожалению, товары по вашему запросу не найдены."

    total = len(products)
    shown = products[:max_results]
    result = f"Нашла **{total}** товар(ов) по вашему запросу:\n\n"

    for i, p in enumerate(shown, 1):
        url = p.get_absolute_url()
        price_str = f"{p.price} ₸"
        result += f"**{i}. [{p.name}]({url})**\n"
        result += f"   💰 {price_str}"
        if p.old_price and p.old_price > p.price:
            disc = round(100 - float(p.price) / float(p.old_price) * 100)
            result += f"  ~~{p.old_price} ₸~~ (-{disc}%)"
        result += "\n"
        if p.description:
            desc = p.description[:100] + "…" if len(p.description) > 100 else p.description
            result += f"   _{desc}_\n"
        result += f"   🔗 [Смотреть товар]({url})\n\n"

    if total > max_results:
        q = quote_plus(' '.join(search_keywords)) if search_keywords else ''
        catalog_url = f"/products/?q={q}" if q else "/products/"
        result += f"_…ещё {total - max_results} товаров_\n"
        result += f"👉 [Все результаты в каталоге]({catalog_url})"

    return result


def search_products_with_ai(query, user=None):
    """AI-powered search for REST endpoint."""
    if not _configure_genai():
        return {
            "categories": [],
            "keywords": query.split(),
            "price_range": {"min": None, "max": None},
            "filters": {}
        }

    model, _ = _get_model()
    if model is None:
        return {"categories": [], "keywords": query.split(),
                "price_range": {"min": None, "max": None}, "filters": {}}

    prompt = (
        f'Analyse this search query: "{query}"\n'
        'Return ONLY valid JSON, no extra text:\n'
        '{"categories":[],"keywords":[],"price_range":{"min":null,"max":null},"filters":{}}'
    )

    try:
        resp = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
        )
        return json.loads(resp.text.strip())
    except Exception as e:
        logger.error("search_products_with_ai error: %s", e)
        return {"categories": [], "keywords": query.split(),
                "price_range": {"min": None, "max": None}, "filters": {}}


# ── Semantic / vector search ──────────────────────────────────────────────────

def cosine_similarity(a, b):
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def build_product_text(product):
    parts = [product.name or "", product.description or ""]
    if product.category:
        parts.append(product.category.name)
    if hasattr(product, "attributes"):
        parts.extend(f"{a.name}: {a.value}" for a in product.attributes.all())
    return "\n".join(p for p in parts if p)


def embed_text(text, task_type="retrieval_document"):
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


def semantic_vector_search(query_text, max_results=5):
    """Semantic search via embeddings. Returns [] if embeddings unavailable."""
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


def merge_product_lists(primary, secondary):
    seen = set()
    merged = []
    for p in list(primary) + list(secondary):
        if p.id not in seen:
            seen.add(p.id)
            merged.append(p)
    return merged
