from .auth_views import (
    UserLoginView,
    UserLogoutView,
)

from .registration_views import (
    RegisterOrVerifyEmailView,
    ResendOTPView,
)

from .password_views import (
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChangePasswordView,
)

from .profile_views import (
    UserProfileView,
)

from .oauth_views import (
    GoogleLoginView,
    GoogleLoginTokenView,
)

from .kyc_views import (
    KYCStatusView,
    KYCResubmissionView,
    KYCApprovalView,
    KYCPendingListView,
    KYCAllListersView,
)

__all__ = [
    # Auth
    'UserLoginView',
    'UserLogoutView',
    
    # Registration
    'RegisterOrVerifyEmailView',
    'ResendOTPView',
    
    # Password
    'PasswordResetRequestView',
    'PasswordResetConfirmView',
    'ChangePasswordView',
    
    # Profile
    'UserProfileView',
    
    # OAuth
    'GoogleLoginView',
    'GoogleLoginTokenView',

    # KYC
    'KYCStatusView',
    'KYCResubmissionView',
    'KYCApprovalView',
    'KYCPendingListView',
    'KYCAllListersView',
]