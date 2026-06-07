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

# Удалить ВСЕ старые миграции — Django сгенерирует чистые при старте
RUN find /app/apps -path "*/migrations/*.py" ! -name "__init__.py" -delete

RUN mkdir -p /app/static /app/media /app/staticfiles

RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000
