import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Notification

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.notification_group_name = f'user_{self.user.id}_notifications'
        
        # Присоединение к группе
        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Отправка непрочитанных уведомлений при подключении
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))
    
    async def disconnect(self, close_code):
        # Отключение от группы
        await self.channel_layer.group_discard(
            self.notification_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        command = text_data_json.get('command', '')
        
        if command == 'mark_as_read':
            notification_id = text_data_json.get('notification_id')
            await self.mark_as_read(notification_id)
            
            # Отправка обновленного количества непрочитанных
            unread_count = await self.get_unread_count()
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'count': unread_count
            }))
        
        elif command == 'mark_all_as_read':
            await self.mark_all_as_read()
            
            # Отправка обновленного количества непрочитанных
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'count': 0
            }))
    
    async def notification(self, event):
        """Отправка уведомления пользователю"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': {
                'id': event['notification_id'],
                'title': event['title'],
                'message': event['message'],
                'notification_type': event['notification_type'],
                'link': event['link'],
                'created_at': event['created_at']
            }
        }))
        
        # Отправка обновленного количества непрочитанных
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))
    
    @database_sync_to_async
    def get_unread_count(self):
        return Notification.objects.filter(user=self.user, is_read=False).count()
    
    @database_sync_to_async
    def mark_as_read(self, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id, user=self.user)
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False
    
    @database_sync_to_async
    def mark_all_as_read(self):
        return Notification.objects.filter(user=self.user, is_read=False).update(is_read=True)
