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

from .admin_views import (
    UserListView,
)

from .oauth_views import (
    GoogleLoginView,
    GoogleLoginTokenView,
)

from .kyc_views import (
    KYCSubmissionView,
    KYCApprovalView,
    KYCPendingListView,
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
    
    # Admin
    'UserListView',
    
    # OAuth
    'GoogleLoginView',
    'GoogleLoginTokenView',

     # KYC
    'KYCSubmissionView',
    'KYCApprovalView',
    'KYCPendingListView',
]