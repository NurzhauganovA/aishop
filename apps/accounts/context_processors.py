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


def notifications_processor(request):
    """
    Контекст-процессор для добавления счетчиков непрочитанных сообщений и уведомлений
    к контексту шаблона для всех страниц
    """
    context = {
        'unread_notifications_count': 0,
        'unread_messages_count': 0,
        'total_unread_count': 0
    }

    # Проверяем, аутентифицирован ли пользователь
    if request.user.is_authenticated:
        # Получаем количество непрочитанных уведомлений
        from apps.notifications.models import Notification
        unread_notifications = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()

        # Получаем количество непрочитанных сообщений из всех бесед
        from apps.chat.models import Message, Conversation
        from django.db.models import Q, Count

        # Подсчитываем все непрочитанные сообщения во всех беседах пользователя
        # (как покупателя и как продавца)
        unread_messages = Message.objects.filter(
            Q(conversation__buyer=request.user) | Q(conversation__seller=request.user),
            sender__id__ne=request.user.id,  # Сообщения не от текущего пользователя
            is_read=False
        ).count()

        # Обновляем контекст
        context['unread_notifications_count'] = unread_notifications
        context['unread_messages_count'] = unread_messages
        context['total_unread_count'] = unread_notifications + unread_messages

    return context