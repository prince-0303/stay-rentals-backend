from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from .models import UserProfile, ListerProfile
from .serializers import UserProfileSerializer, ListerProfileSerializer


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class ListerProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ListerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        if self.request.user.role != 'lister':
            raise PermissionDenied("Only listers can access this profile.")
        profile, _ = ListerProfile.objects.get_or_create(user=self.request.user)
        return profile