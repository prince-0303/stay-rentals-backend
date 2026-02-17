from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from ..models import User, MFASession
from ..serializers import UserLoginSerializer, UserLoginResponseSerializer, get_tokens_for_user
from ..utils import (
    user_requires_mfa,
    user_has_mfa_enabled,
    get_user_primary_mfa_method,
    create_mfa_verification_code,
    get_client_ip,
    get_user_agent,
)
import logging

logger = logging.getLogger(__name__)


# ─── LOGIN ────────────────────────────────────────────────────────────────────

class UserLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})

        if not serializer.is_valid():
            return Response(
                {'detail': 'Invalid email or password', 'errors': serializer.errors},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = serializer.validated_data['user']

        # ── Account checks ────────────────────────────────────────────
        if not user.is_active:
            return Response(
                {'detail': 'Your account has been disabled. Please contact support.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not user.is_email_verified:
            return Response(
                {
                    'detail': 'Please verify your email before logging in.',
                    'email': user.email,
                    'requires_verification': True,
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # ── KYC checks for listers ────────────────────────────────────
        if user.role == User.LISTER:
            if user.kyc_status == User.KYC_PENDING:
                return Response(
                    {
                        'detail': 'Your KYC verification is pending.',
                        'kyc_status': user.kyc_status,
                        'requires_kyc': True,
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            elif user.kyc_status == User.KYC_REJECTED:
                return Response(
                    {
                        'detail': f'Your KYC was rejected. Reason: {user.kyc_rejection_reason or "Not specified"}',
                        'kyc_status': user.kyc_status,
                        'rejection_reason': user.kyc_rejection_reason,
                        'requires_kyc': True,
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            elif user.kyc_status != User.KYC_APPROVED:
                return Response(
                    {
                        'detail': 'Please submit your KYC documents to access your account.',
                        'kyc_status': user.kyc_status,
                        'requires_kyc': True,
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        # ── MFA check ─────────────────────────────────────────────────
        mfa_required = user_requires_mfa(user)
        mfa_enabled = user_has_mfa_enabled(user)

        if mfa_required and not mfa_enabled:
            return Response(
                {
                    'detail': 'MFA is mandatory for admin accounts.',
                    'requires_mfa_setup': True,
                    'mfa_enforced': True,
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if mfa_enabled:
            ip_address = get_client_ip(request)
            user_agent = get_user_agent(request)

            mfa_session = MFASession.create_session(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent
            )

            primary_method = get_user_primary_mfa_method(user)

            if primary_method and primary_method.method_type in ['sms', 'email']:
                create_mfa_verification_code(user, primary_method.method_type)

            logger.info(f"MFA required for {user.email}")

            return Response({
                'detail': 'MFA verification required',
                'requires_mfa': True,
                'mfa_session_token': mfa_session.session_token,
                'mfa_method': primary_method.method_type if primary_method else None,
                'message': _get_mfa_message(primary_method),
            }, status=status.HTTP_200_OK)

        # ── Set cookies and return user info ──────────────────────────
        tokens = get_tokens_for_user(user)

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        logger.info(f"Login successful for {user.email}")

        response = Response({
            'message': 'Login successful',
            'user': UserLoginResponseSerializer(user).data,
        }, status=status.HTTP_200_OK)

        # ✅ Access token cookie (15 min, httpOnly)
        response.set_cookie(
            key='access_token',
            value=tokens['access'],
            httponly=True,
            secure=False,       # Set True in production (HTTPS)
            samesite='Lax',
            max_age=900,        # 15 minutes
        )

        # ✅ Refresh token cookie (7 days, httpOnly)
        response.set_cookie(
            key='refresh_token',
            value=tokens['refresh'],
            httponly=True,
            secure=False,       # Set True in production (HTTPS)
            samesite='Lax',
            max_age=604800,     # 7 days
        )

        return response


def _get_mfa_message(mfa_method):
    if not mfa_method:
        return 'Please verify with your MFA method.'
    if mfa_method.method_type == 'totp':
        return 'Please enter the 6-digit code from your authenticator app.'
    elif mfa_method.method_type == 'email':
        return 'A verification code has been sent to your email.'
    return 'Please verify with your MFA method.'


# ─── LOGOUT ───────────────────────────────────────────────────────────────────

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception as e:
            logger.error(f"Logout blacklist error: {e}")

        response = Response({'detail': 'Logged out successfully'}, status=status.HTTP_200_OK)
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response


# ─── TOKEN REFRESH ────────────────────────────────────────────────────────────

class CookieTokenRefreshView(TokenRefreshView):
    """
    Reads refresh_token from cookie → returns new access_token as cookie.
    Frontend doesn't need to handle tokens at all.
    """

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {'detail': 'No refresh token found. Please log in again.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Inject into request data for simplejwt to process
        request.data._mutable = True if hasattr(request.data, '_mutable') else None
        try:
            request.data['refresh'] = refresh_token
        except AttributeError:
            # QueryDict is immutable — create mutable copy
            data = request.data.copy()
            data['refresh'] = refresh_token
            request._data = data

        try:
            response = super().post(request, *args, **kwargs)
        except (TokenError, InvalidToken):
            return Response(
                {'detail': 'Refresh token expired. Please log in again.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if response.status_code == 200:
            new_access = response.data.get('access')
            new_refresh = response.data.get('refresh')  # rotated refresh token

            # Set new access cookie
            response.set_cookie(
                key='access_token',
                value=new_access,
                httponly=True,
                secure=False,
                samesite='Lax',
                max_age=900,
            )

            # Update refresh cookie if rotated
            if new_refresh:
                response.set_cookie(
                    key='refresh_token',
                    value=new_refresh,
                    httponly=True,
                    secure=False,
                    samesite='Lax',
                    max_age=604800,
                )

            # Don't expose tokens in response body
            response.data = {'detail': 'Token refreshed successfully'}

        return response