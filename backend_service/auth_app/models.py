from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from cloudinary.models import CloudinaryField


class UserManager(BaseUserManager):
    """Custom user manager."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError('Email is required')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser (Admin)."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.ADMIN)
        extra_fields.setdefault('is_email_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model with role-based access and email verification."""
    
    # User Roles
    ADMIN = 'admin'
    LISTER = 'lister'
    USER = 'user'
    
    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (LISTER, 'Lister'),
        (USER, 'User'),
    ]
    
    # Basic Information
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number format: '+999999999'. Up to 15 digits."
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True
    )
    
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True
    )
    
    # Role and Status
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=USER
    )

    # KYC Status
    KYC_NOT_SUBMITTED = 'not_submitted'
    KYC_PENDING = 'pending'
    KYC_APPROVED = 'approved'
    KYC_REJECTED = 'rejected'

    KYC_STATUS_CHOICES = [
        (KYC_NOT_SUBMITTED, 'Not Submitted'),
        (KYC_PENDING, 'Pending'),
        (KYC_APPROVED, 'Approved'),
        (KYC_REJECTED, 'Rejected'),
    ]

    kyc_status = models.CharField(
        max_length=20,
        choices=KYC_STATUS_CHOICES,
        default=KYC_NOT_SUBMITTED
    )

    is_kyc_submitted = models.BooleanField(default=False)
    kyc_submitted_at = models.DateTimeField(blank=True, null=True)
    kyc_verified_at = models.DateTimeField(blank=True, null=True)
    
    # AADHAAR - UPDATED with front and back
    aadhar_number = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        unique=True,
        help_text="12-digit Aadhaar number"
    )
    
    aadhar_front_image = CloudinaryField(
        'image',
        folder='kyc/aadhar/front',
        blank=True,
        null=True,
        help_text="Aadhaar card front image"
    )
    
    aadhar_back_image = CloudinaryField(
        'image',
        folder='kyc/aadhar/back',
        blank=True,
        null=True,
        help_text="Aadhaar card back image"
    )
    
    kyc_rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for KYC rejection"
    )
    
    # Email Verification
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(blank=True, null=True)
    
    # Permissions
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Manager
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_email_verified']),
            models.Index(fields=['kyc_status']),
        ]
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        """Return the user's short name."""
        return self.first_name
    
    @property
    def is_admin(self):
        """Check if user is an admin."""
        return self.role == self.ADMIN
    
    @property
    def is_lister(self):
        """Check if user is a lister."""
        return self.role == self.LISTER
    
    @property
    def is_regular_user(self):
        """Check if user is a regular user."""
        return self.role == self.USER
    
    @property
    def can_login(self):
        if not self.is_active:
            return False

        if self.role == self.LISTER:
            return self.kyc_status == self.KYC_APPROVED

        return True


class OTP(models.Model):
    """
    OTP model for email verification and password reset.
    """
    
    OTP_TYPE_CHOICES = [
        ('email_verification', 'Email Verification'),
        ('password_reset', 'Password Reset'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='otps',
        null=True,
        blank=True
    )
    
    email = models.EmailField(db_index=True)
    otp_code = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPE_CHOICES)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    pending_data = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'otps'
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.email} - {self.otp_type} - {self.otp_code}"
    
    def is_valid(self):
        """Check if OTP is still valid."""
        return not self.is_used and timezone.now() < self.expires_at