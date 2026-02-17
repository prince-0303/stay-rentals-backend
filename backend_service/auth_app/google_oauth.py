import requests
import logging
from urllib.parse import unquote
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


def exchange_code_for_token(code):
    """
    Exchange authorization code for access token
    """
    # Validate input
    if not code or not isinstance(code, str):
        logger.warning("Invalid authorization code received")
        raise AuthenticationFailed('Invalid authorization code')
    
    # Decode URL-encoded code
    code = unquote(code)
    
    token_url = 'https://oauth2.googleapis.com/token'
    data = {
        'code': code,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code',
    }
    
    try:
        response = requests.post(token_url, data=data, timeout=10)
        response.raise_for_status()
        token_data = response.json()
        
        # Validate response contains id_token
        if 'id_token' not in token_data:
            logger.error("No id_token in Google response")
            raise AuthenticationFailed('Invalid response from Google')
        
        return token_data
        
    except requests.exceptions.Timeout:
        logger.error("Timeout connecting to Google OAuth")
        raise AuthenticationFailed('Google authentication timeout. Please try again.')
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Google OAuth token exchange failed: {str(e)}")
        raise AuthenticationFailed(f'Failed to exchange code for token: {str(e)}')


def verify_google_token(id_token_str):
    """
    Verify Google ID token and extract user info
    """
    if not id_token_str or not isinstance(id_token_str, str):
        raise AuthenticationFailed('Invalid ID token')
    
    try:
        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )
        
        # Token is valid, validate issuer
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            logger.warning(f"Invalid token issuer: {idinfo['iss']}")
            raise AuthenticationFailed('Invalid token issuer')
        
        # Extract user info
        email = idinfo.get('email')
        if not email:
            raise AuthenticationFailed('Email not provided by Google')
        
        return {
            'email': email,
            'first_name': idinfo.get('given_name', ''),
            'last_name': idinfo.get('family_name', ''),
            'profile_picture': idinfo.get('picture'),
            'email_verified': idinfo.get('email_verified', False),
        }
        
    except ValueError as e:
        logger.error(f"Google token verification failed: {str(e)}")
        raise AuthenticationFailed(f'Invalid token: {str(e)}')
    
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {str(e)}")
        raise AuthenticationFailed('Token verification failed')


def get_or_create_user_from_google(google_user_data):
    """
    Get or create user from Google user data
    """
    from django.db import transaction
    from .models import User
    
    email = google_user_data.get('email')
    if not email:
        raise AuthenticationFailed('Email not provided by Google')
    
    try:
        with transaction.atomic():
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
            
            logger.info(f"Google OAuth: User {'created' if created else 'logged in'}: {email}")
            
            return user, created
    
    except Exception as e:
        logger.error(f"Error creating/retrieving user from Google data: {str(e)}")
        raise AuthenticationFailed('Failed to create user account')