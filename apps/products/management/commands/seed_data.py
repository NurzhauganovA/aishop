"""
Management command to populate the database with demo products.
Usage: python manage.py seed_data
       python manage.py seed_data --clear  (clears existing data first)
"""
import os
import io
import random
import urllib.request
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.core.files import File
from django.utils.text import slugify
from django.contrib.auth import get_user_model

from apps.products.models import Category, Product, ProductImage, ProductAttribute

User = get_user_model()

# ─── Image placeholder service ───────────────────────────────────────────────
# Uses picsum.photos which returns real CC0 photos by seed
def placeholder_url(seed: int, width=600, height=600):
    return f"https://picsum.photos/seed/{seed}/{width}/{height}"

# Curated Unsplash image IDs for product categories
PRODUCT_IMAGES = {
    "smartphone": [
        "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=600&q=80",
        "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=600&q=80",
        "https://images.unsplash.com/photo-1580910051074-3eb694886505?w=600&q=80",
        "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=600&q=80",
    ],
    "laptop": [
        "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=600&q=80",
        "https://images.unsplash.com/photo-1484788984921-03950022c9ef?w=600&q=80",
        "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=600&q=80",
    ],
    "headphones": [
        "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
        "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=600&q=80",
        "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=600&q=80",
    ],
    "watch": [
        "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
        "https://images.unsplash.com/photo-1508057198894-247b23fe5ade?w=600&q=80",
        "https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=600&q=80",
    ],
    "shoes": [
        "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80",
        "https://images.unsplash.com/photo-1600185365926-3a2ce3cdb9eb?w=600&q=80",
        "https://images.unsplash.com/photo-1539185441755-769473a23570?w=600&q=80",
    ],
    "backpack": [
        "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600&q=80",
        "https://images.unsplash.com/photo-1581605405669-fcdf81165afa?w=600&q=80",
    ],
    "camera": [
        "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80",
        "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=600&q=80",
    ],
    "tshirt": [
        "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600&q=80",
        "https://images.unsplash.com/photo-1583744946564-b52ac1c389c8?w=600&q=80",
    ],
    "tablet": [
        "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=600&q=80",
        "https://images.unsplash.com/photo-1561154464-82e9adf32764?w=600&q=80",
    ],
    "default": [
        "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
        "https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=600&q=80",
    ],
}

