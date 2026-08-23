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


def test_normalize_head_min_thickness(base_extraction):
    """Test that HEAD TH. 29 (MIN. 22.88) extracts the MINIMUM thickness (22.88) even if LLM provided nominal 29."""
    from src.domain.schema import Evidence

    normalizer = Normalizer()

    # Scenario 1: LLM extracted nominal 29.0, but evidence has MIN. 22.88
    base_extraction.head_min_thk_mm.value = 29.0
    base_extraction.head_min_thk_mm.status = FieldStatus.EXTRACTED
    base_extraction.head_min_thk_mm.evidence = [
        Evidence(page=3, text="2:1 ELLIP. HEAD TH. 29 (MIN. 22.88) (BOTH HEADS)")
    ]

    res = normalizer.normalize(base_extraction)
    assert res.head_min_thk_mm.value == 22.88
    assert res.head_min_thk_mm.status == FieldStatus.NORMALIZED

    # Scenario 2: LLM extracted raw string "HEAD TH. 29 (MIN. 22.88)"
    base_extraction.head_min_thk_mm.value = "HEAD TH. 29 (MIN. 22.88)"
    base_extraction.head_min_thk_mm.status = FieldStatus.EXTRACTED
    base_extraction.head_min_thk_mm.evidence = []

    res2 = normalizer.normalize(base_extraction)
    assert res2.head_min_thk_mm.value == 22.88
    assert res2.head_min_thk_mm.status == FieldStatus.NORMALIZED

    # Scenario 3: Standard single thickness without MIN
    base_extraction.shell_min_thk_mm.value = 29.0
    base_extraction.shell_min_thk_mm.status = FieldStatus.EXTRACTED
    base_extraction.shell_min_thk_mm.evidence = [
        Evidence(page=3, text="54870 (T.L. - T.L.) - TH. 29")
    ]

    res3 = normalizer.normalize(base_extraction)
    assert res3.shell_min_thk_mm.value == 29.0
    assert res3.shell_min_thk_mm.status == FieldStatus.NORMALIZED


def test_boolean_evidence_contradiction():
    """Test radio button pattern matching in _check_evidence_contradiction."""
    from src.domain.schema import Evidence, ExtractionField
    from src.extraction.service import GeminiExtractionService

    # 1. ◯ YES ◉ NO with value YES -> should suggest NO
    field_impact = ExtractionField[str](
        value="YES",
        status=FieldStatus.EXTRACTED,
        confidence=0.8,
        evidence=[Evidence(page=2, text="IMPACT TESTING (IT): ◯ YES ◉ NO ☑ CODE")],
    )
    suggested = GeminiExtractionService._check_evidence_contradiction(field_impact)
    assert suggested == "NO"

    # 2. ◉ YES ◯ NO with value NO -> should suggest YES
    field_pwht = ExtractionField[str](
        value="NO",
        status=FieldStatus.EXTRACTED,
        confidence=0.8,
        evidence=[Evidence(page=2, text="PWHT: ◉ YES ◯ NO ☐ CODE ☑ SERVICE")],
    )
    suggested_pwht = GeminiExtractionService._check_evidence_contradiction(field_pwht)
    assert suggested_pwht == "YES"

    # 3. ◯ YES ◉ NO with value NO -> no contradiction (returns None)
    field_correct = ExtractionField[str](
        value="NO",
        status=FieldStatus.EXTRACTED,
        confidence=0.9,
        evidence=[Evidence(page=2, text="IMPACT TESTING (IT): ◯ YES ◉ NO ☑ CODE")],
    )
    assert GeminiExtractionService._check_evidence_contradiction(field_correct) is None


