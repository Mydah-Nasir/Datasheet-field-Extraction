"""Unit tests for the canonical domain schema."""

import json

import pytest
from pydantic import ValidationError

from src.domain.schema import (
    Evidence,
    ExtractionField,
    ExtractionResult,
    FieldStatus,
    PaintingField,
)


class TestEvidence:
    """Tests for the Evidence model."""

    def test_valid_evidence(self):
        evidence = Evidence(page=1, text="Material: SA-516")
        assert evidence.page == 1
        assert evidence.text == "Material: SA-516"
        assert evidence.bbox is None

    def test_valid_evidence_with_bbox(self):
        evidence = Evidence(page=2, text="ID 5800 mm", bbox=(10.5, 20.0, 100.0, 50.5))
        assert evidence.bbox == [10.5, 20.0, 100.0, 50.5]

    def test_invalid_page(self):
        # The gt=0 constraint was removed to allow Gemini structured outputs to parse
        # cleanly. The application layer handles real validation.
        evidence = Evidence(page=0, text="test")
        assert evidence.page == 0

    def test_invalid_text(self):
        # min_length=1 was removed for Gemini schema support
        evidence = Evidence(page=1, text="")
        assert evidence.text == ""


class TestFieldStatus:
    """Tests for the FieldStatus enum."""

    def test_all_statuses_exist(self):
        assert hasattr(FieldStatus, "EXTRACTED")
        assert hasattr(FieldStatus, "NORMALIZED")
        assert hasattr(FieldStatus, "CALCULATED")
        assert hasattr(FieldStatus, "MISSING")
        assert hasattr(FieldStatus, "AMBIGUOUS")
        assert hasattr(FieldStatus, "INVALID")
        assert hasattr(FieldStatus, "CONFLICT")
        assert hasattr(FieldStatus, "USER_CONFIRMED")
        assert hasattr(FieldStatus, "USER_CORRECTED")

    def test_serialization(self):
        status = FieldStatus.EXTRACTED
        assert json.dumps(status) == '"EXTRACTED"'


class TestExtractionField:
    """Tests for the generic ExtractionField model."""

    def test_valid_string_value(self):
        field = ExtractionField[str](value="SA-516", status=FieldStatus.EXTRACTED, confidence=0.9)
        assert field.value == "SA-516"

    def test_valid_numeric_value(self):
        field = ExtractionField[float](value=5800.0, status=FieldStatus.NORMALIZED, confidence=1.0)
        assert field.value == 5800.0

    def test_missing_value(self):
        field = ExtractionField[str](value=None, status=FieldStatus.MISSING, confidence=0.0)
        assert field.value is None

    def test_confidence_bounds(self):
        # ge/le were removed for Gemini schema support
        field = ExtractionField(value="test", status=FieldStatus.EXTRACTED, confidence=1.5)
        assert field.confidence == 1.5

    def test_multiple_evidence(self):
        evidence1 = Evidence(page=1, text="text1")
        evidence2 = Evidence(page=2, text="text2")
        field = ExtractionField[str](
            value="test",
            status=FieldStatus.EXTRACTED,
            confidence=0.8,
            evidence=[evidence1, evidence2],
        )
        assert len(field.evidence) == 2
        assert field.evidence[0].page == 1
        assert field.evidence[1].page == 2

    def test_json_serialization(self):
        field = ExtractionField[str](
            value="test",
            status=FieldStatus.EXTRACTED,
            confidence=0.8,
            evidence=[Evidence(page=1, text="source")],
        )
        data = field.model_dump()
        assert data["value"] == "test"
        assert data["status"] == "EXTRACTED"
        assert data["confidence"] == 0.8
        assert data["evidence"][0]["page"] == 1

        json_str = field.model_dump_json()
        assert "EXTRACTED" in json_str


class TestPaintingField:
    """Tests for the PaintingField model."""

    def test_painting_field_structure(self):
        field = PaintingField(
            external=ExtractionField[str](
                value="epoxy", status=FieldStatus.EXTRACTED, confidence=0.9
            ),
            internal=ExtractionField[str](value=None, status=FieldStatus.MISSING, confidence=0.0),
        )
        assert field.external.value == "epoxy"
        assert field.internal.value is None
        assert field.internal.status == FieldStatus.MISSING


