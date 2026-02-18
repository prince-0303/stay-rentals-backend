from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db import transaction
from django.conf import settings

from ..models import User, OTP
from ..serializers import RegisterOrVerifySerializer, ResendOTPSerializer
from ..utils import generate_otp, send_otp_email


class RegisterOrVerifyEmailView(APIView):
    """
    PRODUCTION-READY Registration & Email Verification
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        otp_code = request.data.get('otp', '').strip()
        
        if otp_code:
            # VERIFICATION MODE
            return self._handle_verification(request.data)
        else:
            # REGISTRATION MODE
            return self._handle_registration(request.data)
    
    def _handle_registration(self, data):
        """
        User Registration (NO KYC data collected here)
        """
        
        # Extract fields
        email = data.get('email', '').strip().lower()
        password = data.get('password', '').strip()
        password_confirm = data.get('password_confirm', '').strip()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        role = data.get('role', 'user').strip().lower()
        phone_number = data.get('phone_number', '').strip()
        
        # VALIDATION
        
        # Required fields
        if not all([email, password, password_confirm, first_name, last_name]):
            return Response(
                {'detail': 'Email, password, first name, and last name are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Password match
        if password != password_confirm:
            return Response(
                {'detail': 'Passwords do not match.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Valid role
        if role not in ['user', 'lister']:
            return Response(
                {'detail': 'Invalid role. Must be "user" or "lister".'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if email already registered & verified
        existing_user = User.objects.filter(email=email, is_email_verified=True).first()
        if existing_user:
            return Response(
                {'detail': 'Email already registered. Please login.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # CLEANUP OLD DATA
        
        # Delete unverified user with this email (allow re-registration)
        User.objects.filter(email=email, is_email_verified=False).delete()
        
        # Delete old OTPs
        OTP.objects.filter(email=email, otp_type='email_verification').delete()
        
        # CREATE OTP WITH PENDING DATA
        
        otp_code = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)
        
        pending_data = {
            'email': email,
            'password': password,  # Will be hashed after verification
            'first_name': first_name,
            'last_name': last_name,
            'role': role,
            'phone_number': phone_number,
        }
        
        # Create OTP
        OTP.objects.create(
            email=email,
            otp_code=otp_code,
            otp_type='email_verification',
            expires_at=expires_at,
            pending_data=pending_data,
        )
        
        # Send OTP email
        send_otp_email(email, otp_code, 'email_verification')
        
        # if settings.DEBUG:
        #     print(f"\n{'='*70}")
        #     print(f"📧 REGISTRATION STARTED")
        #     print(f"{'='*70}")
        #     print(f"Email: {email}")
        #     print(f"Role: {role}")
        #     print(f"OTP: {otp_code}")
        #     print(f"{'='*70}\n")
        
        return Response({
            'detail': 'Registration successful! Please verify your email with the OTP sent.',
            'email': email,
            'otp_sent': True,
        }, status=status.HTTP_201_CREATED)
    
    def _handle_verification(self, data):
        """
        Email Verification
        """
        
        email = data.get('email', '').strip().lower()
        otp_code = data.get('otp', '').strip()
        
        if not email or not otp_code:
            return Response(
                {'detail': 'Email and OTP are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
        
        # Check if OTP expired
        if not otp.is_valid():
            otp.delete()
            return Response(
                {'detail': 'OTP expired. Please request a new one.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get pending data
        pending = otp.pending_data
        if not pending:
            return Response(
                {'detail': 'Registration data not found. Please register again.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # CREATE USER ACCOUNT
        
        try:
            with transaction.atomic():
                # Final check - no verified user with this email
                if User.objects.filter(email=email, is_email_verified=True).exists():
                    return Response(
                        {'detail': 'Email already verified. Please login.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Delete any unverified user
                User.objects.filter(email=email, is_email_verified=False).delete()
                
                # Create user
                user = User.objects.create(
                    email=email,
                    first_name=pending['first_name'],
                    last_name=pending['last_name'],
                    role=pending['role'],
                    phone_number=pending.get('phone_number', ''),
                    is_email_verified=True,
                    is_active=True,
                    # ⚠️ NO AADHAR DATA HERE - will be added via KYC endpoint
                )
                
                user.set_password(pending['password'])
                user.save()
                
                # Delete OTP
                otp.delete()
                
                #  GENERATE JWT TOKENS FOR AUTO-LOGIN
                from ..serializers import get_tokens_for_user
                tokens = get_tokens_for_user(user)
                
                # if settings.DEBUG:
                #     print(f"\n{'='*70}")
                #     print(f"✅ USER CREATED & TOKENS GENERATED")
                #     print(f"{'='*70}")
                #     print(f"Email: {user.email}")
                #     print(f"Role: {user.role}")
                #     print(f"ID: {user.id}")
                #     print(f"Access Token: {tokens['access'][:50]}...")
                #     print(f"{'='*70}\n")
                
                # Different response based on role
                if user.role == User.LISTER:
                    return Response({
                        'detail': 'Email verified! Please submit your KYC documents to access your account.',
                        'email': user.email,
                        'verified': True,
                        'role': user.role,
                        'kyc_status': user.kyc_status,
                        'requires_kyc': True,
                        'access': tokens['access'],
                        'refresh': tokens['refresh'],
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response({
                        'detail': 'Email verified successfully! You can now login.',
                        'email': user.email,
                        'verified': True,
                        'role': user.role,
                        'access': tokens['access'],
                        'refresh': tokens['refresh'],
                    }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            if settings.DEBUG:
                print(f"❌ Error creating user: {e}")
                import traceback
                traceback.print_exc()
            
            return Response(
                {'detail': f'Error creating account: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ResendOTPView(APIView):
    """Resend verification OTP"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email'].lower()
        
        try:
            # Find the latest OTP
            old_otp = OTP.objects.filter(
                email=email,
                otp_type='email_verification',
                is_used=False
            ).latest('created_at')
            
            pending = old_otp.pending_data
            
            if not pending:
                return Response(
                    {'detail': 'No pending registration found. Please register again.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Delete old OTPs
            OTP.objects.filter(email=email, otp_type='email_verification').delete()
            
            # Create new OTP
            new_code = generate_otp()
            expires_at = timezone.now() + timedelta(minutes=10)
            
            OTP.objects.create(
                email=email,
                otp_code=new_code,
                otp_type='email_verification',
                expires_at=expires_at,
                pending_data=pending
            )
            
            # Send new OTP
            send_otp_email(email, new_code, 'email_verification')
            
            if settings.DEBUG:
                print(f"🔄 OTP resent to {email}: {new_code}")
            
            return Response(
                {'detail': 'New OTP sent to your email!'},
                status=status.HTTP_200_OK
            )
            
        except OTP.DoesNotExist:
            return Response(
                {'detail': 'No pending registration found for this email.'},
                status=status.HTTP_404_NOT_FOUND
            )