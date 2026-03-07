from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework import generics
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


# ── NEW: Picture upload views ──────────────────────────────────────────────────

class UserProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        file = request.FILES.get('profile_picture')
        if not file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        profile.profile_picture = file
        profile.save()
        return Response(UserProfileSerializer(profile).data)


class ListerProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        if request.user.role != 'lister':
            raise PermissionDenied("Only listers can access this.")
        profile, _ = ListerProfile.objects.get_or_create(user=request.user)
        file = request.FILES.get('profile_picture')
        if not file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        profile.profile_picture = file
        profile.save()
        return Response(ListerProfileSerializer(profile).data)