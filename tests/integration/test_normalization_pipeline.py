"""Pipeline test for normalization and validation on realistic data."""

import pytest

from src.domain.schema import (
    Evidence,
    ExtractionField,
    ExtractionResult,
    FieldStatus,
    PaintingField,
)
from src.extraction.normalization import Normalizer
from src.extraction.validation import Validator


# A deterministic fixture representing realistic extracted values from the actual Mechanical Datasheet.
# (Synthetic/Mocked to represent Gemini's raw output without requiring an API key)
@pytest.fixture
def realistic_extraction() -> ExtractionResult:
    return ExtractionResult(
        tag_no=ExtractionField(
            value="V-101",
            status=FieldStatus.EXTRACTED,
            confidence=0.95,
            evidence=[Evidence(page=1, text="Tag No. V-101")],
        ),
        description=ExtractionField(
            value="Production Separator",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="Description: Production Separator")],
        ),
        ref_data_sheet=ExtractionField(
            value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
        ),
        design_code=ExtractionField(
            value="ASME Sec VIII Div 1",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="Code: ASME Sec VIII Div 1")],
        ),
        moc=ExtractionField(
            value="SA 516 Gr. 70",
            status=FieldStatus.EXTRACTED,
            confidence=0.8,
            evidence=[Evidence(page=1, text="Material: SA 516 Gr. 70")],
        ),
        qty=ExtractionField(
            value="1",
            status=FieldStatus.EXTRACTED,
            confidence=0.99,
            evidence=[Evidence(page=1, text="Quantity 1")],
        ),
        orientation=ExtractionField(
            value="HOR",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="Orientation: HOR")],
        ),
        vessel_id_mm=ExtractionField(
            value="2400",
            status=FieldStatus.EXTRACTED,
            confidence=0.85,
            evidence=[Evidence(page=2, text="ID 2400 mm")],
        ),
        vessel_tl_tl_length_mm=ExtractionField(
            value="5.8",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=2, text="5.8 m")],
        ),
        shell_min_thk_mm=ExtractionField(
            value="25",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=2, text="Thk 25mm")],
        ),
        head_min_thk_mm=ExtractionField(
            value="22",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=2, text="22 mm")],
        ),
        head_type=ExtractionField(
            value="2:1 Elliptical",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=2, text="2:1 Elliptical")],
        ),
        nozzle_type=ExtractionField(
            value="Flanged",
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=2, text="Flanged")],
        ),
        impact_tested=ExtractionField(
            value="YES",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=3, text="Impact Tested: YES")],
        ),
        rt=ExtractionField(
            value="100%",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=3, text="RT 100%")],
        ),
        pwht=ExtractionField(
            value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
        ),  # Missing intentionally for review test
        support_type=ExtractionField(
            value="Saddles",
            status=FieldStatus.EXTRACTED,
            confidence=0.8,
            evidence=[Evidence(page=3, text="Saddles")],
        ),
        painting=PaintingField(
            external=ExtractionField(
                value="System A",
                status=FieldStatus.EXTRACTED,
                confidence=0.9,
                evidence=[Evidence(page=4, text="Ext: System A")],
            ),
            internal=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
        ),
        weight_tons_each=ExtractionField(
            value="15000",
            status=FieldStatus.EXTRACTED,
            confidence=0.8,
            evidence=[Evidence(page=4, text="15000 kg")],
        ),
    )


def test_full_validation_pipeline(realistic_extraction, capsys):
    """Run normalization and validation on the realistic mock and print developer report."""

    # 1. Normalization
    normalizer = Normalizer()
    normalized = normalizer.normalize(realistic_extraction)

    # 2. Validation
    validator = Validator()
    val_result = validator.validate(normalized)

    # 3. Print Report
    print("\n\n" + "=" * 80)
    print("PHASE 4 DEVELOPER REPORT: NORMALIZATION & VALIDATION")
    print("=" * 80)
    print(f"OVERALL STATUS: {val_result.status.value}")
    if val_result.issues:
        print(f"TOTAL ISSUES: {len(val_result.issues)}")

    print("-" * 120)
    print(
        f"{'FIELD'.ljust(25)} | {'EXTRACTED'.ljust(15)} | {'NORMALIZED'.ljust(15)} | {'STATUS'.ljust(15)} | {'ISSUES'.ljust(10)} | EVIDENCE"
    )
    print("-" * 120)

    fields = [
        ("TAG NO", realistic_extraction.tag_no, normalized.tag_no),
        ("DESCRIPTION", realistic_extraction.description, normalized.description),
        ("REF DATA SHEET", realistic_extraction.ref_data_sheet, normalized.ref_data_sheet),
        ("DESIGN CODE", realistic_extraction.design_code, normalized.design_code),
        ("MOC", realistic_extraction.moc, normalized.moc),
        ("QTY", realistic_extraction.qty, normalized.qty),
        ("ORIENTATION", realistic_extraction.orientation, normalized.orientation),
        ("VESSEL ID", realistic_extraction.vessel_id_mm, normalized.vessel_id_mm),
        ("LENGTH", realistic_extraction.vessel_tl_tl_length_mm, normalized.vessel_tl_tl_length_mm),
        ("SHELL THK", realistic_extraction.shell_min_thk_mm, normalized.shell_min_thk_mm),
        ("HEAD THK", realistic_extraction.head_min_thk_mm, normalized.head_min_thk_mm),
        ("HEAD TYPE", realistic_extraction.head_type, normalized.head_type),
        ("NOZZLE TYPE", realistic_extraction.nozzle_type, normalized.nozzle_type),
        ("IMPACT TESTED", realistic_extraction.impact_tested, normalized.impact_tested),
        ("RT", realistic_extraction.rt, normalized.rt),
        ("PWHT", realistic_extraction.pwht, normalized.pwht),
        ("SUPPORT TYPE", realistic_extraction.support_type, normalized.support_type),
        ("EXT PAINT", realistic_extraction.painting.external, normalized.painting.external),
        ("INT PAINT", realistic_extraction.painting.internal, normalized.painting.internal),
        ("WEIGHT", realistic_extraction.weight_tons_each, normalized.weight_tons_each),
    ]

    for name, raw_f, norm_f in fields:
        raw_val = str(raw_f.value) if raw_f.value is not None else "null"
        norm_val = str(norm_f.value) if norm_f.value is not None else "null"
        status = norm_f.status.value

        # Check issues for this field
        field_issues = [
            i
            for i in val_result.issues
            if i.field.replace("_mm", "").startswith(name.lower().replace(" ", "_").split("_")[0])
        ]
        issue_str = str(len(field_issues)) if field_issues else "0"

        ev_text = norm_f.evidence[0].text if norm_f.evidence else "None"

        print(
            f"{name.ljust(25)} | {raw_val.ljust(15)} | {norm_val.ljust(15)} | {status.ljust(15)} | {issue_str.ljust(10)} | {ev_text}"
        )

    print("=" * 80 + "\n")

    # Assertions
    assert val_result.normalized_extraction.vessel_tl_tl_length_mm.value == 5800.0
    assert val_result.normalized_extraction.weight_tons_each.value == 15.0
    assert val_result.normalized_extraction.orientation.value == "HORIZONTAL"
    assert (
        val_result.status.value == "NEEDS_REVIEW"
    )  # Because PWHT is missing and Ref Data Sheet is missing
