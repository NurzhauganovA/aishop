from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_cart_review_wishlist_reviewimage_productvideo_and_more'),
        ('ai_assistant', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductEmbedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vector', models.JSONField(default=list, verbose_name='Вектор')),
                ('dim', models.PositiveIntegerField(default=0, verbose_name='Размерность')),
                ('source_model', models.CharField(default='models/embedding-001', max_length=100, verbose_name='Модель эмбеддинга')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='embedding', to='products.product')),
            ],
            options={
                'verbose_name': 'Эмбеддинг товара',
                'verbose_name_plural': 'Эмбеддинги товаров',
            },
        ),
    ]

