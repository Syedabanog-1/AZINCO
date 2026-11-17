"""TOTP multi-factor authentication.

Secrets are encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256).
"""

from __future__ import annotations

import io

import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class MfaUnavailableError(RuntimeError):
    """AZINCO_MFA_ENCRYPTION_KEY is not configured."""


def _fernet(key: SecretStr | None) -> Fernet:
    if key is None:
        raise MfaUnavailableError
    return Fernet(key.get_secret_value().encode("ascii"))


def new_secret() -> str:
    return pyotp.random_base32()


def encrypt_secret(key: SecretStr | None, secret: str) -> str:
    return _fernet(key).encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(key: SecretStr | None, token: str) -> str:
    try:
        return _fernet(key).decrypt(token.encode("ascii")).decode("ascii")
    except InvalidToken as exc:
        raise MfaUnavailableError("MFA secret cannot be decrypted with the configured key") from exc


def verify_code(secret: str, code: str) -> bool:
    code = code.strip().replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def provisioning_uri(secret: str, email: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def qr_svg(uri: str) -> str:
    buffer = io.BytesIO()
    segno.make(uri, error="m").save(buffer, kind="svg", scale=5, border=2, xmldecl=False)
    return buffer.getvalue().decode("utf-8")
