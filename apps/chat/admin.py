from django.contrib import admin
from .models import Conversation, Message, AIConversation, AIMessage

class MessageInline(admin.TabularInline):
    model = Message
    readonly_fields = ('sender', 'message_type', 'content', 'is_read', 'created_at')
    extra = 0
    max_num = 10

class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'seller', 'product', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('buyer__username', 'seller__username', 'product__name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MessageInline]

class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'message_type', 'is_read', 'created_at')
    list_filter = ('message_type', 'is_read', 'created_at')
    search_fields = ('conversation__buyer__username', 'conversation__seller__username', 'content')
    readonly_fields = ('created_at',)

class AIMessageInline(admin.TabularInline):
    model = AIMessage
    readonly_fields = ('role', 'content', 'created_at')
    extra = 0
    max_num = 10

class AIConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [AIMessageInline]

admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(AIConversation, AIConversationAdmin)
admin.site.register(AIMessage)