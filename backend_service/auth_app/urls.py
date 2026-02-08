from django.urls import path
from .views import (
    # UserRegistrationView,
    # VerifyEmailView,
    ResendOTPView,
    UserLoginView,
    UserLogoutView,
    UserProfileView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChangePasswordView,
    UserListView,
    GoogleLoginView,
    GoogleLoginTokenView,
    RegisterOrVerifyEmailView,
)

app_name = 'auth_app'

urlpatterns = [
    # Registration & Verification
    # path('register/', UserRegistrationView.as_view(), name='register'),
    # path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('RegisterOrVerifyEmailView/', RegisterOrVerifyEmailView.as_view(), name='verify-email'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    
    # Login & Logout
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('google/login/', GoogleLoginView.as_view(), name='google-login'),
    path('google/token/', GoogleLoginTokenView.as_view(), name='google-token'),
    
    # Password Management
    path('password/reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('password/change/', ChangePasswordView.as_view(), name='change-password'),
    
    # User Profile
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    
    # User Management (Admin)
    path('users/', UserListView.as_view(), name='user-list'),
]