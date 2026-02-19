from rest_framework import serializers
from .models import UserProfile, ListerProfile


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    kyc_status = serializers.CharField(source='user.kyc_status', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'email', 'full_name', 'phone_number', 'role',
            'profile_picture', 'date_of_birth', 'gender',
            'address_line', 'city', 'state', 'pincode',
            'preferred_location', 'budget_min', 'budget_max',
            'kyc_status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'email', 'full_name', 'phone_number',
            'role', 'kyc_status', 'created_at', 'updated_at'
        ]


class ListerProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    kyc_status = serializers.CharField(source='user.kyc_status', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)

    class Meta:
        model = ListerProfile
        fields = [
            'email', 'full_name', 'phone_number', 'role',
            'profile_picture', 'business_name', 'bio',
            'city', 'state', 'is_verified', 'kyc_status',
            'total_listings', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'email', 'full_name', 'phone_number', 'role',
            'is_verified', 'kyc_status', 'total_listings',
            'created_at', 'updated_at'
        ]