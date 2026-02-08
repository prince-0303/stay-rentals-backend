from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, OTP


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Minimal but safe User admin."""
    
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_email_verified', 'is_active']
    list_filter = ['role', 'is_email_verified', 'is_active']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number', 'profile_picture')}),
        ('Permissions', {'fields': ('role', 'is_email_verified', 'kyc_status', 'is_active', 'is_staff')}),
    )
    
    add_fieldsets = (
        (None, {
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'role'),
        }),
    )


# Simple registration for OTP
admin.site.register(OTP)