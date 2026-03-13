from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from auth_app.models import User
from profile_app.models import UserProfile, ListerProfile
from .permissions import IsAdminUser
from .models import AuditLog
from .serializers import AdminUserSerializer, AdminUserDetailSerializer,AdminListerDetailSerializer,AdminCreateUserSerializer,AdminKYCSerializer,BlockActionSerializer, AdminKYCActionSerializer
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from payments_app.models import Payment
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
        search = request.query_params.get('search')
        is_active = request.query_params.get('is_active')

        if search:
            users = users.filter(email__icontains=search) | \
                    users.filter(first_name__icontains=search) | \
                    users.filter(last_name__icontains=search)
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

    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
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
        responses={200: OpenApiResponse(description='User blocked/unblocked')}
    )
    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        reason = request.data.get('reason', '')

        if action not in ['block', 'unblock']:
            return Response({'detail': 'Action must be block or unblock'}, status=status.HTTP_400_BAD_REQUEST)

        is_blocked = action == 'block'

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


class AdminListerDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="Get full lister details including KYC and aadhar images",
        responses={200: OpenApiResponse(description='Lister detail with KYC')}
    )
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role='lister')
        except User.DoesNotExist:
            return Response({'detail': 'Lister not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminListerDetailSerializer(user).data)

    @extend_schema(responses={200: OpenApiResponse(description='Lister updated')})
    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role='lister')
        except User.DoesNotExist:
            return Response({'detail': 'Lister not found'}, status=status.HTTP_404_NOT_FOUND)

        allowed = ['first_name', 'last_name', 'phone_number', 'is_active']
        data = {k: v for k, v in request.data.items() if k in allowed}
        for attr, value in data.items():
            setattr(user, attr, value)
        user.save()

        log_action(request.user, 'update_lister', 'User', user.id, f'Updated fields: {list(data.keys())}')
        return Response(AdminListerDetailSerializer(user).data)

    @extend_schema(responses={200: OpenApiResponse(description='Lister deleted')})
    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role='lister')
        except User.DoesNotExist:
            return Response({'detail': 'Lister not found'}, status=status.HTTP_404_NOT_FOUND)
        email = user.email
        user.delete()
        log_action(request.user, 'delete_lister', 'User', user_id, f'Deleted lister {email}')
        return Response({'detail': f'Lister {email} deleted.'}, status=status.HTTP_200_OK)


# ── KYC ────────────────────────────────────────────────────────────────────

class AdminKYCListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='status', type=str, required=False,
                           description='Filter by KYC status: pending, approved, rejected, not_submitted'),
        ],
        responses={200: OpenApiResponse(description='KYC list')}
    )
    def get(self, request):
        from django.db.models import F
        kyc_status = request.query_params.get('status', 'all')

        listers = User.objects.filter(
            role='lister'
        ).order_by(F('kyc_submitted_at').desc(nulls_last=True))

        if kyc_status and kyc_status != 'all':
            listers = listers.filter(kyc_status=kyc_status)

        serializer = AdminKYCSerializer(listers, many=True)
        return Response({'count': listers.count(), 'kyc_list': serializer.data})


