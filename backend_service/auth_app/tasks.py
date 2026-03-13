import logging
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

logger = logging.getLogger(__name__)


def _send_html_email(subject, to_email, html_content, plain_content):
    """Helper to send HTML email with plain text fallback."""
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email_task(self, email, otp_code):
    """Send OTP verification email asynchronously."""
    subject = 'Verify Your Email – Accommodation Rentals'

    plain = f"Your OTP code is: {otp_code}\nThis code expires in 10 minutes."

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr>
          <td align="center">
            <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
              
              <!-- Header -->
              <tr>
                <td style="background:linear-gradient(135deg,#2563eb,#1d4ed8);padding:36px 40px;text-align:center;">
                  <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;letter-spacing:-0.5px;">Accommodation Rentals</h1>
                  <p style="color:#bfdbfe;margin:8px 0 0;font-size:14px;">Email Verification</p>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:40px 40px 32px;">
                  <h2 style="color:#1e293b;font-size:20px;margin:0 0 12px;">Verify your email address</h2>
                  <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 28px;">
                    Thank you for registering! Use the OTP below to verify your email address. This code expires in <strong>10 minutes</strong>.
                  </p>

                  <!-- OTP Box -->
                  <div style="background:#f0f7ff;border:2px dashed #2563eb;border-radius:10px;padding:24px;text-align:center;margin-bottom:28px;">
                    <p style="color:#64748b;font-size:13px;margin:0 0 8px;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Your OTP Code</p>
                    <span style="font-size:42px;font-weight:800;color:#2563eb;letter-spacing:10px;">{otp_code}</span>
                  </div>

                  <p style="color:#94a3b8;font-size:13px;margin:0;">
                    If you didn't create an account, you can safely ignore this email.
                  </p>
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                  <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Accommodation Rentals. All rights reserved.</p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email_task(self, email, otp_code):
    """Send password reset OTP email asynchronously."""
    subject = 'Reset Your Password – Accommodation Rentals'

    plain = f"Your password reset OTP is: {otp_code}\nExpires in 10 minutes."

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr>
          <td align="center">
            <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
              <tr>
                <td style="background:linear-gradient(135deg,#dc2626,#b91c1c);padding:36px 40px;text-align:center;">
                  <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;">Accommodation Rentals</h1>
                  <p style="color:#fecaca;margin:8px 0 0;font-size:14px;">Password Reset</p>
                </td>
              </tr>
              <tr>
                <td style="padding:40px 40px 32px;">
                  <h2 style="color:#1e293b;font-size:20px;margin:0 0 12px;">Reset your password</h2>
                  <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 28px;">
                    We received a request to reset your password. Use the OTP below. Expires in <strong>10 minutes</strong>.
                  </p>
                  <div style="background:#fff5f5;border:2px dashed #dc2626;border-radius:10px;padding:24px;text-align:center;margin-bottom:28px;">
                    <p style="color:#64748b;font-size:13px;margin:0 0 8px;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Reset OTP</p>
                    <span style="font-size:42px;font-weight:800;color:#dc2626;letter-spacing:10px;">{otp_code}</span>
                  </div>
                  <p style="color:#94a3b8;font-size:13px;margin:0;">If you didn't request this, please ignore this email. Your password won't change.</p>
                </td>
              </tr>
              <tr>
                <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                  <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Accommodation Rentals. All rights reserved.</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_mfa_email_task(self, email, first_name, code):
    """Send MFA verification code email asynchronously."""
    subject = 'Your MFA Verification Code – Accommodation Rentals'
    plain = f"Your MFA code is: {code}\nExpires in 10 minutes."

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <tr>
              <td style="background:linear-gradient(135deg,#7c3aed,#6d28d9);padding:36px 40px;text-align:center;">
                <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;">Accommodation Rentals</h1>
                <p style="color:#ddd6fe;margin:8px 0 0;font-size:14px;">Two-Factor Authentication</p>
              </td>
            </tr>
            <tr>
              <td style="padding:40px 40px 32px;">
                <h2 style="color:#1e293b;font-size:20px;margin:0 0 12px;">Hi {first_name},</h2>
                <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 28px;">
                  Your MFA verification code is below. It expires in <strong>10 minutes</strong>.
                </p>
                <div style="background:#f5f3ff;border:2px dashed #7c3aed;border-radius:10px;padding:24px;text-align:center;margin-bottom:28px;">
                  <p style="color:#64748b;font-size:13px;margin:0 0 8px;text-transform:uppercase;letter-spacing:1px;font-weight:600;">MFA Code</p>
                  <span style="font-size:42px;font-weight:800;color:#7c3aed;letter-spacing:10px;">{code}</span>
                </div>
                <p style="color:#94a3b8;font-size:13px;margin:0;">If you didn't attempt to log in, please secure your account immediately.</p>
              </td>
            </tr>
            <tr>
              <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Accommodation Rentals. All rights reserved.</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_kyc_approved_email_task(self, email, first_name):
    """Send KYC approval email asynchronously."""
    subject = 'KYC Approved – You can now list properties!'

    plain = f"Hi {first_name}, your KYC has been approved. You can now create property listings."

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <tr>
              <td style="background:linear-gradient(135deg,#16a34a,#15803d);padding:36px 40px;text-align:center;">
                <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;">Accommodation Rentals</h1>
                <p style="color:#bbf7d0;margin:8px 0 0;font-size:14px;">KYC Verification</p>
              </td>
            </tr>
            <tr>
              <td style="padding:40px 40px 32px;">
                <div style="text-align:center;margin-bottom:24px;">
                  <div style="width:64px;height:64px;background:#dcfce7;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px;">
                    <span style="font-size:32px;">✅</span>
                  </div>
                  <h2 style="color:#1e293b;font-size:22px;margin:0;">KYC Approved!</h2>
                </div>
                <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Hi <strong>{first_name}</strong>, congratulations! Your KYC verification has been approved.
                  You can now log in and start listing your properties on our platform.
                </p>
                <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:16px 20px;border-radius:6px;margin-bottom:24px;">
                  <p style="color:#15803d;font-size:14px;margin:0;font-weight:600;">✓ Identity Verified</p>
                  <p style="color:#15803d;font-size:14px;margin:4px 0 0;font-weight:600;">✓ Account Fully Activated</p>
                  <p style="color:#15803d;font-size:14px;margin:4px 0 0;font-weight:600;">✓ Ready to List Properties</p>
                </div>
                <p style="color:#94a3b8;font-size:13px;margin:0;">Log in to your account to get started.</p>
              </td>
            </tr>
            <tr>
              <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Accommodation Rentals. All rights reserved.</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_kyc_rejected_email_task(self, email, first_name, reason):
    """Send KYC rejection email asynchronously."""
    subject = 'KYC Verification Update – Action Required'

    plain = f"Hi {first_name}, your KYC was rejected. Reason: {reason}. Please resubmit."

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <tr>
              <td style="background:linear-gradient(135deg,#dc2626,#b91c1c);padding:36px 40px;text-align:center;">
                <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;">Accommodation Rentals</h1>
                <p style="color:#fecaca;margin:8px 0 0;font-size:14px;">KYC Verification</p>
              </td>
            </tr>
            <tr>
              <td style="padding:40px 40px 32px;">
                <div style="text-align:center;margin-bottom:24px;">
                  <span style="font-size:48px;">❌</span>
                  <h2 style="color:#1e293b;font-size:22px;margin:12px 0 0;">KYC Not Approved</h2>
                </div>
                <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Hi <strong>{first_name}</strong>, unfortunately your KYC verification was not approved.
                </p>
                <div style="background:#fff5f5;border-left:4px solid #dc2626;padding:16px 20px;border-radius:6px;margin-bottom:24px;">
                  <p style="color:#991b1b;font-size:13px;font-weight:700;margin:0 0 6px;text-transform:uppercase;letter-spacing:0.5px;">Reason</p>
                  <p style="color:#7f1d1d;font-size:15px;margin:0;">{reason or 'No specific reason provided.'}</p>
                </div>
                <p style="color:#64748b;font-size:14px;line-height:1.6;margin:0 0 8px;">
                  Please log in and resubmit your KYC documents addressing the reason above.
                </p>
                <p style="color:#94a3b8;font-size:13px;margin:0;">Contact support if you need assistance.</p>
              </td>
            </tr>
            <tr>
              <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Accommodation Rentals. All rights reserved.</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def cleanup_expired_tokens_task():
    """Periodic task to clean up expired OTPs and MFA sessions."""
    from auth_app.utils import cleanup_expired_mfa_sessions
    result = cleanup_expired_mfa_sessions()
    logger.info(f"Cleanup complete: {result}")
    return result

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email_task(self, email, first_name):
    subject = 'Welcome to Ez-Stay!'
    plain = f"Hi {first_name}, welcome to Ez-Stay! Start exploring properties today."
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <tr>
              <td style="background:linear-gradient(135deg,#2563eb,#1d4ed8);padding:36px 40px;text-align:center;">
                <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;">Ez-Stay</h1>
                <p style="color:#bfdbfe;margin:8px 0 0;font-size:14px;">Welcome Aboard!</p>
              </td>
            </tr>
            <tr>
              <td style="padding:40px 40px 32px;">
                <h2 style="color:#1e293b;font-size:22px;margin:0 0 12px;">Hi {first_name}, welcome to Ez-Stay! 🎉</h2>
                <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Your account is ready. Start exploring verified rental properties, schedule visits, and find your perfect stay.
                </p>
                <div style="background:#f0f7ff;border-left:4px solid #2563eb;padding:16px 20px;border-radius:6px;margin-bottom:24px;">
                  <p style="color:#1d4ed8;font-size:14px;margin:0;font-weight:600;">✓ Browse thousands of properties</p>
                  <p style="color:#1d4ed8;font-size:14px;margin:4px 0 0;font-weight:600;">✓ Schedule property visits</p>
                  <p style="color:#1d4ed8;font-size:14px;margin:4px 0 0;font-weight:600;">✓ Secure advance payments</p>
                </div>
                <p style="color:#94a3b8;font-size:13px;margin:0;">Happy house hunting!</p>
              </td>
            </tr>
            <tr>
              <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Ez-Stay. All rights reserved.</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_confirmed_email_task(self, email, first_name, property_title, amount, payment_id):
    subject = f'Booking Confirmed – {property_title}'
    plain = f"Hi {first_name}, your advance payment of ₹{amount} for {property_title} is confirmed. Payment ID: {payment_id}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <tr>
              <td style="background:linear-gradient(135deg,#16a34a,#15803d);padding:36px 40px;text-align:center;">
                <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;">Ez-Stay</h1>
                <p style="color:#bbf7d0;margin:8px 0 0;font-size:14px;">Booking Confirmed</p>
              </td>
            </tr>
            <tr>
              <td style="padding:40px 40px 32px;">
                <div style="text-align:center;margin-bottom:24px;">
                  <span style="font-size:48px;">🏠</span>
                  <h2 style="color:#1e293b;font-size:22px;margin:12px 0 0;">Booking Confirmed!</h2>
                </div>
                <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Hi <strong>{first_name}</strong>, your advance payment for <strong>{property_title}</strong> has been received and confirmed.
                </p>
                <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:16px 20px;border-radius:6px;margin-bottom:24px;">
                  <p style="color:#15803d;font-size:14px;margin:0;font-weight:600;">Property: {property_title}</p>
                  <p style="color:#15803d;font-size:14px;margin:4px 0 0;font-weight:600;">Amount Paid: ₹{amount}</p>
                  <p style="color:#15803d;font-size:14px;margin:4px 0 0;font-weight:600;">Payment ID: {payment_id}</p>
                </div>
                <p style="color:#94a3b8;font-size:13px;margin:0;">The lister will contact you shortly to arrange move-in details.</p>
              </td>
            </tr>
            <tr>
              <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Ez-Stay. All rights reserved.</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_received_email_task(self, email, lister_name, tenant_name, property_title, amount, payment_id):
    subject = f'Advance Payment Received – {property_title}'
    plain = f"Hi {lister_name}, {tenant_name} has paid ₹{amount} advance for {property_title}. Payment ID: {payment_id}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <tr>
              <td style="background:linear-gradient(135deg,#2563eb,#1d4ed8);padding:36px 40px;text-align:center;">
                <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;">Ez-Stay</h1>
                <p style="color:#bfdbfe;margin:8px 0 0;font-size:14px;">Payment Received</p>
              </td>
            </tr>
            <tr>
              <td style="padding:40px 40px 32px;">
                <div style="text-align:center;margin-bottom:24px;">
                  <span style="font-size:48px;">💰</span>
                  <h2 style="color:#1e293b;font-size:22px;margin:12px 0 0;">Advance Payment Received!</h2>
                </div>
                <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Hi <strong>{lister_name}</strong>, <strong>{tenant_name}</strong> has paid the advance for your property.
                </p>
                <div style="background:#f0f7ff;border-left:4px solid #2563eb;padding:16px 20px;border-radius:6px;margin-bottom:24px;">
                  <p style="color:#1d4ed8;font-size:14px;margin:0;font-weight:600;">Property: {property_title}</p>
                  <p style="color:#1d4ed8;font-size:14px;margin:4px 0 0;font-weight:600;">Tenant: {tenant_name}</p>
                  <p style="color:#1d4ed8;font-size:14px;margin:4px 0 0;font-weight:600;">Amount: ₹{amount}</p>
                  <p style="color:#1d4ed8;font-size:14px;margin:4px 0 0;font-weight:600;">Payment ID: {payment_id}</p>
                </div>
                <p style="color:#94a3b8;font-size:13px;margin:0;">Please contact the tenant to arrange move-in details.</p>
              </td>
            </tr>
            <tr>
              <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Ez-Stay. All rights reserved.</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email_task(self, email, first_name):
    subject = 'Welcome to Ez-Stay!'
    plain = f"Hi {first_name}, welcome to Ez-Stay! Start exploring properties today."
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <tr>
              <td style="background:linear-gradient(135deg,#2563eb,#1d4ed8);padding:36px 40px;text-align:center;">
                <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;">Ez-Stay</h1>
                <p style="color:#bfdbfe;margin:8px 0 0;font-size:14px;">Welcome Aboard!</p>
              </td>
            </tr>
            <tr>
              <td style="padding:40px 40px 32px;">
                <h2 style="color:#1e293b;font-size:22px;margin:0 0 12px;">Hi {first_name}, welcome to Ez-Stay! 🎉</h2>
                <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Your account is ready. Start exploring verified rental properties, schedule visits, and find your perfect stay.
                </p>
                <div style="background:#f0f7ff;border-left:4px solid #2563eb;padding:16px 20px;border-radius:6px;margin-bottom:24px;">
                  <p style="color:#1d4ed8;font-size:14px;margin:0;font-weight:600;">✓ Browse thousands of properties</p>
                  <p style="color:#1d4ed8;font-size:14px;margin:4px 0 0;font-weight:600;">✓ Schedule property visits</p>
                  <p style="color:#1d4ed8;font-size:14px;margin:4px 0 0;font-weight:600;">✓ Secure advance payments</p>
                </div>
                <p style="color:#94a3b8;font-size:13px;margin:0;">Happy house hunting!</p>
              </td>
            </tr>
            <tr>
              <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Ez-Stay. All rights reserved.</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_confirmed_email_task(self, email, first_name, property_title, amount, payment_id):
    subject = f'Booking Confirmed – {property_title}'
    plain = f"Hi {first_name}, your advance payment of ₹{amount} for {property_title} is confirmed. Payment ID: {payment_id}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <tr>
              <td style="background:linear-gradient(135deg,#16a34a,#15803d);padding:36px 40px;text-align:center;">
                <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;">Ez-Stay</h1>
                <p style="color:#bbf7d0;margin:8px 0 0;font-size:14px;">Booking Confirmed</p>
              </td>
            </tr>
            <tr>
              <td style="padding:40px 40px 32px;">
                <div style="text-align:center;margin-bottom:24px;">
                  <span style="font-size:48px;">🏠</span>
                  <h2 style="color:#1e293b;font-size:22px;margin:12px 0 0;">Booking Confirmed!</h2>
                </div>
                <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Hi <strong>{first_name}</strong>, your advance payment for <strong>{property_title}</strong> has been received and confirmed.
                </p>
                <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:16px 20px;border-radius:6px;margin-bottom:24px;">
                  <p style="color:#15803d;font-size:14px;margin:0;font-weight:600;">Property: {property_title}</p>
                  <p style="color:#15803d;font-size:14px;margin:4px 0 0;font-weight:600;">Amount Paid: ₹{amount}</p>
                  <p style="color:#15803d;font-size:14px;margin:4px 0 0;font-weight:600;">Payment ID: {payment_id}</p>
                </div>
                <p style="color:#94a3b8;font-size:13px;margin:0;">The lister will contact you shortly to arrange move-in details.</p>
              </td>
            </tr>
            <tr>
              <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Ez-Stay. All rights reserved.</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_received_email_task(self, email, lister_name, tenant_name, property_title, amount, payment_id):
    subject = f'Advance Payment Received – {property_title}'
    plain = f"Hi {lister_name}, {tenant_name} has paid ₹{amount} advance for {property_title}. Payment ID: {payment_id}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <tr>
              <td style="background:linear-gradient(135deg,#2563eb,#1d4ed8);padding:36px 40px;text-align:center;">
                <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;">Ez-Stay</h1>
                <p style="color:#bfdbfe;margin:8px 0 0;font-size:14px;">Payment Received</p>
              </td>
            </tr>
            <tr>
              <td style="padding:40px 40px 32px;">
                <div style="text-align:center;margin-bottom:24px;">
                  <span style="font-size:48px;">💰</span>
                  <h2 style="color:#1e293b;font-size:22px;margin:12px 0 0;">Advance Payment Received!</h2>
                </div>
                <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 20px;">
                  Hi <strong>{lister_name}</strong>, <strong>{tenant_name}</strong> has paid the advance for your property.
                </p>
                <div style="background:#f0f7ff;border-left:4px solid #2563eb;padding:16px 20px;border-radius:6px;margin-bottom:24px;">
                  <p style="color:#1d4ed8;font-size:14px;margin:0;font-weight:600;">Property: {property_title}</p>
                  <p style="color:#1d4ed8;font-size:14px;margin:4px 0 0;font-weight:600;">Tenant: {tenant_name}</p>
                  <p style="color:#1d4ed8;font-size:14px;margin:4px 0 0;font-weight:600;">Amount: ₹{amount}</p>
                  <p style="color:#1d4ed8;font-size:14px;margin:4px 0 0;font-weight:600;">Payment ID: {payment_id}</p>
                </div>
                <p style="color:#94a3b8;font-size:13px;margin:0;">Please contact the tenant to arrange move-in details.</p>
              </td>
            </tr>
            <tr>
              <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;text-align:center;">
                <p style="color:#94a3b8;font-size:12px;margin:0;">© 2025 Ez-Stay. All rights reserved.</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    try:
        _send_html_email(subject, email, html, plain)
    except Exception as exc:
        raise self.retry(exc=exc)