def test_normalize_nozzle_type(base_extraction):
    """Test nozzle_type normalization preserving full specifications, pressure classes, and standards."""
    normalizer = Normalizer()

    # Scenario 1: Complete specification with pressure classes, designations, and standards
    base_extraction.nozzle_type.value = (
        "150# RFSRWN, 300# RFSRWN, 150# RFLWN, 300# RFLWN, B16.47 SERIES A"
    )
    base_extraction.nozzle_type.status = FieldStatus.EXTRACTED

    res = normalizer.normalize(base_extraction)
    assert (
        res.nozzle_type.value == "150# RFSRWN, 300# RFSRWN, 150# RFLWN, 300# RFLWN, B16.47 SERIES A"
    )
    assert res.nozzle_type.status == FieldStatus.NORMALIZED

    # Scenario 2: Whitespace and separator noise (semicolons, newlines, extra spaces)
    base_extraction.nozzle_type.value = "  150#   RFSRWN ;  300# RFSRWN \n 150# RFLWN , 300# RFLWN "
    base_extraction.nozzle_type.status = FieldStatus.EXTRACTED

    res2 = normalizer.normalize(base_extraction)
    assert res2.nozzle_type.value == "150# RFSRWN, 300# RFSRWN, 150# RFLWN, 300# RFLWN"
    assert res2.nozzle_type.status == FieldStatus.NORMALIZED

    # Scenario 3: Deduplication of duplicate entries across multiple rows
    base_extraction.nozzle_type.value = (
        "150# RFSRWN, 150# RFSRWN, 300# RFLWN, 150# RFSRWN, B16.47 SERIES A"
    )
    base_extraction.nozzle_type.status = FieldStatus.EXTRACTED

    res3 = normalizer.normalize(base_extraction)
    assert res3.nozzle_type.value == "150# RFSRWN, 300# RFLWN, B16.47 SERIES A"
    assert res3.nozzle_type.status == FieldStatus.NORMALIZED


def test_recover_values_from_evidence():
    """Test that Normalizer extracts values from evidence when field.value is None or empty."""
    normalizer = Normalizer()

    extraction = ExtractionResult(
        tag_no=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="TAG NO: V-202")],
        ),
        description=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="FLARE KNOCKOUT DRUM")],
        ),
        ref_data_sheet=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="SD-8500-13513-0001")],
        ),
        design_code=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="ASME SEC VIII DIV 1")],
        ),
        moc=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="SA 516 GR 70N")],
        ),
        qty=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="QTY: 2 UNITS")],
        ),
        orientation=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="HORIZONTAL VESSEL")],
        ),
        vessel_id_mm=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="ID 3200 mm")],
        ),
        vessel_tl_tl_length_mm=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="T/T LENGTH: 14500 mm")],
        ),
        shell_min_thk_mm=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="SHELL THK. 25.4 mm (MIN. 22.0 mm)")],
        ),
        head_min_thk_mm=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="HEAD THK 18 mm")],
        ),
        head_type=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="2:1 ELLIPSOIDAL")],
        ),
        nozzle_type=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="150# RFSRWN, 300# RFLWN")],
        ),
        impact_tested=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="IMPACT TESTING: ◯ YES ◉ NO")],
        ),
        rt=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="RT-1 100%")],
        ),
        pwht=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="PWHT: ◉ YES ◯ NO")],
        ),
        support_type=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="SADDLE & PAD")],
        ),
        painting=PaintingField(
            external=ExtractionField(
                value=None,
                status=FieldStatus.EXTRACTED,
                confidence=0.7,
                evidence=[Evidence(page=1, text="APCS-1B")],
            ),
            internal=ExtractionField(
                value=None,
                status=FieldStatus.EXTRACTED,
                confidence=0.7,
                evidence=[Evidence(page=1, text="NONE")],
            ),
        ),
        pickling_passivation=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="APCS-104")],
        ),
        weight_tons_each=ExtractionField(
            value=None,
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=1, text="OPERATING WEIGHT: 85,000 kg")],
        ),
    )

    res = normalizer.normalize(extraction)

    assert res.tag_no.value == "V-202"
    assert res.description.value == "FLARE KNOCKOUT DRUM"
    assert res.ref_data_sheet.value == "SD-8500-13513-0001"
    assert res.design_code.value == "ASME SEC VIII DIV 1"
    assert res.moc.value == "SA 516 GR 70N"
    assert res.qty.value == 2
    assert res.orientation.value == "HORIZONTAL"
    assert res.vessel_id_mm.value == 3200.0
    assert res.vessel_tl_tl_length_mm.value == 14500.0
    assert res.shell_min_thk_mm.value == 22.0
    assert res.head_min_thk_mm.value == 18.0
    assert res.head_type.value == "2:1 ELLIPSOIDAL"
    assert res.nozzle_type.value == "150# RFSRWN, 300# RFLWN"
    assert res.impact_tested.value == "NO"
    assert res.rt.value == "RT-1 100%"
    assert res.pwht.value == "YES"
    assert res.support_type.value == "SADDLE & PAD"
    assert res.painting.external.value == "APCS-1B"
    assert res.painting.internal.value == "NONE"
    assert res.pickling_passivation.value == "APCS-104"
    assert res.weight_tons_each.value == 85.0


