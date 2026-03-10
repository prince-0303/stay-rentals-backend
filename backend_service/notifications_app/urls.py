from django.urls import path
from .views import RegisterFCMTokenView, NotificationListView, MarkNotificationsReadView

urlpatterns = [
    path('register-token/', RegisterFCMTokenView.as_view(), name='register-fcm-token'),
    path('', NotificationListView.as_view(), name='notifications-list'),
    path('mark-read/', MarkNotificationsReadView.as_view(), name='notifications-mark-read'),
]
