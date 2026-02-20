from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from auth_app.models import User
from profile_app.models import UserProfile, ListerProfile
from .permissions import IsAdminUser
from .models import AuditLog
from .serializers import (
    AdminUserSerializer, AdminUserDetailSerializer,
    AdminCreateUserSerializer, AdminKYCSerializer, BlockActionSerializer
)
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter


def log_action(admin, action, model, target_id, detail=''):
    AuditLog.objects.create(admin=admin, action=action, target_model=model, target_id=target_id, detail=detail)


# ── USERS ──────────────────────────────────────────────────────────────────

class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='search', type=str, required=False),
            OpenApiParameter(name='is_active', type=bool, required=False),
        ],
        responses={200: OpenApiResponse(description='List of users')}
    )

    def get(self, request):
        users = User.objects.filter(role='user').order_by('-date_joined')

        # Filters
        search = request.query_params.get('search')
        is_active = request.query_params.get('is_active')

        if search:
            users = users.filter(
                email__icontains=search
            ) | users.filter(
                first_name__icontains=search
            ) | users.filter(
                last_name__icontains=search
            )
        if is_active is not None:
            users = users.filter(is_active=is_active.lower() == 'true')

        serializer = AdminUserSerializer(users, many=True)
        return Response({'count': users.count(), 'users': serializer.data})
    
    @extend_schema(
        request=AdminCreateUserSerializer,
        responses={201: OpenApiResponse(description='User created')}
    )

    def post(self, request):
        serializer = AdminCreateUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        log_action(request.user, 'create_user', 'User', user.id, f'Created user {user.email}')
        return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_user(self, user_id, role=None):
        try:
            qs = User.objects.filter(id=user_id)
            if role:
                qs = qs.filter(role=role)
            return qs.get()
        except User.DoesNotExist:
            return None
        
    @extend_schema(responses={200: OpenApiResponse(description='User detail')})
    def get(self, request, user_id):
        user = self.get_user(user_id)
        if not user:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminUserDetailSerializer(user).data)
    
    @extend_schema(responses={200: OpenApiResponse(description='User updated')})
    def patch(self, request, user_id):
        user = self.get_user(user_id)
        if not user:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Only allow safe fields to be updated by admin
        allowed = ['first_name', 'last_name', 'phone_number', 'is_active']
        data = {k: v for k, v in request.data.items() if k in allowed}

        for attr, value in data.items():
            setattr(user, attr, value)
        user.save()

        log_action(request.user, 'update_user', 'User', user.id, f'Updated fields: {list(data.keys())}')
        return Response(AdminUserDetailSerializer(user).data)
    
    @extend_schema(responses={200: OpenApiResponse(description='User deleted')})
    def delete(self, request, user_id):
        user = self.get_user(user_id)
        if not user:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        email = user.email
        user.delete()
        log_action(request.user, 'delete_user', 'User', user_id, f'Deleted user {email}')
        return Response({'detail': f'User {email} deleted.'}, status=status.HTTP_200_OK)


class AdminUserBlockView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        request=BlockActionSerializer,
        responses={
            200: OpenApiResponse(description='User blocked/unblocked'),
            400: OpenApiResponse(description='Invalid action'),
        }
    )
    
    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')  # 'block' or 'unblock'
        reason = request.data.get('reason', '')

        if action not in ['block', 'unblock']:
            return Response({'detail': 'Action must be block or unblock'}, status=status.HTTP_400_BAD_REQUEST)

        is_blocked = action == 'block'

        # Update the right profile
        if user.role == 'user':
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.is_blocked = is_blocked
            profile.blocked_at = timezone.now() if is_blocked else None
            profile.blocked_reason = reason if is_blocked else None
            profile.save()
        elif user.role == 'lister':
            profile, _ = ListerProfile.objects.get_or_create(user=user)
            profile.is_blocked = is_blocked
            profile.blocked_at = timezone.now() if is_blocked else None
            profile.blocked_reason = reason if is_blocked else None
            profile.save()

        # Also deactivate the user account on block
        user.is_active = not is_blocked
        user.save(update_fields=['is_active'])

        log_action(request.user, f'{action}_user', 'User', user.id, reason)
        return Response({'detail': f'User {action}ed successfully.', 'is_active': user.is_active})


# ── LISTERS ────────────────────────────────────────────────────────────────

class AdminListerListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='search', type=str, required=False),
            OpenApiParameter(name='kyc_status', type=str, required=False),
            OpenApiParameter(name='is_active', type=bool, required=False),
        ],
        responses={200: OpenApiResponse(description='List of listers')}
    )

    def get(self, request):
        listers = User.objects.filter(role='lister').order_by('-date_joined')

        search = request.query_params.get('search')
        kyc_status = request.query_params.get('kyc_status')
        is_active = request.query_params.get('is_active')

        if search:
            listers = listers.filter(email__icontains=search) | \
                      listers.filter(first_name__icontains=search) | \
                      listers.filter(last_name__icontains=search)
        if kyc_status:
            listers = listers.filter(kyc_status=kyc_status)
        if is_active is not None:
            listers = listers.filter(is_active=is_active.lower() == 'true')

        serializer = AdminUserSerializer(listers, many=True)
        return Response({'count': listers.count(), 'listers': serializer.data})
    
    @extend_schema(
        request=AdminCreateUserSerializer,
        responses={201: OpenApiResponse(description='Lister created')}
    )

    def post(self, request):
        data = request.data.copy()
        data['role'] = 'lister'
        serializer = AdminCreateUserSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        log_action(request.user, 'create_lister', 'User', user.id, f'Created lister {user.email}')
        return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


# ── KYC ────────────────────────────────────────────────────────────────────

class AdminKYCListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='status', type=str, required=False,
                           description='Filter by KYC status: pending, approved, rejected'),
        ],
        responses={200: OpenApiResponse(description='KYC list')}
    )
    def get(self, request):
        kyc_status = request.query_params.get('status', 'pending')
        listers = User.objects.filter(
            role='lister',
            is_kyc_submitted=True,
            kyc_status=kyc_status
        ).order_by('-kyc_submitted_at')

        serializer = AdminKYCSerializer(listers, many=True)
        return Response({'count': listers.count(), 'kyc_list': serializer.data})