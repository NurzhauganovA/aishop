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

        # Присоединение к группе комнаты
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Покидание группы комнаты
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json.get('message', '')

            if not message.strip():
                await self.send(text_data=json.dumps({
                    'status': 'error',
                    'message': 'Сообщение не может быть пустым'
                }))
                return

            user = self.scope['user']

            # Сохранение сообщения пользователя
            user_message = await self.save_message(message, 'user')

            # Отправка сообщения пользователя в группу
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'role': 'user',
                    'user_id': user.id,
                    'message_id': user_message.id
                }
            )

            # Получение истории сообщений для контекста
            conversation_history = await self.get_conversation_history()

            # Обработка запроса в ИИ
            ai_response = await database_sync_to_async(chat_with_ai_assistant)(user, message, conversation_history)

            # Пытаемся определить, является ли ответ JSON для результатов поиска
            try:
                if ai_response.startswith('{') and ai_response.endswith('}'):
                    # Это похоже на JSON - попытка распарсить
                    search_results = json.loads(ai_response)

                    # Сохраняем сообщение от ИИ
                    await self.save_message(f"Вот результаты по вашему запросу:", 'ai')

                    # Отправляем результаты поиска
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'search_results',
                            'results': search_results
                        }
                    )
                else:
                    # Это текстовый ответ
                    ai_message = await self.save_message(ai_response, 'ai')

                    # Отправка ответа от ИИ в группу
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'chat_message',
                            'message': ai_response,
                            'role': 'ai',
                            'message_id': ai_message.id
                        }
                    )
            except json.JSONDecodeError:
                # Если не удалось распарсить как JSON, отправляем как обычное сообщение
                ai_message = await self.save_message(ai_response, 'ai')

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': ai_response,
                        'role': 'ai',
                        'message_id': ai_message.id
                    }
                )

            logger.info(f"Сообщение от пользователя '{user.username}' обработано успешно")

        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {str(e)}")
            await self.send(text_data=json.dumps({
                'status': 'error',
                'message': f'Произошла ошибка: {str(e)}'
            }))

    async def chat_message(self, event):
        message = event['message']
        role = event['role']
        message_id = event.get('message_id')

        logger.info(f"Сообщение отправлено: {message}")

        await self.send(text_data=json.dumps({
            'message': message,
            'role': role,
            'message_id': message_id
        }))

    async def search_results(self, event):
        results = event['results']

        await self.send(text_data=json.dumps({
            'status': 'success',
            'results': results
        }))

    @database_sync_to_async
    def save_message(self, content, role):
        conversation = AIConversation.objects.get(id=self.conversation_id)
        message = AIMessage.objects.create(
            conversation=conversation,
            role=role,
            content=content
        )
        return message

    @database_sync_to_async
    def get_conversation_history(self):
        conversation = AIConversation.objects.get(id=self.conversation_id)
        # Получаем последние 10 сообщений (или меньше) для контекста
        return conversation.messages.order_by('-created_at')[:10][::-1]