from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, OTP


class RegisterOrVerifySerializer(serializers.Serializer):
    """
    Handles both registration and verification
    """
    email = serializers.EmailField(required=True)
    
    # Make these NOT required - we'll validate conditionally
    password = serializers.CharField(
        write_only=True,
        required=False,
        validators=[validate_password],
    )
    password_confirm = serializers.CharField(write_only=True, required=False)
    first_name = serializers.CharField(required=False, max_length=150)
    last_name = serializers.CharField(required=False, max_length=150)
    role = serializers.ChoiceField(
        choices=[User.USER, User.LISTER],
        default=User.USER,
        required=False
    )
    phone_number = serializers.CharField(required=False, allow_blank=True)
    
    otp = serializers.CharField(required=False, max_length=6, allow_blank=True)
    
    def validate(self, attrs):
        otp = attrs.get('otp', '').strip()
        
        # VERIFICATION MODE: Only email + OTP needed
        if otp:
            return attrs
        
        # REGISTRATION MODE: All fields required
        required_fields = {
            'password': 'Password is required.',
            'password_confirm': 'Password confirmation is required.',
            'first_name': 'First name is required.',
            'last_name': 'Last name is required.',
            'role': 'Role is required.',
        }
        
        errors = {}
        for field, error_msg in required_fields.items():
            if not attrs.get(field):
                errors[field] = error_msg
        
        if errors:
            raise serializers.ValidationError(errors)
        
        # Validate passwords match
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords don't match."})
        
        # Validate role
        if attrs.get('role') not in {User.USER, User.LISTER}:
            raise serializers.ValidationError({"role": "Invalid role."})
        
        return attrs


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class GoogleLoginSerializer(serializers.Serializer):
    code = serializers.CharField(required=True)


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        user = authenticate(
            request=self.context.get('request'),
            username=email,
            password=password
        )
        
        if not user:
            raise serializers.ValidationError('Invalid email or password.')
        
        if not user.is_active:
            raise serializers.ValidationError('Account is disabled.')
        
        attrs['user'] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No account found.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp_code = serializers.CharField(required=True, max_length=6)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
    )
    new_password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Passwords don't match."})
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
    )
    new_password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Passwords don't match."})
        return attrs
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password incorrect.")
        return value


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = '__all__'
        read_only_fields = [
            'id', 'email', 'role', 'is_email_verified',
            'is_active', 'date_joined', 'last_login', 'kyc_status',
            'is_kyc_submitted', 'kyc_submitted_at', 'kyc_verified_at',
        ]

class UserLoginResponseSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'is_active', 'is_email_verified']
        

class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'profile_picture']


class KYCSubmissionSerializer(serializers.Serializer):
    """Serializer for KYC Aadhaar submission"""
    
    aadhar_number = serializers.CharField(
        max_length=12,
        min_length=12,
        required=True,
        validators=[
            RegexValidator(
                regex=r'^\d{12}$',
                message='Aadhaar number must be exactly 12 digits'
            )
        ],
        help_text="12-digit Aadhaar number"
    )
    
    aadhar_image = serializers.ImageField(
        required=True,
        help_text="Clear image of Aadhaar card"
    )
    
    def validate_aadhar_number(self, value):
        """Check if Aadhaar already exists"""
        user = self.context.get('user')
        if User.objects.filter(aadhar_number=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This Aadhaar number is already registered.")
        return value
    
    def validate_aadhar_image(self, value):
        """Validate Aadhaar image"""
        # Check file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image size should not exceed 10MB.")
        
        # Check file type
        valid_extensions = ['jpg', 'jpeg', 'png']
        ext = value.name.split('.')[-1].lower()
        if ext not in valid_extensions:
            raise serializers.ValidationError(
                f"Only JPG, JPEG, PNG files are allowed."
            )
        
        return value


class KYCStatusSerializer(serializers.ModelSerializer):
    """Serializer for KYC status display"""
    
    aadhar_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'is_kyc_submitted',
            'kyc_status',
            'kyc_submitted_at',
            'kyc_verified_at',
            'aadhar_number',
            'aadhar_image_url',
            'kyc_rejection_reason',
        ]
        read_only_fields = fields
    
    def get_aadhar_image_url(self, obj):
        """Get Cloudinary URL for Aadhaar image"""
        if obj.aadhar_image:
            return obj.aadhar_image.url
        return None
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Mask Aadhaar number (show only last 4 digits to user)
        if data.get('aadhar_number'):
            data['aadhar_number'] = 'XXXX-XXXX-' + data['aadhar_number'][-4:]
        return data


def get_tokens_for_user(user):
    """Generate JWT tokens"""
    refresh = RefreshToken.for_user(user)
    refresh['email'] = user.email
    refresh['role'] = user.role
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }