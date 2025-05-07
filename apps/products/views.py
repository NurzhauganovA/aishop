from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count, Sum
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView  # Добавьте эти классы
from apps.orders.models import Order  # Добавьте импорт Order

from apps.orders.models import OrderStatus
from .models import Product, Category, Cart, CartItem, ProductImage, ProductVideo, ReviewImage, Wishlist, Review, ProductTracking, ProductAttribute
from .forms import ProductAttributeFormSet, ProductForm, ReviewForm
from apps.ai_assistant.utils import generate_ai_product_description
import time
import json
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.user_activities.models import UserActivity

def home(request):
    featured_products = Product.objects.filter(status='active').order_by('-created_at')[:8]
    top_categories = Category.objects.annotate(product_count=Count('products')).order_by('-product_count')[:6]
    best_selling = Product.objects.filter(status='active').annotate(order_count=Count('order_items')).order_by('-order_count')[:8]
    top_rated = Product.objects.filter(status='active', reviews__isnull=False).annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')[:8]
    
    context = {
        'featured_products': featured_products,
        'top_categories': top_categories,
        'best_selling': best_selling,
        'top_rated': top_rated,
    }
    return render(request, 'products/home.html', context)

def product_list(request):
    categories = Category.objects.all()
    products = Product.objects.filter(status='active')
    
    # Фильтрация по категории
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    
    # Фильтрация по цене
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    
    # Поиск по названию или описанию
    search_query = request.GET.get('q')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Сортировка
    sort_by = request.GET.get('sort_by', 'newest')
    if sort_by == 'newest':
        products = products.order_by('-created_at')
    elif sort_by == 'price_low':
        products = products.order_by('price')
    elif sort_by == 'price_high':
        products = products.order_by('-price')
    elif sort_by == 'rating':
        products = products.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
    elif sort_by == 'popularity':
        products = products.annotate(order_count=Count('order_items')).order_by('-order_count')
    
    context = {
        'categories': categories,
        'products': products,
        'search_query': search_query,
        'sort_by': sort_by,
    }
    return render(request, 'products/product_list.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, status='active')
    reviews = product.reviews.all().order_by('-created_at')
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    
    # Запись времени активности пользователя
    if request.user.is_authenticated:
        view_time_start = request.session.get(f'view_time_start_{product.id}')
        if not view_time_start:
            request.session[f'view_time_start_{product.id}'] = time.time()
        
        # Обновление счетчика просмотров и активности
        user_activity, created = request.user.activities.get_or_create(product=product)
        if not created:
            user_activity.view_count += 1
            user_activity.save()
    
    # Форма отзыва
    form = ReviewForm()
    can_review = False
    has_reviewed = False
    
    if request.user.is_authenticated:
        # Проверка, купил ли пользователь товар
        has_purchased = request.user.orders.filter(
            items__product=product, status='completed'
        ).exists()
        can_review = has_purchased
        has_reviewed = Review.objects.filter(product=product, user=request.user).exists()
    
    context = {
        'product': product,
        'reviews': reviews,
        'related_products': related_products,
        'form': form,
        'can_review': can_review,
        'has_reviewed': has_reviewed,
    }
    return render(request, 'products/product_detail.html', context)

@login_required
def leave_view_time(request, product_id):
    view_time_start = request.session.get(f'view_time_start_{product_id}')
    if view_time_start:
        view_time = int(time.time() - view_time_start)
        user_activity, created = UserActivity.objects.get_or_create(user=request.user, product_id=product_id)
        user_activity.view_time += view_time
        user_activity.save()
        del request.session[f'view_time_start_{product_id}']
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def add_to_cart(request):
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    
    product = get_object_or_404(Product, id=product_id, status='active')
    
    # Проверка доступности товара
    if product.stock < quantity:
        messages.error(request, f'Недостаточно товара в наличии. Доступно: {product.stock}')
        return redirect('product_detail', slug=product.slug)
    
    # Получение или создание корзины
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    # Добавление в корзину
    cart_item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)
    
    if not item_created:
        cart_item.quantity += quantity
    else:
        cart_item.quantity = quantity
    
    cart_item.save()
    
    messages.success(request, 'Товар добавлен в корзину')
    return redirect('cart')

