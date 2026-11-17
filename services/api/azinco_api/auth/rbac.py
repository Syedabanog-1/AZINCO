"""Role-based access control (Blueprint Part 1 §1.4, BS §3.1, §8.7, §12).

Permissions are checked in two layers:
1. here, in the API (role -> permission), before any database work;
2. in PostgreSQL via Row-Level Security (tenant isolation), as the last line of defence.

Hard rules encoded below (never granted to any role here):
* nobody edits a posted journal entry (corrections are reversals);
* agents have no human permissions at all (they get narrow tool scopes, not roles);
* approvals of statements / tax outputs are only for reviewer roles (and MFA-verified sessions).
"""

from __future__ import annotations

import enum
from collections.abc import Iterable

from azinco_api.db.models import PlatformRole, TenantRole


class Permission(enum.StrEnum):
    # tenant / organisation
    TENANT_READ = "tenant:read"
    TENANT_MANAGE = "tenant:manage"
    MEMBERS_INVITE = "members:invite"
    # tasks & documents
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_READ = "document:read"
    # billing
    INVOICE_READ = "invoice:read"
    PAYMENT_MAKE = "payment:make"
    ENGAGEMENT_SIGN = "engagement:sign"
    DELIVERABLE_DOWNLOAD = "deliverable:download"
    # accounting & review
    JOURNAL_READ = "journal:read"
    JOURNAL_DRAFT = "journal:draft"
    JOURNAL_REVERSE = "journal:reverse"
    REVIEW_ITEM_DECIDE = "review:decide"
    STATEMENT_APPROVE = "statement:approve"
    TAX_APPROVE = "tax:approve"
    PERIOD_LOCK = "period:lock"
    SECOND_REVIEW_APPROVE = "review:second_approve"
    PARTNER_COSIGN = "review:partner_cosign"
    # audit
    AUDIT_READ = "audit:read"
    # platform (not tenant-scoped)
    PLATFORM_PORTFOLIO_READ = "platform:portfolio_read"
    PLATFORM_PRICING_MANAGE = "platform:pricing_manage"
    PLATFORM_PAYMENT_PROVIDERS_MANAGE = "platform:payment_providers_manage"
    PLATFORM_RULE_PACKS_MANAGE = "platform:rule_packs_manage"
    PLATFORM_MODEL_REGISTRY_PROPOSE = "platform:model_registry_propose"
    PLATFORM_KILL_SWITCH = "platform:kill_switch"
    PLATFORM_AUDIT_READ = "platform:audit_read"


P = Permission

TENANT_ROLE_PERMISSIONS: dict[TenantRole, frozenset[Permission]] = {
    TenantRole.CLIENT_OWNER: frozenset(
        {
            P.TENANT_READ,
            P.TENANT_MANAGE,
            P.MEMBERS_INVITE,
            P.TASK_CREATE,
            P.TASK_READ,
            P.DOCUMENT_UPLOAD,
            P.DOCUMENT_READ,
            P.INVOICE_READ,
            P.PAYMENT_MAKE,
            P.ENGAGEMENT_SIGN,
            P.DELIVERABLE_DOWNLOAD,
            P.JOURNAL_READ,
        }
    ),
    TenantRole.CLIENT_STAFF: frozenset(
        {
            P.TENANT_READ,
            P.TASK_READ,
            P.DOCUMENT_UPLOAD,
            P.DOCUMENT_READ,
        }
    ),
    TenantRole.SUPPORT_OPS: frozenset(
        {
            P.TENANT_READ,
            P.TASK_CREATE,
            P.TASK_READ,
            P.DOCUMENT_UPLOAD,
            P.DOCUMENT_READ,
            P.INVOICE_READ,
        }
    ),
    TenantRole.REVIEWER: frozenset(
        {
            P.TENANT_READ,
            P.TASK_READ,
            P.DOCUMENT_READ,
            P.DOCUMENT_UPLOAD,
            P.JOURNAL_READ,
            P.JOURNAL_DRAFT,
            P.JOURNAL_REVERSE,
            P.REVIEW_ITEM_DECIDE,
            P.STATEMENT_APPROVE,
            P.TAX_APPROVE,
            P.PERIOD_LOCK,
            P.DELIVERABLE_DOWNLOAD,
            P.AUDIT_READ,
        }
    ),
    TenantRole.SECOND_REVIEWER: frozenset(
        {
            P.TENANT_READ,
            P.TASK_READ,
            P.DOCUMENT_READ,
            P.JOURNAL_READ,
            P.SECOND_REVIEW_APPROVE,
            P.STATEMENT_APPROVE,
            P.TAX_APPROVE,
            P.DELIVERABLE_DOWNLOAD,
            P.AUDIT_READ,
        }
    ),
    TenantRole.LOCAL_PARTNER: frozenset(
        {
            P.TENANT_READ,
            P.TASK_READ,
            P.DOCUMENT_READ,
            P.JOURNAL_READ,
            P.PARTNER_COSIGN,
            P.DELIVERABLE_DOWNLOAD,
            P.AUDIT_READ,
        }
    ),
    TenantRole.AUDITOR: frozenset(
        {
            P.TENANT_READ,
            P.JOURNAL_READ,
            P.DELIVERABLE_DOWNLOAD,
            P.AUDIT_READ,
        }
    ),
}

