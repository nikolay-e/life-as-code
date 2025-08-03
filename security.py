"""
Security utilities for Life-as-Code application.
Handles password hashing and credential encryption.
"""

import logging
import os
from base64 import b64decode, b64encode
from typing import cast

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


# --- Per-User Credential Encryption ---
MASTER_KEY = os.getenv("FERNET_KEY")  # Renamed for clarity
master_fernet = None  # Initialize lazily


def _get_master_fernet():
    """Get or initialize master Fernet cipher for sealing user keys."""
    global master_fernet
    if master_fernet is None:
        if not MASTER_KEY:
            raise ValueError(
                "FERNET_KEY (master key) not found in environment variables. "
                'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        try:
            master_fernet = Fernet(MASTER_KEY.encode())
        except Exception as e:
            raise ValueError(f"Invalid FERNET_KEY format: {e}") from e
    return master_fernet


def _generate_user_key() -> str:
    """Generate a new encryption key for a user."""
    return str(Fernet.generate_key().decode())


def _seal_user_key(user_key: str) -> str:
    """Seal a user's encryption key with the master key."""
    master_cipher = _get_master_fernet()
    return b64encode(master_cipher.encrypt(user_key.encode())).decode()


def _unseal_user_key(sealed_key: str) -> str:
    """Unseal a user's encryption key using the master key."""
    master_cipher = _get_master_fernet()
    return str(master_cipher.decrypt(b64decode(sealed_key.encode())).decode())


def get_or_create_user_key(user_id: int) -> str:
    """Get or create a per-user encryption key."""
    from database import SessionLocal
    from models import User

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        if user.encryption_key_sealed:
            # User already has a key, unseal it
            return _unseal_user_key(cast(str, user.encryption_key_sealed))
        else:
            # Generate new key for user
            user_key = _generate_user_key()
            user.encryption_key_sealed = _seal_user_key(user_key)  # type: ignore[assignment]
            db.commit()
            logger.info(f"Generated new encryption key for user {user_id}")
            return user_key
    finally:
        db.close()


def encrypt_data_for_user(data: str, user_id: int) -> str:
    """Encrypt sensitive data for a specific user."""
    if not data:
        return ""
    try:
        user_key = get_or_create_user_key(user_id)
        user_cipher = Fernet(user_key.encode())
        return str(user_cipher.encrypt(data.encode()).decode())
    except Exception as e:
        logger.error(f"Encryption error for user {user_id}: {e}")
        raise


def decrypt_data_for_user(encrypted_data: str, user_id: int) -> str:
    """Decrypt sensitive data for a specific user."""
    if not encrypted_data:
        return ""
    try:
        user_key = get_or_create_user_key(user_id)
        user_cipher = Fernet(user_key.encode())
        return str(user_cipher.decrypt(encrypted_data.encode()).decode())
    except Exception as e:
        logger.error(f"Decryption error for user {user_id}: {e}")
        raise


# Legacy functions for backward compatibility - these should be replaced
def encrypt_data(data: str) -> str:
    """DEPRECATED: Use encrypt_data_for_user instead."""
    logger.warning(
        "Using deprecated encrypt_data function without user_id - this is insecure!"
    )
    if not data:
        return ""
    try:
        cipher = _get_master_fernet()
        return str(cipher.encrypt(data.encode()).decode())
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        raise


def decrypt_data(encrypted_data: str) -> str:
    """DEPRECATED: Use decrypt_data_for_user instead."""
    logger.warning(
        "Using deprecated decrypt_data function without user_id - this is insecure!"
    )
    if not encrypted_data:
        return ""
    try:
        cipher = _get_master_fernet()
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
