from cryptography.fernet import Fernet
from django.conf import settings

_fernet = None

def get_fernet():
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.MESSAGE_ENCRYPTION_KEY.encode())
    return _fernet

def encrypt_message(text: str) -> str:
    return get_fernet().encrypt(text.encode()).decode()

def decrypt_message(token: str) -> str:
    try:
        return get_fernet().decrypt(token.encode()).decode()
    except Exception:
        return token  # fallback for any unencrypted legacy messages