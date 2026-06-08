"""
Management command to download and attach images to products that have none.

Usage:
    python manage.py add_product_images            # only products without images
    python manage.py add_product_images --all      # re-download for ALL products
    python manage.py add_product_images --timeout 15
"""
import io
import re
import time
import urllib.request
from urllib.error import URLError, HTTPError

from django.core.files import File
from django.core.management.base import BaseCommand

from apps.products.models import Product, ProductImage

# ── Per-product image map (product name fragment → Unsplash photo ID) ─────────
# Key is a lowercase substring of the product name.
# Value is a list of Unsplash photo IDs (tried in order until one succeeds).
PRODUCT_IMAGE_MAP = {
    # ── iPhones ────────────────────────────────────────────────────────────
    "iphone 15 pro max":     ["photo-1696426358498-f53a11db1c0a", "photo-1510557880182-3d4d3cba35a5"],
    "iphone 15 pro":         ["photo-1616410011236-7a42121dd981", "photo-1565849904461-04a58ad377e0"],
    "iphone":                ["photo-1510557880182-3d4d3cba35a5", "photo-1580910051074-3eb694886505"],

    # ── Samsung phones ─────────────────────────────────────────────────────
    "samsung galaxy s24 ultra": ["photo-1678685888221-cebbd2d57f0c", "photo-1598327105666-5b89351aff97"],
    "samsung galaxy a55":    ["photo-1587829741301-dc798b83add3", "photo-1598327105666-5b89351aff97"],
    "samsung galaxy":        ["photo-1598327105666-5b89351aff97", "photo-1580910051074-3eb694886505"],

    # ── Other phones ───────────────────────────────────────────────────────
    "xiaomi 14 ultra":       ["photo-1655890168929-e98f5fb7b50f", "photo-1598327105666-5b89351aff97"],
    "google pixel":          ["photo-1598327105666-5b89351aff97", "photo-1580910051074-3eb694886505"],
    "realme":                ["photo-1534723328310-e82dad3ee43f", "photo-1598327105666-5b89351aff97"],

    # ── MacBooks ───────────────────────────────────────────────────────────
    "macbook pro 14":        ["photo-1629131726692-1accd0c53ce0", "photo-1496181133206-80ce9b88a853"],
    "macbook air 15":        ["photo-1611186871525-5cc2864f53d7", "photo-1517336714731-489689fd1ca8"],
    "macbook":               ["photo-1496181133206-80ce9b88a853", "photo-1517336714731-489689fd1ca8"],

    # ── Gaming laptops ─────────────────────────────────────────────────────
    "asus rog":              ["photo-1593642632559-0c6d3fc62b89", "photo-1484788984921-03950022c9ef"],
    "msi stealth":           ["photo-1593642632559-0c6d3fc62b89", "photo-1484788984921-03950022c9ef"],

    # ── Business/office laptops ────────────────────────────────────────────
    "thinkpad":              ["photo-1593642634443-44adaa06623a", "photo-1484788984921-03950022c9ef"],
    "hp spectre":            ["photo-1593642634524-b40b5baae6bb", "photo-1484788984921-03950022c9ef"],
    "dell xps":              ["photo-1593642634315-48f5414c3ad9", "photo-1484788984921-03950022c9ef"],

    # ── Headphones ─────────────────────────────────────────────────────────
    "airpods pro":           ["photo-1603351154351-5e2d0600bb77", "photo-1505740420928-5e560c06d30e"],
    "sony wh-1000xm5":       ["photo-1484704849700-f032a568e944", "photo-1546435770-a3e426bf472b"],
    "samsung galaxy buds":   ["photo-1590658268037-6bf12165a8df", "photo-1505740420928-5e560c06d30e"],
    "bose quietcomfort":     ["photo-1505740420928-5e560c06d30e", "photo-1583394838336-acd977736f90"],
    "jbl":                   ["photo-1545127398-14699f92334b", "photo-1505740420928-5e560c06d30e"],

    # ── Apple Watch ────────────────────────────────────────────────────────
    "apple watch":           ["photo-1551816230-ef5deaed4a26", "photo-1523275335684-37898b6baf30"],
    "samsung galaxy watch":  ["photo-1523275335684-37898b6baf30", "photo-1546868871-7041f2a55e12"],
    "xiaomi smart band":     ["photo-1575311373937-040b8e1fd5b6", "photo-1508057198894-247b23fe5ade"],
    "garmin":                ["photo-1510017803434-a899398421b3", "photo-1523275335684-37898b6baf30"],

    # ── Tablets ────────────────────────────────────────────────────────────
    "ipad pro":              ["photo-1544244015-0df4b3ffc6b0", "photo-1561154464-82e9adf32764"],
    "samsung galaxy tab":    ["photo-1561154464-82e9adf32764", "photo-1544244015-0df4b3ffc6b0"],
    "xiaomi pad":            ["photo-1561154464-82e9adf32764", "photo-1544244015-0df4b3ffc6b0"],

    # ── Cameras ────────────────────────────────────────────────────────────
    "sony alpha":            ["photo-1516035069371-29a1b244cc32", "photo-1502920917128-1aa500764cbd"],
    "canon eos":             ["photo-1502920917128-1aa500764cbd", "photo-1516035069371-29a1b244cc32"],
    "nikon z8":              ["photo-1452780212441-d9b8b1d0e5b0", "photo-1516035069371-29a1b244cc32"],

    # ── Sneakers ───────────────────────────────────────────────────────────
    "nike air max":          ["photo-1542291026-7eec264c27ff", "photo-1600185365926-3a2ce3cdb9eb"],
    "adidas ultraboost":     ["photo-1608231387042-66d1773070a5", "photo-1539185441755-769473a23570"],
    "new balance":           ["photo-1539185441755-769473a23570", "photo-1542291026-7eec264c27ff"],
    "asics gel":             ["photo-1600185365926-3a2ce3cdb9eb", "photo-1542291026-7eec264c27ff"],

    # ── Bags / backpacks ───────────────────────────────────────────────────
    "nike sportswear heritage": ["photo-1553062407-98eeb64c6a62", "photo-1581605405669-fcdf81165afa"],
    "samsonite":             ["photo-1553062407-98eeb64c6a62", "photo-1581605405669-fcdf81165afa"],
    "osprey":                ["photo-1622560480605-d83c853bc5c3", "photo-1553062407-98eeb64c6a62"],

    # ── Clothing ───────────────────────────────────────────────────────────
    "nike dri-fit":          ["photo-1521572163474-6864f9cf17ab", "photo-1583744946564-b52ac1c389c8"],
    "adidas originals":      ["photo-1618354691438-25bc04584c23", "photo-1583744946564-b52ac1c389c8"],
    "zara":                  ["photo-1558171813-4882e23bdd3f", "photo-1583744946564-b52ac1c389c8"],
}