@login_required
def cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    context = {'cart': cart}
    return render(request, 'products/cart.html', context)

@login_required
@require_POST
def update_cart(request):
    data = json.loads(request.body)
    item_id = data.get('item_id')
    quantity = int(data.get('quantity'))
    
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    
    # Проверка доступности товара
    if cart_item.product.stock < quantity:
        return JsonResponse({
            'status': 'error',
            'message': f'Недостаточно товара в наличии. Доступно: {cart_item.product.stock}'
        })
    
    if quantity > 0:
        cart_item.quantity = quantity
        cart_item.save()
    else:
        cart_item.delete()
    
    cart = Cart.objects.get(user=request.user)
    
    return JsonResponse({
        'status': 'success',
        'subtotal': str(cart_item.subtotal) if quantity > 0 else "0",
        'total': str(cart.total_price),
        'item_count': cart.item_count
    })

@login_required
@require_POST
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    
    messages.success(request, 'Товар удалён из корзины')
    return redirect('cart')

def product_detail_by_id(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    reviews = product.reviews.all().order_by('-created_at')
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    
    # Запись времени активности пользователя
    if request.user.is_authenticated:
        view_time_start = request.session.get(f'view_time_start_{product.id}')
        if not view_time_start:
            request.session[f'view_time_start_{product.id}'] = time.time()
        
        # Обновление счетчика просмотров и активности
        user_activity, created = request.user.activities.get_or_create(product=product)
        if not created:
            user_activity.view_count += 1
            user_activity.save()
    
    # Форма отзыва
    form = ReviewForm()
    can_review = False
    has_reviewed = False
    
    if request.user.is_authenticated:
        # Проверка, купил ли пользователь товар
        has_purchased = request.user.orders.filter(
            items__product=product, status='completed'
        ).exists()
        can_review = has_purchased
        has_reviewed = Review.objects.filter(product=product, user=request.user).exists()
    
    context = {
        'product': product,
        'reviews': reviews,
        'related_products': related_products,
        'form': form,
        'can_review': can_review,
        'has_reviewed': has_reviewed,
    }
    return render(request, 'products/product_detail.html', context)

@login_required
@require_POST
def add_to_wishlist(request):
    product_id = request.POST.get('product_id')
    product = get_object_or_404(Product, id=product_id, status='active')
    
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    
    if product in wishlist.products.all():
        wishlist.products.remove(product)
        added = False
        message = 'Товар удалён из списка желаний'
    else:
        wishlist.products.add(product)
        added = True
        message = 'Товар добавлен в список желаний'
    
    # Замена устаревшего is_ajax() на проверку заголовка
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'added': added,
            'message': message
        })
    
    messages.success(request, message)
    return redirect('product_detail_by_id', product_id=product.id)

@login_required
def wishlist(request):
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    context = {'wishlist': wishlist}
    return render(request, 'products/wishlist.html', context)

@login_required
@require_POST
def submit_review(request, product_id):
    product = get_object_or_404(Product, id=product_id, status='active')
    
    # Проверка, купил ли пользователь товар
    has_purchased = request.user.orders.filter(
        items__product=product, status='completed'
    ).exists()
    
    if not has_purchased:
        messages.error(request, 'Вы можете оставить отзыв только после покупки товара')
        return redirect('product_detail', slug=product.slug)
    
    # Проверка, оставил ли пользователь уже отзыв
    has_reviewed = Review.objects.filter(product=product, user=request.user).exists()
    if has_reviewed:
        messages.error(request, 'Вы уже оставили отзыв на этот товар')
        return redirect('product_detail', slug=product.slug)
    
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.user = request.user
        review.product = product
        review.save()
        
        # Сохранение изображений отзыва
        for image in request.FILES.getlist('images'):
            ReviewImage.objects.create(review=review, image=image)
        
        messages.success(request, 'Ваш отзыв добавлен')
    else:
        messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
    
    return redirect('product_detail', slug=product.slug)

