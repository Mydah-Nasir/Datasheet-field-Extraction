"""Graph node functions for orchestrating extraction."""

import os

from langgraph.types import interrupt

from src.annexure.builder import build_annexure
from src.document.service import DocumentIngestionService
from src.domain.schema import ExtractionField, ExtractionResult, FieldStatus
from src.extraction.normalization import Normalizer
from src.extraction.service import GeminiExtractionService
from src.extraction.validation import Validator
from src.graph.state import ExtractionState


def ingest_document_node(state: ExtractionState) -> dict:
    """Ingest the uploaded PDF document."""
    if "document_path" not in state:
        return {"error": "document_path not provided."}

    doc_path = state["document_path"]
    filename = os.path.basename(doc_path)

    ingest_service = DocumentIngestionService()
    try:
        document = ingest_service.ingest_file(doc_path, filename)
        return {"document": document}
    except Exception as e:
        return {"error": f"Ingestion failed: {str(e)}"}


def extract_parameters_node(state: ExtractionState) -> dict:
    """Call Gemini to extract semantic fields."""
    if state.get("error"):
        return {}

    document = state["document"]
    extraction_service = GeminiExtractionService()

    try:
        result = extraction_service.extract(document)
        return {"extraction": result}
    except Exception as e:
        return {"error": f"Extraction failed: {str(e)}"}


def normalize_parameters_node(state: ExtractionState) -> dict:
    """Deterministically clean, parse, and normalize all extracted values."""
    if state.get("error"):
        return {}

    extraction = state["extraction"]
    if isinstance(extraction, dict):
        extraction = ExtractionResult.model_validate(extraction)
    elif hasattr(extraction, "model_dump") and not isinstance(extraction, ExtractionResult):
        extraction = ExtractionResult.model_validate(extraction.model_dump())

    normalizer = Normalizer()

    try:
        normalized = normalizer.normalize(extraction)
        return {"normalized_extraction": normalized}
    except Exception as e:
        return {"error": f"Normalization failed: {str(e)}"}


def _cast_field_value(field_name: str, new_val: any) -> any:
    """Cast user input value to the appropriate Python type expected by the schema."""
    import math

    if new_val is None:
        return None
    if isinstance(new_val, float) and math.isnan(new_val):
        return None

    val_str = str(new_val).strip()
    if val_str == "" or val_str.lower() in ("none", "null", "nan"):
        return None

    int_fields = {"qty"}
    float_fields = {
        "vessel_id_mm",
        "vessel_tl_tl_length_mm",
        "shell_min_thk_mm",
        "head_min_thk_mm",
        "weight_tons_each",
    }

    if field_name in int_fields:
        try:
            return int(float(val_str.replace(",", "")))
        except (ValueError, TypeError):
            return None

    if field_name in float_fields:
        try:
            return float(val_str.replace(",", ""))
        except (ValueError, TypeError):
            return None

    return val_str


def validate_parameters_node(state: ExtractionState) -> dict:
    """Run deterministic validation rules."""
    if state.get("error"):
        return {}

    normalized = state["normalized_extraction"]
    if isinstance(normalized, dict):
        normalized = ExtractionResult.model_validate(normalized)
    elif hasattr(normalized, "model_dump") and not isinstance(normalized, ExtractionResult):
        normalized = ExtractionResult.model_validate(normalized.model_dump())

    validator = Validator()

    try:
        val_result = validator.validate(normalized)
        return {"validation_result": val_result, "normalized_extraction": normalized}
    except Exception as e:
        return {"error": f"Validation failed: {str(e)}"}