PRODUCTS_DATA = [
    # ── Смартфоны ──────────────────────────────────────────────────────────
    {
        "name": "iPhone 15 Pro Max 256GB Чёрный",
        "category": "Смартфоны",
        "price": 649000, "old_price": 720000, "stock": 15,
        "description": "Флагманский смартфон Apple с чипом A17 Pro, 48 Мп камерой, ProMotion дисплеем 120 Гц и USB-C. Корпус из титана, Dynamic Island.",
        "attrs": [("Цвет", "Чёрный"), ("Память", "256 ГБ"), ("ОЗУ", "8 ГБ"), ("Экран", "6.7\""), ("Чип", "A17 Pro")],
        "img_key": "smartphone",
    },
    {
        "name": "iPhone 15 Pro 512GB Натуральный титан",
        "category": "Смартфоны",
        "price": 729000, "old_price": None, "stock": 8,
        "description": "iPhone 15 Pro с 512 ГБ памяти. Камера 48 Мп, оптический зум 5x, Action Button, USB-C 3.0.",
        "attrs": [("Цвет", "Натуральный титан"), ("Память", "512 ГБ"), ("ОЗУ", "8 ГБ"), ("Экран", "6.1\"")],
        "img_key": "smartphone",
    },
    {
        "name": "Samsung Galaxy S24 Ultra 12/256GB Чёрный",
        "category": "Смартфоны",
        "price": 549000, "old_price": 620000, "stock": 20,
        "description": "Топовый Android-флагман с S-Pen, 200 Мп камерой, Snapdragon 8 Gen 3 и 6.8\" QHD+ дисплеем.",
        "attrs": [("Цвет", "Чёрный"), ("Память", "256 ГБ"), ("ОЗУ", "12 ГБ"), ("Экран", "6.8\"")],
        "img_key": "smartphone",
    },
    {
        "name": "Samsung Galaxy A55 8/256GB Синий",
        "category": "Смартфоны",
        "price": 189000, "old_price": 210000, "stock": 35,
        "description": "Стильный смартфон среднего класса с AMOLED-дисплеем 120 Гц, тройной камерой 50 Мп и защитой IP67.",
        "attrs": [("Цвет", "Синий"), ("Память", "256 ГБ"), ("ОЗУ", "8 ГБ")],
        "img_key": "smartphone",
    },
    {
        "name": "Xiaomi 14 Ultra 16/512GB Белый",
        "category": "Смартфоны",
        "price": 479000, "old_price": 530000, "stock": 12,
        "description": "Профессиональная камерная система Leica, Snapdragon 8 Gen 3, 90W зарядка. Четыре камеры 50 Мп.",
        "attrs": [("Цвет", "Белый"), ("Память", "512 ГБ"), ("ОЗУ", "16 ГБ"), ("Камера", "50 Мп × 4")],
        "img_key": "smartphone",
    },
    {
        "name": "Google Pixel 8 Pro 12/256GB Чёрный",
        "category": "Смартфоны",
        "price": 359000, "old_price": 400000, "stock": 10,
        "description": "Чистый Android с фотофишками Google — функции ИИ, Tensor G3, лучшая в классе камера 50 Мп.",
        "attrs": [("Цвет", "Чёрный"), ("Память", "256 ГБ"), ("ОЗУ", "12 ГБ"), ("Обновления", "7 лет")],
        "img_key": "smartphone",
    },

    # ── Ноутбуки ────────────────────────────────────────────────────────────
    {
        "name": "Apple MacBook Pro 14\" M3 Pro 18/512GB",
        "category": "Ноутбуки",
        "price": 899000, "old_price": 980000, "stock": 7,
        "description": "Профессиональный ноутбук с чипом M3 Pro, Liquid Retina XDR дисплеем, до 22 часов автономной работы.",
        "attrs": [("Процессор", "Apple M3 Pro"), ("ОЗУ", "18 ГБ"), ("SSD", "512 ГБ"), ("Дисплей", "14.2\" MiniLED"), ("Цвет", "Space Gray")],
        "img_key": "laptop",
    },
    {
        "name": "Apple MacBook Air 15\" M3 8/256GB",
        "category": "Ноутбуки",
        "price": 699000, "old_price": None, "stock": 14,
        "description": "Самый тонкий 15\" ноутбук Apple. M3, IPS 2880×1864, MagSafe, две камеры Thunderbolt 4.",
        "attrs": [("Процессор", "Apple M3"), ("ОЗУ", "8 ГБ"), ("SSD", "256 ГБ"), ("Цвет", "Midnight")],
        "img_key": "laptop",
    },
    {
        "name": "ASUS ROG Zephyrus G14 AMD Ryzen 9 / RTX 4070",
        "category": "Ноутбуки",
        "price": 649000, "old_price": 720000, "stock": 6,
        "description": "Геймерский ноутбук с AMD Ryzen 9 8945HS, RTX 4070, 165 Гц QHD+ дисплеем и 73 Вт/ч батареей.",
        "attrs": [("Процессор", "AMD Ryzen 9 8945HS"), ("Видеокарта", "RTX 4070"), ("ОЗУ", "16 ГБ"), ("SSD", "1 ТБ")],
        "img_key": "laptop",
    },
    {
        "name": "Lenovo ThinkPad X1 Carbon Gen 12 Intel Core Ultra 7",
        "category": "Ноутбуки",
        "price": 589000, "old_price": None, "stock": 9,
        "description": "Бизнес-ультрабук. Вес 1.12 кг, 14\" OLED 2K, Intel Core Ultra 7, MIL-SPEC прочность.",
        "attrs": [("Процессор", "Intel Core Ultra 7 165U"), ("ОЗУ", "32 ГБ"), ("SSD", "1 ТБ"), ("Дисплей", "14\" OLED")],
        "img_key": "laptop",
    },
    {
        "name": "HP Spectre x360 14\" OLED Intel Core Ultra 9",
        "category": "Ноутбуки",
        "price": 529000, "old_price": 599000, "stock": 5,
        "description": "Трансформер 2-в-1 с 14\" OLED 120 Гц, Core Ultra 9, активным стилусом и Thunderbolt 4.",
        "attrs": [("Процессор", "Intel Core Ultra 9"), ("ОЗУ", "16 ГБ"), ("SSD", "1 ТБ"), ("Форм-фактор", "2-в-1")],
        "img_key": "laptop",
    },

    # ── Наушники ─────────────────────────────────────────────────────────────
    {
        "name": "Apple AirPods Pro 2 (USB-C)",
        "category": "Наушники",
        "price": 139000, "old_price": 159000, "stock": 40,
        "description": "Беспроводные наушники с активным шумоподавлением H2, Адаптивным аудио, MagSafe и до 30 часов работы.",
        "attrs": [("Тип", "TWS"), ("АНШ", "Есть"), ("Автономность", "30 ч"), ("Соединение", "Bluetooth 5.3")],
        "img_key": "headphones",
    },
    {
        "name": "Sony WH-1000XM5 Чёрные",
        "category": "Наушники",
        "price": 129000, "old_price": 150000, "stock": 25,
        "description": "Лучшие накладные наушники с ANC: 30 часов работы, Ultra HD Audio, Speak-to-Chat, мультиточечное подключение.",
        "attrs": [("Тип", "Накладные"), ("АНШ", "Есть"), ("Автономность", "30 ч"), ("Кодеки", "LDAC, AAC, SBC")],
        "img_key": "headphones",
    },
    {
        "name": "Samsung Galaxy Buds3 Pro Белые",
        "category": "Наушники",
        "price": 89000, "old_price": 99000, "stock": 30,
        "description": "Флагманские TWS-наушники с ANC, Hi-Fi звуком 24-bit и адаптивным шумоподавлением.",
        "attrs": [("Тип", "TWS"), ("АНШ", "Есть"), ("Автономность", "22 ч")],
        "img_key": "headphones",
    },
    {
        "name": "Bose QuietComfort Ultra Наушники",
        "category": "Наушники",
        "price": 159000, "old_price": None, "stock": 15,
        "description": "Иммерсивное 3D-аудио, лучшее ANC в классе, 24 ч автономной работы, мягкое оголовье.",
        "attrs": [("Тип", "Накладные"), ("АНШ", "Premium"), ("Автономность", "24 ч")],
        "img_key": "headphones",
    },

    # ── Умные часы ───────────────────────────────────────────────────────────
    {
        "name": "Apple Watch Series 10 45mm GPS + LTE",
        "category": "Умные часы",
        "price": 229000, "old_price": 259000, "stock": 18,
        "description": "Самые тонкие Apple Watch. Always-On Retina дисплей, мониторинг здоровья, eSIM, S10 чип.",
        "attrs": [("Корпус", "45 мм"), ("Связь", "GPS + LTE"), ("ОС", "watchOS 11"), ("Материал", "Алюминий")],
        "img_key": "watch",
    },
    {
        "name": "Samsung Galaxy Watch 7 44mm LTE",
        "category": "Умные часы",
        "price": 159000, "old_price": 180000, "stock": 22,
        "description": "Умные часы на Wear OS 5, датчик BioActive 3-в-1, Galaxy AI, AMOLED дисплей.",
        "attrs": [("Корпус", "44 мм"), ("Связь", "GPS + LTE"), ("ОС", "Wear OS 5")],
        "img_key": "watch",
    },
    {
        "name": "Xiaomi Smart Band 9 Pro",
        "category": "Умные часы",
        "price": 29900, "old_price": 35000, "stock": 60,
        "description": "Фитнес-трекер с AMOLED-дисплеем 1.74\", GPS, 140 видов тренировок и 21 днями работы.",
        "attrs": [("Дисплей", "1.74\" AMOLED"), ("Автономность", "21 день"), ("Датчики", "ЧСС, SpO2, GPS")],
        "img_key": "watch",
    },

    # ── Кроссовки ─────────────────────────────────────────────────────────────
    {
        "name": "Nike Air Max 270 React Мужские Чёрные",
        "category": "Кроссовки",
        "price": 45000, "old_price": 55000, "stock": 50,
        "description": "Культовые кроссовки с подошвой Air Max 270 и React-пеной для максимальной амортизации и комфорта.",
        "attrs": [("Цвет", "Чёрный"), ("Размеры", "40-46"), ("Материал", "Mesh+Пена"), ("Сезон", "Весна-Лето")],
        "img_key": "shoes",
    },
    {
        "name": "Adidas Ultraboost 23 Бело-синие",
        "category": "Кроссовки",
        "price": 52000, "old_price": None, "stock": 35,
        "description": "Беговые кроссовки с технологией Boost и Continental-подошвой для отличного сцепления на любой поверхности.",
        "attrs": [("Цвет", "Белый/Синий"), ("Размеры", "38-47"), ("Технология", "Boost")],
        "img_key": "shoes",
    },
    {
        "name": "New Balance 990v6 Made in USA",
        "category": "Кроссовки",
        "price": 89000, "old_price": 98000, "stock": 20,
        "description": "Культовые американские кроссовки ручной сборки с замшевым верхом и пятой ENCAP.",
        "attrs": [("Производство", "USA"), ("Цвет", "Серый"), ("Размеры", "40-45")],
        "img_key": "shoes",
    },
    {
        "name": "Skechers GOrun Razor 5 Мужские",
        "category": "Кроссовки",
        "price": 32000, "old_price": 39000, "stock": 45,
        "description": "Лёгкие беговые кроссовки с гипер-взрывной пеной Hyper Burst и системой SPEED SOCK.",
        "attrs": [("Вес", "191 г"), ("Технология", "Hyper Burst"), ("Размеры", "40-46")],
        "img_key": "shoes",
    },

    # ── Рюкзаки ───────────────────────────────────────────────────────────────
    {
        "name": "Nike Sportswear Heritage Рюкзак Чёрный",
        "category": "Рюкзаки и сумки",
        "price": 18500, "old_price": 22000, "stock": 40,
        "description": "Стильный рюкзак с мягкими лямками, отделением для ноутбука 15\" и боковыми карманами для бутылок.",
        "attrs": [("Объём", "25 л"), ("Цвет", "Чёрный"), ("Материал", "100% Polyester")],
        "img_key": "backpack",
    },
    {
        "name": "Samsonite Classic Leather 15.6\" Коричневый",
        "category": "Рюкзаки и сумки",
        "price": 62000, "old_price": 75000, "stock": 12,
        "description": "Премиальный кожаный рюкзак для ноутбука 15.6\" с USB-портом для зарядки и TSA-замком.",
        "attrs": [("Материал", "Натуральная кожа"), ("Цвет", "Коричневый"), ("Замок", "TSA"), ("Ноутбук", "до 15.6\"")],
        "img_key": "backpack",
    },

    # ── Планшеты ────────────────────────────────────────────────────────────
    {
        "name": "Apple iPad Pro 13\" M4 Wi-Fi 256GB",
        "category": "Планшеты",
        "price": 569000, "old_price": 620000, "stock": 10,
        "description": "Тончайший планшет Apple на M4, Ultra Retina XDR OLED дисплей, Apple Pencil Pro, поддержка Magic Keyboard.",
        "attrs": [("Чип", "Apple M4"), ("Дисплей", "13\" OLED"), ("Память", "256 ГБ"), ("Подключение", "Wi-Fi 6E")],
        "img_key": "tablet",
    },
    {
        "name": "Samsung Galaxy Tab S10+ 12/256GB Wi-Fi",
        "category": "Планшеты",
        "price": 349000, "old_price": 389000, "stock": 14,
        "description": "12.4\" Dynamic AMOLED 2X, Snapdragon 8 Gen 3, S Pen в комплекте, DeX-режим рабочего стола.",
        "attrs": [("Дисплей", "12.4\" Dynamic AMOLED 2X"), ("Процессор", "Snapdragon 8 Gen 3"), ("ОЗУ", "12 ГБ"), ("S Pen", "Включён")],
        "img_key": "tablet",
    },

    # ── Одежда ──────────────────────────────────────────────────────────────
    {
        "name": "Nike Dri-FIT Мужская футболка Белая XL",
        "category": "Одежда",
        "price": 9500, "old_price": 12000, "stock": 100,
        "description": "Технологичная спортивная футболка с влагоотводящей технологией Dri-FIT для тренировок и бега.",
        "attrs": [("Размер", "XL"), ("Цвет", "Белый"), ("Материал", "100% Polyester"), ("Технология", "Dri-FIT")],
        "img_key": "tshirt",
    },
    {
        "name": "Adidas Originals Trefoil Hoodie Чёрный M",
        "category": "Одежда",
        "price": 18000, "old_price": 22000, "stock": 80,
        "description": "Классическое худи Adidas Originals из 100% хлопка с культовым логотипом Trefoil.",
        "attrs": [("Размер", "M"), ("Цвет", "Чёрный"), ("Материал", "100% Cotton")],
        "img_key": "tshirt",
    },

    # ── Фотоаппараты ─────────────────────────────────────────────────────────
    {
        "name": "Sony Alpha A7 IV Mirrorless 33 Мп Body",
        "category": "Фотоаппараты",
        "price": 649000, "old_price": None, "stock": 5,
        "description": "Полнокадровая беззеркалка Sony с 33 Мп сенсором BIONZ XR, 4K-видео 60p и Real-time Eye AF.",
        "attrs": [("Матрица", "33 Мп полный кадр"), ("Видео", "4K 60fps"), ("Стабилизация", "5-осевая"), ("Серийная съёмка", "10 кадр/с")],
        "img_key": "camera",
    },
    {
        "name": "Canon EOS R6 Mark II Kit 24-105mm f/4L",
        "category": "Фотоаппараты",
        "price": 749000, "old_price": 820000, "stock": 4,
        "description": "24 Мп CMOS, 40 кадр/с RAW, Dual Pixel AF, 6K RAW видео. В комплекте объектив 24-105mm f/4L IS.",
        "attrs": [("Матрица", "24 Мп"), ("Видео", "6K RAW"), ("Автофокус", "Dual Pixel CMOS AF II"), ("Объектив", "24-105mm f/4L")],
        "img_key": "camera",
    },
]

