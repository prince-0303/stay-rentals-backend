import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Conversation, Message
from .encryption import encrypt_message


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        self.user = self.scope['user']
        print(f"[WS Connect] User {self.user} attempting to connect to room {self.room_group_name}")

        if not self.user or not self.user.is_authenticated:
            print(f"[WS Connect] User not authenticated, closing.")
            await self.close()
            return

        if not await self.user_in_conversation():
            print(f"[WS Connect] User {self.user} not in conversation {self.conversation_id}, closing.")
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print(f"[WS Connect] Connection accepted for room {self.room_group_name}")

    async def disconnect(self, close_code):
        print(f"[WS Disconnect] Room {self.room_group_name}, code: {close_code}")
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        print(f"[WS Receive] Data: {text_data}")
        data = json.loads(text_data)
        content = data.get('content', '').strip()

        if not content:
            return

        message = await self.save_message(content)
        print(f"[WS Receive] Message saved ID: {message.id}. Broadcasting to group.")

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': message.id,
                'content': content,  # send plain text to recipient
                'sender_id': self.user.id,
                'sender_name': self.user.get_full_name(),
                'created_at': message.created_at.isoformat(),
            }
        )

    async def chat_message(self, event):
        if event['sender_id'] == self.user.id:
            return
        await self.send(text_data=json.dumps({
            'message_id': event['message_id'],
            'content': event['content'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'created_at': event['created_at'],
        }))

    @database_sync_to_async
    def user_in_conversation(self):
        try:
            conv = Conversation.objects.get(id=self.conversation_id)
            return self.user in [conv.user, conv.lister]
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content):
        conv = Conversation.objects.get(id=self.conversation_id)
        conv.save()
        message = Message.objects.create(
            conversation=conv,
            sender=self.user,
            content=encrypt_message(content)
        )
        return message

    async def receive(self, text_data):
        data = json.loads(text_data)
        content = data.get('content', '').strip()
        if not content:
            return
        message = await self.save_message(content)
        
        # Broadcast message to chat room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': message.id,
                'content': content,
                'sender_id': self.user.id,
                'sender_name': self.user.get_full_name(),
                'created_at': message.created_at.isoformat(),
            }
        )
        
        # Notify recipient's notification channel
        recipient_id = await self.get_recipient_id()
        if recipient_id:
            unread_count = await self.get_unread_count(recipient_id)
            await self.channel_layer.group_send(
                f'notifications_{recipient_id}',
                {
                    'type': 'send_notification',
                    'data': {
                        'type': 'unread_count',
                        'conversation_id': self.conversation_id,
                        'unread_count': unread_count,
                    }
                }
            )

    @database_sync_to_async
    def get_recipient_id(self):
        try:
            conv = Conversation.objects.get(id=self.conversation_id)
            if conv.user == self.user:
                return conv.lister.id
            return conv.user.id
        except Exception:
            return None

    @database_sync_to_async
    def get_unread_count(self, user_id):
        from .models import Message
        return Message.objects.filter(
            conversation__id=self.conversation_id,
            is_read=False
        ).exclude(sender__id=user_id).count()
    
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return
        self.group_name = f'notifications_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_notification(self, event):
        await self.send(text_data=json.dumps(event['data']))