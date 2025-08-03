"""
Security utilities for Life-as-Code application.
Handles password hashing and credential encryption.
"""

import logging
import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv
from passlib.context import CryptContext

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    try:
        return bool(pwd_context.verify(plain_password, hashed_password))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return str(pwd_context.hash(password))


# --- Credential Encryption ---
FERNET_KEY = os.getenv("FERNET_KEY")
fernet = None  # Initialize lazily


def _get_fernet():
    """Get or initialize Fernet cipher."""
    global fernet
    if fernet is None:
        if not FERNET_KEY:
            raise ValueError(
                "FERNET_KEY not found in environment variables. "
                'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        try:
            fernet = Fernet(FERNET_KEY.encode())
        except Exception as e:
            raise ValueError(f"Invalid FERNET_KEY format: {e}") from e
    return fernet


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data for database storage."""
    if not data:
        return ""
    try:
        cipher = _get_fernet()
        return str(cipher.encrypt(data.encode()).decode())
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        raise


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data from database."""
    if not encrypted_data:
        return ""
    try:
        cipher = _get_fernet()
        return str(cipher.decrypt(encrypted_data.encode()).decode())
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        raise


def validate_username(username: str) -> bool:
    """Validate username format."""
    if not username or len(username) < 3 or len(username) > 80:
        return False
    # Allow alphanumeric, underscore, dot, and @ for email usernames
    allowed_chars = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.@-"
    )
    return all(c in allowed_chars for c in username)


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength."""
    if not password:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if len(password) > 128:
        return False, "Password must be less than 128 characters"

    # Check for at least one number and one letter
    has_number = any(c.isdigit() for c in password)
    has_letter = any(c.isalpha() for c in password)

    if not (has_number and has_letter):
        return False, "Password must contain at least one letter and one number"

    return True, "Password is valid"


if __name__ == "__main__":
    # Test the security functions
    print("🔐 Testing Security Functions")
    print("=" * 30)

    # Test password hashing
    test_password = "test123"
    hashed = get_password_hash(test_password)
    print(f"Password hash: {hashed[:50]}...")
    print(f"Verification: {verify_password(test_password, hashed)}")

    # Test data encryption
    test_data = "my-secret-api-key"
    encrypted = encrypt_data(test_data)
    decrypted = decrypt_data(encrypted)
    print(f"Original: {test_data}")
    print(f"Encrypted: {encrypted[:50]}...")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {test_data == decrypted}")

    # Test validation
    print(f"Username 'user123': {validate_username('user123')}")
    print(f"Password 'weak': {validate_password('weak')}")
    print(f"Password 'strong123': {validate_password('strong123')}")
