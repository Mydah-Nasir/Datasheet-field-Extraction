"""LangGraph typed state for the extraction workflow."""

from typing import TypedDict

from src.document.models import IngestedDocument
from src.domain.schema import ExtractionResult
from src.domain.validation import ValidationResult


class ExtractionState(TypedDict, total=False):
    """The shared state passed between all nodes in the workflow."""

    workflow_id: str
    document_path: str

    # After Ingestion
    document: IngestedDocument | None

    # After Extraction
    extraction: ExtractionResult | None

    # After Normalization
    normalized_extraction: ExtractionResult | None

    # After Validation
    validation_result: ValidationResult | None

    # After Human Review (Interrupt Response)
    # Expected format: list[dict] e.g. [{"field": "pwht", "value": "YES"}]
    human_review_decision: list[dict] | None

    # After Finalization
    final_annex: dict | None

    # Unrecoverable error state
    error: str | None
