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

        # Join the group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        print(f"WebSocket connection accepted for conversation {self.conversation_id}")

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"WebSocket disconnected for conversation {self.conversation_id}, code: {close_code}")

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json['message']
            print(f"Received message from client: {message[:50]}...")

            # Save user message
            user_message = await self.save_user_message(message)

            # Send message to group
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

            # Get conversation history
            conversation_history = await self.get_conversation_history()

            # Get AI response
            ai_response = await database_sync_to_async(chat_with_ai_assistant)(
                self.user, message, conversation_history
            )

            # Save AI response
            ai_message = await self.save_ai_message(ai_response)

            # Send AI response to group
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
            print(f"Sent AI response to group: {ai_response[:50]}...")
        except Exception as e:
            print(f"Error in receive method: {str(e)}")
            # Send error message to client
            await self.send(text_data=json.dumps({
                'error': str(e),
                'message': 'Произошла ошибка при обработке вашего сообщения.',
                'role': 'system'
            }))

    async def chat_message(self, event):
        try:
            # Forward message to WebSocket
            await self.send(text_data=json.dumps({
                'message': event['message'],
                'role': event['role'],
                'message_id': event['message_id'],
                'timestamp': event['timestamp']
            }))
            print(f"Message forwarded to WebSocket: {event['role']} - {event['message'][:50]}...")
        except Exception as e:
            print(f"Error in chat_message method: {str(e)}")

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


class AIChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = f'ai_chat_{self.user.id}'

        # Join the group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        print(f"WebSocket connection accepted for user {self.user.username}")
        await self.send(text_data=json.dumps({
            'message': 'Welcome to the AI Chat!',
            'role': 'system'
        }))
        print(f"Sent welcome message to user {self.user.username}")

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"WebSocket disconnected for user {self.user.username}, code: {close_code}")

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json['message']
            print(f"Received message from client: {message[:50]}...")

            # Save user message
            user_message = await self.save_user_message(message)

            # Send message to group
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

            # Get AI response
            ai_response = await database_sync_to_async(chat_with_ai_assistant)(
                self.user, message, []
            )

            # Save AI response
            ai_message = await self.save_ai_message(ai_response)

            # Send AI response to group
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
            print(f"Sent AI response to group: {ai_response[:50]}...")
        except Exception as e:
            print(f"Error in receive method: {str(e)}")

            # Send error message to client
            await self.send(text_data=json.dumps({
                'error': str(e),
                'message': 'Произошла ошибка при обработке вашего сообщения.',
                'role': 'system'
            }))

    async def chat_message(self, event):
        try:
            # Forward message to WebSocket
            await self.send(text_data=json.dumps({
                'message': event['message'],
                'role': event['role'],
                'message_id': event['message_id'],
                'timestamp': event['timestamp']
            }))
            print(f"Message forwarded to WebSocket: {event['role']} - {event['message'][:50]}...")
        except Exception as e:
            print(f"Error in chat_message method: {str(e)}")

    @database_sync_to_async
    def save_user_message(self, message):
        conversation, _ = AIConversation.objects.get_or_create(
            user=self.user
        )
        return AIMessage.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )

    @database_sync_to_async
    def save_ai_message(self, message):
        conversation = AIConversation.objects.get(user=self.user)
        return AIMessage.objects.create(
            conversation=conversation,
            role='ai',
            content=message
        )

    @database_sync_to_async
    def get_conversation_history(self):
        conversation = AIConversation.objects.get(user=self.user)
        return list(conversation.messages.order_by('created_at'))

    @database_sync_to_async
    def get_conversation(self):
        return AIConversation.objects.get(user=self.user)