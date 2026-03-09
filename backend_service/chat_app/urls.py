from django.urls import path
from .views import ConversationListCreateView, MessageListView, ChatTokenView

urlpatterns = [
    path('conversations/', ConversationListCreateView.as_view(), name='conversations'),
    path('conversations/<int:conversation_id>/messages/', MessageListView.as_view(), name='messages'),
    path('token/', ChatTokenView.as_view(), name='chat_token'),
]