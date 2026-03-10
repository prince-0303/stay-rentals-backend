from django.urls import path
from .views import CreateOrderView, VerifyPaymentView, PaymentStatusView, ListerEarningsView, UserPaymentHistoryView

urlpatterns = [
    path('create-order/<int:pk>/', CreateOrderView.as_view(), name='create-order'),
    path('verify/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('status/<int:property_id>/', PaymentStatusView.as_view(), name='payment-status'),
    path('lister-earnings/', ListerEarningsView.as_view(), name='lister-earnings'),
    path('my-payments/', UserPaymentHistoryView.as_view(), name='my-payments'),
]
