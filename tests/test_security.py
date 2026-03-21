import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from security import get_password_hash, verify_password


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "secure-test-password-123"  # pragma: allowlist secret
        hashed = get_password_hash(password)
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = get_password_hash("correct-password")
        assert not verify_password("wrong-password", hashed)

    def test_different_hashes_for_same_password(self):
        pw = "same-password"
        h1 = get_password_hash(pw)
        h2 = get_password_hash(pw)
        assert h1 != h2


class TestEncryption:
    def test_seal_unseal_roundtrip(self, monkeypatch):
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()

        import security

        monkeypatch.setattr(security, "MASTER_KEY", test_key)
        monkeypatch.setattr(security, "master_fernet", None)

        user_key = security._generate_user_key()
        sealed = security._seal_user_key(user_key)
        unsealed = security._unseal_user_key(sealed)
        assert unsealed == user_key
        assert sealed != user_key

    def test_different_master_keys_fail(self, monkeypatch):
        from cryptography.fernet import Fernet

        import security

        key1 = Fernet.generate_key().decode()
        monkeypatch.setattr(security, "MASTER_KEY", key1)
        monkeypatch.setattr(security, "master_fernet", None)

        user_key = security._generate_user_key()
        sealed = security._seal_user_key(user_key)

        key2 = Fernet.generate_key().decode()
        monkeypatch.setattr(security, "MASTER_KEY", key2)
        monkeypatch.setattr(security, "master_fernet", None)

        with pytest.raises(Exception):
            security._unseal_user_key(sealed)


class TestValidation:
    def test_valid_username(self):
        from security import validate_username

        assert validate_username("admin@test.com")
        assert validate_username("user_name")
        assert validate_username("test.user-name")

    def test_invalid_username(self):
        from security import validate_username

        assert not validate_username("")
        assert not validate_username("ab")
        assert not validate_username("a" * 81)

    def test_valid_password(self):
        from security import validate_password

        valid, _ = validate_password("Str0ng!Pass_wd")
        assert valid

    def test_short_password(self):
        from security import validate_password

        valid, _ = validate_password("Short1!")
        assert not valid

    def test_password_missing_requirements(self):
        from security import validate_password

        valid, _ = validate_password("alllowercaselong!")
        assert not valid

        valid, _ = validate_password("ALLUPPERCASELONG!")
        assert not valid

        valid, _ = validate_password("NoDigitsHere!Long")
        assert not valid

        valid, _ = validate_password("NoSpecialChar1Long")
        assert not valid