class AdminKYCActionView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="Get full KYC detail for a lister",
        responses={200: OpenApiResponse(description='KYC detail')}
    )
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role='lister')
        except User.DoesNotExist:
            return Response({'detail': 'Lister not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminListerDetailSerializer(user)
        return Response(serializer.data)

    @extend_schema(
        summary="Admin approve or reject a lister's KYC",
        request=AdminKYCActionSerializer,
        responses={200: OpenApiResponse(description='KYC approved or rejected')}
    )
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role='lister')
        except User.DoesNotExist:
            return Response({'detail': 'Lister not found'}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_kyc_submitted:
            return Response(
                {'detail': 'This lister has not submitted KYC yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.kyc_status != User.KYC_PENDING:
            return Response(
                {'detail': f'KYC is already {user.kyc_status}. Cannot action again.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AdminKYCActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')

        if action == 'approve':
            user.kyc_status = User.KYC_APPROVED
            user.kyc_verified_at = timezone.now()
            user.kyc_rejection_reason = None
            message = f'KYC approved for {user.email}.'
        else:
            user.kyc_status = User.KYC_REJECTED
            user.kyc_rejection_reason = reason
            user.kyc_verified_at = None
            message = f'KYC rejected for {user.email}. Reason: {reason}'

        user.save(update_fields=['kyc_status', 'kyc_verified_at', 'kyc_rejection_reason'])
        from notifications_app.tasks import send_notification_task
        send_notification_task.delay(
            user.id,
            'KYC Status Update',
            f'Your KYC has been {action}',
            {'type': 'kyc_update', 'status': action}
        )
        # Send email
        if action == 'approve':
            from auth_app.tasks import send_kyc_approved_email_task
            send_kyc_approved_email_task.delay(user.email, user.first_name)
        else:
            from auth_app.tasks import send_kyc_rejected_email_task
            send_kyc_rejected_email_task.delay(user.email, user.first_name, reason)

        log_action(request.user, f'kyc_{action}', 'User', user.id, message)

        return Response({
            'detail': message,
            'kyc_status': user.kyc_status,
            'user_email': user.email,
        }, status=status.HTTP_200_OK)


# ── DASHBOARD ──────────────────────────────────────────────────────────────

class AdminDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(responses={200: OpenApiResponse(description='Dashboard Stats')})
    def get(self, request):
        total_users = User.objects.filter(role='user').count()
        total_listers = User.objects.filter(role='lister').count()
        pending_kyc = User.objects.filter(role='lister', is_kyc_submitted=True, kyc_status='pending').count()
        approved_kyc = User.objects.filter(role='lister', is_kyc_submitted=True, kyc_status='approved').count()
        rejected_kyc = User.objects.filter(role='lister', is_kyc_submitted=True, kyc_status='rejected').count()
        not_submitted_kyc = User.objects.filter(role='lister', is_kyc_submitted=False).count()

        return Response({
            'total_users': total_users,
            'total_listers': total_listers,
            'pending_kyc': pending_kyc,
            'approved_kyc': approved_kyc,
            'rejected_kyc': rejected_kyc,
            'not_submitted_kyc': not_submitted_kyc,
        })


class AdminDashboardChartsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(responses={200: OpenApiResponse(description='Dashboard Charts')})
    def get(self, request):
        import datetime
        from django.db.models import Count
        from django.db.models.functions import TruncMonth

        pending = User.objects.filter(role='lister', is_kyc_submitted=True, kyc_status='pending').count()
        approved = User.objects.filter(role='lister', is_kyc_submitted=True, kyc_status='approved').count()
        rejected = User.objects.filter(role='lister', is_kyc_submitted=True, kyc_status='rejected').count()
        not_submitted = User.objects.filter(role='lister', is_kyc_submitted=False).count()

        kyc_breakdown = [
            {'name': 'Approved', 'value': approved},
            {'name': 'Pending', 'value': pending},
            {'name': 'Rejected', 'value': rejected},
            {'name': 'Not Submitted', 'value': not_submitted},
        ]

        six_months_ago = timezone.now() - datetime.timedelta(days=180)

        users_growth = (
            User.objects.filter(role='user', date_joined__gte=six_months_ago)
            .annotate(month=TruncMonth('date_joined'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        listers_growth = (
            User.objects.filter(role='lister', date_joined__gte=six_months_ago)
            .annotate(month=TruncMonth('date_joined'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        month_map = {}
        for i in range(5, -1, -1):
            d = timezone.now() - datetime.timedelta(days=30 * i)
            m_str = d.strftime('%b')
            month_map[m_str] = {'month': m_str, 'users': 0, 'listers': 0}

        for entry in users_growth:
            m_str = entry['month'].strftime('%b')
            if m_str in month_map:
                month_map[m_str]['users'] = entry['count']

        for entry in listers_growth:
            m_str = entry['month'].strftime('%b')
            if m_str in month_map:
                month_map[m_str]['listers'] = entry['count']

        return Response({
            'kyc_breakdown': kyc_breakdown,
            'user_growth': list(month_map.values()),
        })

class AdminEarningsOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        payments = Payment.objects.filter(
            status='success'
        ).select_related('property', 'property__lister', 'user')

        total_earned = payments.aggregate(total=Sum('amount'))['total'] or 0
        total_bookings = payments.count()

        # Per lister summary
        lister_summary = (
            payments
            .values(
                'property__lister__id',
                'property__lister__email',
                'property__lister__first_name',
                'property__lister__last_name',
            )
            .annotate(
                total=Sum('amount'),
                bookings=Count('id')
            )
            .order_by('-total')
        )

        lister_list = [
            {
                "lister_id": l['property__lister__id'],
                "lister_email": l['property__lister__email'],
                "lister_name": f"{l['property__lister__first_name']} {l['property__lister__last_name']}".strip(),
                "total_earned": float(l['total']),
                "total_bookings": l['bookings'],
            }
            for l in lister_summary
        ]

        # Monthly summary
        monthly_data = (
            payments
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(amount=Sum('amount'))
            .order_by('month')
        )

        monthly_summary = [
            {
                "month": entry['month'].strftime("%b %Y"),
                "amount": float(entry['amount'])
            }
            for entry in monthly_data
        ]

        return Response({
            "total_earned": float(total_earned),
            "total_bookings": total_bookings,
            "total_listers": len(lister_list),
            "lister_summary": lister_list,
            "monthly_summary": monthly_summary,
        })
    
class AdminListerEarningsDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, lister_id):
        payments = Payment.objects.filter(
            property__lister__id=lister_id,
            status='success'
        ).select_related('property', 'user').order_by('-created_at')

        total_earned = payments.aggregate(total=Sum('amount'))['total'] or 0

        payments_list = [
            {
                "property_title": p.property.title,
                "tenant_email": p.user.email,
                "amount": float(p.amount),
                "paid_at": p.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            for p in payments
        ]

        lister = payments.first().property.lister if payments.exists() else None
        lister_info = {
            "id": lister.id,
            "email": lister.email,
            "name": f"{lister.first_name} {lister.last_name}".strip(),
        } if lister else {}

        return Response({
            "lister": lister_info,
            "total_earned": float(total_earned),
            "total_bookings": payments.count(),
            "payments": payments_list,
        })
    
class AdminOccupancyView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        view_type = request.query_params.get('view', 'properties')

        if view_type == 'users':
            payments = Payment.objects.filter(
                status='success'
            ).select_related('user', 'property', 'property__lister').order_by('-created_at')

            user_map = {}
            for p in payments:
                uid = p.user.id
                if uid not in user_map:
                    user_map[uid] = {
                        "user_id": uid,
                        "user_name": f"{p.user.first_name} {p.user.last_name}".strip() or p.user.email,
                        "user_email": p.user.email,
                        "booked_properties": []
                    }
                user_map[uid]["booked_properties"].append({
                    "property_id": p.property.id,
                    "property_title": p.property.title,
                    "city": p.property.city,
                    "amount_paid": float(p.amount),
                    "paid_at": p.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "lister_name": f"{p.property.lister.first_name} {p.property.lister.last_name}".strip() or p.property.lister.email,
                })

            return Response({
                "view": "users",
                "count": len(user_map),
                "data": list(user_map.values())
            })

        else:
            # Properties → who booked them
            payments = Payment.objects.filter(
                status='success'
            ).select_related('property', 'property__lister', 'user').order_by('-created_at')

            property_map = {}
            for p in payments:
                pid = p.property.id
                if pid not in property_map:
                    property_map[pid] = {
                        "property_id": pid,
                        "property_title": p.property.title,
                        "city": p.property.city,
                        "state": p.property.state,
                        "rent_price": float(p.property.rent_price),
                        "lister_name": f"{p.property.lister.first_name} {p.property.lister.last_name}".strip() or p.property.lister.email,
                        "lister_email": p.property.lister.email,
                        "booked_by": {
                            "user_id": p.user.id,
                            "user_name": f"{p.user.first_name} {p.user.last_name}".strip() or p.user.email,
                            "user_email": p.user.email,
                            "amount_paid": float(p.amount),
                            "paid_at": p.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }
                    }

            return Response({
                "view": "properties",
                "count": len(property_map),
                "data": list(property_map.values())
            })