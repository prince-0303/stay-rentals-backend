from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from ..models import User, OTP
from ..serializers import (
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
)
from ..utils import generate_otp, send_otp_email


class PasswordResetRequestView(APIView):
    """Request password reset OTP"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            OTP.objects.filter(user=user, otp_type='password_reset').delete()
            
            otp_code = generate_otp()
            expires_at = timezone.now() + timedelta(minutes=10)
            
            OTP.objects.create(
                user=user,
                email=email,
                otp_code=otp_code,
                otp_type='password_reset',
                expires_at=expires_at
            )
            
            send_otp_email(email, otp_code, 'password_reset')
            
            return Response(
                {'detail': 'Password reset OTP sent.'},
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            return Response(
                {'detail': 'If account exists, OTP will be sent.'},
                status=status.HTTP_200_OK
            )


class PasswordResetConfirmView(APIView):
    """Confirm password reset with OTP"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp_code']
        new_password = serializer.validated_data['new_password']
        
        try:
            otp = OTP.objects.get(
                email=email,
                otp_code=otp_code,
                otp_type='password_reset',
                is_used=False
            )
            
            if not otp.is_valid():
                otp.delete()
                return Response(
                    {'detail': 'OTP expired.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user = otp.user
            user.set_password(new_password)
            user.save()
            
            otp.delete()
            
            return Response(
                {'detail': 'Password reset successful.'},
                status=status.HTTP_200_OK
            )
            
        except OTP.DoesNotExist:
            return Response(
                {'detail': 'Invalid OTP.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ChangePasswordView(APIView):
    """Change password (logged in)"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        new_password = serializer.validated_data['new_password']
        
        request.user.set_password(new_password)
        request.user.save()
        
        return Response(
            {'detail': 'Password changed.'},
            status=status.HTTP_200_OK
        )