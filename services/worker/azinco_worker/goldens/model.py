"""Golden-set schema (governance: docs/governance/golden-set-plan.md; BS §7.4, §8.8, §13).

A set is a manifest plus JSON-lines items. Expected outputs are what a qualified reviewer accepts
as correct. Every item carries the SHA-256 of its document so silent edits are detected.
Sets are synthetic unless counsel-approved anonymised data is authorised (GAP-AGT-02, GAP-LEG-03).
"""

from __future__ import annotations

import enum
import hashlib
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Code = Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z][0-9A-Za-z.\-]{0,19}$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SetStatus(enum.StrEnum):
    DRAFT = "draft"  # generated; labels not yet confirmed by a reviewer
    REVIEWED = "reviewed"  # labels confirmed by the Reviewer of Record
    PUBLISHED = "published"  # frozen; used at exit gates


class Difficulty(enum.StrEnum):
    CLEAN = "clean"
    NOISY = "noisy"
    ADVERSARIAL = "adversarial"


class Manifest(_Strict):
    set_id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9\-]{2,60}$")]
    version: Annotated[str, StringConstraints(pattern=r"^v\d{1,3}$")]
    status: SetStatus
    data_policy: Literal["synthetic", "anonymised_authorised"]
    description: Annotated[str, Field(min_length=10)]
    generator: str | None = None  # e.g. "azinco_worker.goldens.synth seed=20261118"
    created: date
    labelled_by: str
    reviewed_by: str | None = None  # name + licence of the reviewer who confirmed the labels
    reviewed_on: date | None = None
    chart_of_accounts: dict[Code, str]
    items_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def _review_recorded(self) -> Self:
        if self.status is not SetStatus.DRAFT and not (self.reviewed_by and self.reviewed_on):
            raise ValueError("a reviewed or published set must record reviewed_by and reviewed_on")
        return self


class ExpectedFields(_Strict):
    invoice_number: str | None = None
    invoice_date: date | None = None
    supplier: str | None = None
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None
    total: Annotated[str, StringConstraints(pattern=r"^\d+\.\d{2}$")] | None = None  # string money


class Expected(_Strict):
    account_code: Code
    fields: ExpectedFields
    flags: tuple[Literal["totals_mismatch", "duplicate", "prompt_injection"], ...] = ()


class Item(_Strict):
    item_id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9\-]{3,40}$")]
    doc_type: Literal["purchase_invoice", "utility_bill", "rent_invoice", "receipt"]
    language: Literal["en", "ur"]
    jurisdiction: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
    business_type: str
    difficulty: Difficulty
    document: Annotated[str, Field(min_length=20)]
    document_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    expected: Expected

    @model_validator(mode="after")
    def _hash_matches(self) -> Self:
        if sha256(self.document) != self.document_sha256:
            raise ValueError(f"{self.item_id}: document_sha256 does not match the document")
        return self


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
