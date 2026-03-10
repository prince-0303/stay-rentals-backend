import firebase_admin
from firebase_admin import credentials, messaging
import os

def initialize_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH'))
        firebase_admin.initialize_app(cred)

def send_push_notification(token, title, body, data=None):
    initialize_firebase()
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=token,
        )
        messaging.send(message)
        return True
    except Exception as e:
        print(f"FCM error: {e}")
        return False

def send_push_to_user(user, title, body, data=None):
    from .models import FCMToken
    tokens = FCMToken.objects.filter(user=user).values_list('token', flat=True)
    for token in tokens:
        send_push_notification(token, title, body, data)