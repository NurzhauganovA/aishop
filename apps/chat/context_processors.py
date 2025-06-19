from django.db.models import Q

def unread_messages_count(request):
    count = 0
    if request.user.is_authenticated:
        # Get all conversations where the user is either buyer or seller
        from apps.chat.models import Message
        count = Message.objects.filter(
            (Q(conversation__buyer=request.user) | Q(conversation__seller=request.user)) & 
            ~Q(sender=request.user) &  # Exclude messages sent by the current user
            Q(is_read=False)  # Only unread messages
        ).count()
    return {'unread_messages_count': count}