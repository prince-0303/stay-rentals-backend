from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import FCMToken

class RegisterFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'token required'}, status=400)
        FCMToken.objects.update_or_create(
            token=token,
            defaults={'user': request.user}
        )
        return Response({'message': 'Token registered'})

    def delete(self, request):
        token = request.data.get('token')
        FCMToken.objects.filter(user=request.user, token=token).delete()
        return Response({'message': 'Token removed'})


from .models import Notification

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user)[:30]
        data = [{
            'id': n.id,
            'title': n.title,
            'body': n.body,
            'data': n.data,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        } for n in notifications]
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'notifications': data, 'unread_count': unread_count})


class MarkNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        notification_id = request.data.get('id')
        if notification_id:
            Notification.objects.filter(user=request.user, id=notification_id).delete()
        else:
            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'message': 'Done'})
