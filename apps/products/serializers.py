from rest_framework import serializers
from .models import Product, Category, ProductImage, ProductAttribute, Review, ReviewImage

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_main']

class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ['id', 'name', 'value']

class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ['id', 'image']

class ReviewSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source='user.username')
    images = ReviewImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'user', 'user_username', 'rating', 'text', 'created_at', 'images']

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    seller_username = serializers.ReadOnlyField(source='seller.username')
    images = ProductImageSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    rating = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'old_price',
            'stock', 'status', 'category', 'category_name', 'seller',
            'seller_username', 'images', 'attributes', 'reviews',
            'rating', 'created_at', 'updated_at'
        ]

class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    seller_username = serializers.ReadOnlyField(source='seller.username')
    main_image = serializers.SerializerMethodField()
    rating = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'price', 'old_price', 'stock',
            'status', 'category_name', 'seller_username', 'main_image',
            'rating'
        ]
    
    def get_main_image(self, obj):
        main_image = obj.images.filter(is_main=True).first()
        if main_image:
            return ProductImageSerializer(main_image).data
        return None
