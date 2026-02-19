from django.urls import path
from . import views

urlpatterns = [
    path('profile/user/', views.UserProfileView.as_view(), name='user-profile'),
    path('profile/lister/', views.ListerProfileView.as_view(), name='lister-profile'),
]