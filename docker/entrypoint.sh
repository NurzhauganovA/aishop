#!/bin/bash
set -e

echo "================================================"
echo "  AIShop Marketplace — Startup"
echo "================================================"

# Ждём PostgreSQL
echo "⏳ Ожидание PostgreSQL..."
until pg_isready -h "${DB_HOST:-db}" -p "${DB_PORT:-5432}" -U "${DB_USER:-aishop_user}"; do
  >&2 echo "   PostgreSQL не готов, ждём..."
  sleep 2
done
echo "✅ PostgreSQL готов"

# Статика
echo ""
echo "📦 Сбор статических файлов..."
python manage.py collectstatic --noinput 2>&1 | tail -3
echo "✅ Статика собрана"

# ── Миграции ────────────────────────────────────────────────────
# Django сам генерирует миграции для всех приложений.
# --fake-initial: если таблицы уже существуют (повторный запуск) —
#   пропускает CREATE TABLE и просто записывает в django_migrations.
echo ""
echo "📝 Генерация миграций..."
python manage.py makemigrations \
    accounts products orders chat notifications ai_assistant user_activities \
    --noinput 2>&1
python manage.py makemigrations --noinput 2>/dev/null || true
echo "✅ Миграции сгенерированы"

echo ""
echo "🗄️  Применение миграций..."
python manage.py migrate --fake-initial --noinput
echo "✅ Миграции применены"

# Суперпользователь
echo ""
echo "👤 Проверка суперпользователя..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123456')
    user.role = 'admin'
    user.save()
    print('✓ admin / admin123456 создан')
else:
    print('  admin уже существует')
"

# Seed demo data (only if DB is empty)
echo ""
echo "🛍️  Загрузка демо-товаров..."
python manage.py shell -c "
from apps.products.models import Product, Category
if not Product.objects.exists():
    import subprocess
    result = subprocess.run(['python', 'manage.py', 'seed_data'], capture_output=True, text=True)
    print(result.stdout[-500:] if result.stdout else 'No output')
    if result.returncode != 0:
        print('Seed error:', result.stderr[-300:])
    else:
        print('✅ Демо-товары загружены')
else:
    print(f'  Товаров уже {Product.objects.count()}, пропускаем')
" 2>&1

# Legacy fixtures (kept for compatibility)
python manage.py loaddata apps/products/fixtures/initial_data.json 2>/dev/null || true

# Site
python manage.py shell -c "
import os
from django.contrib.sites.models import Site
domain = os.environ.get('SITE_DOMAIN', 'donor.asia')
Site.objects.update_or_create(id=1, defaults={'domain': domain, 'name': 'AIShop'})
print(f'  Site: {domain}')
" 2>/dev/null || true

echo ""
echo "🎉 AIShop готов!"
echo "   URL:   https://${SITE_DOMAIN:-donor.asia}"
echo "   Admin: admin / admin123456"
echo ""
echo "🚀 Запуск Daphne..."
exec daphne -b 0.0.0.0 -p 8000 marketplace.asgi:application
