from django.db import models
from django.conf import settings
from cloudinary.models import CloudinaryField


class UserProfile(models.Model):
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    profile_picture = CloudinaryField('image', folder='accommodation/profiles/users/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], blank=True, null=True)
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)

    preferred_location = models.CharField(max_length=255, blank=True)
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    is_blocked = models.BooleanField(default=False)
    blocked_at = models.DateTimeField(blank=True, null=True)
    blocked_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'

    def __str__(self):
        return f"{self.user.get_full_name()} - Profile"


class ListerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name= 'lister_profile')
    profile_picture = CloudinaryField('image', folder='accommodation/profiles/listers/', blank=True, null=True)
    business_name = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)

    # Set to True by admin after KYC approved
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(blank=True, null=True)

    # Admin control
    is_blocked = models.BooleanField(default=False)
    blocked_at = models.DateTimeField(blank=True, null=True)
    blocked_reason = models.TextField(blank=True, null=True)

    total_listings = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lister_profiles'

    def __str__(self):
        return f"{self.user.get_full_name()} - Lister Profile"