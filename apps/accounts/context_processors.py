from apps.products.models import Cart, CartItem, Wishlist

def cart_items_count(request):
    count = 0
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        count = CartItem.objects.filter(cart=cart).count()
    return {'cart_items_count': count}

def wishlist_items_count(request):
    count = 0
    if request.user.is_authenticated:
        wishlist, created = Wishlist.objects.get_or_create(user=request.user)
        count = wishlist.products.count()
    return {'wishlist_items_count': count}
