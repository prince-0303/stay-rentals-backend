from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from ..models import User
from ..permissions import IsAdmin
import logging
logger = logging.getLogger(__name__)

class KYCStatusView(APIView):
    """Get KYC status for current user (lister only)"""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={
            200: OpenApiResponse(description='KYC status retrieved successfully'),
            403: OpenApiResponse(description='Only listers have KYC status'),
        }
    )

    def get(self, request):
        user = request.user
        
        if user.role != User.LISTER:
            return Response(
                {'detail': 'Only listers have KYC status'},
                status=status.HTTP_403_FORBIDDEN
            )
        
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
    """
    Lister submits/resubmits KYC with Cloudinary upload
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'aadhar_number': {'type': 'string', 'description': '12-digit Aadhar number'},
                    'aadhar_front': {'type': 'string', 'format': 'binary', 'description': 'Front image of Aadhar (JPG/PNG, max 10MB)'},
                    'aadhar_back': {'type': 'string', 'format': 'binary', 'description': 'Back image of Aadhar (JPG/PNG, max 10MB)'},
                },
                'required': ['aadhar_number', 'aadhar_front', 'aadhar_back']
            }
        },
        responses={
            200: OpenApiResponse(description='KYC submitted successfully'),
            400: OpenApiResponse(description='Validation error'),
            403: OpenApiResponse(description='Only listers can submit KYC'),
            500: OpenApiResponse(description='Cloudinary upload failed'),
        }
    )

    def post(self, request):
        user = request.user
        
        if user.role != User.LISTER:
            return Response(
                {'detail': 'Only listers can submit KYC'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if user.kyc_status not in [User.KYC_NOT_SUBMITTED, User.KYC_REJECTED]:
            return Response(
                {'detail': f'Cannot submit KYC. Current status: {user.kyc_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        aadhar_number = request.data.get('aadhar_number', '').strip()
        aadhar_front = request.FILES.get('aadhar_front')
        aadhar_back = request.FILES.get('aadhar_back')
        
        if not aadhar_number:
            return Response(
                {'detail': 'Aadhar number is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(aadhar_number) != 12 or not aadhar_number.isdigit():
            return Response(
                {'detail': 'Aadhar number must be exactly 12 digits.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not aadhar_front or not aadhar_back:
            return Response(
                {'detail': 'Both front and back images of Aadhar card are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        allowed_extensions = ['jpg', 'jpeg', 'png']
        for file_obj, file_name in [(aadhar_front, 'Front image'), (aadhar_back, 'Back image')]:
            if file_obj:
                ext = file_obj.name.split('.')[-1].lower()
                if ext not in allowed_extensions:
                    return Response(
                        {'detail': f'{file_name} must be JPG, JPEG, or PNG.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if file_obj.size > 10 * 1024 * 1024:
                    return Response(
                        {'detail': f'{file_name} size must not exceed 10MB.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        if User.objects.filter(aadhar_number=aadhar_number).exclude(id=user.id).exists():
            return Response(
                {'detail': 'This Aadhar number is already registered with another account.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            logger.info(f"Uploading KYC documents for user {user.email}")
            
            front_upload = cloudinary.uploader.upload(
                aadhar_front,
                folder=f'kyc/aadhar/front',
                resource_type='image',
                public_id=f'user_{user.id}_front_{timezone.now().timestamp()}',
                overwrite=True,
                invalidate=True,
                transformation=[
                    {'width': 1200, 'height': 1200, 'crop': 'limit'},
                    {'quality': 'auto:good'}
                ]
            )
            
            back_upload = cloudinary.uploader.upload(
                aadhar_back,
                folder=f'kyc/aadhar/back',
                resource_type='image',
                public_id=f'user_{user.id}_back_{timezone.now().timestamp()}',
                overwrite=True,
                invalidate=True,
                transformation=[
                    {'width': 1200, 'height': 1200, 'crop': 'limit'},
                    {'quality': 'auto:good'}
                ]
            )
            
            logger.info(f"Cloudinary upload successful for user {user.email}")
            logger.info(f"Front image URL: {front_upload.get('secure_url')}")
            logger.info(f"Back image URL: {back_upload.get('secure_url')}")
            
            if user.aadhar_front_image:
                try:
                    old_front_public_id = user.aadhar_front_image.public_id
                    cloudinary.uploader.destroy(old_front_public_id)
                    logger.info(f"Deleted old front image: {old_front_public_id}")
                except Exception as e:
                    logger.warning(f"Could not delete old front image: {e}")
            
            if user.aadhar_back_image:
                try:
                    old_back_public_id = user.aadhar_back_image.public_id
                    cloudinary.uploader.destroy(old_back_public_id)
                    logger.info(f"Deleted old back image: {old_back_public_id}")
                except Exception as e:
                    logger.warning(f"Could not delete old back image: {e}")
            
            user.aadhar_number = aadhar_number
            user.aadhar_front_image = front_upload['public_id']
            user.aadhar_back_image = back_upload['public_id']
            user.is_kyc_submitted = True
            user.kyc_submitted_at = timezone.now()
            user.kyc_status = User.KYC_PENDING
            user.kyc_rejection_reason = None
            user.save()
            
            logger.info(f"KYC submitted successfully for user {user.email}")
            
            return Response(
                {
                    'detail': 'KYC submitted successfully. Admin will review your documents.',
                    'kyc_status': user.kyc_status,
                    'aadhar_front_url': front_upload['secure_url'],
                    'aadhar_back_url': back_upload['secure_url'],
                },
                status=status.HTTP_200_OK
            )
            
        except CloudinaryError as e:
            logger.error(f"Cloudinary upload error for user {user.email}: {str(e)}")
            return Response(
                {'detail': f'Image upload failed: {str(e)}. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        except Exception as e:
            logger.error(f"KYC submission error for user {user.email}: {str(e)}")
            return Response(
                {'detail': f'KYC submission failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class KYCApprovalView(APIView):
    """Admin manually verifies Aadhaar and approves/rejects"""
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @extend_schema(
        responses={
            200: OpenApiResponse(description='KYC details for admin review'),
            404: OpenApiResponse(description='Lister not found'),
        }
    )

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
    
    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['approve', 'reject'], 'description': 'Approve or reject KYC'},
                    'reason': {'type': 'string', 'description': 'Required if action is reject'},
                },
                'required': ['action']
            }
        },
        responses={
            200: OpenApiResponse(description='KYC approved or rejected'),
            400: OpenApiResponse(description='Invalid action or missing rejection reason'),
            404: OpenApiResponse(description='Lister not found'),
        }
    )

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
            
            logger.info(f"Admin approved KYC for user {user.email}")
            
        elif action == 'reject':
            if not rejection_reason:
                return Response(
                    {'detail': 'Rejection reason is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user.kyc_status = User.KYC_REJECTED
            user.kyc_rejection_reason = rejection_reason
            message = f'KYC rejected for {user.email}. Reason: {rejection_reason}'
            
            logger.info(f"Admin rejected KYC for user {user.email}: {rejection_reason}")
            
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
    
    @extend_schema(
        responses={
            200: OpenApiResponse(description='List of pending KYC submissions'),
        }
    )


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
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='status',
                type=str,
                description='Filter by KYC status (e.g. pending, approved, rejected)',
                required=False,
            )
        ],
        responses={
            200: OpenApiResponse(description='List of all listers with KYC status'),
        }
    )
    
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