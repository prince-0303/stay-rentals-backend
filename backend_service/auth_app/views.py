from django.utils import timezone
from django.contrib.auth.hashers import make_password
from datetime import timedelta
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, OTP
from .serializers import (
    RegisterOrVerifySerializer,
    ResendOTPSerializer,
    UserLoginSerializer,
    GoogleLoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
    UserSerializer,
    UserUpdateSerializer,
    get_tokens_for_user,
)
from .permissions import IsAdmin
from .utils import generate_otp, send_otp_email
from .google_oauth import exchange_code_for_token, verify_google_token, get_or_create_user_from_google


class RegisterOrVerifyEmailView(APIView):
    """
    Registration & Verification in ONE endpoint.
    
    WITHOUT otp → Register (create OTP entry, DON'T create user)
    WITH otp → Verify (create user from pending_data, delete OTP)
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = RegisterOrVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        otp_code = serializer.validated_data.get('otp', '').strip()
        
        # No OTP = Registration
        if not otp_code:
            return self._handle_registration(serializer.validated_data)
        
        # Has OTP = Verification
        return self._handle_verification(serializer.validated_data)
    
    def _handle_registration(self, data):
        """Step 1: Save pending data in OTP, send email, DON'T create user"""
        email = data['email']
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            return Response(
                {'detail': 'Email already registered.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete old pending OTPs
        OTP.objects.filter(email=email, otp_type='email_verification').delete()
        
        # Create OTP with pending data
        otp_code = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)
        
        OTP.objects.create(
            email=email,
            otp_code=otp_code,
            otp_type='email_verification',
            expires_at=expires_at,
            user=None,  # No user yet!
            pending_data={
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'password': make_password(data['password']),  # Hash it
                'role': data['role'],
                'phone_number': data.get('phone_number', ''),
            }
        )
        
        # Send OTP
        send_otp_email(email, otp_code, 'email_verification')
        
        return Response({
            'detail': 'OTP sent! Check your email.',
            'email': email
        }, status=status.HTTP_200_OK)
    
    def _handle_verification(self, data):
        """Step 2: Verify OTP, create user from pending_data, delete OTP"""
        email = data['email']
        otp_code = data['otp']
        
        # Find OTP
        try:
            otp = OTP.objects.get(
                email=email,
                otp_code=otp_code,
                otp_type='email_verification',
                is_used=False
            )
        except OTP.DoesNotExist:
            return Response(
                {'detail': 'Invalid or expired OTP.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check expiry
        if not otp.is_valid():
            otp.delete()
            return Response(
                {'detail': 'OTP expired. Please register again.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check user doesn't exist (safety)
        if User.objects.filter(email=email).exists():
            otp.delete()
            return Response(
                {'detail': 'Email already registered.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user from pending_data
        pending = otp.pending_data
        user = User.objects.create(
            email=email,
            first_name=pending['first_name'],
            last_name=pending['last_name'],
            password=pending['password'],  # Already hashed
            role=pending['role'],
            phone_number=pending.get('phone_number', ''),
            is_email_verified=True,  # Verified!
            is_active=True,
        )
        
        # Delete OTP
        otp.delete()
        
        return Response({
            'detail': 'Email verified! You can now login.',
            'email': user.email
        }, status=status.HTTP_201_CREATED)


class ResendOTPView(APIView):
    """Resend OTP for pending registration"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        # Find pending OTP
        try:
            old_otp = OTP.objects.filter(
                email=email,
                otp_type='email_verification',
                is_used=False
            ).latest('created_at')
            
            # Delete old, create new
            pending = old_otp.pending_data
            OTP.objects.filter(email=email, otp_type='email_verification').delete()
            
            new_code = generate_otp()
            expires_at = timezone.now() + timedelta(minutes=10)
            
            OTP.objects.create(
                email=email,
                otp_code=new_code,
                otp_type='email_verification',
                expires_at=expires_at,
                user=None,
                pending_data=pending  # Reuse pending data
            )
            
            send_otp_email(email, new_code, 'email_verification')
            
            return Response(
                {'detail': 'New OTP sent!'},
                status=status.HTTP_200_OK
            )
            
        except OTP.DoesNotExist:
            return Response(
                {'detail': 'No pending registration found.'},
                status=status.HTTP_404_NOT_FOUND
            )


class GoogleLoginView(APIView):
    """Google OAuth Login"""
    permission_classes = [AllowAny]
    
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
            
            return Response({
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'user': UserSerializer(user).data,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class GoogleLoginTokenView(APIView):
    """Alternative Google endpoint"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        return GoogleLoginView.as_view()(request)


class UserLoginView(APIView):
    """Email/Password Login"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        tokens = get_tokens_for_user(user)
        
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        return Response({
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': UserSerializer(user).data,
        }, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    """Logout"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'detail': 'Logged out'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'detail': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


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


class UserProfileView(generics.RetrieveUpdateAPIView):
    """Get/Update user profile"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserSerializer
        return UserUpdateSerializer
    
    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    """List users (Admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = UserSerializer
    queryset = User.objects.all()
    
    def get_queryset(self):
        queryset = User.objects.all()
        
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        is_verified = self.request.query_params.get('is_email_verified')
        if is_verified is not None:
            queryset = queryset.filter(is_email_verified=is_verified.lower() == 'true')
        
        return queryset