def human_review_node(state: ExtractionState) -> dict:
    """
    Pause execution and wait for a human decision.
    Always presents ALL fields for review so the user can correct any value.
    """
    val_result = state["validation_result"]
    normalized = state["normalized_extraction"]
    if isinstance(normalized, dict):
        normalized = ExtractionResult.model_validate(normalized)
    elif hasattr(normalized, "model_dump") and not isinstance(normalized, ExtractionResult):
        normalized = ExtractionResult.model_validate(normalized.model_dump())

    # Build review payload for ALL fields (not just flagged ones)
    fields_for_review = []

    all_field_attrs = [
        "tag_no",
        "description",
        "ref_data_sheet",
        "design_code",
        "moc",
        "qty",
        "orientation",
        "vessel_id_mm",
        "vessel_tl_tl_length_mm",
        "shell_min_thk_mm",
        "head_min_thk_mm",
        "head_type",
        "nozzle_type",
        "impact_tested",
        "rt",
        "pwht",
        "support_type",
        "pickling_passivation",
        "weight_tons_each",
    ]

    for attr in all_field_attrs:
        field: ExtractionField = getattr(normalized, attr)
        issues = [i for i in val_result.issues if i.field == attr]

        needs_attention = (
            field.status
            in (
                FieldStatus.MISSING,
                FieldStatus.AMBIGUOUS,
                FieldStatus.CONFLICT,
                FieldStatus.INVALID,
            )
            or issues
            or field.confidence < 0.8
        )

        if needs_attention:
            fields_for_review.append(
                {
                    "field": attr,
                    "current_value": field.value,
                    "status": field.status.value,
                    "confidence": field.confidence,
                    "issues": [i.message for i in issues],
                }
            )

    # Add painting fields
    for p_attr in ["external", "internal"]:
        field: ExtractionField = getattr(normalized.painting, p_attr)
        issues = [i for i in val_result.issues if i.field == f"painting_{p_attr}"]

        needs_attention = (
            field.status
            in (
                FieldStatus.MISSING,
                FieldStatus.AMBIGUOUS,
                FieldStatus.CONFLICT,
                FieldStatus.INVALID,
            )
            or issues
            or field.confidence < 0.8
        )

        if needs_attention:
            fields_for_review.append(
                {
                    "field": f"painting_{p_attr}",
                    "current_value": field.value,
                    "status": field.status.value,
                    "confidence": field.confidence,
                    "issues": [i.message for i in issues],
                }
            )

    review_request = {
        "type": "ANNEX_VALIDATION",
        "message": "Review all extracted fields. Fields needing attention are flagged.",
        "fields": fields_for_review,
    }

    # Interrupt pauses execution here until Command(resume=...) is called
    decision = interrupt(review_request)

    return {"human_review_decision": decision}


def apply_human_decision_node(state: ExtractionState) -> dict:
    """
    Apply the human's decision back into the normalized extraction state.
    """
    decision_list = state.get("human_review_decision", [])
    normalized = state["normalized_extraction"]
    if isinstance(normalized, dict):
        normalized = ExtractionResult.model_validate(normalized)
    elif hasattr(normalized, "model_dump") and not isinstance(normalized, ExtractionResult):
        normalized = ExtractionResult.model_validate(normalized.model_dump())

    if decision_list:
        for decision in decision_list:
            field_name = decision.get("field")
            raw_val = decision.get("value")
            casted_val = _cast_field_value(field_name, raw_val)

            if field_name.startswith("painting_"):
                p_attr = field_name.split("_")[1]
                field: ExtractionField = getattr(normalized.painting, p_attr)
                field.value = casted_val
                field.confidence = 1.0 if casted_val is not None else 0.0
                field.status = (
                    FieldStatus.USER_CORRECTED if casted_val is not None else FieldStatus.MISSING
                )
            else:
                if hasattr(normalized, field_name):
                    field: ExtractionField = getattr(normalized, field_name)
                    field.value = casted_val
                    field.confidence = 1.0 if casted_val is not None else 0.0
                    field.status = (
                        FieldStatus.USER_CORRECTED
                        if casted_val is not None
                        else FieldStatus.MISSING
                    )

    # Any non-null field that was reviewed and approved without changes becomes USER_CONFIRMED
    all_fields = [
        normalized.tag_no,
        normalized.description,
        normalized.ref_data_sheet,
        normalized.design_code,
        normalized.moc,
        normalized.qty,
        normalized.orientation,
        normalized.vessel_id_mm,
        normalized.vessel_tl_tl_length_mm,
        normalized.shell_min_thk_mm,
        normalized.head_min_thk_mm,
        normalized.head_type,
        normalized.nozzle_type,
        normalized.impact_tested,
        normalized.rt,
        normalized.pwht,
        normalized.support_type,
        normalized.painting.external,
        normalized.painting.internal,
        normalized.pickling_passivation,
        normalized.weight_tons_each,
    ]
    for field in all_fields:
        if field.value is not None and field.status in (
            FieldStatus.AMBIGUOUS,
            FieldStatus.EXTRACTED,
            FieldStatus.NORMALIZED,
        ):
            field.status = FieldStatus.USER_CONFIRMED
            field.confidence = max(field.confidence, 0.95)

    # Clear the human review decision and mark user_approved so graph can finalize
    return {
        "normalized_extraction": normalized,
        "human_review_decision": None,
        "user_approved": True,
    }


def finalize_annex_node(state: ExtractionState) -> dict:
    """Format the final Annex dictionary payload."""
    if state.get("error"):
        return {}

    normalized = state["normalized_extraction"]
    if isinstance(normalized, dict):
        normalized = ExtractionResult.model_validate(normalized)
    elif hasattr(normalized, "model_dump") and not isinstance(normalized, ExtractionResult):
        normalized = ExtractionResult.model_validate(normalized.model_dump())

    try:
        annexure_record = build_annexure(normalized)
        return {"final_annex": annexure_record.model_dump()}
    except Exception as e:
        return {"error": f"Annexure generation failed: {str(e)}"}