# Fallback by category name fragment
CATEGORY_IMAGE_MAP = {
    "смартфон":    ["photo-1510557880182-3d4d3cba35a5", "photo-1598327105666-5b89351aff97"],
    "ноутбук":     ["photo-1496181133206-80ce9b88a853", "photo-1517336714731-489689fd1ca8"],
    "наушник":     ["photo-1505740420928-5e560c06d30e", "photo-1546435770-a3e426bf472b"],
    "часы":        ["photo-1523275335684-37898b6baf30", "photo-1546868871-7041f2a55e12"],
    "планшет":     ["photo-1544244015-0df4b3ffc6b0", "photo-1561154464-82e9adf32764"],
    "фотоаппар":   ["photo-1502920917128-1aa500764cbd", "photo-1516035069371-29a1b244cc32"],
    "кроссовк":    ["photo-1542291026-7eec264c27ff", "photo-1600185365926-3a2ce3cdb9eb"],
    "рюкзак":      ["photo-1553062407-98eeb64c6a62", "photo-1581605405669-fcdf81165afa"],
    "сумк":        ["photo-1553062407-98eeb64c6a62", "photo-1581605405669-fcdf81165afa"],
    "одежд":       ["photo-1521572163474-6864f9cf17ab", "photo-1583744946564-b52ac1c389c8"],
    "мужск":       ["photo-1521572163474-6864f9cf17ab", "photo-1583744946564-b52ac1c389c8"],
    "женск":       ["photo-1558171813-4882e23bdd3f", "photo-1583744946564-b52ac1c389c8"],
    "мебел":       ["photo-1555041469-a586c61ea9bc", "photo-1555041469-a586c61ea9bc"],
    "посуд":       ["photo-1556911220-bff31c812dba", "photo-1543013309-0d1f7494291a"],
    "косметик":    ["photo-1556228578-0d85b1a4d571", "photo-1585386959984-a4155224a1ad"],
    "парфюм":      ["photo-1541643600914-78b084683702", "photo-1585386959984-a4155224a1ad"],
}

