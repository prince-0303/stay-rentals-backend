from rest_framework import serializers
from auth_app.models import User
from profile_app.models import UserProfile, ListerProfile


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    is_blocked = serializers.SerializerMethodField()
    total_listings = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name',
            'phone_number', 'role', 'is_active', 'is_blocked',
            'kyc_status', 'is_kyc_submitted', 'date_joined',
            'total_listings'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'updated_at']

    def get_is_blocked(self, obj):
        try:
            if obj.role == 'user':
                return obj.profile.is_blocked
            elif obj.role == 'lister':
                return obj.lister_profile.is_blocked
        except Exception:
            pass
        return False

    def get_total_listings(self, obj):
        try:
            if obj.role == 'lister':
                return obj.properties.count()
        except Exception:
            pass
        return 0


class AdminUserDetailSerializer(AdminUserSerializer):
    city = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    class Meta(AdminUserSerializer.Meta):
        fields = [
            'id', 'email', 'full_name', 'phone_number',
            'role', 'is_active', 'is_blocked',
            'is_email_verified', 'kyc_status',
            'date_joined', 'last_login', 'updated_at',
            'city', 'profile_picture',
        ]

    def get_city(self, obj):
        try:
            if obj.role == 'user':
                return obj.profile.city
            elif obj.role == 'lister':
                return obj.lister_profile.city
        except Exception:
            pass
        return None

    def get_profile_picture(self, obj):
        try:
            if obj.role == 'user':
                pic = obj.profile.profile_picture
            elif obj.role == 'lister':
                pic = obj.lister_profile.profile_picture
            else:
                return None
            return pic.url if pic else None
        except Exception:
            return None


class AdminListerDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    is_blocked = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    aadhar_front_url = serializers.SerializerMethodField()
    aadhar_back_url = serializers.SerializerMethodField()
    total_listings = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'phone_number',
            'role', 'is_active', 'is_blocked',
            'is_email_verified',
            'kyc_status', 'is_kyc_submitted',
            'kyc_submitted_at', 'kyc_verified_at',
            'kyc_rejection_reason',
            'aadhar_number', 'aadhar_front_url', 'aadhar_back_url',
            'city', 'profile_picture', 'total_listings',
            'date_joined', 'last_login', 'updated_at',
        ]

    def get_is_blocked(self, obj):
        try:
            return obj.lister_profile.is_blocked
        except Exception:
            return False

    def get_profile_picture(self, obj):
        try:
            pic = obj.lister_profile.profile_picture
            return pic.url if pic else None
        except Exception:
            return None

    def get_city(self, obj):
        try:
            return obj.lister_profile.city
        except Exception:
            return None

    def get_aadhar_front_url(self, obj):
        return obj.aadhar_front_image.url if obj.aadhar_front_image else None

    def get_aadhar_back_url(self, obj):
        return obj.aadhar_back_image.url if obj.aadhar_back_image else None

    def get_total_listings(self, obj):
        try:
            return obj.properties.count()
        except Exception:
            return 0


class AdminCreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name',
            'phone_number', 'role', 'password'
        ]

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data, is_email_verified=True, is_active=True)
        user.set_password(password)
        user.save()
        return user


class AdminKYCSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    aadhar_front_url = serializers.SerializerMethodField()
    aadhar_back_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'phone_number',
            'aadhar_number', 'aadhar_front_url', 'aadhar_back_url',
            'kyc_status', 'is_kyc_submitted',
            'kyc_submitted_at', 'kyc_verified_at',
            'kyc_rejection_reason', 'date_joined',
        ]

    def get_aadhar_front_url(self, obj):
        return obj.aadhar_front_image.url if obj.aadhar_front_image else None

    def get_aadhar_back_url(self, obj):
        return obj.aadhar_back_image.url if obj.aadhar_back_image else None


class BlockActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['block', 'unblock'])
    reason = serializers.CharField(required=False, allow_blank=True)


class AdminKYCActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['action'] == 'reject':
            reason = attrs.get('reason', '').strip()
            if not reason:
                raise serializers.ValidationError({
                    'reason': 'A rejection reason is required when rejecting KYC.'
                })
        return attrs