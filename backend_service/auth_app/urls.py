from django.urls import path
from .views import (
    UserLoginView,
    GoogleLoginView,
    UserLogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChangePasswordView,
    UserProfileView,
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
    
    # KYC - Lister
    path('kyc/status/', KYCStatusView.as_view(), name='kyc-status'),
    path('kyc/resubmit/', KYCResubmissionView.as_view(), name='kyc-resubmit'),
    
    # KYC - Admin
    path('kyc/pending/', KYCPendingListView.as_view(), name='kyc-pending'),
    path('kyc/review/<int:user_id>/', KYCApprovalView.as_view(), name='kyc-review'),
    path('kyc/all/', KYCAllListersView.as_view(), name='kyc-all-listers'),
]