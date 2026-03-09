from rest_framework import serializers
from .models import Conversation, Message
from .encryption import decrypt_message


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    sender_id = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()  # ← changed to method field

    class Meta:
        model = Message
        fields = ['id', 'sender_id', 'sender_name', 'content', 'is_read', 'created_at']

    def get_sender_name(self, obj):
        return obj.sender.get_full_name()

    def get_sender_id(self, obj):
        return obj.sender.id

    def get_content(self, obj):
        return decrypt_message(obj.content)  # ← decrypt on read


class ConversationSerializer(serializers.ModelSerializer):
    property_title = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    lister_name = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'property', 'property_title',
            'user_name', 'lister_name',
            'last_message', 'unread_count',
            'created_at', 'updated_at'
        ]

    def get_property_title(self, obj):
        return obj.property.title

    def get_user_name(self, obj):
        return obj.user.get_full_name()

    def get_lister_name(self, obj):
        return obj.lister.get_full_name()

    def get_last_message(self, obj):
        msg = obj.messages.last()
        if msg:
            return {
                'content': decrypt_message(msg.content),  # ← decrypt here too
                'created_at': msg.created_at,
                'sender_name': msg.sender.get_full_name()
            }
        return None

    def get_unread_count(self, obj):
        user = self.context.get('request').user
        return obj.messages.filter(is_read=False).exclude(sender=user).count()