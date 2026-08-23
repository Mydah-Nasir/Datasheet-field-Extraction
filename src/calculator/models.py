"""Data models for Shell Weight & Cost Calculator."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ShellCalculationInput(BaseModel):
    """Inputs required for pressure vessel shell weight and cost calculations."""

    # Extracted from datasheet (MDS)
    component_part: str = Field(default="Shell", description="Component part name (e.g. Shell)")
    vessel_id_mm: float = Field(..., gt=0, description="Vessel internal diameter (ID) in mm")
    tl_tl_length_mm: float = Field(
        ..., gt=0, description="Vessel tangent-to-tangent (T/T) length in mm"
    )
    shell_thickness_mm: float = Field(..., gt=0, description="Shell minimum thickness in mm")
    moc: str = Field(default="UNKNOWN", description="Material of construction (MOC)")
    qty: int = Field(default=1, ge=1, description="Quantity of shells/vessels (User Input)")

    # User-entered or looked up
    plate_width_mm: float = Field(..., gt=0, description="Flat plate stock width in mm")
    plate_length_h_mm: float = Field(..., gt=0, description="Flat plate stock length (H) in mm")
    bending_allowance_mm: float = Field(
        default=0.0, ge=0, description="Bending allowance per side in mm"
    )
    density_f2: float = Field(
        default=7.85, gt=0, description="Material density constant in kg/(m^2*mm)"
    )
    material_rate_per_kg: float = Field(..., ge=0, description="Material unit pricing rate per kg")

    @field_validator("moc", mode="before")
    @classmethod
    def validate_moc(cls, v: str | None) -> str:
        if v is None:
            return "UNKNOWN"
        s = str(v).strip()
        if not s:
            return "UNKNOWN"
        return s


class ShellCalculationResult(BaseModel):
    """Outputs produced by the 5-step shell weight and cost formulas."""

    plate_length_per_shell_mm: float = Field(
        ..., description="Step 1: Developed plate circumference + bending allowance in mm"
    )
    total_weight_actual_kg: float = Field(
        ..., description="Step 2: Actual total weight of cylindrical shell in kg"
    )
    wt_each_kg: float = Field(
        ..., description="Step 3: Weight of a single rectangular plate piece in kg"
    )
    material_weight_kg: float = Field(
        ..., description="Step 4: Total procurement material weight for all units in kg"
    )
    cost: float = Field(..., description="Step 5: Total material cost in currency units")
