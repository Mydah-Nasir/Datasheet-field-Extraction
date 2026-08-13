"""Unit tests for deterministic normalization."""

import pytest

from src.domain.schema import (
    Evidence,
    ExtractionField,
    ExtractionResult,
    FieldStatus,
    PaintingField,
)
from src.extraction.normalization import Normalizer


@pytest.fixture
def base_extraction() -> ExtractionResult:
    """Fixture providing a base unnormalized extraction result."""
    return ExtractionResult(
        tag_no=ExtractionField(value="  V-101   ", status=FieldStatus.EXTRACTED, confidence=0.9),
        description=ExtractionField(
            value="Separator  Vessel", status=FieldStatus.EXTRACTED, confidence=0.9
        ),
        ref_data_sheet=ExtractionField(value=None, status=FieldStatus.MISSING, confidence=0.0),
        design_code=ExtractionField(value=None, status=FieldStatus.MISSING, confidence=0.0),
        moc=ExtractionField(value=None, status=FieldStatus.MISSING, confidence=0.0),
        qty=ExtractionField(
            value=1,
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="1")],
        ),
        orientation=ExtractionField(value="VERT", status=FieldStatus.EXTRACTED, confidence=0.9),
        vessel_id_mm=ExtractionField(
            value=580.0,
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="580 cm")],
        ),
        vessel_tl_tl_length_mm=ExtractionField(
            value=5.8,
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="5.8 m")],
        ),
        shell_min_thk_mm=ExtractionField(
            value=30.0,
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="30 mm")],
        ),
        head_min_thk_mm=ExtractionField(
            value=21.82,
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="21.82 mm")],
        ),
        head_type=ExtractionField(value=None, status=FieldStatus.MISSING, confidence=0.0),
        nozzle_type=ExtractionField(value=None, status=FieldStatus.MISSING, confidence=0.0),
        impact_tested=ExtractionField(value="Yes", status=FieldStatus.EXTRACTED, confidence=0.9),
        rt=ExtractionField(value="100%", status=FieldStatus.EXTRACTED, confidence=0.9),
        pwht=ExtractionField(value="N", status=FieldStatus.EXTRACTED, confidence=0.9),
        support_type=ExtractionField(value=None, status=FieldStatus.MISSING, confidence=0.0),
        painting=PaintingField(
            external=ExtractionField(value=None, status=FieldStatus.MISSING, confidence=0.0),
            internal=ExtractionField(value=None, status=FieldStatus.MISSING, confidence=0.0),
        ),
        weight_tons_each=ExtractionField(
            value=1500.0,
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="1500 kg")],
        ),
    )


def test_normalize_string_fields(base_extraction):
    normalizer = Normalizer()
    res = normalizer.normalize(base_extraction)

    assert res.tag_no.value == "V-101"
    assert res.tag_no.status == FieldStatus.NORMALIZED

    assert res.description.value == "Separator Vessel"
    assert res.description.status == FieldStatus.NORMALIZED

    # Check that missing fields stay missing
    assert res.ref_data_sheet.status == FieldStatus.MISSING
    assert res.ref_data_sheet.value is None


def test_normalize_numeric_fields(base_extraction):
    normalizer = Normalizer()
    res = normalizer.normalize(base_extraction)

    # 580 cm -> 5800 mm
    assert res.vessel_id_mm.value == 5800.0
    assert res.vessel_id_mm.status == FieldStatus.NORMALIZED

    # 5.8 m -> 5800 mm
    assert res.vessel_tl_tl_length_mm.value == 5800.0

    # 30.0 mm -> 30.0
    assert res.shell_min_thk_mm.value == 30.0
    assert isinstance(res.shell_min_thk_mm.value, float)

    # 21.82 mm -> 21.82
    assert res.head_min_thk_mm.value == 21.82

    # 1500 kg -> 1.5 ton
    assert res.weight_tons_each.value == 1.5

    # 1 qty (string parse) -> 1
    assert res.qty.value == 1
    assert isinstance(res.qty.value, int)


def test_normalize_boolean_fields(base_extraction):
    normalizer = Normalizer()
    res = normalizer.normalize(base_extraction)

    assert res.impact_tested.value == "YES"
    assert res.impact_tested.status == FieldStatus.NORMALIZED

    assert res.pwht.value == "NO"
    assert res.pwht.status == FieldStatus.NORMALIZED


def test_normalize_orientation(base_extraction):
    normalizer = Normalizer()
    res = normalizer.normalize(base_extraction)

    assert res.orientation.value == "VERTICAL"
    assert res.orientation.status == FieldStatus.NORMALIZED


def test_evidence_preserved(base_extraction):
    normalizer = Normalizer()
    res = normalizer.normalize(base_extraction)

    # Evidence must survive normalization
    assert len(res.vessel_id_mm.evidence) == 1
    assert res.vessel_id_mm.evidence[0].text == "580 cm"


def test_idempotence(base_extraction):
    normalizer = Normalizer()
    res1 = normalizer.normalize(base_extraction)
    res2 = normalizer.normalize(res1)

    assert res1.vessel_id_mm.value == 5800.0
    assert res2.vessel_id_mm.value == 5800.0

    assert res1.tag_no.value == "V-101"
    assert res2.tag_no.value == "V-101"

    # Should stay NORMALIZED
    assert res2.tag_no.status == FieldStatus.NORMALIZED
