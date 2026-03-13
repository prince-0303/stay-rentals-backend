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
        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ChatTokenView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description='WS Token generated')})
    def get(self, request):
        user = request.user
        tokens = get_tokens_for_user(user)
        return Response({'token': tokens['access']}, status=status.HTTP_200_OK)