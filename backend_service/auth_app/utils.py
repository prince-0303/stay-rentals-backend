import secrets
import string
import logging
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_otp(length=6):
    """Generate random OTP code"""
    return ''.join(secrets.choice(string.digits) for _ in range(length))


def generate_mfa_code(length=6):
    """Generate random MFA code"""
    return ''.join(secrets.choice('0123456789') for _ in range(length))


def send_verification_email(email, otp_code):
    """Send email verification OTP"""
    subject = 'Verify Your Email Address'
    message = f"""
Hello,

Thank you for registering! Please use the following OTP to verify your email address:

OTP Code: {otp_code}

This code will expire in 10 minutes.

If you did not request this, please ignore this email.

Best regards,
Accommodation Rentals
    """
    
    if settings.DEBUG:
        print("\n" + "="*70)
        print("📧 EMAIL VERIFICATION OTP")
        print("="*70)
        print(f"📧 Email: {email}")
        print(f"🔢 OTP Code: {otp_code}")
        print(f"⏰ Valid for: 10 minutes")
        print("="*70 + "\n")
    
    try:
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        
        if settings.DEBUG:
            print(f"✅ Email sent successfully! Result: {result}\n")
        
        logger.info(f"OTP sent to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        if settings.DEBUG:
            print(f"❌ Email sending failed: {str(e)}")
            print(f"✅ But OTP is printed above: {otp_code}")
            print("="*70 + "\n")
        return False


def send_otp_email(email, otp_code, otp_type):
    """Send OTP via email for different purposes"""
    subject_map = {
        'password_reset': 'Reset Your Password',
        'email_verification': 'Verify Your Email Address',
    }
    
    message_map = {
        'password_reset': f"""
Hello,

You have requested to reset your password. Please use the following OTP:

OTP Code: {otp_code}

This code will expire in 10 minutes.

If you did not request this, please ignore this email.

Best regards,
Accommodation Rentals
        """,
        'email_verification': f"""
Hello,

Thank you for registering! Please use the following OTP to verify your email address:

OTP Code: {otp_code}

This code will expire in 10 minutes.

If you did not request this, please ignore this email.

Best regards,
Accommodation Rentals
        """,
    }
    
    subject = subject_map.get(otp_type, 'Your OTP Code')
    message = message_map.get(otp_type, f'Your OTP code is: {otp_code}')
    
    if settings.DEBUG:
        type_emoji = "📧" if otp_type == 'email_verification' else "🔑"
        type_name = otp_type.replace('_', ' ').title()
        
        print("\n" + "="*70)
        print(f"{type_emoji} {type_name} OTP")
        print("="*70)
        print(f"📧 Email: {email}")
        print(f"🔢 OTP Code: {otp_code}")
        print(f"📝 Type: {otp_type}")
        print(f"⏰ Valid for: 10 minutes")
        print("="*70 + "\n")
    
    try:
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        
        if settings.DEBUG:
            print(f"✅ Email sent successfully! Result: {result}\n")
        
        logger.info(f"OTP sent to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        if settings.DEBUG:
            print(f"❌ Email sending failed: {str(e)}")
            print(f"✅ But OTP is printed above: {otp_code}")
            print("="*70 + "\n")
        return False


def send_mfa_email(user, code):
    """Send MFA code via email"""
    subject = 'Your MFA Verification Code'
    message = f"""
Hello {user.first_name},

Your MFA verification code is:

{code}

This code will expire in 10 minutes.

If you did not request this code, please secure your account immediately.

Best regards,
Accommodation Rentals Security Team
    """
    
    # if settings.DEBUG:
    #     print("\n" + "="*70)
    #     print("🔐 MFA EMAIL VERIFICATION CODE")
    #     print("="*70)
    #     print(f"📧 Email: {user.email}")
    #     print(f"🔢 Code: {code}")
    #     print(f"⏰ Valid for: 10 minutes")
    #     print("="*70 + "\n")
    
    try:
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        if settings.DEBUG:
            print(f"✅ MFA email sent successfully! Result: {result}\n")
        
        logger.info(f"MFA code sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending MFA email to {user.email}: {e}")
        # if settings.DEBUG:
        #     print(f"❌ Email sending failed: {str(e)}")
        #     print(f"✅ But code is printed above: {code}")
        #     print("="*70 + "\n")
        return False


def create_mfa_verification_code(user, method_type):
    """Create and send MFA verification code (Email only)"""
    from .models import MFAVerificationCode
    
    # Delete old codes
    MFAVerificationCode.objects.filter(user=user, method_type=method_type).delete()
    
    # Generate code
    code = generate_mfa_code()
    expires_at = timezone.now() + timedelta(minutes=10)
    
    # Create verification code
    verification = MFAVerificationCode.objects.create(
        user=user,
        code=code,
        method_type=method_type,
        expires_at=expires_at
    )
    
    # Send code via email
    if method_type == 'email':
        send_mfa_email(user, code)
    
    return verification


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Get user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')[:500]


def check_mfa_rate_limit(email, ip_address):
    """Check MFA rate limiting"""
    from .models import MFALoginAttempt
    
    is_limited_email, attempts_email, time_email = MFALoginAttempt.check_rate_limit(
        email=email, minutes=15, max_attempts=5
    )
    
    is_limited_ip, attempts_ip, time_ip = MFALoginAttempt.check_rate_limit(
        ip_address=ip_address, minutes=15, max_attempts=10
    )
    
    if is_limited_email:
        minutes_left = int(time_email / 60) + 1
        return True, f"Too many failed attempts. Please try again in {minutes_left} minutes."
    
    if is_limited_ip:
        minutes_left = int(time_ip / 60) + 1
        return True, f"Too many failed attempts from this IP. Please try again in {minutes_left} minutes."
    
    return False, None


def log_mfa_attempt(user, ip_address, success, failure_reason=''):
    """Log MFA login attempt"""
    from .models import MFALoginAttempt
    
    MFALoginAttempt.objects.create(
        user=user,
        email=user.email,
        ip_address=ip_address,
        success=success,
        failure_reason=failure_reason
    )


def user_requires_mfa(user):
    """Check if user MUST use MFA (admins only)"""
    return user.role == 'admin'


def user_has_mfa_enabled(user):
    """Check if user has MFA enabled"""
    from .models import MFAMethod
    
    return MFAMethod.objects.filter(
        user=user,
        is_enabled=True,
        verified_at__isnull=False
    ).exists()


def get_user_primary_mfa_method(user):
    """Get user's primary MFA method"""
    from .models import MFAMethod
    
    # Try to get primary method
    primary = MFAMethod.objects.filter(
        user=user,
        is_enabled=True,
        is_primary=True,
        verified_at__isnull=False
    ).first()
    
    if primary:
        return primary
    
    # Fallback to any enabled method
    return MFAMethod.objects.filter(
        user=user,
        is_enabled=True,
        verified_at__isnull=False
    ).first()


def cleanup_expired_mfa_sessions():
    """Cleanup expired MFA sessions and codes"""
    from .models import MFASession, MFAVerificationCode, OTP
    
    cutoff = timezone.now()
    
    # Delete expired items
    count_sessions = MFASession.objects.filter(expires_at__lt=cutoff).delete()[0]
    count_codes = MFAVerificationCode.objects.filter(expires_at__lt=cutoff).delete()[0]
    count_otps = OTP.objects.filter(expires_at__lt=cutoff).delete()[0]
    
    logger.info(
        f"Cleaned up {count_sessions} expired MFA sessions, "
        f"{count_codes} expired MFA codes, and {count_otps} expired OTPs"
    )
    
    return {
        'sessions': count_sessions,
        'codes': count_codes,
        'otps': count_otps,
    }