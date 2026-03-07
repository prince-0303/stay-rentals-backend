from rest_framework import serializers
from .models import UserProfile, ListerProfile


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    phone_number = serializers.CharField(source='user.phone_number', required=False, allow_blank=True)
    kyc_status = serializers.CharField(source='user.kyc_status', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'email', 'full_name', 'first_name', 'last_name',
            'phone_number', 'role', 'profile_picture',
            'date_of_birth', 'gender', 'address_line',
            'city', 'state', 'pincode',
            'kyc_status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'email', 'full_name', 'role',
            'kyc_status', 'created_at', 'updated_at'
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user

        if 'first_name' in user_data:
            user.first_name = user_data['first_name']
        if 'last_name' in user_data:
            user.last_name = user_data['last_name']
        if 'phone_number' in user_data:
            user.phone_number = user_data['phone_number']
        user.save(update_fields=['first_name', 'last_name', 'phone_number'])

        return super().update(instance, validated_data)


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