from django.db import models
from django.conf import settings
from property_app.models import Property


class Conversation(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='conversations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_conversations')
    lister = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lister_conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversations'
        unique_together = ['property', 'user', 'lister']
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.get_full_name()} ↔ {self.lister.get_full_name()} re: {self.property.title}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.get_full_name()}: {self.content[:50]}"