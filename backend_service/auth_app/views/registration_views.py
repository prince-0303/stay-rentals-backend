from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction
from django.conf import settings

from ..models import User, OTP
from ..serializers import RegisterOrVerifySerializer, ResendOTPSerializer
from ..utils import generate_otp, send_otp_email


class RegisterOrVerifyEmailView(APIView):
    """
    Registration & Verification in ONE endpoint.
    Handles both regular users and listers with KYC.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def post(self, request):
        # Check if this is verification (has OTP) or registration
        otp_code = request.data.get('otp', '').strip()
        
        if otp_code:
            # VERIFICATION MODE
            return self._handle_verification(request.data)
        else:
            # REGISTRATION MODE
            return self._handle_registration(request.data, request.FILES)
    
    def _handle_registration(self, data, files):
        """Step 1: Validate, create temp user for listers, send OTP"""
        
        if settings.DEBUG:
            print(f"\n{'='*70}")
            print(f"REGISTRATION DEBUG")
            print(f"{'='*70}")
            print(f"Email: {data.get('email')}")
            print(f"Role: {data.get('role')}")
            print(f"Files received: {list(files.keys())}")
            print(f"{'='*70}\n")
        
        # Extract basic fields
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        password_confirm = data.get('password_confirm', '').strip()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        role = data.get('role', 'user').strip()
        phone_number = data.get('phone_number', '').strip()
        
        # Validate required fields
        if not all([email, password, password_confirm, first_name, last_name]):
            return Response(
                {'detail': 'Email, password, first name, and last name are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate passwords match
        if password != password_confirm:
            return Response(
                {'detail': 'Passwords do not match.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate role
        if role not in ['user', 'lister']:
            return Response(
                {'detail': 'Invalid role. Must be "user" or "lister".'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user already exists and is verified
        existing_user = User.objects.filter(email=email).first()
        if existing_user and existing_user.is_email_verified:
            return Response(
                {'detail': 'Email already registered and verified. Please login.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # If lister, validate KYC fields
        aadhar_number = None
        aadhar_front = None
        aadhar_back = None
        
        if role == 'lister':
            aadhar_number = data.get('aadhar_number', '').strip()
            aadhar_front = files.get('aadhar_front')
            aadhar_back = files.get('aadhar_back')
            
            # Validate KYC fields for listers
            if not aadhar_number:
                return Response(
                    {'detail': 'Aadhar number is required for listers.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(aadhar_number) != 12 or not aadhar_number.isdigit():
                return Response(
                    {'detail': 'Aadhar number must be exactly 12 digits.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not aadhar_front or not aadhar_back:
                return Response(
                    {'detail': 'Both front and back images of Aadhar card are required for listers.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if aadhar already exists (excluding temp users and unverified users)
            existing_aadhar = User.objects.filter(
                aadhar_number=aadhar_number,
                is_email_verified=True
            ).exclude(
                email__startswith='temp_'
            ).first()
            
            if existing_aadhar:
                return Response(
                    {'detail': 'This Aadhar number is already registered.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file sizes (max 10MB each)
            for img, name in [(aadhar_front, 'front'), (aadhar_back, 'back')]:
                if img.size > 10 * 1024 * 1024:
                    return Response(
                        {'detail': f'Aadhar {name} image must be less than 10MB.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate file type
                ext = img.name.split('.')[-1].lower()
                if ext not in ['jpg', 'jpeg', 'png']:
                    return Response(
                        {'detail': f'Aadhar {name} image must be JPG, JPEG, or PNG.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        # CLEANUP: Delete old unverified registrations
        # Delete unverified user with this email
        if existing_user and not existing_user.is_email_verified:
            if settings.DEBUG:
                print(f"Deleting old unverified user: {existing_user.email}")
            existing_user.delete()
        
        # Delete any temp users with this email
        temp_email = f"temp_{email}"
        deleted_temp = User.objects.filter(email=temp_email).delete()
        if settings.DEBUG and deleted_temp[0] > 0:
            print(f"Deleted {deleted_temp[0]} temp users with email: {temp_email}")
        
        # If lister, delete any temp users with this aadhar
        if role == 'lister' and aadhar_number:
            deleted_aadhar = User.objects.filter(
                aadhar_number=aadhar_number,
                is_email_verified=False
            ).delete()
            if settings.DEBUG and deleted_aadhar[0] > 0:
                print(f"Deleted {deleted_aadhar[0]} unverified users with Aadhar: {aadhar_number}")
        
        # Delete old pending OTPs
        deleted_otps = OTP.objects.filter(email=email, otp_type='email_verification').delete()
        if settings.DEBUG and deleted_otps[0] > 0:
            print(f"Deleted {deleted_otps[0]} old OTPs for email: {email}")
        
        # Create OTP with pending data
        otp_code = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)
        
        # Prepare pending data
        pending_data = {
            'first_name': first_name,
            'last_name': last_name,
            'password': password,
            'role': role,
            'phone_number': phone_number,
        }
        
        # Add KYC data for listers
        if role == 'lister':
            pending_data['aadhar_number'] = aadhar_number
            pending_data['has_kyc_files'] = True
        
        # Create OTP record
        otp_record = OTP.objects.create(
            email=email,
            otp_code=otp_code,
            otp_type='email_verification',
            expires_at=expires_at,
            user=None,
            pending_data=pending_data
        )
        
        # For listers, create temporary user to store KYC files
        if role == 'lister':
            try:
                if settings.DEBUG:
                    print(f"\nCreating temp user for lister...")
                    print(f"Temp email: temp_{email}")
                    print(f"Aadhar number: {aadhar_number}")
                
                temp_user = User(
                    email=f"temp_{email}",
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                    is_email_verified=False,
                    is_active=False,
                    aadhar_number=aadhar_number,
                    aadhar_front_image=aadhar_front,
                    aadhar_back_image=aadhar_back,
                )
                temp_user.set_unusable_password()
                temp_user.save()
                
                if settings.DEBUG:
                    print(f"✅ Temp user created with ID: {temp_user.id}")
                    print(f"Aadhar front URL: {temp_user.aadhar_front_image.url if temp_user.aadhar_front_image else 'None'}")
                    print(f"Aadhar back URL: {temp_user.aadhar_back_image.url if temp_user.aadhar_back_image else 'None'}")
                
                # Store temp user ID in OTP pending data
                pending_data['temp_user_id'] = temp_user.id
                otp_record.pending_data = pending_data
                otp_record.save()
                
            except Exception as e:
                if settings.DEBUG:
                    print(f"❌ Error creating temp user: {e}")
                    import traceback
                    traceback.print_exc()
                return Response(
                    {'detail': f'Error storing KYC documents: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Send OTP
        send_otp_email(email, otp_code, 'email_verification')
        
        return Response({
            'detail': 'Registration successful! OTP sent to your email. Please verify within 10 minutes.',
            'email': email,
            'requires_verification': True,
            'role': role
        }, status=status.HTTP_200_OK)
    
    def _handle_verification(self, data):
        """Step 2: Verify OTP, create user from pending_data, delete OTP"""
        email = data.get('email', '').strip()
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
                {'detail': 'Invalid OTP. Please check and try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check expiry
        if not otp.is_valid():
            # Clean up temp user if exists
            if otp.pending_data and otp.pending_data.get('temp_user_id'):
                try:
                    temp_user = User.objects.get(id=otp.pending_data['temp_user_id'])
                    temp_user.delete()
                    if settings.DEBUG:
                        print(f"Cleaned up expired temp user: {temp_user.id}")
                except User.DoesNotExist:
                    pass
            
            otp.delete()
            return Response(
                {'detail': 'OTP has expired. Please register again.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check user doesn't exist (safety)
        if User.objects.filter(email=email, is_email_verified=True).exists():
            # Clean up temp user if exists
            if otp.pending_data and otp.pending_data.get('temp_user_id'):
                try:
                    temp_user = User.objects.get(id=otp.pending_data['temp_user_id'])
                    temp_user.delete()
                except User.DoesNotExist:
                    pass
            otp.delete()
            return Response(
                {'detail': 'Email already registered and verified. Please login.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user from pending_data
        pending = otp.pending_data
        
        try:
            # Use transaction to ensure atomicity
            with transaction.atomic():
                # Delete any unverified user with this email
                User.objects.filter(email=email, is_email_verified=False).delete()
                
                # Check if this is a lister with temp user
                if pending.get('role') == 'lister' and pending.get('temp_user_id'):
                    # Get temp user with KYC files
                    try:
                        temp_user = User.objects.get(id=pending['temp_user_id'])
                        
                        if settings.DEBUG:
                            print(f"\n{'='*70}")
                            print(f"Creating verified lister from temp user...")
                            print(f"Email: {email}")
                            print(f"Temp user ID: {temp_user.id}")
                            print(f"Aadhar: {temp_user.aadhar_number}")
                            print(f"{'='*70}\n")
                        
                        # This handles edge cases where duplicate might exist
                        deleted_duplicates = User.objects.filter(
                            aadhar_number=temp_user.aadhar_number
                        ).exclude(
                            id=temp_user.id
                        ).delete()
                        
                        if settings.DEBUG and deleted_duplicates[0] > 0:
                            print(f"Deleted {deleted_duplicates[0]} duplicate Aadhar entries")
                        
                        # Create actual user with KYC data from temp user
                        user = User.objects.create(
                            email=email,
                            first_name=pending['first_name'],
                            last_name=pending['last_name'],
                            role=pending['role'],
                            phone_number=pending.get('phone_number', ''),
                            is_email_verified=True,
                            is_active=True,
                            aadhar_number=temp_user.aadhar_number,
                            aadhar_front_image=temp_user.aadhar_front_image,
                            aadhar_back_image=temp_user.aadhar_back_image,
                            is_kyc_submitted=True,
                            kyc_submitted_at=timezone.now(),
                            kyc_status=User.KYC_PENDING,
                        )
                        
                        user.set_password(pending['password'])
                        user.save()
                        
                        if settings.DEBUG:
                            print(f"✅ Lister created successfully!")
                            print(f"User ID: {user.id}")
                            print(f"Aadhar front: {user.aadhar_front_image.url if user.aadhar_front_image else 'None'}")
                            print(f"Aadhar back: {user.aadhar_back_image.url if user.aadhar_back_image else 'None'}")
                            print(f"{'='*70}\n")
                        
                        # Delete temp user
                        temp_user.delete()
                        
                        # Delete OTP
                        otp.delete()
                        
                        return Response({
                            'detail': 'Email verified successfully! Your KYC is pending admin approval. You will be able to login once approved.',
                            'email': user.email,
                            'verified': True,
                            'role': user.role,
                            'kyc_status': user.kyc_status,
                            'requires_kyc_approval': True
                        }, status=status.HTTP_201_CREATED)
                        
                    except User.DoesNotExist:
                        return Response(
                            {'detail': 'Temporary registration data not found. Please register again.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                else:
                    # Regular user (no KYC)
                    user = User.objects.create(
                        email=email,
                        first_name=pending['first_name'],
                        last_name=pending['last_name'],
                        role=pending['role'],
                        phone_number=pending.get('phone_number', ''),
                        is_email_verified=True,
                        is_active=True,
                    )
                    
                    user.set_password(pending['password'])
                    user.save()
                    
                    otp.delete()
                    
                    if settings.DEBUG:
                        print(f"✅ Regular user created: {user.email}")
                    
                    return Response({
                        'detail': 'Email verified successfully! You can now login with your credentials.',
                        'email': user.email,
                        'verified': True,
                        'role': user.role
                    }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            # Clean up temp user if error occurs
            if pending.get('temp_user_id'):
                try:
                    temp_user = User.objects.get(id=pending['temp_user_id'])
                    temp_user.delete()
                    if settings.DEBUG:
                        print(f"Cleaned up temp user due to error: {temp_user.id}")
                except User.DoesNotExist:
                    pass
            
            if settings.DEBUG:
                print(f"❌ Error creating user: {e}")
                import traceback
                traceback.print_exc()
            
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
        
        try:
            old_otp = OTP.objects.filter(
                email=email,
                otp_type='email_verification',
                is_used=False
            ).latest('created_at')
            
            pending = old_otp.pending_data
            
            if not pending:
                return Response(
                    {'detail': 'No pending registration data found. Please register again.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Keep the same pending data (including temp_user_id)
            temp_user_id = pending.get('temp_user_id')
            
            # Delete old OTPs but keep temp user
            OTP.objects.filter(email=email, otp_type='email_verification').delete()
            
            new_code = generate_otp()
            expires_at = timezone.now() + timedelta(minutes=10)
            
            OTP.objects.create(
                email=email,
                otp_code=new_code,
                otp_type='email_verification',
                expires_at=expires_at,
                user=None,
                pending_data=pending
            )
            
            send_otp_email(email, new_code, 'email_verification')
            
            if settings.DEBUG:
                print(f"OTP resent to {email}. Temp user ID: {temp_user_id}")
            
            return Response(
                {'detail': 'New OTP sent to your email!'},
                status=status.HTTP_200_OK
            )
            
        except OTP.DoesNotExist:
            return Response(
                {'detail': 'No pending registration found for this email.'},
                status=status.HTTP_404_NOT_FOUND
            )