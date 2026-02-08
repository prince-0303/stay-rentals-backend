from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from ..models import User
from ..serializers import UserSerializer
from ..permissions import IsAdmin


class UserListView(generics.ListAPIView):
    """List users (Admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = UserSerializer
    queryset = User.objects.all()
    
    def get_queryset(self):
        queryset = User.objects.all()
        
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        is_verified = self.request.query_params.get('is_email_verified')
        if is_verified is not None:
            queryset = queryset.filter(is_email_verified=is_verified.lower() == 'true')
        
        return queryset