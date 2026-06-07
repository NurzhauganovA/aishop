FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        gettext \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . /app/

# Clean up duplicate migrations (only keep __init__.py + real 0002 for products)
RUN find /app/apps/accounts/migrations    -name "*.py" ! -name "__init__.py" -delete && \
    find /app/apps/user_activities/migrations -name "*.py" ! -name "__init__.py" -delete && \
    find /app/apps/products/migrations    -name "*.py" \
        ! -name "__init__.py" \
        ! -name "0002_cart_review_wishlist_reviewimage_productvideo_and_more.py" \
        -delete && \
    mkdir -p /app/apps/accounts/migrations \
             /app/apps/products/migrations \
             /app/apps/orders/migrations \
             /app/apps/chat/migrations \
             /app/apps/notifications/migrations \
             /app/apps/ai_assistant/migrations \
             /app/apps/user_activities/migrations

RUN mkdir -p /app/static /app/media /app/staticfiles

RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000
