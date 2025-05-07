#!/bin/bash
set -e

# Ожидаем готовности PostgreSQL
until pg_isready -h db -p 5432; do
  >&2 echo "PostgreSQL еще не готов - ждем..."
  sleep 1
done

>&2 echo "PostgreSQL готов - продолжаем..."

# Создаем директорию для статических файлов
mkdir -p /app/staticfiles
echo "Директория для статических файлов создана или уже существует"

# Собираем статические файлы
python manage.py collectstatic --noinput

# # 5. Удаляем существующие миграции, чтобы начать с чистого листа
# echo "Удаляем существующие миграции для предотвращения конфликтов..."
# find /app/apps -path "*/migrations/*.py" -not -name "__init__.py" -delete

# 6. Создаем пустые начальные миграции с правильными зависимостями
echo "Создаем начальные миграции для разрыва циклической зависимости..."

# Базовая миграция для accounts
python manage.py makemigrations accounts --empty --name initial_accounts
ACCOUNTS_MIGRATION=$(find /app/apps/accounts/migrations -name "0001_initial_accounts.py")
cat > $ACCOUNTS_MIGRATION << 'EOF'
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
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(max_length=150, unique=True)),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='Email')),
                ('first_name', models.CharField(blank=True, max_length=150)),
                ('last_name', models.CharField(blank=True, max_length=150)),
                ('is_staff', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now)),
                ('phone_number', models.CharField(blank=True, max_length=15, null=True, verbose_name='Номер телефона')),
                ('role', models.CharField(choices=[('buyer', 'Покупатель'), ('seller', 'Продавец'), ('admin', 'Администратор')], default='buyer', max_length=10, verbose_name='Роль')),
                ('is_online', models.BooleanField(default=False, verbose_name='В сети')),
                ('last_activity', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Последняя активность')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'abstract': False,
            },
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
            options={
                'verbose_name': 'Адрес',
                'verbose_name_plural': 'Адреса',
            },
        ),
    ]
EOF

# Базовая миграция для products
python manage.py makemigrations products --empty --name initial_products
PRODUCTS_MIGRATION=$(find /app/apps/products/migrations -name "0001_initial_products.py")
cat > $PRODUCTS_MIGRATION << 'EOF'
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
            options={
                'verbose_name': 'Категория',
                'verbose_name_plural': 'Категории',
            },
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
                ('status', models.CharField(choices=[('active', 'Активен'), ('archive', 'Архив'), ('out_of_stock', 'Нет в наличии')], default='active', max_length=20, verbose_name='Статус')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='products.category', verbose_name='Категория')),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='accounts.customuser', verbose_name='Продавец')),
            ],
            options={
                'verbose_name': 'Товар',
                'verbose_name_plural': 'Товары',
            },
        ),
    ]
EOF

# Базовая миграция для user_activities
python manage.py makemigrations user_activities --empty --name initial_user_activity
USER_ACTIVITIES_MIGRATION=$(find /app/apps/user_activities/migrations -name "0001_initial_user_activity.py")
cat > $USER_ACTIVITIES_MIGRATION << 'EOF'
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
EOF

# 7. Применяем миграции в правильном порядке
echo "Применяем миграции в правильном порядке..."

# Базовые приложения Django
python manage.py migrate auth
python manage.py migrate contenttypes
echo "Применяем миграции для accounts..."
python manage.py migrate accounts
echo "Применяем миграции для admin..."
python manage.py migrate admin
echo "Применяем миграции для products..."
python manage.py migrate products
echo "Применяем миграции для user_activities..."
python manage.py migrate user_activities
echo "Применяем остальные миграции..."
python manage.py migrate sessions
python manage.py migrate sites

# 8. Создаем миграции для остальных приложений
echo "Создаем миграции для остальных приложений..."
python manage.py makemigrations orders chat notifications ai_assistant
python manage.py migrate

# 9. Создаем суперпользователя
echo "Проверяем наличие суперпользователя..."
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123456');
    user.role = 'admin';
    user.save();
    print('Суперпользователь создан');
else:
    admin_user = User.objects.get(username='admin');
    if admin_user.role != 'admin':
        admin_user.role = 'admin';
        admin_user.save();
        print('Роль суперпользователя обновлена до admin');
    else:
        print('Суперпользователь уже существует');
"

# 10. Загружаем начальные данные
echo "Загружаем начальные данные..."
python manage.py loaddata initial_data.json || echo "Нет начальных данных для загрузки"

# 11. Запускаем сервер
echo "Запускаем Django сервер..."
exec python manage.py runserver 0.0.0.0:8000