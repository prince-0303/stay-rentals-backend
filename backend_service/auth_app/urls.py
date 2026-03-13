from django.urls import path
from .views import (
    UserLoginView,
    GoogleLoginView,
    UserLogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChangePasswordView,
    UserProfileView,
    UserAvatarUploadView,
)
from .views import (
    RegisterOrVerifyEmailView,
    ResendOTPView,
)
from .views import (
    KYCStatusView,
    KYCResubmissionView,
    KYCApprovalView,
    KYCPendingListView,
    KYCAllListersView,
)

from .views import (
    MFAStatusView,
    MFASetupInitView,
    MFAVerifySetupView,
    MFARegenerateBackupCodesView,
    MFADisableView,
    MFASendCodeView,
    MFALoginVerifyView,
)
from .views import CookieTokenRefreshView
from .views import DeactivateAccountView, DeleteAccountView



urlpatterns = [
    # Authentication
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    
    # Registration & Email Verification
    path('register/', RegisterOrVerifyEmailView.as_view(), name='register-or-verify'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    
    # Password Management
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    
    # Google OAuth
    path('google/login/', GoogleLoginView.as_view(), name='google-login'),
    
    # User Profile
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('profile/avatar/', UserAvatarUploadView.as_view(), name='profile-avatar'),
    
    # KYC - Lister
    path('kyc/status/', KYCStatusView.as_view(), name='kyc-status'),
    path('kyc/submit/', KYCResubmissionView.as_view(), name='kyc-resubmit'),
    
    # KYC - Admin
    path('kyc/pending/', KYCPendingListView.as_view(), name='kyc-pending'),
    path('kyc/review/<int:user_id>/', KYCApprovalView.as_view(), name='kyc-review'),
    path('kyc/all/', KYCAllListersView.as_view(), name='kyc-all-listers'),
    
    # MFA Status
    path('mfa/status/', MFAStatusView.as_view(), name='mfa-status'),
    
    # MFA Setup
    path('mfa/setup/init/', MFASetupInitView.as_view(), name='mfa-setup-init'),
    path('mfa/setup/verify/', MFAVerifySetupView.as_view(), name='mfa-setup-verify'),
    
    # MFA Management
    path('mfa/backup-codes/regenerate/', MFARegenerateBackupCodesView.as_view(), name='mfa-regenerate-codes'),
    path('mfa/disable/', MFADisableView.as_view(), name='mfa-disable'),
    
    # MFA Login Verification
    path('mfa/send-code/', MFASendCodeView.as_view(), name='mfa-send-code'),
    path('mfa/verify/', MFALoginVerifyView.as_view(), name='mfa-verify'),

    # Token
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token-refresh'),

    # Account activity
    path('account/deactivate/', DeactivateAccountView.as_view(), name='account-deactivate'),
    path('account/delete/', DeleteAccountView.as_view(), name='account-delete'),
]