from django.urls import path
from .views import (
    UserProfileView, ListerProfileView,
    UserProfilePictureView, ListerProfilePictureView
)

urlpatterns = [
    path('user/', UserProfileView.as_view(), name='user-profile'),
    path('lister/', ListerProfileView.as_view(), name='lister-profile'),
    path('user/picture/', UserProfilePictureView.as_view(), name='user-profile-picture'),
    path('lister/picture/', ListerProfilePictureView.as_view(), name='lister-profile-picture'),
]