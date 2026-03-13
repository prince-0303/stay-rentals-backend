from .auth_views import UserLoginView, UserLogoutView, CookieTokenRefreshView
from .registration_views import RegisterOrVerifyEmailView, ResendOTPView
from .password_views import PasswordResetRequestView, PasswordResetConfirmView, ChangePasswordView
from .profile_views import UserProfileView, UserAvatarUploadView
from .oauth_views import GoogleLoginView, GoogleLoginTokenView
from .kyc_views import KYCStatusView, KYCResubmissionView, KYCApprovalView, KYCPendingListView, KYCAllListersView
from .mfa_views import (
    MFAStatusView,
    MFASetupInitView,
    MFAVerifySetupView,
    MFARegenerateBackupCodesView,
    MFADisableView,
    MFASendCodeView,
    MFALoginVerifyView,
)
from .auth_views import UserLoginView, UserLogoutView, CookieTokenRefreshView, DeactivateAccountView, DeleteAccountView
__all__ = [
    'UserLoginView', 'UserLogoutView', 'CookieTokenRefreshView'
    'RegisterOrVerifyEmailView', 'ResendOTPView',
    'PasswordResetRequestView', 'PasswordResetConfirmView', 'ChangePasswordView',
    'UserProfileView', 'UserAvatarUploadView',
    'GoogleLoginView', 'GoogleLoginTokenView',
    'KYCStatusView', 'KYCResubmissionView', 'KYCApprovalView', 'KYCPendingListView', 'KYCAllListersView',
    'MFAStatusView', 'MFASetupInitView', 'MFAVerifySetupView',
    'MFARegenerateBackupCodesView', 'MFADisableView', 'MFASendCodeView', 'MFALoginVerifyView',
    'DeactivateAccountView', 'DeleteAccountView',
]