PLATFORM_ROLE_PERMISSIONS: dict[PlatformRole, frozenset[Permission]] = {
    PlatformRole.PLATFORM_ADMIN: frozenset(
        {
            P.PLATFORM_PORTFOLIO_READ,
            P.PLATFORM_PRICING_MANAGE,
            P.PLATFORM_PAYMENT_PROVIDERS_MANAGE,
            P.PLATFORM_RULE_PACKS_MANAGE,
            P.PLATFORM_KILL_SWITCH,
            P.PLATFORM_AUDIT_READ,
        }
    ),
    PlatformRole.AI_ENGINEER: frozenset({P.PLATFORM_MODEL_REGISTRY_PROPOSE}),
    PlatformRole.COMPLIANCE_OFFICER: frozenset({P.PLATFORM_AUDIT_READ}),
}

# Roles whose holders must use MFA (BS §12: "MFA for staff and Reviewers").
MFA_REQUIRED_TENANT_ROLES = frozenset(
    {
        TenantRole.SUPPORT_OPS,
        TenantRole.REVIEWER,
        TenantRole.SECOND_REVIEWER,
        TenantRole.LOCAL_PARTNER,
    }
)

# Permissions that additionally require an MFA-verified session (sensitive sign-offs).
STEP_UP_PERMISSIONS = frozenset(
    {
        P.STATEMENT_APPROVE,
        P.TAX_APPROVE,
        P.PERIOD_LOCK,
        P.SECOND_REVIEW_APPROVE,
        P.PARTNER_COSIGN,
        P.JOURNAL_REVERSE,
        P.PLATFORM_PAYMENT_PROVIDERS_MANAGE,
        P.PLATFORM_KILL_SWITCH,
    }
)


def tenant_permissions(roles: Iterable[TenantRole]) -> frozenset[Permission]:
    result: set[Permission] = set()
    for role in roles:
        result |= TENANT_ROLE_PERMISSIONS[role]
    return frozenset(result)


def platform_permissions(roles: Iterable[PlatformRole]) -> frozenset[Permission]:
    result: set[Permission] = set()
    for role in roles:
        result |= PLATFORM_ROLE_PERMISSIONS[role]
    return frozenset(result)


def mfa_required(
    user_is_staff: bool, tenant_roles: Iterable[TenantRole], platform_roles: Iterable[PlatformRole]
) -> bool:
    return (
        user_is_staff
        or any(True for _ in platform_roles)
        or any(r in MFA_REQUIRED_TENANT_ROLES for r in tenant_roles)
    )
