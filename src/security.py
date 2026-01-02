import os
from base64 import b64decode, b64encode
from typing import cast

from cryptography.fernet import Fernet
from dotenv import load_dotenv
from passlib.context import CryptContext

from logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    try:
        return bool(pwd_context.verify(plain_password, hashed_password))
    except Exception as e:
        logger.error("password_verification_error", error=str(e))
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
    from database import get_independent_session
    from models import User

    with get_independent_session() as db:
        user = db.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        if user.encryption_key_sealed:
            return _unseal_user_key(cast(str, user.encryption_key_sealed))
        else:
            user_key = _generate_user_key()
            user.encryption_key_sealed = _seal_user_key(user_key)  # type: ignore[assignment]
            logger.info("encryption_key_generated", user_id=user_id)
            return user_key


def encrypt_data_for_user(data: str, user_id: int) -> str:
    """Encrypt sensitive data for a specific user."""
    if not data:
        return ""
    try:
        user_key = get_or_create_user_key(user_id)
        user_cipher = Fernet(user_key.encode())
        return str(user_cipher.encrypt(data.encode()).decode())
    except Exception as e:
        logger.error("encryption_error", user_id=user_id, error=str(e))
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
        logger.error("decryption_error", user_id=user_id, error=str(e))
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
    """
    Validate password strength.

    Requirements:
    - Minimum 12 characters (NIST SP 800-63B recommendation)
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
    """
    if not password:
        return False, "Password is required"

    if len(password) < 12:
        return False, "Password must be at least 12 characters long"

    if len(password) > 128:
        return False, "Password must be less than 128 characters"

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    special_chars = set("!@#$%^&*()_+-=[]{}|;:,.<>?")
    has_special = any(c in special_chars for c in password)

    missing_requirements = []
    if not has_upper:
        missing_requirements.append("uppercase letter")
    if not has_lower:
        missing_requirements.append("lowercase letter")
    if not has_digit:
        missing_requirements.append("digit")
    if not has_special:
        missing_requirements.append("special character (!@#$%^&*...)")

    if missing_requirements:
        return (
            False,
            f"Password must contain at least one {', one '.join(missing_requirements)}",
        )

    return True, "Password is valid"