UNSPLASH_BASE = "https://images.unsplash.com/{photo_id}?w=700&q=85&fit=crop"


class Command(BaseCommand):
    help = "Download and attach product images from Unsplash"

    def add_arguments(self, parser):
        parser.add_argument(
            '--all', action='store_true',
            help='Re-download images for ALL products (not just those missing images)'
        )
        parser.add_argument(
            '--timeout', type=int, default=12,
            help='HTTP timeout per image (seconds, default 12)'
        )
        parser.add_argument(
            '--delay', type=float, default=0.3,
            help='Delay between requests in seconds (default 0.3)'
        )

    def handle(self, *args, **options):
        qs = Product.objects.select_related('category').all()
        if not options['all']:
            qs = qs.filter(images__isnull=True).distinct()

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('All products already have images.'))
            return

        self.stdout.write(f'Downloading images for {total} products...\n')
        timeout = options['timeout']
        delay = options['delay']

        ok = 0
        fail = 0
        for product in qs:
            photo_id = self._resolve_photo_id(product)
            url = UNSPLASH_BASE.format(photo_id=photo_id)

            if self._download(product, url, timeout, options['all']):
                self.stdout.write(self.style.SUCCESS(f'  ✓ {product.name[:60]}'))
                ok += 1
            else:
                # Retry with category fallback
                fallback_id = self._category_fallback(product)
                fallback_url = UNSPLASH_BASE.format(photo_id=fallback_id)
                if self._download(product, fallback_url, timeout, options['all']):
                    self.stdout.write(f'  ~ {product.name[:60]} (fallback)')
                    ok += 1
                else:
                    self.stdout.write(self.style.WARNING(f'  ✗ {product.name[:60]}'))
                    fail += 1

            time.sleep(delay)

        self.stdout.write(
            self.style.SUCCESS(f'\nDone. ✓ {ok} images downloaded, ✗ {fail} failed.')
        )

    # ─────────────────────────────────────────────────────────────────────────

    def _resolve_photo_id(self, product):
        name_lower = product.name.lower()
        # Try longest matching key first
        for key in sorted(PRODUCT_IMAGE_MAP.keys(), key=len, reverse=True):
            if key in name_lower:
                candidates = PRODUCT_IMAGE_MAP[key]
                return candidates[0]
        # Fallback to category-based map
        return self._category_fallback(product)

    def _category_fallback(self, product):
        if product.category:
            cat_lower = product.category.name.lower()
            # Also check parent
            parent_lower = (
                product.category.parent.name.lower()
                if product.category.parent else ''
            )
            for key, ids in CATEGORY_IMAGE_MAP.items():
                if key in cat_lower or key in parent_lower:
                    return ids[0]
        # Ultimate fallback
        return "photo-1523275335684-37898b6baf30"

    def _download(self, product, url, timeout, replace_all):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': (
                        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
                    )
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()

            if len(data) < 5000:
                # Too small — probably an error page
                return False

            if replace_all:
                product.images.all().delete()

            pi = ProductImage(product=product, is_main=True)
            filename = f"product_{product.id}.jpg"
            pi.image.save(filename, File(io.BytesIO(data)), save=True)
            return True

        except (URLError, HTTPError, OSError):
            return False
