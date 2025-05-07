from django.contrib import admin
from .models import (
    Category, Product, ProductImage, ProductVideo, ProductAttribute,
    Review, ReviewImage, Cart, CartItem, Wishlist, ProductTracking
)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent')
    list_filter = ('parent',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductVideoInline(admin.TabularInline):
    model = ProductVideo
    extra = 0

class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 3

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock', 'status', 'created_at')
    list_filter = ('category', 'status', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductVideoInline, ProductAttributeInline]
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('price', 'stock', 'status')
    fieldsets = (
        (None, {
            'fields': ('seller', 'category', 'name', 'slug', 'description')
        }),
        ('Цена', {
            'fields': ('price', 'old_price')
        }),
        ('Информация о наличии', {
            'fields': ('stock', 'status')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 1

class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('text', 'product__name', 'user__username')
    readonly_fields = ('created_at',)
    inlines = [ReviewImageInline]

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at', 'total_price', 'item_count')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at', 'total_price', 'item_count')
    inlines = [CartItemInline]

admin.site.register(Category, CategoryAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Review, ReviewAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(Wishlist)
admin.site.register(ProductTracking)
