"""Domain layer — canonical schema, statuses, and validation rules."""

from src.domain.schema import (
    Evidence,
    ExtractionField,
    ExtractionResult,
    FieldStatus,
    PaintingField,
)
from src.domain.validation import (
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    ValidationStatus,
)

__all__ = [
    "Evidence",
    "ExtractionField",
    "ExtractionResult",
    "FieldStatus",
    "PaintingField",
    "ValidationStatus",
    "ValidationSeverity",
    "ValidationIssue",
    "ValidationResult",
]
