"""The API contract and the schema supplied to Gemini."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_REVIEW_LENGTH = 10_000

TrustSignal = Literal[
    "clinic_named", "surgeon_named", "procedure_named", "procedure_date_present",
    "price_present", "recovery_details_present", "complications_described",
    "before_after_mentioned", "firsthand_experience",
]


class NormalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review: str = Field(min_length=1, max_length=MAX_REVIEW_LENGTH, strict=True)

    @field_validator("review")
    @classmethod
    def review_is_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Paste a review before normalizing.")
        return value


class ReviewExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_language: Literal["Korean", "English", "Mixed", "Other"]
    translated_review: str = Field(min_length=1, description="Natural English translation; preserve meaning and all uncertainty.")
    clinic_raw: str | None = Field(default=None, description="Exact clinic name as written in the source, in the original script; null if absent.")
    procedure_raw: str | None = Field(default=None, description="Exact procedure phrase as written in the source; null if absent.")
    procedure_normalized: str | None = Field(default=None, description="English procedure term supported by the source; null if absent.")
    surgeon: str | None = None
    price: str | None = Field(default=None, description="Stated amount and currency; never guess currency or convert prices.")
    procedure_date: str | None = Field(default=None, description="Only the stated date. Preserve relative dates; never infer a year.")
    positive_outcomes: list[str] = Field(default_factory=list)
    negative_outcomes: list[str] = Field(default_factory=list)
    trust_signals: list[TrustSignal] = Field(default_factory=list)

    @field_validator("translated_review")
    @classmethod
    def translation_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("The translation must not be blank.")
        return value.strip()

    @field_validator("clinic_raw", "procedure_raw", "procedure_normalized", "surgeon", "price", "procedure_date")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ClinicNormalization(BaseModel):
    clinic_raw: str | None
    clinic_canonical: str | None
    matched_alias: str | None
    confidence: float = Field(ge=0, le=1)
    status: Literal["matched", "unresolved", "not_mentioned"]
    match_method: Literal["exact", "fuzzy"] | None = None


class NormalizeResponse(BaseModel):
    extraction: ReviewExtraction
    normalization: ClinicNormalization
