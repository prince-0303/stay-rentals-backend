from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from auth_app.serializers import get_tokens_for_user
from property_app.models import Property
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class ConversationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ConversationSerializer(many=True))
    def get(self, request):
        user = request.user
        conversations = Conversation.objects.filter(
            user=user
        ) | Conversation.objects.filter(lister=user)
        conversations = conversations.distinct().order_by('-updated_at')
        serializer = ConversationSerializer(conversations, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(responses=ConversationSerializer)
    def post(self, request):
        property_id = request.data.get('property_id')
        property = get_object_or_404(Property, pk=property_id, is_active=True, is_blocked=False)

        if request.user == property.lister:
            return Response({"error": "You cannot start a conversation with yourself."}, status=status.HTTP_400_BAD_REQUEST)

        conversation, created = Conversation.objects.get_or_create(
            property=property,
            user=request.user,
            lister=property.lister
        )
        serializer = ConversationSerializer(conversation, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MessageSerializer(many=True))
    def get(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if request.user not in [conversation.user, conversation.lister]:
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        messages = conversation.messages.all()
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if request.user not in [conversation.user, conversation.lister]:
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        content = request.data.get('content', '').strip()
        if not content:
            return Response({"error": "Message content is required."}, status=status.HTTP_400_BAD_REQUEST)

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content,
        )
        conversation.updated_at = message.created_at
        conversation.save(update_fields=['updated_at'])

        # Determine recipient (the other party in the conversation)
        recipient = conversation.lister if request.user == conversation.user else conversation.user

        channel_layer = get_channel_layer()

        # Broadcast the new message to the chat room group (same as WS path)
        async_to_sync(channel_layer.group_send)(
            f'chat_{conversation_id}',
            {
                'type': 'chat_message',
                'message_id': message.id,
                'content': content,
                'sender_id': request.user.id,
                'sender_name': request.user.get_full_name(),
                'created_at': message.created_at.isoformat(),
            }
        )

        # Broadcast unread count update to recipient's notification socket
        unread_count = Message.objects.filter(
            conversation__id=conversation_id,
            is_read=False
        ).exclude(sender__id=recipient.id).count()

        async_to_sync(channel_layer.group_send)(
            f'notifications_{recipient.id}',
            {
                'type': 'send_notification',
                'data': {
                    'type': 'unread_count',
                    'conversation_id': conversation_id,
                    'unread_count': unread_count,
                }
            }
        )

        # Trigger FCM push notification via Celery (same as WS path)
        from notifications_app.tasks import send_notification_task
        sender_name = request.user.get_full_name() or request.user.email
        send_notification_task.delay(
            recipient.id,
            'New Message',
            f'{sender_name} sent you a message',
            {'type': 'message', 'conversation_id': str(conversation_id)}
        )

        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ChatTokenView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description='WS Token generated')})
    def get(self, request):
        user = request.user
        tokens = get_tokens_for_user(user)
        return Response({'token': tokens['access']}, status=status.HTTP_200_OK)