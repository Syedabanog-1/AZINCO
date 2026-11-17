"""Password hashing with Argon2id (OWASP recommended) and a minimal password policy."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LENGTH = 12
MAX_LENGTH = 128

_hasher = PasswordHasher()  # argon2-cffi defaults: Argon2id, RFC 9106 low-memory profile
# Used when the e-mail is unknown so response time does not reveal whether an account exists.
_DUMMY_HASH = _hasher.hash("azinco-dummy-password-for-timing-only")


class PasswordPolicyError(ValueError):
    pass


def validate_password(password: str, email: str) -> None:
    if len(password) < MIN_LENGTH:
        raise PasswordPolicyError(f"Password must be at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        raise PasswordPolicyError(f"Password must be at most {MAX_LENGTH} characters.")
    if password.strip().lower() == email.strip().lower():
        raise PasswordPolicyError("Password must not be your e-mail address.")
    if len(set(password)) < 5:
        raise PasswordPolicyError("Password is too repetitive.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-work check: always runs one Argon2 verification."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
