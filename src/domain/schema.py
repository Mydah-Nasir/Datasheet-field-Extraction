"""Canonical schema for Mechanical Datasheet Annex Extraction.

This schema defines the exact structure and contract for all data flowing through the pipeline:
extraction, validation, human review, and final outputs.
"""

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class FieldStatus(StrEnum):
    """Represents the current processing state of an extracted field."""

    EXTRACTED = "EXTRACTED"
    NORMALIZED = "NORMALIZED"
    CALCULATED = "CALCULATED"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"
    CONFLICT = "CONFLICT"
    USER_CONFIRMED = "USER_CONFIRMED"
    USER_CORRECTED = "USER_CORRECTED"


class Evidence(BaseModel):
    """Proof and location of an extracted value from a source document."""

    page: int = Field(description="1-indexed page number where the value was found")
    text: str = Field(description="The raw source text")
    bbox: list[float] | None = Field(
        default=None,
        description="Bounding box in [x1, y1, x2, y2] format",
    )


class ExtractionField(BaseModel, Generic[T]):
    """A generic wrapper for an engineering value, including its status and evidence."""

    value: T | None = Field(default=None, description="The extracted or normalized value")
    status: FieldStatus = Field(description="The current state of this field")
    confidence: float = Field(
        description="Extraction confidence score between 0.0 and 1.0"
    )
    evidence: list[Evidence] = Field(
        default_factory=list, description="List of evidence items supporting this value"
    )


class PaintingField(BaseModel):
    """Logical representation of painting requirements."""

    external: ExtractionField[str] = Field(description="External painting specification")
    internal: ExtractionField[str] = Field(description="Internal painting specification")


class ExtractionResult(BaseModel):
    """The canonical 19-parameter representation of a Mechanical Datasheet.

    This model must be used by the LLM for extraction, and by the application
    for validation, human review, and the final validated Annex dataset.
    """

    # 1. TAG NO.
    tag_no: ExtractionField[str]
    # 2. DESCRIPTION
    description: ExtractionField[str]
    # 3. Ref Data Sheet
    ref_data_sheet: ExtractionField[str]
    # 4. DESIGN CODE
    design_code: ExtractionField[str]
    # 5. MOC (Main Material)
    moc: ExtractionField[str]
    # 6. QTY.
    qty: ExtractionField[int]
    # 7. VERT / HOR
    orientation: ExtractionField[str]
    # 8. VESSEL ID (mm)
    vessel_id_mm: ExtractionField[float]
    # 9. VESSEL (TL-TL) LENGTH (mm)
    vessel_tl_tl_length_mm: ExtractionField[float]
    # 10. SHELL MIN. THK. (mm)
    shell_min_thk_mm: ExtractionField[float]
    # 11. HEAD MIN. THK. (mm)
    head_min_thk_mm: ExtractionField[float]
    # 12. HEAD TYPE
    head_type: ExtractionField[str]
    # 13. NOZZLE TYPE
    nozzle_type: ExtractionField[str]
    # 14. Impact Tested
    impact_tested: ExtractionField[str]
    # 15. RT (Radiography)
    rt: ExtractionField[str]
    # 16. PWHT
    pwht: ExtractionField[str]
    # 17. TYPE OF SUPPORT
    support_type: ExtractionField[str]
    # 18. PAINTING (Contains external and internal)
    painting: PaintingField
    # 19. WT-Tons (Each) (Approx.)
    weight_tons_each: ExtractionField[float]
