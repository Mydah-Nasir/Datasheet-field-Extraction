"""Unit tests for deterministic validation."""

import pytest

from src.domain.schema import ExtractionField, ExtractionResult, FieldStatus, PaintingField
from src.domain.validation import ValidationSeverity, ValidationStatus
from src.extraction.validation import Validator


@pytest.fixture
def valid_extraction() -> ExtractionResult:
    """Fixture providing a perfectly valid extraction result."""
    return ExtractionResult(
        tag_no=ExtractionField(value="V-101", status=FieldStatus.NORMALIZED, confidence=0.9),
        description=ExtractionField(
            value="Separator", status=FieldStatus.NORMALIZED, confidence=0.9
        ),
        ref_data_sheet=ExtractionField(
            value="DS-01", status=FieldStatus.NORMALIZED, confidence=0.9
        ),
        design_code=ExtractionField(value="ASME", status=FieldStatus.NORMALIZED, confidence=0.9),
        moc=ExtractionField(value="CS", status=FieldStatus.NORMALIZED, confidence=0.9),
        qty=ExtractionField(value=1, status=FieldStatus.NORMALIZED, confidence=0.9),
        orientation=ExtractionField(
            value="VERTICAL", status=FieldStatus.NORMALIZED, confidence=0.9
        ),
        vessel_id_mm=ExtractionField(value=5800.0, status=FieldStatus.NORMALIZED, confidence=0.9),
        vessel_tl_tl_length_mm=ExtractionField(
            value=5800.0, status=FieldStatus.NORMALIZED, confidence=0.9
        ),
        shell_min_thk_mm=ExtractionField(value=30.0, status=FieldStatus.NORMALIZED, confidence=0.9),
        head_min_thk_mm=ExtractionField(value=21.82, status=FieldStatus.NORMALIZED, confidence=0.9),
        head_type=ExtractionField(
            value="Ellipsoidal", status=FieldStatus.NORMALIZED, confidence=0.9
        ),
        nozzle_type=ExtractionField(value="Flanged", status=FieldStatus.NORMALIZED, confidence=0.9),
        impact_tested=ExtractionField(value="YES", status=FieldStatus.NORMALIZED, confidence=0.9),
        rt=ExtractionField(value="100%", status=FieldStatus.NORMALIZED, confidence=0.9),
        pwht=ExtractionField(value="NO", status=FieldStatus.NORMALIZED, confidence=0.9),
        support_type=ExtractionField(value="Skirt", status=FieldStatus.NORMALIZED, confidence=0.9),
        painting=PaintingField(
            external=ExtractionField(value="Yes", status=FieldStatus.NORMALIZED, confidence=0.9),
            internal=ExtractionField(value="None", status=FieldStatus.NORMALIZED, confidence=0.9),
        ),
        weight_tons_each=ExtractionField(value=1.5, status=FieldStatus.NORMALIZED, confidence=0.9),
    )


def test_validation_success(valid_extraction):
    validator = Validator()
    res = validator.validate(valid_extraction)

    assert res.status == ValidationStatus.VALID
    assert len(res.issues) == 0


def test_validation_missing_required(valid_extraction):
    # Nullify required field
    valid_extraction.tag_no.value = None
    valid_extraction.tag_no.status = FieldStatus.MISSING

    validator = Validator()
    res = validator.validate(valid_extraction)

    assert res.status == ValidationStatus.NEEDS_REVIEW
    assert len(res.issues) == 1
    assert res.issues[0].field == "tag_no"
    assert res.issues[0].code == "MISSING_REQUIRED_FIELD"
    assert res.issues[0].severity == ValidationSeverity.ERROR


def test_validation_negative_physical(valid_extraction):
    valid_extraction.vessel_id_mm.value = -100.0

    validator = Validator()
    res = validator.validate(valid_extraction)

    assert res.status == ValidationStatus.NEEDS_REVIEW
    assert len(res.issues) == 1
    assert res.issues[0].field == "vessel_id_mm"
    assert res.issues[0].code == "NEGATIVE_PHYSICAL_VALUE"


def test_validation_invalid_numeric(valid_extraction):
    valid_extraction.qty.value = "two"

    validator = Validator()
    res = validator.validate(valid_extraction)

    assert res.status == ValidationStatus.NEEDS_REVIEW
    assert len(res.issues) == 1
    assert res.issues[0].field == "qty"
    assert res.issues[0].code == "INVALID_NUMERIC_VALUE"


def test_validation_needs_review_on_ambiguous(valid_extraction):
    # Ambiguous but not technically an invalid value structure
    valid_extraction.head_type.status = FieldStatus.AMBIGUOUS

    validator = Validator()
    res = validator.validate(valid_extraction)

    assert res.status == ValidationStatus.NEEDS_REVIEW
    assert len(res.issues) == 0  # No structural issue, just routing status
