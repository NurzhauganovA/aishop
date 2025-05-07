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
