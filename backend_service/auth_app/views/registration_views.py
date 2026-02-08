from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from ..models import User, OTP
from ..serializers import RegisterOrVerifySerializer, ResendOTPSerializer
from ..utils import generate_otp, send_otp_email


class RegisterOrVerifyEmailView(APIView):
    """
    Registration & Verification in ONE endpoint.
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
        
        # Check if user already exists and is verified
        existing_user = User.objects.filter(email=email).first()
        if existing_user and existing_user.is_email_verified:
            return Response(
                {'detail': 'Email already registered and verified. Please login.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # If user exists but not verified, delete old user and OTPs
        if existing_user and not existing_user.is_email_verified:
            existing_user.delete()
        
        # Delete old pending OTPs
        OTP.objects.filter(email=email, otp_type='email_verification').delete()
        
        # Create OTP with pending data
        otp_code = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)
        
        # Store password in plain text in pending_data (will be hashed when creating user)
        OTP.objects.create(
            email=email,
            otp_code=otp_code,
            otp_type='email_verification',
            expires_at=expires_at,
            user=None,  # No user yet!
            pending_data={
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'password': data['password'],  # Store plain password - will hash on user creation
                'role': data['role'],
                'phone_number': data.get('phone_number', ''),
            }
        )
        
        # Send OTP
        send_otp_email(email, otp_code, 'email_verification')
        
        return Response({
            'detail': 'Registration successful! OTP sent to your email. Please verify within 10 minutes.',
            'email': email,
            'requires_verification': True
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
                {'detail': 'Invalid OTP. Please check and try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check expiry
        if not otp.is_valid():
            otp.delete()
            return Response(
                {'detail': 'OTP has expired. Please register again.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check user doesn't exist (safety)
        if User.objects.filter(email=email, is_email_verified=True).exists():
            otp.delete()
            return Response(
                {'detail': 'Email already registered and verified. Please login.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user from pending_data
        pending = otp.pending_data
        
        try:
            # Delete any unverified user with this email
            User.objects.filter(email=email, is_email_verified=False).delete()
            
            # Create new user - password will be hashed by set_password
            user = User.objects.create(
                email=email,
                first_name=pending['first_name'],
                last_name=pending['last_name'],
                role=pending['role'],
                phone_number=pending.get('phone_number', ''),
                is_email_verified=True,  # Verified!
                is_active=True,
            )
            
            # Set password (this hashes it)
            user.set_password(pending['password'])
            user.save()
            
            # Delete OTP
            otp.delete()
            
            return Response({
                'detail': 'Email verified successfully! You can now login with your credentials.',
                'email': user.email,
                'verified': True
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'detail': f'Error creating user: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            
            if not pending:
                return Response(
                    {'detail': 'No pending registration data found. Please register again.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
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
                {'detail': 'New OTP sent to your email!'},
                status=status.HTTP_200_OK
            )
            
        except OTP.DoesNotExist:
            return Response(
                {'detail': 'No pending registration found for this email.'},
                status=status.HTTP_404_NOT_FOUND
            )