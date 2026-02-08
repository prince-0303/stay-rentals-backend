from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from ..serializers import GoogleLoginSerializer, UserSerializer, get_tokens_for_user
from ..google_oauth import exchange_code_for_token, verify_google_token, get_or_create_user_from_google


class GoogleLoginView(APIView):
    """Google OAuth Login"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data['code']
        
        try:
            token_data = exchange_code_for_token(code)
            id_token_str = token_data.get('id_token')
            
            if not id_token_str:
                return Response(
                    {'error': 'No ID token from Google'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            google_user_data = verify_google_token(id_token_str)
            user, created = get_or_create_user_from_google(google_user_data)
            
            tokens = get_tokens_for_user(user)
            
            return Response({
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'user': UserSerializer(user).data,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class GoogleLoginTokenView(APIView):
    """Alternative Google endpoint"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        return GoogleLoginView.as_view()(request)