class TestExtractionResult:
    """Tests for the complete ExtractionResult canonical schema."""

    def _get_dummy_field(self, value=None):
        return ExtractionField(
            value=value,
            status=FieldStatus.MISSING if value is None else FieldStatus.EXTRACTED,
            confidence=0.0 if value is None else 0.9,
        )

    def _get_dummy_painting(self):
        return PaintingField(
            external=self._get_dummy_field("external paint"),
            internal=self._get_dummy_field("internal paint"),
        )

    def test_complete_result(self):
        result = ExtractionResult(
            tag_no=self._get_dummy_field("V-101"),
            description=self._get_dummy_field("Separator"),
            ref_data_sheet=self._get_dummy_field("DS-1"),
            design_code=self._get_dummy_field("ASME"),
            moc=self._get_dummy_field("Carbon Steel"),
            qty=self._get_dummy_field(2),
            orientation=self._get_dummy_field("VERTICAL"),
            vessel_id_mm=self._get_dummy_field(5800.0),
            vessel_tl_tl_length_mm=self._get_dummy_field(12000.0),
            shell_min_thk_mm=self._get_dummy_field(25.0),
            head_min_thk_mm=self._get_dummy_field(30.0),
            head_type=self._get_dummy_field("Ellipsoidal"),
            nozzle_type=self._get_dummy_field("Flanged"),
            impact_tested=self._get_dummy_field("YES"),
            rt=self._get_dummy_field("FULL"),
            pwht=self._get_dummy_field("YES"),
            support_type=self._get_dummy_field("SKIRT"),
            painting=self._get_dummy_painting(),
            weight_tons_each=self._get_dummy_field(45.5),
        )

        assert result.tag_no.value == "V-101"
        assert result.qty.value == 2
        assert result.vessel_id_mm.value == 5800.0
        assert result.painting.external.value == "external paint"

        # Check parameter count (20 fields including pickling_passivation)
        fields = list(ExtractionResult.model_fields.keys())
        assert len(fields) == 20
        assert "painting" in fields
        assert "tag_no" in fields
        assert "pickling_passivation" in fields

    def test_missing_values(self):
        result = ExtractionResult(
            tag_no=self._get_dummy_field("V-101"),
            description=self._get_dummy_field(None),
            ref_data_sheet=self._get_dummy_field(None),
            design_code=self._get_dummy_field(None),
            moc=self._get_dummy_field(None),
            qty=self._get_dummy_field(None),
            orientation=self._get_dummy_field(None),
            vessel_id_mm=self._get_dummy_field(None),
            vessel_tl_tl_length_mm=self._get_dummy_field(None),
            shell_min_thk_mm=self._get_dummy_field(None),
            head_min_thk_mm=self._get_dummy_field(None),
            head_type=self._get_dummy_field(None),
            nozzle_type=self._get_dummy_field(None),
            impact_tested=self._get_dummy_field(None),
            rt=self._get_dummy_field(None),
            pwht=self._get_dummy_field(None),
            support_type=self._get_dummy_field(None),
            painting=PaintingField(
                external=self._get_dummy_field(None),
                internal=self._get_dummy_field(None),
            ),
            weight_tons_each=self._get_dummy_field(None),
        )

        assert result.description.value is None
        assert result.description.status == FieldStatus.MISSING
        assert result.painting.external.value is None
        assert result.painting.external.status == FieldStatus.MISSING

    def test_serialization(self):
        result = ExtractionResult(
            tag_no=self._get_dummy_field("V-101"),
            description=self._get_dummy_field("Separator"),
            ref_data_sheet=self._get_dummy_field("DS-1"),
            design_code=self._get_dummy_field("ASME"),
            moc=self._get_dummy_field("Carbon Steel"),
            qty=self._get_dummy_field(2),
            orientation=self._get_dummy_field("VERTICAL"),
            vessel_id_mm=self._get_dummy_field(5800.0),
            vessel_tl_tl_length_mm=self._get_dummy_field(12000.0),
            shell_min_thk_mm=self._get_dummy_field(25.0),
            head_min_thk_mm=self._get_dummy_field(30.0),
            head_type=self._get_dummy_field("Ellipsoidal"),
            nozzle_type=self._get_dummy_field("Flanged"),
            impact_tested=self._get_dummy_field("YES"),
            rt=self._get_dummy_field("FULL"),
            pwht=self._get_dummy_field("YES"),
            support_type=self._get_dummy_field("SKIRT"),
            painting=self._get_dummy_painting(),
            weight_tons_each=self._get_dummy_field(45.5),
        )

        dump = result.model_dump()
        assert dump["tag_no"]["value"] == "V-101"
        assert dump["tag_no"]["status"] == "EXTRACTED"
        assert dump["qty"]["value"] == 2
        assert dump["painting"]["external"]["value"] == "external paint"

        json_str = result.model_dump_json()
        assert '"tag_no"' in json_str
        assert '"V-101"' in json_str

        # Verify it can be loaded back by standard json module
        data = json.loads(json_str)
        assert data["tag_no"]["value"] == "V-101"
