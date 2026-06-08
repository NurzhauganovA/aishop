import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import logging

from apps.chat.models import AIConversation, AIMessage
from .utils import chat_with_ai_assistant

logger = logging.getLogger(__name__)


class AIAssistantConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'aisha_{self.conversation_id}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = (data.get('message') or '').strip()

            if not message:
                await self.send(text_data=json.dumps({
                    'status': 'error',
                    'message': 'Сообщение не может быть пустым'
                }))
                return

            user = self.scope['user']

            # Save user message to DB (no echo back — UI already shows it optimistically)
            await self.save_message(message, 'user')

            # Send "typing" indicator so user sees activity
            await self.send(text_data=json.dumps({'status': 'typing'}))

            # Fetch context history
            conversation_history = await self.get_conversation_history()

            # Call AI (runs in thread pool to not block event loop)
            ai_response = await database_sync_to_async(
                chat_with_ai_assistant
            )(user, message, conversation_history)

            if not ai_response:
                ai_response = (
                    "Извините, не смогла обработать запрос. "
                    "Попробуйте ещё раз или воспользуйтесь поиском в каталоге."
                )

            # Save AI response
            ai_msg = await self.save_message(ai_response, 'ai')

            # Send AI response to client
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': ai_response,
                    'role': 'ai',
                    'message_id': ai_msg.id,
                }
            )

            logger.info("Processed message from user '%s': %s", user.username, message[:80])

        except Exception as e:
            logger.error("Error in AIAssistantConsumer.receive: %s", e, exc_info=True)
            await self.send(text_data=json.dumps({
                'status': 'error',
                'message': 'Произошла внутренняя ошибка. Попробуйте ещё раз.'
            }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'role': event['role'],
            'message_id': event.get('message_id'),
        }))

    async def search_results(self, event):
        await self.send(text_data=json.dumps({
            'status': 'success',
            'results': event['results'],
        }))

    @database_sync_to_async
    def save_message(self, content, role):
        conversation = AIConversation.objects.get(id=self.conversation_id)
        return AIMessage.objects.create(
            conversation=conversation,
            role=role,
            content=content,
        )

    @database_sync_to_async
    def get_conversation_history(self):
        try:
            conversation = AIConversation.objects.get(id=self.conversation_id)
            # Last 10 messages for context, in chronological order
            return list(conversation.messages.order_by('-created_at')[:10])[::-1]
        except AIConversation.DoesNotExist:
            return []
