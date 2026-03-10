from celery import shared_task
from .firebase import send_push_to_user
from django.contrib.auth import get_user_model
User = get_user_model()

@shared_task
def send_notification_task(user_id, title, body, data=None):
    try:
        user = User.objects.get(id=user_id)
        # Save to DB
        from .models import Notification
        Notification.objects.create(user=user, title=title, body=body, data=data or {})
        # Firebase push
        send_push_to_user(user, title, body, data or {})
    except User.DoesNotExist:
        pass
