from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from ..models import User
from ..permissions import IsAdmin
from ..serializers import KYCSubmissionSerializer, KYCStatusSerializer, UserSerializer


class KYCSubmissionView(APIView):
    """Lister submits Aadhaar for KYC verification"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        user = request.user
        
        if user.role != User.LISTER:
            return Response(
                {'detail': 'Only listers can submit KYC'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if user.kyc_status == User.KYC_APPROVED:
            return Response(
                {'detail': 'Your KYC is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = KYCSubmissionSerializer(data=request.data, context={'user': user})
        serializer.is_valid(raise_exception=True)
        
        user.aadhar_number = serializer.validated_data['aadhar_number']
        user.aadhar_image = serializer.validated_data['aadhar_image']
        user.is_kyc_submitted = True
        user.kyc_submitted_at = timezone.now()
        user.kyc_status = User.KYC_PENDING
        user.kyc_rejection_reason = None
        user.save()
        
        return Response(
            {
                'detail': 'KYC submitted successfully. Admin will verify your Aadhaar.',
                'kyc_status': user.kyc_status,
                'aadhar_image_url': user.aadhar_image.url if user.aadhar_image else None
            },
            status=status.HTTP_200_OK
        )
    
    def get(self, request):
        """Get KYC status"""
        user = request.user
        
        if user.role != User.LISTER:
            return Response(
                {'detail': 'Only listers have KYC status'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = KYCStatusSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
            'aadhar_image_url': user.aadhar_image.url if user.aadhar_image else None,
            'kyc_status': user.kyc_status,
            'is_kyc_submitted': user.is_kyc_submitted,
            'kyc_submitted_at': user.kyc_submitted_at,
            'kyc_verified_at': user.kyc_verified_at,
            'kyc_rejection_reason': user.kyc_rejection_reason,
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
            message = 'KYC approved. Lister verified successfully.'
            
        elif action == 'reject':
            if not rejection_reason:
                return Response(
                    {'detail': 'Rejection reason is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user.kyc_status = User.KYC_REJECTED
            user.is_kyc_submitted = False
            user.kyc_rejection_reason = rejection_reason
            message = f'KYC rejected. Reason: {rejection_reason}'
            
        else:
            return Response(
                {'detail': 'Invalid action. Use "approve" or "reject"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.save()
        
        return Response(
            {
                'detail': message,
                'kyc_status': user.kyc_status
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
        )
        
        data = []
        for user in pending_listers:
            data.append({
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'aadhar_number': user.aadhar_number,
                'aadhar_image_url': user.aadhar_image.url if user.aadhar_image else None,
                'kyc_submitted_at': user.kyc_submitted_at,
            })
        
        return Response({
            'count': pending_listers.count(),
            'pending_kyc': data
        }, status=status.HTTP_200_OK)