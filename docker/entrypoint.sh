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

# Собираем статику
echo ""
echo "📦 Сбор статических файлов..."
python manage.py collectstatic --noinput 2>&1 | tail -3
echo "✅ Статика собрана"

# ── Начальные миграции (пишем файлы НАПРЯМУЮ, без makemigrations) ──

echo ""
echo "📝 Проверка начальных миграций..."

# accounts/0001
if [ ! -f "/app/apps/accounts/migrations/0001_initial_accounts.py" ]; then
  echo "   → Создаём accounts/0001..."
  cat > /app/apps/accounts/migrations/0001_initial_accounts.py << 'MIGRATION_EOF'
from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [
        migrations.CreateModel(
            name='CustomUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False)),
                ('username', models.CharField(max_length=150, unique=True)),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='Email')),
                ('first_name', models.CharField(blank=True, max_length=150)),
                ('last_name', models.CharField(blank=True, max_length=150)),
                ('is_staff', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now)),
                ('phone_number', models.CharField(blank=True, max_length=15, null=True, verbose_name='Номер телефона')),
                ('role', models.CharField(choices=[('buyer','Покупатель'),('seller','Продавец'),('admin','Администратор')], default='buyer', max_length=10, verbose_name='Роль')),
                ('is_online', models.BooleanField(default=False, verbose_name='В сети')),
                ('last_activity', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Последняя активность')),
                ('avatar', models.ImageField(blank=True, null=True, upload_to='avatars/', verbose_name='Аватар')),
                ('groups', models.ManyToManyField(blank=True, related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100, verbose_name='Название')),
                ('full_name', models.CharField(max_length=100, verbose_name='Полное имя')),
                ('phone', models.CharField(max_length=15, verbose_name='Телефон')),
                ('city', models.CharField(max_length=100, verbose_name='Город')),
                ('postal_code', models.CharField(blank=True, max_length=20, verbose_name='Почтовый индекс')),
                ('address_line1', models.CharField(max_length=255, verbose_name='Адрес')),
                ('address_line2', models.CharField(blank=True, max_length=255, verbose_name='Дополнительный адрес')),
                ('is_default', models.BooleanField(default=False, verbose_name='По умолчанию')),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='addresses', to='accounts.customuser')),
            ],
            options={'verbose_name': 'Адрес', 'verbose_name_plural': 'Адреса'},
        ),
    ]
MIGRATION_EOF
  echo "   ✓ accounts/0001 создана"
fi

# products/0001 (0002 уже существует и зависит от него)
if [ ! -f "/app/apps/products/migrations/0001_initial_products.py" ]; then
  echo "   → Создаём products/0001..."
  cat > /app/apps/products/migrations/0001_initial_products.py << 'MIGRATION_EOF'
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('accounts', '0001_initial_accounts'),
    ]
    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название')),
                ('slug', models.SlugField(max_length=100, unique=True, verbose_name='Слаг')),
                ('image', models.ImageField(blank=True, null=True, upload_to='categories/', verbose_name='Изображение')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='products.category', verbose_name='Родительская категория')),
            ],
            options={'verbose_name': 'Категория', 'verbose_name_plural': 'Категории'},
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Название')),
                ('slug', models.SlugField(max_length=200, unique=True, verbose_name='Слаг')),
                ('description', models.TextField(verbose_name='Описание')),
                ('price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Цена')),
                ('old_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Старая цена')),
                ('stock', models.PositiveIntegerField(verbose_name='Количество')),
                ('status', models.CharField(choices=[('active','Активен'),('archive','Архив'),('out_of_stock','Нет в наличии')], default='active', max_length=20, verbose_name='Статус')),
                ('is_featured', models.BooleanField(default=False, verbose_name='Рекомендуемый')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='products.category', verbose_name='Категория')),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='accounts.customuser', verbose_name='Продавец')),
            ],
            options={'verbose_name': 'Товар', 'verbose_name_plural': 'Товары'},
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='products/', verbose_name='Изображение')),
                ('is_main', models.BooleanField(default=False, verbose_name='Главное')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='products.product')),
            ],
            options={'verbose_name': 'Изображение товара', 'verbose_name_plural': 'Изображения товаров'},
        ),
    ]
MIGRATION_EOF
  echo "   ✓ products/0001 создана"
fi

# user_activities/0001
if [ ! -f "/app/apps/user_activities/migrations/0001_initial_user_activity.py" ]; then
  echo "   → Создаём user_activities/0001..."
  cat > /app/apps/user_activities/migrations/0001_initial_user_activity.py << 'MIGRATION_EOF'
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('accounts', '0001_initial_accounts'),
        ('products', '0001_initial_products'),
    ]
    operations = [
        migrations.CreateModel(
            name='UserActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('view_time', models.IntegerField(default=0, verbose_name='Время просмотра (сек)')),
                ('view_count', models.IntegerField(default=1, verbose_name='Количество просмотров')),
                ('last_viewed', models.DateTimeField(auto_now=True, verbose_name='Последний просмотр')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_activities', to='products.product')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='accounts.customuser')),
            ],
            options={
                'verbose_name': 'Активность пользователя',
                'verbose_name_plural': 'Активности пользователей',
                'unique_together': {('user', 'product')},
            },
        ),
    ]
MIGRATION_EOF
  echo "   ✓ user_activities/0001 создана"
fi

echo "✅ Начальные миграции готовы"

# ── Генерируем миграции для остальных приложений ──
echo ""
echo "📝 Генерация миграций для orders/chat/notifications/ai_assistant..."
python manage.py makemigrations orders chat notifications ai_assistant --noinput 2>/dev/null || true
python manage.py makemigrations --noinput 2>/dev/null || true

# ── Применяем миграции ──
echo ""
echo "🗄️  Применение миграций..."
python manage.py migrate auth --noinput
python manage.py migrate contenttypes --noinput
python manage.py migrate accounts --noinput
python manage.py migrate admin --noinput
python manage.py migrate products --noinput
python manage.py migrate user_activities --noinput
python manage.py migrate --noinput
echo "✅ Миграции применены"

# ── Суперпользователь ──
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

# ── Категории ──
echo ""
echo "📦 Загрузка категорий..."
python manage.py loaddata apps/products/fixtures/initial_data.json 2>/dev/null \
  && echo "✅ Категории загружены" \
  || echo "  Категории уже загружены"

# ── Site ──
python manage.py shell -c "
from django.contrib.sites.models import Site
import os
domain = os.environ.get('SITE_DOMAIN', 'donor.asia')
Site.objects.update_or_create(id=1, defaults={'domain': domain, 'name': 'AIShop'})
" 2>/dev/null || true

echo ""
echo "🎉 AIShop готов!"
echo "   URL:   https://${SITE_DOMAIN:-donor.asia}"
echo "   Admin: admin / admin123456"
echo ""
echo "🚀 Запуск Daphne..."
exec daphne -b 0.0.0.0 -p 8000 marketplace.asgi:application