def test_normalize_weight_fabricated_vs_empty():
    """Verify client rule: If Fabricated Weight is present, use it. Otherwise use Empty Weight."""
    normalizer = Normalizer()

    # Scenario 1: Both Fabricated Weight (418,000 kg) and Empty Weight (380,000 kg) present -> must choose Fabricated (418 tons)
    field_both = ExtractionField[float](
        value=None,
        status=FieldStatus.EXTRACTED,
        confidence=0.9,
        evidence=[
            Evidence(
                page=1,
                text="EMPTY WEIGHT: 380,000 KG. FABRICATED WEIGHT: 418,000 KG. OPERATING WEIGHT: 520,000 KG.",
            )
        ],
    )
    normalizer._normalize_weight(field_both)
    assert field_both.value == 418.0
    assert field_both.status == FieldStatus.NORMALIZED

    # Scenario 2: Only Empty Weight (85,000 kg) present -> must fallback to Empty Weight (85 tons)
    field_empty_only = ExtractionField[float](
        value=None,
        status=FieldStatus.EXTRACTED,
        confidence=0.9,
        evidence=[Evidence(page=1, text="WEIGHT: EMPTY WT: 85,000 KG, FULL OF WATER: 190,000 KG.")],
    )
    normalizer._normalize_weight(field_empty_only)
    assert field_empty_only.value == 85.0
    assert field_empty_only.status == FieldStatus.NORMALIZED

    # Scenario 3: Weight already in tons
    field_tons = ExtractionField[float](
        value=None,
        status=FieldStatus.EXTRACTED,
        confidence=0.9,
        evidence=[Evidence(page=1, text="FABRICATED WT: 350.5 TONS")],
    )
    normalizer._normalize_weight(field_tons)
    assert field_tons.value == 350.5
    assert field_tons.status == FieldStatus.NORMALIZED


def test_normalize_drawing_callout_patterns():
    """Verify normalization of GA/elevation drawing callout patterns from multi-page packages."""
    normalizer = Normalizer()

    # 1. Head thickness with MIN. THK. AFTER FORMING
    head_field = ExtractionField[float](
        value=None,
        status=FieldStatus.EXTRACTED,
        confidence=0.9,
        evidence=[
            Evidence(page=10, text='2:1 ELLIPSOIDAL HEAD 26 [1.024"] MIN. THK. AFTER FORMING')
        ],
    )
    normalizer._normalize_thickness(head_field)
    assert head_field.value == 26.0
    assert head_field.status == FieldStatus.NORMALIZED

    # 2. Shell course dimension "<Length> x <Thickness> THK."
    shell_field = ExtractionField[float](
        value=None,
        status=FieldStatus.EXTRACTED,
        confidence=0.9,
        evidence=[Evidence(page=10, text='18607.2 [61\'-0 5/8"] x 28.6 [1.126"] THK.')],
    )
    normalizer._normalize_thickness(shell_field)
    assert shell_field.value == 28.6
    assert shell_field.status == FieldStatus.NORMALIZED

    # 3. TL-TL Length with dual dimensions
    tl_field = ExtractionField[float](
        value=None,
        status=FieldStatus.EXTRACTED,
        confidence=0.9,
        evidence=[Evidence(page=10, text="32207.2 [105'-8\"] T.L. TO T.L.")],
    )
    normalizer._normalize_numeric(tl_field, "mm")
    assert tl_field.value == 32207.2
    assert tl_field.status == FieldStatus.NORMALIZED

    # 4. Vessel ID with dual dimensions
    id_field = ExtractionField[float](
        value=None,
        status=FieldStatus.EXTRACTED,
        confidence=0.9,
        evidence=[Evidence(page=10, text="6200 [20'-4 1/8\"] I.D.")],
    )
    normalizer._normalize_numeric(id_field, "mm")
    assert id_field.value == 6200.0
    assert id_field.status == FieldStatus.NORMALIZED
