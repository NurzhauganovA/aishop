from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone

from .models import Order, OrderItem, OrderStatus
from apps.products.models import Cart, CartItem, Product
from apps.accounts.models import Address
from .forms import OrderForm

@login_required
def checkout(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = CartItem.objects.filter(cart=cart)
    
    if not cart_items.exists():
        messages.warning(request, 'Ваша корзина пуста. Добавьте товары перед оформлением заказа.')
        return redirect('cart')
    
    # Группируем товары по продавцу
    sellers_products = {}
    for item in cart_items:
        seller = item.product.seller
        if seller not in sellers_products:
            sellers_products[seller] = []
        sellers_products[seller].append(item)
    
    # Проверяем наличие товаров
    for items in sellers_products.values():
        for item in items:
            if item.quantity > item.product.stock:
                messages.error(request, f'К сожалению, товара "{item.product.name}" осталось только {item.product.stock} шт.')
                return redirect('cart')
    
    # Получаем адреса пользователя
    addresses = Address.objects.filter(user=request.user)
    default_address = addresses.filter(is_default=True).first() or addresses.first()
    
    context = {
        'cart': cart,
        'sellers_products': sellers_products,
        'addresses': addresses,
        'default_address': default_address,
        'form': OrderForm(initial={'address': default_address.id} if default_address else None)
    }
    return render(request, 'orders/checkout.html', context)

@login_required
@transaction.atomic
def place_order(request):
    if request.method != 'POST':
        return redirect('checkout')
    
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = CartItem.objects.filter(cart=cart)
    
    if not cart_items.exists():
        messages.warning(request, 'Ваша корзина пуста.')
        return redirect('cart')
    
    form = OrderForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
        return redirect('checkout')
    
    # Получаем данные из формы
    full_name = form.cleaned_data['full_name']
    email = form.cleaned_data['email']
    phone = form.cleaned_data['phone']
    address_line = form.cleaned_data['address_line']
    city = form.cleaned_data['city']
    postal_code = form.cleaned_data['postal_code']
    comment = form.cleaned_data['comment']
    
    # Группируем товары по продавцу
    sellers_products = {}
    for item in cart_items:
        seller = item.product.seller
        if seller not in sellers_products:
            sellers_products[seller] = []
        sellers_products[seller].append(item)
    
    orders = []
    
    # Создаем заказы для каждого продавца
    for seller, items in sellers_products.items():
        # Проверяем наличие товаров
        for item in items:
            if item.quantity > item.product.stock:
                messages.error(request, f'К сожалению, товара "{item.product.name}" осталось только {item.product.stock} шт.')
                return redirect('cart')
        
        # Рассчитываем общую стоимость
        total_price = sum(item.product.price * item.quantity for item in items)
        
        # Создаем заказ
        order = Order.objects.create(
            buyer=request.user,
            seller=seller,
            full_name=full_name,
            email=email,
            phone=phone,
            address=address_line,
            city=city,
            postal_code=postal_code,
            status='new',
            total_price=total_price,
            comment=comment
        )
        
        # Создаем элементы заказа и обновляем остаток товара
        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                price=item.product.price,
                quantity=item.quantity
            )
            
            # Обновляем остаток товара
            product = item.product
            product.stock -= item.quantity
            if product.stock == 0:
                product.status = 'out_of_stock'
            product.save()
        
        # Создаем запись о статусе заказа
        OrderStatus.objects.create(
            order=order,
            status='new',
            comment='Заказ создан',
            created_by=request.user
        )
        
        orders.append(order)
    
    # Очищаем корзину
    cart_items.delete()
    
    messages.success(request, f'Ваш заказ успешно оформлен! Номер заказа: {", ".join(str(order.id) for order in orders)}')
    return redirect('payment_success')

@login_required
def payment_success(request):
    # В реальном проекте здесь нужно обрабатывать результаты оплаты
    recent_orders = Order.objects.filter(buyer=request.user).order_by('-created_at')[:5]
    return render(request, 'orders/payment_success.html', {'orders': recent_orders})

@login_required
def my_orders(request):
    orders = Order.objects.filter(buyer=request.user).order_by('-created_at')
    return render(request, 'orders/my_orders.html', {'orders': orders})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    status_updates = order.status_updates.all().order_by('created_at')
    return render(request, 'orders/order_detail.html', {'order': order, 'status_updates': status_updates})

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    # Проверяем, можно ли отменить заказ
    if order.status not in ['new', 'processing']:
        messages.error(request, 'Этот заказ нельзя отменить. Обратитесь к продавцу.')
        return redirect('order_detail', order_id=order.id)
    
    if request.method == 'POST':
        with transaction.atomic():
            # Обновляем статус заказа
            order.status = 'cancelled'
            order.save()
            
            # Создаем запись о статусе заказа
            OrderStatus.objects.create(
                order=order,
                status='cancelled',
                comment=request.POST.get('comment', 'Заказ отменен покупателем'),
                created_by=request.user
            )
            
            # Возвращаем товары в наличие
            for item in order.items.all():
                product = item.product
                product.stock += item.quantity
                if product.stock > 0 and product.status == 'out_of_stock':
                    product.status = 'active'
                product.save()
        
        messages.success(request, 'Заказ успешно отменен.')
        return redirect('my_orders')
    
    return render(request, 'orders/cancel_order.html', {'order': order})
