from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from drf_spectacular.utils import extend_schema, OpenApiResponse

from ..models import User, MFASession
from ..serializers import (
    UserLoginSerializer, UserLoginResponseSerializer, get_tokens_for_user,
    GoogleLoginSerializer, UserSerializer,
)
from ..google_oauth import exchange_code_for_token, verify_google_token, get_or_create_user_from_google
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


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _set_auth_cookies(response, tokens):
    """Attach access_token and refresh_token as httpOnly cookies."""
    response.set_cookie(
        key='access_token',
        value=tokens['access'],
        httponly=True,
        secure=False,
        samesite='Lax',
        max_age=900,
    )
    response.set_cookie(
        key='refresh_token',
        value=tokens['refresh'],
        httponly=True,
        secure=False,
        samesite='Lax',
        max_age=604800,
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


# ─── LOGIN ────────────────────────────────────────────────────────────────────

class UserLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=UserLoginSerializer,
        responses={
            200: OpenApiResponse(description='Login successful or MFA required'),
            401: OpenApiResponse(description='Invalid email or password'),
            403: OpenApiResponse(description='Account disabled / Email not verified / KYC pending or rejected / MFA not set up'),
        }
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})

        if not serializer.is_valid():
            return Response(
                {'detail': 'Invalid email or password', 'errors': serializer.errors},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = serializer.validated_data['user']

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

        if user.role == User.LISTER:
            if user.kyc_status == User.KYC_PENDING:
                # Already submitted — cannot do anything; no auth cookie needed
                return Response(
                    {
                        'detail': 'Your KYC verification is pending review by our admin team.',
                        'kyc_status': user.kyc_status,
                        'requires_kyc': True,
                        'user': UserLoginResponseSerializer(user).data,
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            elif user.kyc_status == User.KYC_REJECTED:
                # Rejected — lister must resubmit. Issue tokens so they can call /kyc/submit/
                tokens = get_tokens_for_user(user)
                response = Response(
                    {
                        'detail': f'Your KYC was rejected. Reason: {user.kyc_rejection_reason or "Not specified"}',
                        'kyc_status': user.kyc_status,
                        'rejection_reason': user.kyc_rejection_reason,
                        'requires_kyc': True,
                        'user': UserLoginResponseSerializer(user).data,
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
                return _set_auth_cookies(response, tokens)
            elif user.kyc_status != User.KYC_APPROVED:
                # Not submitted yet — must submit. Issue tokens so they can call /kyc/submit/
                tokens = get_tokens_for_user(user)
                response = Response(
                    {
                        'detail': 'Please submit your KYC documents to access your account.',
                        'kyc_status': user.kyc_status,
                        'requires_kyc': True,
                        'user': UserLoginResponseSerializer(user).data,
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
                return _set_auth_cookies(response, tokens)

        mfa_required = user_requires_mfa(user)
        mfa_enabled = user_has_mfa_enabled(user)

        # if mfa_required and not mfa_enabled:
        #     return Response(
        #         {
        #             'detail': 'MFA is mandatory for admin accounts.',
        #             'requires_mfa_setup': True,
        #             'mfa_enforced': True,
        #         },
        #         status=status.HTTP_403_FORBIDDEN
        #     )

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

        tokens = get_tokens_for_user(user)
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        logger.info(f"Login successful for {user.email}")

        response = Response({
            'message': 'Login successful',
            'user': UserLoginResponseSerializer(user).data,
        }, status=status.HTTP_200_OK)

        return _set_auth_cookies(response, tokens)


# ─── GOOGLE LOGIN ─────────────────────────────────────────────────────────────

class GoogleLoginView(APIView):
    """Google OAuth Login — sets httpOnly cookies, same as UserLoginView."""
    permission_classes = [AllowAny]

    @extend_schema(
        request=GoogleLoginSerializer,
        responses={
            200: OpenApiResponse(description='Login successful'),
            400: OpenApiResponse(description='Invalid Google code or token'),
        }
    )

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']

        try:
            token_data = exchange_code_for_token(code)
            id_token_str = token_data.get('id_token')

            if not id_token_str:
                return Response(
                    {'error': 'No ID token from Google'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            google_user_data = verify_google_token(id_token_str)
            user, created = get_or_create_user_from_google(google_user_data)
            tokens = get_tokens_for_user(user)

            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            logger.info(f"Google OAuth: User logged in: {user.email}")

            response = Response({
                'message': 'Login successful',
                'user': UserSerializer(user).data,
            }, status=status.HTTP_200_OK)

            return _set_auth_cookies(response, tokens)

        except Exception as e:
            logger.error(f"Google OAuth error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class GoogleLoginTokenView(APIView):
    """Alternative Google endpoint"""
    permission_classes = [AllowAny]

    def post(self, request):
        return GoogleLoginView.as_view()(request)


# ─── LOGOUT ───────────────────────────────────────────────────────────────────

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: OpenApiResponse(description='Logged out successfully'),
        }
    )

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
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {'detail': 'No refresh token found. Please log in again.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        request.data['refresh'] = refresh_token

        try:
            response = super().post(request, *args, **kwargs)
        except (TokenError, InvalidToken):
            return Response(
                {'detail': 'Refresh token expired. Please log in again.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if response.status_code == 200:
            new_access = response.data.get('access')
            new_refresh = response.data.get('refresh')
            response.set_cookie('access_token', new_access, httponly=True, secure=False, samesite='Lax', max_age=3600)
            if new_refresh:
                response.set_cookie('refresh_token', new_refresh, httponly=True, secure=False, samesite='Lax', max_age=604800)
            response.data = {'detail': 'Token refreshed successfully'}

        return response


# ─── ACCOUNT MANAGEMENT ───────────────────────────────────────────────────────

class DeactivateAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        user.is_active = False
        user.save(update_fields=['is_active'])
        response = Response({'detail': 'Account deactivated.'}, status=status.HTTP_200_OK)
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.delete()
        response = Response({'detail': 'Account deleted.'}, status=status.HTTP_200_OK)
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response