import secrets
import string
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_otp(length=6):
    """Generate a random OTP code."""
    digits = string.digits
    otp = ''.join(secrets.choice(digits) for _ in range(length))
    return otp


def send_verification_email(email, otp_code):
    """
    Send email verification OTP.
    """
    subject = 'Verify Your Email Address'
    message = f"""
Hello,

Thank you for registering! Please use the following OTP to verify your email address:

OTP Code: {otp_code}

This code will expire in 10 minutes.

If you did not request this, please ignore this email.

Best regards,
Your Accommodation Rentals
    """
    
    # PRINT TO CONSOLE IN DEVELOPMENT
    if settings.DEBUG:
        print("\n" + "="*70)
        print("🔐 EMAIL VERIFICATION OTP")
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
            print(f"✅ Email sent successfully! Mail result: {result}\n")
        
        logger.info(f"OTP sent to {email}")
        logger.debug(f"OTP for {email}: {otp_code}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        if settings.DEBUG:
            print(f"❌ Email sending failed: {str(e)}")
            print(f"✅ But OTP is printed above: {otp_code}")
            print("="*70 + "\n")
            
            # Print full traceback
            import traceback
            traceback.print_exc()
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
    
    # PRINT TO CONSOLE IN DEVELOPMENT
    if settings.DEBUG:
        type_emoji = "🔐" if otp_type == 'email_verification' else "🔑"
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
            print(f"✅ Email sent successfully! Mail result: {result}\n")
        
        logger.info(f"OTP sent to {email}")
        logger.debug(f"OTP for {email}: {otp_code}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        if settings.DEBUG:
            print(f"❌ Email sending failed: {str(e)}")
            print(f"✅ But OTP is printed above: {otp_code}")
            print("="*70 + "\n")
            
            # Print full traceback
            import traceback
            traceback.print_exc()
        return False


def get_client_ip(request):
    """
    Get the client's IP address from the request.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip