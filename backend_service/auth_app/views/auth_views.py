from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import User
from ..serializers import UserLoginSerializer, UserLoginResponseSerializer, get_tokens_for_user


class UserLoginView(APIView):
    """Email/Password Login"""
    permission_classes = [AllowAny]
    
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
                    'requires_verification': True
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        if user.role == User.LISTER:
            if user.kyc_status == User.KYC_PENDING:
                return Response(
                    {
                        'detail': 'Your KYC verification is pending. Admin will review your documents soon.',
                        'kyc_status': user.kyc_status,
                        'requires_kyc': True
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            elif user.kyc_status == User.KYC_REJECTED:
                return Response(
                    {
                        'detail': f'Your KYC was rejected. Reason: {user.kyc_rejection_reason or "Not specified"}',
                        'kyc_status': user.kyc_status,
                        'rejection_reason': user.kyc_rejection_reason,
                        'requires_kyc': True
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            elif user.kyc_status != User.KYC_APPROVED:
                return Response(
                    {
                        'detail': 'Please submit your KYC documents to access your account.',
                        'kyc_status': user.kyc_status,
                        'requires_kyc': True
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
        
        try:
            tokens = get_tokens_for_user(user)
            
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            return Response({
                'message': 'Login successful',
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'user': UserLoginResponseSerializer(user).data,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'detail': f'Error generating tokens: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserLogoutView(APIView):
    """Logout"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'detail': 'Refresh token required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {'detail': 'Successfully logged out'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'detail': f'Logout failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )