from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
import qrcode
import io
import base64
import logging

from ..models import MFAMethod, MFABackupCode, MFASession, MFAVerificationCode
from ..serializers import (
    MFAMethodSerializer,
    MFASetupInitSerializer,
    MFAVerifySetupSerializer,
    MFALoginVerifySerializer,
    MFADisableSerializer,
    MFABackupCodesSerializer,
    MFASendCodeSerializer,
    get_tokens_for_user,
    UserLoginResponseSerializer,
)
from ..utils import (
    create_mfa_verification_code,
    check_mfa_rate_limit,
    log_mfa_attempt,
    user_requires_mfa,
    user_has_mfa_enabled,
    get_user_primary_mfa_method,
    get_client_ip,
)

logger = logging.getLogger(__name__)


class MFAStatusView(APIView):
    """Get MFA status for current user"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        mfa_enabled = user_has_mfa_enabled(user)
        mfa_enforced = user_requires_mfa(user)
        
        methods = MFAMethod.objects.filter(user=user, verified_at__isnull=False)
        backup_codes = MFABackupCode.objects.filter(user=user, is_used=False)
        
        should_show_recommendation = user.role == 'lister' and not mfa_enabled
        
        data = {
            'mfa_enabled': mfa_enabled,
            'mfa_enforced': mfa_enforced,
            'methods': MFAMethodSerializer(methods, many=True).data,
            'backup_codes_count': backup_codes.count(),
            'requires_setup': mfa_enforced and not mfa_enabled,
            'should_show_mfa_recommendation': should_show_recommendation,
        }
        
        return Response(data, status=status.HTTP_200_OK)


class MFASetupInitView(APIView):
    """Initialize MFA setup"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = MFASetupInitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        method_type = serializer.validated_data['method_type']
        
        mfa_method, created = MFAMethod.objects.get_or_create(
            user=user,
            method_type=method_type,
        )
        
        response_data = {'method_type': method_type, 'message': ''}
        
        if method_type == 'totp':
            # Generate TOTP secret and QR code
            if not mfa_method.secret_key:
                mfa_method.generate_totp_secret()
            
            totp_uri = mfa_method.get_totp_uri()
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(totp_uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            response_data.update({
                'qr_code': f'data:image/png;base64,{qr_code_base64}',
                'secret_key': mfa_method.secret_key,
                'message': 'Scan the QR code with your authenticator app.',
            })
        
        elif method_type == 'email':
            # Send email verification code
            create_mfa_verification_code(user, 'email')
            response_data.update({
                'email': user.email,
                'message': f'Verification code sent to {user.email}',
            })
        
        return Response(response_data, status=status.HTTP_200_OK)


class MFAVerifySetupView(APIView):
    """Verify MFA setup with code"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = MFAVerifySetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        method_type = serializer.validated_data['method_type']
        code = serializer.validated_data['code']
        
        try:
            mfa_method = MFAMethod.objects.get(
                user=user,
                method_type=method_type,
                is_enabled=True
            )
        except MFAMethod.DoesNotExist:
            return Response(
                {'detail': 'MFA method not initialized.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        is_valid = False
        
        if method_type == 'totp':
            is_valid = mfa_method.verify_totp_code(code)
        
        elif method_type == 'email':
            try:
                verification = MFAVerificationCode.objects.get(
                    user=user,
                    code=code,
                    method_type='email',
                    is_used=False
                )
                
                if verification.is_valid():
                    is_valid = True
                    verification.is_used = True
                    verification.save(update_fields=['is_used'])
                else:
                    return Response(
                        {'detail': 'Verification code expired.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            except MFAVerificationCode.DoesNotExist:
                return Response(
                    {'detail': 'Invalid verification code.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if not is_valid:
            return Response(
                {'detail': 'Invalid verification code.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark method as verified
        mfa_method.verified_at = timezone.now()
        
        # Set as primary if no other primary method exists
        if not MFAMethod.objects.filter(user=user, is_primary=True, verified_at__isnull=False).exists():
            mfa_method.is_primary = True
        
        mfa_method.save()
        
        # Generate backup codes
        backup_codes = MFABackupCode.generate_backup_codes(user)
        
        return Response({
            'detail': 'MFA setup completed successfully!',
            'backup_codes': backup_codes,
        }, status=status.HTTP_200_OK)


class MFARegenerateBackupCodesView(APIView):
    """Regenerate backup codes"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if not user_has_mfa_enabled(user):
            return Response(
                {'detail': 'MFA is not enabled.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        backup_codes = MFABackupCode.generate_backup_codes(user)
        
        return Response({
            'detail': 'Backup codes regenerated successfully!',
            'backup_codes': backup_codes,
        }, status=status.HTTP_200_OK)


class MFADisableView(APIView):
    """Disable MFA (requires password confirmation)"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = MFADisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        password = serializer.validated_data['password']
        method_type = serializer.validated_data['method_type']
        
        # Verify password
        if not user.check_password(password):
            return Response(
                {'detail': 'Incorrect password.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Admins cannot disable MFA
        if user_requires_mfa(user):
            return Response(
                {'detail': 'Admins cannot disable MFA.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if method_type == 'all':
            MFAMethod.objects.filter(user=user).delete()
            MFABackupCode.objects.filter(user=user).delete()
            
            logger.info(f"All MFA methods disabled for {user.email}")
            
            return Response(
                {'detail': 'All MFA methods have been disabled.'},
                status=status.HTTP_200_OK
            )
        else:
            deleted_count, _ = MFAMethod.objects.filter(
                user=user,
                method_type=method_type
            ).delete()
            
            if deleted_count == 0:
                return Response(
                    {'detail': f'{method_type.upper()} MFA is not enabled.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Delete backup codes if no methods remain
            if not MFAMethod.objects.filter(user=user, verified_at__isnull=False).exists():
                MFABackupCode.objects.filter(user=user).delete()
            
            logger.info(f"{method_type.upper()} MFA disabled for {user.email}")
            
            return Response(
                {'detail': f'{method_type.upper()} MFA has been disabled.'},
                status=status.HTTP_200_OK
            )


class MFASendCodeView(APIView):
    """Resend MFA code (Email only)"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = MFASendCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        mfa_session_token = request.data.get('mfa_session_token', '')
        
        if not mfa_session_token:
            return Response(
                {'detail': 'MFA session token required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            mfa_session = MFASession.objects.get(session_token=mfa_session_token)
        except MFASession.DoesNotExist:
            return Response(
                {'detail': 'Invalid MFA session.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not mfa_session.is_valid():
            return Response(
                {'detail': 'MFA session expired or invalid.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = mfa_session.user
        ip_address = get_client_ip(request)
        
        # Check rate limiting
        is_limited, limit_message = check_mfa_rate_limit(user.email, ip_address)
        
        if is_limited:
            return Response(
                {'detail': limit_message},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Send code via email
        create_mfa_verification_code(user, 'email')
        
        return Response(
            {'detail': f'Verification code sent to {user.email}'},
            status=status.HTTP_200_OK
        )


class MFALoginVerifyView(APIView):
    """Verify MFA code during login"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = MFALoginVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        mfa_session_token = serializer.validated_data['mfa_session_token']
        code = serializer.validated_data['code']
        
        try:
            mfa_session = MFASession.objects.get(session_token=mfa_session_token)
        except MFASession.DoesNotExist:
            return Response(
                {'detail': 'Invalid MFA session.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not mfa_session.is_valid():
            return Response(
                {'detail': 'MFA session expired or too many attempts.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = mfa_session.user
        ip_address = get_client_ip(request)
        
        # Check rate limiting
        is_limited, limit_message = check_mfa_rate_limit(user.email, ip_address)
        
        if is_limited:
            return Response(
                {'detail': limit_message},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        is_valid = False
        used_backup_code = False
        
        # Try backup code first (8 characters)
        if len(code) == 8:
            try:
                backup_code = MFABackupCode.objects.get(
                    user=user,
                    code=code,
                    is_used=False
                )
                backup_code.mark_as_used(ip_address=ip_address)
                is_valid = True
                used_backup_code = True
                
                logger.info(f"Backup code used for {user.email}")
            
            except MFABackupCode.DoesNotExist:
                pass
        
        # Try regular MFA methods (6 digits)
        if not is_valid and len(code) == 6:
            primary_method = get_user_primary_mfa_method(user)
            
            if not primary_method:
                log_mfa_attempt(user, ip_address, False, 'No MFA method configured')
                return Response(
                    {'detail': 'No MFA method configured.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if primary_method.method_type == 'totp':
                is_valid = primary_method.verify_totp_code(code)
            
            elif primary_method.method_type == 'email':
                try:
                    verification = MFAVerificationCode.objects.get(
                        user=user,
                        code=code,
                        method_type='email',
                        is_used=False
                    )
                    
                    if verification.is_valid():
                        is_valid = True
                        verification.is_used = True
                        verification.save(update_fields=['is_used'])
                
                except MFAVerificationCode.DoesNotExist:
                    pass
        
        if not is_valid:
            mfa_session.increment_attempts()
            log_mfa_attempt(user, ip_address, False, 'Invalid MFA code')
            
            remaining = mfa_session.max_attempts - mfa_session.attempts
            
            return Response(
                {
                    'detail': f'Invalid MFA code. {remaining} attempts remaining.',
                    'attempts_remaining': remaining,
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # MFA verified successfully
        mfa_session.is_verified = True
        mfa_session.save(update_fields=['is_verified'])
        
        log_mfa_attempt(user, ip_address, True)
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # Generate JWT tokens
        tokens = get_tokens_for_user(user)
        
        response_data = {
            'message': 'Login successful',
            'user': UserLoginResponseSerializer(user).data,
        }
        
        if used_backup_code:
            remaining_codes = MFABackupCode.objects.filter(
                user=user,
                is_used=False
            ).count()
            
            response_data['backup_code_warning'] = (
                f'You have {remaining_codes} backup codes remaining. '
                'Consider regenerating them if running low.'
            )
        
        logger.info(f"MFA login successful for {user.email}")
        
        response = Response(response_data, status=status.HTTP_200_OK)

        # ✅ Set Access Token Cookie
        response.set_cookie(
            key='access_token',
            value=tokens['access'],
            httponly=True,
            secure=False,  # Set True in production
            samesite='Lax',
            max_age=900,
        )

        # ✅ Set Refresh Token Cookie
        response.set_cookie(
            key='refresh_token',
            value=tokens['refresh'],
            httponly=True,
            secure=False,  # Set True in production
            samesite='Lax',
            max_age=604800,
        )
        
        return response