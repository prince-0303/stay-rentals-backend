from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from datetime import timedelta
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
import logging

from ..models import User, OTP
from ..serializers import (
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
)
from ..utils import generate_otp, send_otp_email, get_client_ip

logger = logging.getLogger(__name__)


class PasswordResetRequestView(APIView):
    """
    Request password reset OTP
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email'].lower()
        ip_address = get_client_ip(request)
        
        # RATE LIMITING
        
        # Email-based rate limit (5 requests per 5 minutes)
        email_cache_key = f'password_reset_email_{email}'
        email_attempts = cache.get(email_cache_key, 0)
        
        if email_attempts >= 5:
            logger.warning(f"Password reset rate limit exceeded for email: {email}")
            return Response(
                {'detail': 'Too many password reset requests. Please try again in 5 minutes.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # IP-based rate limit (10 requests per 5 minutes)
        ip_cache_key = f'password_reset_ip_{ip_address}'
        ip_attempts = cache.get(ip_cache_key, 0)
        
        if ip_attempts >= 10:
            logger.warning(f"Password reset rate limit exceeded for IP: {ip_address}")
            return Response(
                {'detail': 'Too many password reset requests from this IP. Please try again in 5 minutes.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Increment counters (5 minutes = 300 seconds)
        cache.set(email_cache_key, email_attempts + 1, 300)
        cache.set(ip_cache_key, ip_attempts + 1, 300)
        
        # SEND OTP
        
        try:
            user = User.objects.get(email=email)
            
            # Delete old OTPs
            OTP.objects.filter(user=user, otp_type='password_reset').delete()
            
            # Generate new OTP
            otp_code = generate_otp()
            expires_at = timezone.now() + timedelta(minutes=10)
            
            OTP.objects.create(
                user=user,
                email=email,
                otp_code=otp_code,
                otp_type='password_reset',
                expires_at=expires_at
            )
            
            # Send OTP email
            send_otp_email(email, otp_code, 'password_reset')
            
            logger.info(f"Password reset OTP sent to {email} from IP {ip_address}")
            
            return Response(
                {'detail': 'Password reset OTP sent to your email.'},
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            # Prevent user enumeration - return same message
            logger.info(f"Password reset requested for non-existent email: {email}")
            return Response(
                {'detail': 'If an account exists with this email, you will receive a password reset OTP.'},
                status=status.HTTP_200_OK
            )


class PasswordResetConfirmView(APIView):
    """
    Confirm password reset with OTP
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email'].lower()
        otp_code = serializer.validated_data['otp_code']
        new_password = serializer.validated_data['new_password']
        
        try:
            otp = OTP.objects.get(
                email=email,
                otp_code=otp_code,
                otp_type='password_reset',
                is_used=False
            )
            
            # Check if OTP is valid (not expired)
            if not otp.is_valid():
                otp.delete()
                return Response(
                    {'detail': 'OTP has expired. Please request a new password reset.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user = otp.user
            
            # Wrap in transaction for atomicity
            with transaction.atomic():
                # Change password
                user.set_password(new_password)
                user.save(update_fields=['password'])
                
                # Delete OTP
                otp.delete()
                
                # Delete all other OTPs for this user
                OTP.objects.filter(user=user, otp_type='password_reset').delete()
            
            logger.info(f"Password reset successful for user: {user.email}")
            
            # TODO: Send email notification about password change
            # TODO: Invalidate all existing sessions/tokens for this user
            
            return Response(
                {'detail': 'Password reset successful. You can now login with your new password.'},
                status=status.HTTP_200_OK
            )
            
        except OTP.DoesNotExist:
            logger.warning(f"Invalid OTP attempt for password reset: {email}")
            return Response(
                {'detail': 'Invalid or expired OTP.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ChangePasswordView(APIView):
    """
    Change password (logged in user)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        new_password = serializer.validated_data['new_password']
        user = request.user
        
        # Wrap in transaction
        with transaction.atomic():
            user.set_password(new_password)
            user.save(update_fields=['password'])
        
        logger.info(f"Password changed for user: {user.email}")
        
        # TODO: Send email notification about password change
        # TODO: Optionally invalidate all other sessions (force re-login)
        
        return Response(
            {'detail': 'Password changed successfully.'},
            status=status.HTTP_200_OK
        )