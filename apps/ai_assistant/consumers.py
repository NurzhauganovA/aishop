import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
import logging

from apps.chat.models import AIConversation, AIMessage
from .utils import chat_with_ai_assistant

logger = logging.getLogger(__name__)


class AIAssistantConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Установка соединения WebSocket"""
        try:
            # Проверяем аутентификацию пользователя
            if not self.scope['user'] or isinstance(self.scope['user'], AnonymousUser):
                logger.warning("Попытка подключения неаутентифицированного пользователя")
                await self.close(code=4001, reason="Unauthorized")
                return

            # Получаем ID диалога из URL
            self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']

            # Проверяем, что ID является числом
            try:
                self.conversation_id = int(self.conversation_id)
            except (ValueError, TypeError):
                logger.error(f"Некорректный ID диалога: {self.conversation_id}")
                await self.close(code=4002, reason="Invalid conversation ID")
                return

            # Проверяем существование диалога и права доступа
            conversation_exists = await self.check_conversation_access()
            if not conversation_exists:
                logger.warning(
                    f"Пользователь {self.scope['user'].id} не имеет доступа к диалогу {self.conversation_id}")
                await self.close(code=4003, reason="Conversation not found or access denied")
                return

            # Формируем имя группы
            self.room_group_name = f'aisha_{self.conversation_id}'

            # Присоединение к группе комнаты
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            # Принимаем соединение
            await self.accept()

            logger.info(f"Пользователь {self.scope['user'].username} подключился к AI диалогу {self.conversation_id}")

        except Exception as e:
            logger.error(f"Ошибка при подключении к WebSocket: {str(e)}")
            await self.close(code=4000, reason="Internal server error")

    async def disconnect(self, close_code):
        """Отключение от WebSocket"""
        try:
            # Покидание группы комнаты
            if hasattr(self, 'room_group_name'):
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )

            logger.info(
                f"Пользователь отключился от AI диалога {getattr(self, 'conversation_id', 'unknown')}, код: {close_code}")
        except Exception as e:
            logger.error(f"Ошибка при отключении от WebSocket: {str(e)}")

    async def receive(self, text_data):
        """Обработка входящих сообщений"""
        try:
            # Парсим JSON
            try:
                text_data_json = json.loads(text_data)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON: {str(e)}")
                await self.send_error("Некорректный формат данных")
                return

            # Извлекаем сообщение
            message = text_data_json.get('message', '')
            if not message or not message.strip():
                await self.send_error("Сообщение не может быть пустым")
                return

            # Ограничиваем длину сообщения
            if len(message) > 2000:
                await self.send_error("Сообщение слишком длинное (максимум 2000 символов)")
                return

            user = self.scope['user']

            # Сохранение сообщения пользователя
            user_message = await self.save_message(message, 'user')
            if not user_message:
                await self.send_error("Ошибка сохранения сообщения")
                return

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

            # Получение истории сообщений для контекста (асинхронно)
            conversation_history = await self.get_conversation_history()

            # Обработка запроса в ИИ (с ограничением времени)
            try:
                ai_response = await asyncio.wait_for(
                    database_sync_to_async(chat_with_ai_assistant)(user, message, conversation_history),
                    timeout=30.0  # 30 секунд таймаут
                )
            except asyncio.TimeoutError:
                logger.error(f"Таймаут при обработке запроса для пользователя {user.id}")
                await self.send_error("Время ожидания ответа истекло. Попробуйте еще раз.")
                return
            except Exception as e:
                logger.error(f"Ошибка при обработке AI запроса: {str(e)}")
                await self.send_error("Произошла ошибка при обработке запроса")
                return

            # Проверяем формат ответа
            is_json_response = False
            search_results = None

            try:
                # Проверяем, может ли ответ быть распарсен как JSON
                if ai_response and ai_response.strip().startswith('{') and ai_response.strip().endswith('}'):
                    search_results = json.loads(ai_response)
                    is_json_response = True
                    logger.info(f"Обнаружен JSON-ответ от AI")
            except json.JSONDecodeError:
                # Если это не валидный JSON, обрабатываем как текст
                is_json_response = False
                logger.info("Ответ AI не является JSON форматом")

            if is_json_response and search_results:
                # Сохраняем сообщение от ИИ о результатах поиска
                await self.save_message("Вот результаты по вашему запросу:", 'ai')

                # Отправляем результаты поиска
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'search_results',
                        'results': search_results
                    }
                )
            else:
                # Это обычный текстовый ответ
                if not ai_response:
                    ai_response = "Извините, я не смог обработать ваш запрос. Попробуйте переформулировать вопрос."

                ai_message = await self.save_message(ai_response, 'ai')
                if not ai_message:
                    await self.send_error("Ошибка сохранения ответа AI")
                    return

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

            logger.info(f"Сообщение от пользователя '{user.username}' обработано успешно")

        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {str(e)}")
            await self.send_error(f'Произошла внутренняя ошибка сервера')

    async def chat_message(self, event):
        """Отправка сообщения клиенту"""
        try:
            message = event['message']
            role = event['role']
            message_id = event.get('message_id')

            await self.send(text_data=json.dumps({
                'message': message,
                'role': role,
                'message_id': message_id
            }))

        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {str(e)}")

    async def search_results(self, event):
        """Отправка результатов поиска клиенту"""
        try:
            results = event['results']

            await self.send(text_data=json.dumps({
                'status': 'success',
                'results': results
            }))

        except Exception as e:
            logger.error(f"Ошибка при отправке результатов поиска: {str(e)}")

    async def send_error(self, message):
        """Отправка сообщения об ошибке клиенту"""
        try:
            await self.send(text_data=json.dumps({
                'status': 'error',
                'message': message
            }))
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {str(e)}")

    @database_sync_to_async
    def check_conversation_access(self):
        """Проверка доступа к диалогу"""
        try:
            conversation = AIConversation.objects.get(
                id=self.conversation_id,
                user=self.scope['user']
            )
            return True
        except AIConversation.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке доступа к диалогу: {str(e)}")
            return False

    @database_sync_to_async
    def save_message(self, content, role):
        """Сохранение сообщения в базе данных"""
        try:
            conversation = AIConversation.objects.get(id=self.conversation_id)
            message = AIMessage.objects.create(
                conversation=conversation,
                role=role,
                content=content
            )
            logger.info(f"Сообщение сохранено: {content[:50]}...")
            return message
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения: {str(e)}")
            return None

    @database_sync_to_async
    def get_conversation_history(self):
        """Получение истории диалога"""
        try:
            conversation = AIConversation.objects.get(id=self.conversation_id)
            # Получаем последние 10 сообщений для контекста
            messages = conversation.messages.order_by('-created_at')[:10]
            # Возвращаем в правильном порядке (от старых к новым)
            return list(reversed(messages))
        except Exception as e:
            logger.error(f"Ошибка при получении истории диалога: {str(e)}")
            return []