# ─── Categories with icons ──────────────────────────────────────────────────
CATEGORY_NAMES = [
    "Смартфоны", "Ноутбуки", "Наушники", "Умные часы",
    "Кроссовки", "Рюкзаки и сумки", "Планшеты", "Одежда", "Фотоаппараты",
]


class Command(BaseCommand):
    help = "Seed the database with demo categories and products"

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Clear existing products and categories before seeding'
        )
        parser.add_argument(
            '--no-images', action='store_true',
            help='Skip downloading images (faster, products will show placeholder icons)'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            ProductAttribute.objects.all().delete()
            ProductImage.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared.'))

        skip_images = options.get('no_images', False)

        # 1. Get or create demo seller
        seller = self._get_or_create_seller()

        # 2. Create categories
        categories = self._create_categories()

        # 3. Create products
        self._create_products(categories, seller, skip_images)

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Created {Product.objects.count()} products in {Category.objects.count()} categories.'
        ))

    def _get_or_create_seller(self):
        seller, created = User.objects.get_or_create(
            username='smartshop_seller',
            defaults={
                'email': 'seller@smartshop.kz',
                'role': 'seller',
                'is_active': True,
            }
        )
        if created:
            seller.set_password('SmartShop2025!')
            seller.save()
            self.stdout.write(f'Created seller: {seller.username} / SmartShop2025!')
        else:
            # Make sure the user is a seller
            if hasattr(seller, 'role') and seller.role != 'seller':
                seller.role = 'seller'
                seller.save()
            self.stdout.write(f'Using existing seller: {seller.username}')
        return seller

    def _create_categories(self):
        cats = {}
        for name in CATEGORY_NAMES:
            slug = slugify(name)
            # Handle duplicate slug
            base_slug = slug
            counter = 1
            while Category.objects.exclude(name=name).filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            cat, created = Category.objects.get_or_create(
                name=name,
                defaults={'slug': slug}
            )
            if not cat.slug:
                cat.slug = slug
                cat.save()
            cats[name] = cat
            self.stdout.write(f'  {"Created" if created else "Existing"} category: {name}')
        return cats

    def _create_products(self, categories, seller, skip_images):
        created_count = 0
        for pdata in PRODUCTS_DATA:
            cat_name = pdata['category']
            if cat_name not in categories:
                self.stdout.write(self.style.WARNING(f'  Skipping: category "{cat_name}" not found'))
                continue

            # Build slug
            slug = slugify(pdata['name'])
            base_slug = slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            product = Product.objects.create(
                seller=seller,
                category=categories[cat_name],
                name=pdata['name'],
                slug=slug,
                description=pdata['description'],
                price=Decimal(str(pdata['price'])),
                old_price=Decimal(str(pdata['old_price'])) if pdata['old_price'] else None,
                stock=pdata['stock'],
                status='active',
            )

            # Attributes
            for attr_name, attr_value in pdata.get('attrs', []):
                ProductAttribute.objects.create(
                    product=product,
                    name=attr_name,
                    value=attr_value
                )

            # Image
            if not skip_images:
                img_key = pdata.get('img_key', 'default')
                urls = PRODUCT_IMAGES.get(img_key, PRODUCT_IMAGES['default'])
                img_url = random.choice(urls)
                self._download_image(product, img_url)
            
            created_count += 1
            self.stdout.write(f'  Created: {product.name}')

        self.stdout.write(self.style.SUCCESS(f'\nCreated {created_count} products.'))

    def _download_image(self, product, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                image_data = response.read()

            filename = f"product_{product.id}.jpg"
            image_file = io.BytesIO(image_data)

            product_image = ProductImage(product=product, is_main=True)
            product_image.image.save(filename, File(image_file), save=True)
            self.stdout.write(f'    ✓ Image saved for {product.name}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'    ✗ Could not download image: {e}'))
