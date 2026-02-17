from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from cloudinary.models import CloudinaryField
import pyotp
import secrets
from datetime import timedelta


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.update({
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
            "role": "admin",
            "is_email_verified": True,
        })
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    # Roles
    ADMIN, LISTER, USER = "admin", "lister", "user"
    ROLE_CHOICES = [(ADMIN, "Admin"), (LISTER, "Lister"), (USER, "User")]

    # KYC Status
    KYC_NOT_SUBMITTED, KYC_PENDING, KYC_APPROVED, KYC_REJECTED = (
        "not_submitted", "pending", "approved", "rejected"
    )
    KYC_STATUS_CHOICES = [
        (KYC_NOT_SUBMITTED, "Not Submitted"),
        (KYC_PENDING, "Pending"),
        (KYC_APPROVED, "Approved"),
        (KYC_REJECTED, "Rejected"),
    ]

    # Basic fields
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone_regex = RegexValidator(r'^\+?1?\d{9,15}$', "Invalid phone format")
    phone_number = models.CharField(max_length=17, validators=[phone_regex], blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profile_pictures/", blank=True, null=True)

    # Role
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=USER)

    # KYC
    kyc_status = models.CharField(max_length=20, choices=KYC_STATUS_CHOICES, default=KYC_NOT_SUBMITTED)
    is_kyc_submitted = models.BooleanField(default=False)
    kyc_submitted_at = models.DateTimeField(blank=True, null=True)
    kyc_verified_at = models.DateTimeField(blank=True, null=True)
    aadhar_number = models.CharField(max_length=12, unique=True, blank=True, null=True)
    aadhar_front_image = CloudinaryField("image", folder="kyc/aadhar/front", blank=True, null=True)
    aadhar_back_image = CloudinaryField("image", folder="kyc/aadhar/back", blank=True, null=True)
    kyc_rejection_reason = models.TextField(blank=True, null=True)

    # Email verification
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

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_admin(self):
        return self.role == self.ADMIN

    @property
    def is_lister(self):
        return self.role == self.LISTER

    @property
    def can_login(self):
        if not self.is_active:
            return False
        if self.role == self.LISTER:
            return self.kyc_status == self.KYC_APPROVED
        return True


class OTP(models.Model):
    OTP_TYPE_CHOICES = [
        ("email_verification", "Email Verification"),
        ("password_reset", "Password Reset"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps", null=True, blank=True)
    email = models.EmailField(db_index=True)
    otp_code = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPE_CHOICES)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    pending_data = models.JSONField(null=True, blank=True)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at


class MFAMethod(models.Model):
    METHOD_CHOICES = [
        ("totp", "Authenticator App"),
        ("email", "Email"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_methods")
    method_type = models.CharField(max_length=10, choices=METHOD_CHOICES)
    secret_key = models.CharField(max_length=32, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    is_enabled = models.BooleanField(default=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_totp_secret(self):
        self.secret_key = pyotp.random_base32()
        self.save(update_fields=["secret_key"])
        return self.secret_key

    def get_totp_uri(self):
        if self.method_type == 'totp' and self.secret_key:
            totp = pyotp.TOTP(self.secret_key)
            return totp.provisioning_uri(
                name=self.user.email,
                issuer_name='Accommodation Rentals'
            )
        return None

    def verify_totp_code(self, code):
        if not self.secret_key:
            return False
        return pyotp.TOTP(self.secret_key).verify(code, valid_window=1)


class MFABackupCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_backup_codes")
    code = models.CharField(max_length=12, unique=True)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(blank=True, null=True)
    used_ip = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def generate_backup_codes(user, count=10):
        MFABackupCode.objects.filter(user=user).delete()
        codes = []
        for _ in range(count):
            code = ''.join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
            MFABackupCode.objects.create(user=user, code=code)
            codes.append(code)
        return codes

    def mark_as_used(self, ip_address=None):
        self.is_used = True
        self.used_at = timezone.now()
        self.used_ip = ip_address
        self.save(update_fields=['is_used', 'used_at', 'used_ip'])


class MFASession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_sessions")
    session_token = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (
            not self.is_verified and
            self.attempts < self.max_attempts and
            timezone.now() < self.expires_at
        )

    def increment_attempts(self):
        self.attempts += 1
        self.save(update_fields=['attempts'])

    @staticmethod
    def create_session(user, ip_address, user_agent=''):
        MFASession.objects.filter(user=user).delete()
        return MFASession.objects.create(
            user=user,
            session_token=secrets.token_urlsafe(32),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=timezone.now() + timedelta(minutes=10),
        )


class MFAVerificationCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mfa_verification_codes')
    code = models.CharField(max_length=6)
    method_type = models.CharField(max_length=10, choices=[("email", "Email")])
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

class MFALoginAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mfa_login_attempts', null=True, blank=True)
    email = models.EmailField(db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    success = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mfa_login_attempts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'ip_address', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    @staticmethod
    def check_rate_limit(email=None, ip_address=None, minutes=15, max_attempts=5):
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        query = MFALoginAttempt.objects.filter(created_at__gte=cutoff_time, success=False)
        
        if email:
            query = query.filter(email=email)
        if ip_address:
            query = query.filter(ip_address=ip_address)
        
        attempts_count = query.count()
        is_limited = attempts_count >= max_attempts
        
        time_until_reset = None
        if is_limited:
            oldest_attempt = query.order_by('created_at').first()
            if oldest_attempt:
                reset_time = oldest_attempt.created_at + timedelta(minutes=minutes)
                time_until_reset = (reset_time - timezone.now()).total_seconds()
        
        return is_limited, attempts_count, time_until_reset