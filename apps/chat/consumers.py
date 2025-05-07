import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Conversation, Message

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        
        # Проверяем, принадлежит ли пользователь к этому чату
        is_participant = await self.check_user_in_conversation()
        if not is_participant:
            await self.close()
            return
        
        # Присоединяемся к группе
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Помечаем непрочитанные сообщения как прочитанные
        await self.mark_messages_as_read()
    
    async def disconnect(self, close_code):
        # Покидаем группу
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type', 'text')
        message = text_data_json['message']
        
        conversation = await self.get_conversation()
        
        # Сохраняем сообщение пользователя
        user_message = await self.save_message(conversation, message_type, message)
        
        # Отправляем сообщение в группу
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'message_type': message_type,
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'message_id': user_message.id,
                'timestamp': user_message.created_at.isoformat()
            }
        )
        
        # Создаем уведомление для получателя
        recipient = await self.get_recipient()
        if recipient:
            await self.create_notification(recipient, message)
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'message_type': event['message_type'],
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'message_id': event['message_id'],
            'timestamp': event['timestamp']
        }))
    
    @database_sync_to_async
    def check_user_in_conversation(self):
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            return conversation.buyer == self.user or conversation.seller == self.user
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_conversation(self):
        return Conversation.objects.get(id=self.conversation_id)
    
    @database_sync_to_async
    def save_message(self, conversation, message_type, content):
        return Message.objects.create(
            conversation=conversation,
            sender=self.user,
            message_type=message_type,
            content=content
        )
    
    @database_sync_to_async
    def mark_messages_as_read(self):
        conversation = Conversation.objects.get(id=self.conversation_id)
        # Исправляем метод, чтобы он правильно помечал сообщения как прочитанные
        return Message.objects.filter(
            conversation=conversation, 
            is_read=False
        ).exclude(sender=self.user).update(is_read=True)
    
    @database_sync_to_async
    def get_recipient(self):
        conversation = Conversation.objects.get(id=self.conversation_id)
        if conversation.buyer == self.user:
            return conversation.seller
        return conversation.buyer
    
    @database_sync_to_async
    def create_notification(self, recipient, message):
        from apps.notifications.models import Notification
        return Notification.objects.create(
            user=recipient,
            notification_type='chat_message',
            title=f'Новое сообщение от {self.user.username}',
            message=message[:50] + ('...' if len(message) > 50 else ''),
            link=f'/chat/{self.conversation_id}/'
        )