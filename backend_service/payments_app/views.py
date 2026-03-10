import razorpay
import hmac
import hashlib
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from property_app.models import Property
from .models import Payment
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from notifications_app.tasks import send_notification_task

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        property = Property.objects.filter(pk=pk, is_active=True, is_blocked=False).first()
        if not property:
            return Response({'error': 'Property not found'}, status=status.HTTP_404_NOT_FOUND)

        if Payment.objects.filter(property=property, status=Payment.STATUS_SUCCESS).exists():
            return Response({'error': 'Advance already paid for this property'}, status=status.HTTP_400_BAD_REQUEST)

        advance_amount = int(property.rent_price * 2 * 100)

        order = client.order.create({
            'amount': advance_amount,
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'property_id': str(property.id),
                'user_id': str(request.user.id),
            }
        })

        Payment.objects.create(
            user=request.user,
            property=property,
            amount=property.rent_price * 2,
            razorpay_order_id=order['id'],
        )

        return Response({
            'order_id': order['id'],
            'amount': advance_amount,
            'currency': 'INR',
            'key': settings.RAZORPAY_KEY_ID,
            'property_title': property.title,
            'user_name': request.user.get_full_name() or request.user.email,
            'user_email': request.user.email,
        })


class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')

        payment = Payment.objects.filter(
            razorpay_order_id=razorpay_order_id,
            user=request.user
        ).first()

        if not payment:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        msg = f"{razorpay_order_id}|{razorpay_payment_id}"
        generated_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            msg.encode(),
            hashlib.sha256
        ).hexdigest()

        if generated_signature == razorpay_signature:
            payment.razorpay_payment_id = razorpay_payment_id
            payment.razorpay_signature = razorpay_signature
            payment.status = Payment.STATUS_SUCCESS
            payment.save()

            # Lock the property
            prop = payment.property
            prop.is_blocked = True
            prop.save()

            # Notify tenant
            send_notification_task.delay(
                request.user.id,
                'Payment Successful',
                f'Advance payment for {prop.title} confirmed!',
                {'type': 'payment', 'property_id': str(prop.id)}
            )

            # Notify lister
            lister = prop.lister
            if lister:
                send_notification_task.delay(
                    lister.id,
                    'Advance Payment Received',
                    f'{request.user.get_full_name() or request.user.email} paid advance for {prop.title}!',
                    {'type': 'payment_received', 'property_id': str(prop.id)}
                )

            # Send booking emails
            from auth_app.tasks import send_booking_confirmed_email_task, send_booking_received_email_task
            send_booking_confirmed_email_task.delay(
                request.user.email,
                request.user.first_name or request.user.email,
                prop.title,
                str(payment.amount),
                razorpay_payment_id
            )
            if lister:
                send_booking_received_email_task.delay(
                    lister.email,
                    lister.first_name or lister.email,
                    request.user.get_full_name() or request.user.email,
                    prop.title,
                    str(payment.amount),
                    razorpay_payment_id
                )
            return Response({'message': 'Payment verified successfully'})
        else:
            payment.status = Payment.STATUS_FAILED
            payment.save()
            return Response({'error': 'Payment verification failed'}, status=status.HTTP_400_BAD_REQUEST)


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, property_id):
        payment = Payment.objects.filter(
            property__id=property_id,
            status=Payment.STATUS_SUCCESS
        ).select_related('user').first()

        if payment:
            return Response({
                "is_paid": True,
                "paid_by": payment.user.email,
                "amount": float(payment.amount),
                "paid_at": payment.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
        return Response({
            "is_paid": False,
            "paid_by": None,
            "amount": None,
            "paid_at": None,
        })


class ListerEarningsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = Payment.objects.filter(
            property__lister=request.user,
            status='success'
        ).select_related('property', 'user').order_by('-created_at')

        total_earned = payments.aggregate(total=Sum('amount'))['total'] or 0

        payments_list = [
            {
                "property_title": p.property.title,
                "tenant_email": p.user.email,
                "amount": float(p.amount),
                "paid_at": p.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            for p in payments
        ]

        monthly_data = (
            Payment.objects.filter(
                property__lister=request.user,
                status='success'
            )
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(amount=Sum('amount'))
            .order_by('month')
        )

        monthly_summary = [
            {
                "month": entry['month'].strftime("%b %Y"),
                "amount": float(entry['amount'])
            }
            for entry in monthly_data
        ]

        return Response({
            "total_earned": float(total_earned),
            "payments": payments_list,
            "monthly_summary": monthly_summary,
        })
    
class UserPaymentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = Payment.objects.filter(
            user=request.user,
            status=Payment.STATUS_SUCCESS
        ).select_related('property').order_by('-created_at')

        data = [{
            'id': p.id,
            'property_id': p.property.id,
            'property_title': p.property.title,
            'property_city': p.property.city,
            'amount': str(p.amount),
            'status': p.status,
            'razorpay_payment_id': p.razorpay_payment_id,
            'created_at': p.created_at.strftime('%d %b %Y'),
        } for p in payments]

        return Response({'payments': data, 'total': len(data)})