@login_required
@require_POST
def track_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, status='active')
    
    data = request.POST
    track_price = 'track_price' in data
    track_stock = 'track_stock' in data
    track_discount = 'track_discount' in data
    
    tracking, created = ProductTracking.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={
            'track_price': track_price,
            'track_stock': track_stock,
            'track_discount': track_discount
        }
    )
    
    if not created:
        tracking.track_price = track_price
        tracking.track_stock = track_stock
        tracking.track_discount = track_discount
        tracking.save()
    
    messages.success(request, 'Настройки отслеживания товара обновлены')
    return redirect('product_detail', slug=product.slug)

class SellerDashboardMixin:
    """Миксин для проверки роли продавца"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_seller():
            messages.error(request, 'У вас нет доступа к панели продавца')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)
    
class SellerDashboardView(LoginRequiredMixin, SellerDashboardMixin, TemplateView):
    template_name = 'products/seller_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Получаем статистику продаж
        orders = self.request.user.seller_orders.all()
        completed_orders = orders.filter(status='completed')
        
        # Общая статистика
        context['total_revenue'] = completed_orders.aggregate(
            total=Sum('total_price'))['total'] or 0
        context['total_orders'] = completed_orders.count()
        context['total_products'] = self.request.user.products.filter(
            status='active').count()
        
        # Последние заказы
        context['recent_orders'] = orders.order_by('-created_at')[:5]
        
        # Популярные товары
        context['popular_products'] = self.request.user.products.annotate(
            order_count=Count('order_items')).order_by('-order_count')[:3]
        
        # Данные для графика продаж (последние 7 дней)
        from django.utils import timezone
        import json
        from datetime import timedelta
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=7)
        
        # Заглушка для данных графика
        labels = [(start_date + timedelta(days=i)).strftime('%d.%m') 
                 for i in range(7)]
        # В реальном проекте здесь будет агрегация по датам
        values = [0] * 7  # Заполните реальными данными при необходимости
        
        context['sales_data'] = json.dumps({
            'labels': labels,
            'values': values
        })
        
        return context


@login_required
def seller_generate_description(request):
    if not request.user.is_seller():
        return JsonResponse({'status': 'error', 'message': 'У вас нет доступа к этой функции'})

    data = json.loads(request.body)
    product_name = data.get('name', '')
    product_attrs = data.get('attributes', {})

    try:
        description = generate_ai_product_description(product_name, product_attrs)
        return JsonResponse({'status': 'success', 'description': description})
    except Exception as e:
        error_msg = str(e)
        if "квот" in error_msg.lower() or "лимит" in error_msg.lower():
            # Специальная обработка для ошибок с квотами
            return JsonResponse({
                'status': 'error',
                'message': error_msg,
                'error_type': 'quota_exceeded'
            }, status=429)  # 429 Too Many Requests
        return JsonResponse({'status': 'error', 'message': error_msg})
    
class SellerProductsView(LoginRequiredMixin, SellerDashboardMixin, ListView):
    template_name = 'products/seller_product_list.html'
    context_object_name = 'products'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = self.request.user.products.all()
        
        # Фильтрация по запросу
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query)
            )
        
        # Фильтрация по категории
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Фильтрация по статусу
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context
    
class SellerProductCreateView(LoginRequiredMixin, SellerDashboardMixin, CreateView):
    model = Product
    template_name = 'products/product_add.html'
    form_class = ProductForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context
    
    def form_valid(self, form):
        # Сохраняем основную форму товара
        self.object = form.save(commit=False)
        self.object.seller = self.request.user
        self.object.save()
        
        # Обрабатываем атрибуты товара
        attribute_names = self.request.POST.getlist('attribute_name[]')
        attribute_values = self.request.POST.getlist('attribute_value[]')
        
        for name, value in zip(attribute_names, attribute_values):
            if name.strip() and value.strip():
                ProductAttribute.objects.create(
                    product=self.object,
                    name=name.strip(),
                    value=value.strip()
                )
        
        # Обработка изображений
        for image in self.request.FILES.getlist('images'):
            is_main = not ProductImage.objects.filter(product=self.object).exists()
            ProductImage.objects.create(
                product=self.object,
                image=image,
                is_main=is_main
            )
        
        # Обработка видео
        for video in self.request.FILES.getlist('videos'):
            ProductVideo.objects.create(
                product=self.object,
                video=video
            )
        
        messages.success(self.request, 'Товар успешно добавлен')
        return redirect('seller_products')
    
class SellerProductUpdateView(LoginRequiredMixin, SellerDashboardMixin, UpdateView):
    model = Product
    template_name = 'products/product_edit.html'
    form_class = ProductForm
    
    def get_queryset(self):
        return self.request.user.products.all()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        
        if self.request.POST:
            context['attribute_formset'] = ProductAttributeFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context['attribute_formset'] = ProductAttributeFormSet(instance=self.object)
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        attribute_formset = context['attribute_formset']
        
        if attribute_formset.is_valid():
            self.object = form.save()
            attribute_formset.instance = self.object
            attribute_formset.save()
            
            # Обработка новых изображений
            for image in self.request.FILES.getlist('images'):
                is_main = not ProductImage.objects.filter(product=self.object).exists()
                ProductImage.objects.create(
                    product=self.object,
                    image=image,
                    is_main=is_main
                )
            
            # Обработка новых видео
            for video in self.request.FILES.getlist('videos'):
                ProductVideo.objects.create(
                    product=self.object,
                    video=video
                )
            
            messages.success(self.request, 'Товар успешно обновлен')
            return redirect('seller_products')
        else:
            return self.render_to_response(self.get_context_data(form=form))

class SellerProductDeleteView(LoginRequiredMixin, SellerDashboardMixin, DeleteView):
    model = Product
    template_name = 'products/product_confirm_delete.html'
    success_url = reverse_lazy('seller_products')
    
    def get_queryset(self):
        return self.request.user.products.all()
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Удаляем связанные изображения и видео
        self.object.images.all().delete()
        self.object.videos.all().delete()
        
        self.object.delete()
        messages.success(request, 'Товар успешно удален')
        return HttpResponseRedirect(success_url)

class SellerOrdersView(LoginRequiredMixin, SellerDashboardMixin, ListView):
    template_name = 'orders/seller_orders.html'
    context_object_name = 'orders'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = self.request.user.seller_orders.all()
        
        # Фильтрация по статусу
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')

class SellerOrderDetailView(LoginRequiredMixin, SellerDashboardMixin, DetailView):
    model = Order
    template_name = 'orders/seller_order_detail.html'
    context_object_name = 'order'
    
    def get_queryset(self):
        return self.request.user.seller_orders.all()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_updates'] = self.object.status_updates.all().order_by('created_at')
        return context

class SellerOrderUpdateStatusView(LoginRequiredMixin, SellerDashboardMixin, UpdateView):
    model = Order
    template_name = 'orders/seller_order_update_status.html'
    fields = ['status', 'tracking_number']
    
    def get_queryset(self):
        return self.request.user.seller_orders.all()
    
    def form_valid(self, form):
        # Сохраняем предыдущий статус
        old_status = self.get_object().status
        
        # Сохраняем новый статус
        self.object = form.save()
        
        # Если статус изменился, создаем запись об изменении статуса
        if old_status != self.object.status:
            comment = self.request.POST.get('comment', '')
            OrderStatus.objects.create(
                order=self.object,
                status=self.object.status,
                comment=comment,
                created_by=self.request.user
            )
        
        messages.success(self.request, 'Статус заказа успешно обновлен')
        return redirect('seller_order_detail', pk=self.object.pk)
