"""Deterministic validation domain models."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.schema import ExtractionResult


class ValidationStatus(StrEnum):
    """The overall status of a document after validation."""

    VALID = "VALID"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    INVALID = "INVALID"


class ValidationSeverity(StrEnum):
    """The severity of a validation issue."""

    ERROR = "ERROR"
    WARNING = "WARNING"


class ValidationIssue(BaseModel):
    """A deterministic problem identified during validation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    field: str = Field(description="The name of the field with the issue")
    code: str = Field(description="A machine-readable error code")
    message: str = Field(description="A human-readable description of the issue")
    severity: ValidationSeverity = Field(
        default=ValidationSeverity.ERROR,
        description="Whether this issue prevents automatic processing",
    )


class ValidationResult(BaseModel):
    """The outcome of deterministic validation over normalized data."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: ValidationStatus = Field(description="Overall validation status")
    normalized_extraction: ExtractionResult = Field(
        description="The normalized extraction result used for validation"
    )
    issues: list[ValidationIssue] = Field(
        default_factory=list, description="List of identified issues"
    )

    @field_validator("normalized_extraction", mode="before")
    @classmethod
    def coerce_extraction_result(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return ExtractionResult.model_validate(v)
        if hasattr(v, "model_dump") and not isinstance(v, ExtractionResult):
            return ExtractionResult.model_validate(v.model_dump())
        return v
