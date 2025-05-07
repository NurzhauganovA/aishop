import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from apps.chat.models import AIConversation, AIMessage
from .utils import chat_with_ai_assistant


class AIAssistantConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'ai_assistant_{self.conversation_id}'

        # Присоединяемся к группе
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Покидаем группу
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Сохраняем сообщение пользователя
        user_message = await self.save_user_message(message)

        # Отправляем сообщение в группу
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'role': 'user',
                'message_id': user_message.id,
                'timestamp': user_message.created_at.isoformat()
            }
        )

        # Получаем историю сообщений
        conversation_history = await self.get_conversation_history()

        # Получаем ответ от ИИ
        ai_response = await database_sync_to_async(chat_with_ai_assistant)(
            self.user, message, conversation_history
        )

        # Сохраняем ответ ИИ
        ai_message = await self.save_ai_message(ai_response)

        # Отправляем ответ ИИ в группу
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': ai_response,
                'role': 'ai',
                'message_id': ai_message.id,
                'timestamp': ai_message.created_at.isoformat()
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'role': event['role'],
            'message_id': event['message_id'],
            'timestamp': event['timestamp']
        }))

    @database_sync_to_async
    def save_user_message(self, message):
        conversation, _ = AIConversation.objects.get_or_create(
            id=self.conversation_id,
            defaults={'user': self.user}
        )
        return AIMessage.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )

    @database_sync_to_async
    def save_ai_message(self, message):
        conversation = AIConversation.objects.get(id=self.conversation_id)
        return AIMessage.objects.create(
            conversation=conversation,
            role='ai',
            content=message
        )

    @database_sync_to_async
    def get_conversation_history(self):
        conversation = AIConversation.objects.get(id=self.conversation_id)
        return list(conversation.messages.order_by('created_at'))