import requests
from urllib.parse import unquote
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed


def exchange_code_for_token(code):
    """
    Exchange authorization code for access token
    """
    # Decode URL-encoded code
    code = unquote(code)
    
    token_url = 'https://oauth2.googleapis.com/token'
    
    data = {
        'code': code,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': 'postmessage',
        'grant_type': 'authorization_code',
    }
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise AuthenticationFailed(f'Failed to exchange code for token: {str(e)}')


def verify_google_token(id_token_str):
    """
    Verify Google ID token and extract user info
    """
    try:
        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )
        
        # Token is valid, extract user info
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise AuthenticationFailed('Invalid token issuer')
        
        return {
            'email': idinfo.get('email'),
            'first_name': idinfo.get('given_name', ''),
            'last_name': idinfo.get('family_name', ''),
            'profile_picture': idinfo.get('picture'),
            'email_verified': idinfo.get('email_verified', False),
        }
    
    except ValueError as e:
        raise AuthenticationFailed(f'Invalid token: {str(e)}')


def get_or_create_user_from_google(google_user_data):
    """
    Get or create user from Google user data
    """
    from .models import User
    
    email = google_user_data.get('email')
    
    if not email:
        raise AuthenticationFailed('Email not provided by Google')
    
    # Check if user exists
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'first_name': google_user_data.get('first_name', ''),
            'last_name': google_user_data.get('last_name', ''),
            'is_email_verified': True,
            'role': User.USER,
        }
    )
    
    # If user already exists but signed up with email/password
    if not created and not user.is_email_verified:
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
    
    return user, created
