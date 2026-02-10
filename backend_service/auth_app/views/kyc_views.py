from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from ..models import User
from ..permissions import IsAdmin


class KYCStatusView(APIView):
    """Get KYC status for current user (lister only)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.role != User.LISTER:
            return Response(
                {'detail': 'Only listers have KYC status'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Mask aadhar number (show only last 4 digits)
        masked_aadhar = None
        if user.aadhar_number:
            masked_aadhar = 'XXXX-XXXX-' + user.aadhar_number[-4:]
        
        return Response({
            'is_kyc_submitted': user.is_kyc_submitted,
            'kyc_status': user.kyc_status,
            'kyc_submitted_at': user.kyc_submitted_at,
            'kyc_verified_at': user.kyc_verified_at,
            'aadhar_number': masked_aadhar,
            'aadhar_front_url': user.aadhar_front_image.url if user.aadhar_front_image else None,
            'aadhar_back_url': user.aadhar_back_image.url if user.aadhar_back_image else None,
            'kyc_rejection_reason': user.kyc_rejection_reason,
            'can_resubmit': user.kyc_status == User.KYC_REJECTED,
        }, status=status.HTTP_200_OK)


class KYCResubmissionView(APIView):
    """Lister resubmits KYC after rejection"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        user = request.user
        
        if user.role != User.LISTER:
            return Response(
                {'detail': 'Only listers can submit KYC'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if user.kyc_status != User.KYC_REJECTED:
            return Response(
                {'detail': 'You can only resubmit after rejection.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get new data
        aadhar_number = request.data.get('aadhar_number', '').strip()
        aadhar_front = request.FILES.get('aadhar_front')
        aadhar_back = request.FILES.get('aadhar_back')
        
        # Validate
        if not aadhar_number or len(aadhar_number) != 12 or not aadhar_number.isdigit():
            return Response(
                {'detail': 'Valid 12-digit Aadhar number required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not aadhar_front or not aadhar_back:
            return Response(
                {'detail': 'Both front and back images required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if aadhar already exists (excluding current user)
        if User.objects.filter(aadhar_number=aadhar_number).exclude(id=user.id).exists():
            return Response(
                {'detail': 'This Aadhar number is already registered.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update user
        user.aadhar_number = aadhar_number
        user.aadhar_front_image = aadhar_front
        user.aadhar_back_image = aadhar_back
        user.is_kyc_submitted = True
        user.kyc_submitted_at = timezone.now()
        user.kyc_status = User.KYC_PENDING
        user.kyc_rejection_reason = None
        user.save()
        
        return Response(
            {
                'detail': 'KYC resubmitted successfully. Admin will review your documents.',
                'kyc_status': user.kyc_status,
            },
            status=status.HTTP_200_OK
        )


class KYCApprovalView(APIView):
    """Admin manually verifies Aadhaar and approves/rejects"""
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request, user_id):
        """Get KYC details for admin review"""
        try:
            user = User.objects.get(id=user_id, role=User.LISTER)
        except User.DoesNotExist:
            return Response(
                {'detail': 'Lister not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        data = {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
            'aadhar_number': user.aadhar_number,
            'aadhar_front_url': user.aadhar_front_image.url if user.aadhar_front_image else None,
            'aadhar_back_url': user.aadhar_back_image.url if user.aadhar_back_image else None,
            'kyc_status': user.kyc_status,
            'is_kyc_submitted': user.is_kyc_submitted,
            'kyc_submitted_at': user.kyc_submitted_at,
            'kyc_verified_at': user.kyc_verified_at,
            'kyc_rejection_reason': user.kyc_rejection_reason,
            'date_joined': user.date_joined,
        }
        
        return Response(data, status=status.HTTP_200_OK)
    
    def post(self, request, user_id):
        """Admin approves/rejects after manual verification"""
        try:
            user = User.objects.get(id=user_id, role=User.LISTER)
        except User.DoesNotExist:
            return Response(
                {'detail': 'Lister not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not user.is_kyc_submitted:
            return Response(
                {'detail': 'KYC not yet submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        action = request.data.get('action')
        rejection_reason = request.data.get('reason', '')
        
        if action == 'approve':
            user.kyc_status = User.KYC_APPROVED
            user.kyc_verified_at = timezone.now()
            user.kyc_rejection_reason = None
            message = f'KYC approved for {user.email}. Lister can now login.'
            
        elif action == 'reject':
            if not rejection_reason:
                return Response(
                    {'detail': 'Rejection reason is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user.kyc_status = User.KYC_REJECTED
            user.kyc_rejection_reason = rejection_reason
            message = f'KYC rejected for {user.email}. Reason: {rejection_reason}'
            
        else:
            return Response(
                {'detail': 'Invalid action. Use "approve" or "reject"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.save()
        
        # TODO: Send email notification to user about KYC status
        
        return Response(
            {
                'detail': message,
                'kyc_status': user.kyc_status,
                'user_email': user.email
            },
            status=status.HTTP_200_OK
        )


class KYCPendingListView(APIView):
    """Admin views all pending KYC submissions"""
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        pending_listers = User.objects.filter(
            role=User.LISTER,
            kyc_status=User.KYC_PENDING,
            is_kyc_submitted=True
        ).order_by('-kyc_submitted_at')
        
        data = []
        for user in pending_listers:
            data.append({
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'aadhar_number': user.aadhar_number,
                'aadhar_front_url': user.aadhar_front_image.url if user.aadhar_front_image else None,
                'aadhar_back_url': user.aadhar_back_image.url if user.aadhar_back_image else None,
                'kyc_submitted_at': user.kyc_submitted_at,
                'date_joined': user.date_joined,
            })
        
        return Response({
            'count': pending_listers.count(),
            'pending_kyc': data
        }, status=status.HTTP_200_OK)


class KYCAllListersView(APIView):
    """Admin views all listers with their KYC status"""
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        # Get filter from query params
        status_filter = request.query_params.get('status', None)
        
        listers = User.objects.filter(role=User.LISTER).order_by('-kyc_submitted_at')
        
        if status_filter:
            listers = listers.filter(kyc_status=status_filter)
        
        data = []
        for user in listers:
            data.append({
                'id': user.id,
                'email': user.email,
                'full_name': user.get_full_name(),
                'phone_number': user.phone_number,
                'kyc_status': user.kyc_status,
                'is_kyc_submitted': user.is_kyc_submitted,
                'kyc_submitted_at': user.kyc_submitted_at,
                'kyc_verified_at': user.kyc_verified_at,
                'kyc_rejection_reason': user.kyc_rejection_reason,
                'is_active': user.is_active,
                'date_joined': user.date_joined,
            })
        
        return Response({
            'count': listers.count(),
            'listers': data
        }, status=status.HTTP_200_OK)