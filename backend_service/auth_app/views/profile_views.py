from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
import cloudinary.uploader
import logging

logger = logging.getLogger(__name__)

from ..serializers import UserSerializer, UserUpdateSerializer
from profile_app.models import UserProfile, ListerProfile

class UserProfileView(generics.RetrieveUpdateAPIView):
    """Get/Update user profile"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserSerializer
        return UserUpdateSerializer
    
    def get_object(self):
        return self.request.user


class UserAvatarUploadView(APIView):
    """Upload user avatar to Cloudinary and update profile"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, *args, **kwargs):
        user = request.user
        avatar_file = request.FILES.get('avatar')

        if not avatar_file:
            return Response({'detail': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)
            
        allowed_extensions = ['jpg', 'jpeg', 'png']
        ext = avatar_file.name.split('.')[-1].lower()
        if ext not in allowed_extensions:
            return Response({'detail': 'Image must be JPG, JPEG, or PNG'}, status=status.HTTP_400_BAD_REQUEST)
            
        if avatar_file.size > 5 * 1024 * 1024:
            return Response({'detail': 'Image size must not exceed 5MB'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            upload_result = cloudinary.uploader.upload(
                avatar_file,
                folder=f'accommodation/profiles/{"listers" if user.role == "lister" else "users"}/',
                resource_type='image',
                public_id=f'user_{user.id}_avatar_{timezone.now().timestamp()}',
                overwrite=True,
                invalidate=True,
                transformation=[
                    {'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'},
                    {'quality': 'auto:good'}
                ]
            )

            public_id = upload_result.get('public_id')
            secure_url = upload_result.get('secure_url')
            
            if user.role == 'lister':
                profile, _ = ListerProfile.objects.get_or_create(user=user)
                if profile.profile_picture:
                    try:
                        cloudinary.uploader.destroy(profile.profile_picture.public_id)
                    except Exception as e:
                        logger.warning(f"Could not delete old avatar: {e}")
                profile.profile_picture = public_id
                profile.save()
            else:
                profile, _ = UserProfile.objects.get_or_create(user=user)
                if profile.profile_picture:
                    try:
                        cloudinary.uploader.destroy(profile.profile_picture.public_id)
                    except Exception as e:
                        logger.warning(f"Could not delete old avatar: {e}")
                profile.profile_picture = public_id
                profile.save()

            return Response({
                'detail': 'Avatar updated successfully', 
                'avatar': secure_url
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Avatar upload failed for user {user.email}: {str(e)}")
            return Response({'detail': f'Avatar upload failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)