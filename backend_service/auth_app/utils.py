import secrets
import string
from django.core.mail import send_mail
from django.conf import settings


def generate_otp(length=6):
    """Generate a random OTP code."""
    digits = string.digits
    otp = ''.join(secrets.choice(digits) for _ in range(length))
    return otp


def send_verification_email(email, otp_code):
    """
    Send email verification OTP.
    
    Args:
        email (str): Recipient email address
        otp_code (str): 6-digit OTP code
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = 'Verify Your Email Address'
    message = f"""
Hello,

Thank you for registering! Please use the following OTP to verify your email address:

OTP Code: {otp_code}

This code will expire in 10 minutes.

If you did not request this, please ignore this email.

Best regards,
Your App Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        print(f"✅ OTP sent to {email}: {otp_code}")  # For testing
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        print(f"🔑 OTP for {email}: {otp_code}")  # Print to console for testing
        return False


def send_otp_email(email, otp_code, otp_type):
    """
    Send OTP via email for different purposes.
    """
    
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

If you did not request this, please ignore this email and your password will remain unchanged.

Best regards,
Your App Team
        """,
        'email_verification': f"""
Hello,

Thank you for registering! Please use the following OTP to verify your email address:

OTP Code: {otp_code}

This code will expire in 10 minutes.

If you did not request this, please ignore this email.

Best regards,
Your App Team
        """,
    }
    
    subject = subject_map.get(otp_type, 'Your OTP Code')
    message = message_map.get(otp_type, f'Your OTP code is: {otp_code}')
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        print(f"✅ OTP sent to {email}: {otp_code}")  # For testing
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        print(f"🔑 OTP for {email}: {otp_code}")  # Print to console for testing
        return False


def get_client_ip(request):
    """
    Get the client's IP address from the request.
    
    Args:
        request: Django request object
    
    Returns:
        str: Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip