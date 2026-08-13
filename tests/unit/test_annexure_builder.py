"""Unit tests for the annexure builder."""

import pytest

from src.annexure.builder import AnnexureExportError, build_annexure, validate_for_export
from src.annexure.models import AnnexureRecord
from src.domain.schema import (
    Evidence,
    ExtractionField,
    ExtractionResult,
    FieldStatus,
    PaintingField,
)


def _create_mock_field(value, status=FieldStatus.NORMALIZED, confidence=0.9):
    return ExtractionField(
        value=value,
        status=status,
        confidence=confidence,
        evidence=[Evidence(page=1, text=str(value))]
    )


def create_valid_extraction_result():
    """Create a fully valid ExtractionResult."""
    return ExtractionResult(
        tag_no=_create_mock_field("V-101"),
        description=_create_mock_field("Separator"),
        ref_data_sheet=_create_mock_field("DS-001"),
        design_code=_create_mock_field("ASME Sec VIII"),
        moc=_create_mock_field("SA-516 Gr 70"),
        qty=_create_mock_field(2),
        orientation=_create_mock_field("VERTICAL"),
        vessel_id_mm=_create_mock_field(1500.0),
        vessel_tl_tl_length_mm=_create_mock_field(4000.0),
        shell_min_thk_mm=_create_mock_field(20.0),
        head_min_thk_mm=_create_mock_field(22.0),
        head_type=_create_mock_field("2:1 Elliptical"),
        nozzle_type=_create_mock_field("Flanged"),
        impact_tested=_create_mock_field("YES"),
        rt=_create_mock_field("FULL"),
        pwht=_create_mock_field("YES"),
        support_type=_create_mock_field("Skirt"),
        painting=PaintingField(
            external=_create_mock_field("System 1"),
            internal=_create_mock_field("System 2")
        ),
        weight_tons_each=_create_mock_field(15.5)
    )


def test_validate_for_export_success():
    """Test that a fully valid result passes export validation."""
    result = create_valid_extraction_result()
    # Should not raise any exception
    validate_for_export(result)


def test_validate_for_export_fails_on_missing():
    """Test that export validation fails on MISSING status."""
    result = create_valid_extraction_result()
    result.pwht.status = FieldStatus.MISSING
    result.pwht.value = None

    with pytest.raises(AnnexureExportError, match="Field 'pwht' has unresolved status: MISSING"):
        validate_for_export(result)


def test_validate_for_export_fails_on_ambiguous():
    """Test that export validation fails on AMBIGUOUS status."""
    result = create_valid_extraction_result()
    result.moc.status = FieldStatus.AMBIGUOUS

    with pytest.raises(AnnexureExportError, match="Field 'moc' has unresolved status: AMBIGUOUS"):
        validate_for_export(result)


def test_validate_for_export_fails_on_conflict():
    """Test that export validation fails on CONFLICT status."""
    result = create_valid_extraction_result()
    result.qty.status = FieldStatus.CONFLICT

    with pytest.raises(AnnexureExportError, match="Field 'qty' has unresolved status: CONFLICT"):
        validate_for_export(result)


def test_validate_for_export_fails_on_null_value():
    """Test that export validation fails if a value is null despite status."""
    result = create_valid_extraction_result()
    result.tag_no.value = None

    with pytest.raises(AnnexureExportError, match="Field 'tag_no' has a null value"):
        validate_for_export(result)


def test_build_annexure_success():
    """Test building an AnnexureRecord from a valid ExtractionResult."""
    result = create_valid_extraction_result()
    record = build_annexure(result)

    assert isinstance(record, AnnexureRecord)
    assert record.tag_no == "V-101"
    assert record.description == "Separator"
    assert record.qty == 2
    assert record.vessel_id_mm == 1500.0

    # Check painting is flattened
    assert record.painting_external == "System 1"
    assert record.painting_internal == "System 2"
