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
