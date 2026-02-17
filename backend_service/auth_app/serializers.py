from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, OTP, MFAMethod, MFABackupCode


class RegisterOrVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=False)
    first_name = serializers.CharField(required=False, max_length=150)
    last_name = serializers.CharField(required=False, max_length=150)
    role = serializers.ChoiceField(choices=[User.USER, User.LISTER], default=User.USER, required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    otp = serializers.CharField(required=False, max_length=6, allow_blank=True)
    
    def validate(self, attrs):
        otp = attrs.get('otp', '').strip()
        
        # Verification mode
        if otp:
            return attrs
        
        # Registration mode - all fields required
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
        
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords don't match."})
        
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


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp_code = serializers.CharField(required=True, max_length=6)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Passwords don't match."})
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
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


def get_tokens_for_user(user):
    """Generate JWT tokens"""
    refresh = RefreshToken.for_user(user)
    refresh['email'] = user.email
    refresh['role'] = user.role
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# MFA Serializers

class MFAMethodSerializer(serializers.ModelSerializer):
    method_name = serializers.CharField(source='get_method_type_display', read_only=True)
    qr_code_uri = serializers.SerializerMethodField()
    
    class Meta:
        model = MFAMethod
        fields = [
            'id', 'method_type', 'method_name', 'is_primary',
            'is_enabled', 'verified_at', 'qr_code_uri', 'created_at',
        ]
        read_only_fields = ['id', 'verified_at', 'created_at']
    
    def get_qr_code_uri(self, obj):
        if obj.method_type == 'totp' and not obj.verified_at:
            return obj.get_totp_uri()
        return None


class MFASetupInitSerializer(serializers.Serializer):
    method_type = serializers.ChoiceField(choices=['totp', 'email'], required=True)


class MFAVerifySetupSerializer(serializers.Serializer):
    method_type = serializers.ChoiceField(choices=['totp', 'email'], required=True)
    code = serializers.CharField(required=True, min_length=6, max_length=6)
    
    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('Code must be 6 digits.')
        return value


class MFALoginVerifySerializer(serializers.Serializer):
    mfa_session_token = serializers.CharField(required=True)
    code = serializers.CharField(required=True, min_length=6, max_length=8)
    
    def validate_code(self, value):
        return value.strip().upper().replace(' ', '').replace('-', '')


class MFADisableSerializer(serializers.Serializer):
    password = serializers.CharField(required=True, write_only=True)
    method_type = serializers.ChoiceField(choices=['totp', 'email', 'all'], required=True)


class MFAStatusSerializer(serializers.Serializer):
    mfa_enabled = serializers.BooleanField()
    mfa_enforced = serializers.BooleanField()
    methods = MFAMethodSerializer(many=True)
    backup_codes_count = serializers.IntegerField()
    requires_setup = serializers.BooleanField()
    should_show_mfa_recommendation = serializers.BooleanField()


class MFABackupCodesSerializer(serializers.Serializer):
    codes = serializers.ListField(child=serializers.CharField())
    message = serializers.CharField(
        default="Save these backup codes in a secure location. Each code can only be used once."
    )


class MFASendCodeSerializer(serializers.Serializer):
    method_type = serializers.ChoiceField(choices=['email'], required=True)