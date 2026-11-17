"""Unit tests: passwords, tokens, MFA helpers and the RBAC matrix."""

from __future__ import annotations

import pyotp
import pytest
from pydantic import SecretStr

from azinco_api.auth import mfa
from azinco_api.auth.passwords import (
    PasswordPolicyError,
    hash_password,
    validate_password,
    verify_password,
)
from azinco_api.auth.rbac import (
    PLATFORM_ROLE_PERMISSIONS,
    STEP_UP_PERMISSIONS,
    TENANT_ROLE_PERMISSIONS,
    Permission,
    mfa_required,
    tenant_permissions,
)
from azinco_api.auth.tokens import hash_token, new_token
from azinco_api.db.models import PlatformRole, TenantRole
from tests.conftest import TEST_FERNET_KEY

KEY = SecretStr(TEST_FERNET_KEY)


# ------------------------------------------------------------------ passwords
def test_hash_is_argon2id_and_verifies() -> None:
    h = hash_password("correct horse battery staple")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "correct horse battery staple")
    assert not verify_password(h, "wrong password entirely")


def test_verify_unknown_user_is_false_but_still_works() -> None:
    assert verify_password(None, "anything at all here") is False


@pytest.mark.parametrize(
    ("password", "email"),
    [
        ("short", "a@x.test"),
        ("x" * 129, "a@x.test"),
        ("a@x.test", "A@X.test"),
        ("aaaaaaaaaaaaaaaa", "a@x.test"),
    ],
)
def test_password_policy_rejects(password: str, email: str) -> None:
    with pytest.raises(PasswordPolicyError):
        validate_password(password, email)


def test_password_policy_accepts_reasonable_password() -> None:
    validate_password("Tea-in-Karachi-2026!", "owner@example.com")


# ------------------------------------------------------------------ tokens
def test_tokens_are_random_and_hash_is_sha256() -> None:
    a, b = new_token(), new_token()
    assert a != b and len(a) >= 40
    assert len(hash_token(a)) == 32
    assert hash_token(a) == hash_token(a)


# ------------------------------------------------------------------ MFA
def test_secret_encryption_round_trip_and_not_plaintext() -> None:
    secret = mfa.new_secret()
    enc = mfa.encrypt_secret(KEY, secret)
    assert secret not in enc
    assert mfa.decrypt_secret(KEY, enc) == secret


def test_missing_key_is_reported() -> None:
    with pytest.raises(mfa.MfaUnavailableError):
        mfa.encrypt_secret(None, "ABC")


def test_totp_verification() -> None:
    secret = mfa.new_secret()
    assert mfa.verify_code(secret, pyotp.TOTP(secret).now())
    assert not mfa.verify_code(secret, "000000") or pyotp.TOTP(secret).now() == "000000"
    assert not mfa.verify_code(secret, "12ab56")
    assert not mfa.verify_code(secret, "1234567")


def test_provisioning_uri_and_qr() -> None:
    secret = mfa.new_secret()
    uri = mfa.provisioning_uri(secret, "owner@example.com", "AZINCO")
    assert uri.startswith("otpauth://totp/AZINCO:owner%40example.com?")
    assert mfa.qr_svg(uri).lstrip().startswith("<svg")


# ------------------------------------------------------------------ RBAC
def test_every_role_has_a_permission_set() -> None:
    assert set(TENANT_ROLE_PERMISSIONS) == set(TenantRole)
    assert set(PLATFORM_ROLE_PERMISSIONS) == set(PlatformRole)


def test_only_reviewer_roles_can_approve_statements_and_tax() -> None:
    approvers = {r for r, p in TENANT_ROLE_PERMISSIONS.items() if Permission.STATEMENT_APPROVE in p}
    assert approvers == {TenantRole.REVIEWER, TenantRole.SECOND_REVIEWER}
    tax = {r for r, p in TENANT_ROLE_PERMISSIONS.items() if Permission.TAX_APPROVE in p}
    assert tax == {TenantRole.REVIEWER, TenantRole.SECOND_REVIEWER}


def test_clients_cannot_approve_or_draft_journals() -> None:
    perms = tenant_permissions([TenantRole.CLIENT_OWNER, TenantRole.CLIENT_STAFF])
    assert Permission.STATEMENT_APPROVE not in perms
    assert Permission.JOURNAL_DRAFT not in perms
    assert Permission.REVIEW_ITEM_DECIDE not in perms


def test_only_owner_pays_and_signs() -> None:
    payers = {r for r, p in TENANT_ROLE_PERMISSIONS.items() if Permission.PAYMENT_MAKE in p}
    assert payers == {TenantRole.CLIENT_OWNER}
    signers = {r for r, p in TENANT_ROLE_PERMISSIONS.items() if Permission.ENGAGEMENT_SIGN in p}
    assert signers == {TenantRole.CLIENT_OWNER}


def test_auditor_is_read_only() -> None:
    perms = TENANT_ROLE_PERMISSIONS[TenantRole.AUDITOR]
    writes = {p for p in perms if not p.value.endswith((":read", ":download"))}
    assert writes == set()


def test_sign_offs_need_step_up_mfa() -> None:
    assert {Permission.STATEMENT_APPROVE, Permission.TAX_APPROVE, Permission.PERIOD_LOCK} <= set(
        STEP_UP_PERMISSIONS
    )


def test_mfa_required_for_staff_reviewers_and_platform_roles() -> None:
    assert mfa_required(True, [], [])
    assert mfa_required(False, [TenantRole.REVIEWER], [])
    assert mfa_required(False, [], [PlatformRole.AI_ENGINEER])
    assert not mfa_required(False, [TenantRole.CLIENT_OWNER, TenantRole.CLIENT_STAFF], [])
