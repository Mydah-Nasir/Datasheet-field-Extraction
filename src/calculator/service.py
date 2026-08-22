"""Pure mathematical calculation functions for Pressure Vessel Shell Weight & Cost."""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional

from src.calculator.lookups import CalculatorLookups
from src.calculator.models import ShellCalculationInput, ShellCalculationResult

# =============================================================================
# CONSTANTS
# =============================================================================
BENDING_SIDES_FACTOR: float = 2.0  # Bending allowance applies to both sides of the plate
SINGLE_PLATE_FACTOR: float = 1.0   # Used when calculating a single plate


# =============================================================================
# FORMULA STEP 1: Developed Plate Length
# =============================================================================
def calculate_plate_length_per_shell(
    vessel_id_mm: float,
    shell_thickness_mm: float,
    bending_allowance_mm: float = 1.0,
    bending_sides_factor: float = BENDING_SIDES_FACTOR,
) -> float:
    r"""Calculate the required developed plate length per shell cylinder course.

    Formula:
        plate_length_per_shell_mm = (vessel_id_mm + shell_thickness_mm) * pi * bending_allowance_mm * bending_sides_factor

    Units:
        vessel_id_mm: Internal diameter (ID) in millimeters (mm)
        shell_thickness_mm: Minimum shell thickness in millimeters (mm)
        bending_allowance_mm: Allowance per edge in millimeters (mm)
        bending_sides_factor: Number of edges receiving allowance (default: 2)

    Returns:
        float: Developed plate circumference * bending allowance in mm
    """
    if vessel_id_mm <= 0:
        raise ValueError(f"vessel_id_mm must be > 0, got {vessel_id_mm}")
    if shell_thickness_mm <= 0:
        raise ValueError(f"shell_thickness_mm must be > 0, got {shell_thickness_mm}")
    if bending_allowance_mm < 0:
        raise ValueError(f"bending_allowance_mm must be >= 0, got {bending_allowance_mm}")

    return (vessel_id_mm + shell_thickness_mm) * math.pi * bending_allowance_mm * bending_sides_factor


# =============================================================================
# FORMULA STEP 2: Total Weight Actual
# =============================================================================
def calculate_total_weight_actual(
    plate_length_per_shell_mm: float,
    tl_tl_length_mm: float,
    shell_thickness_mm: float,
    density_f2: float,
) -> float:
    r"""Calculate the total net theoretical weight of the cylindrical shell.

    Formula:
        total_weight_actual_kg = (plate_length_per_shell_mm * 0.001) * (tl_tl_length_mm * 0.001)
                                 * shell_thickness_mm * density_f2

    Units:
        plate_length_per_shell_mm: Developed length in mm (converted to m via * 0.001)
        tl_tl_length_mm: Tangent-to-tangent length in mm (converted to m via * 0.001)
        shell_thickness_mm: Shell thickness in mm
        density_f2: Material plate factor in kg/(m^2*mm) (e.g. 7.85 for carbon steel)

    Returns:
        float: Actual theoretical weight of cylindrical shell in kilograms (kg)
    """
    if plate_length_per_shell_mm <= 0:
        raise ValueError(f"plate_length_per_shell_mm must be > 0, got {plate_length_per_shell_mm}")
    if tl_tl_length_mm <= 0:
        raise ValueError(f"tl_tl_length_mm must be > 0, got {tl_tl_length_mm}")
    if shell_thickness_mm <= 0:
        raise ValueError(f"shell_thickness_mm must be > 0, got {shell_thickness_mm}")
    if density_f2 <= 0:
        raise ValueError(f"density_f2 must be > 0, got {density_f2}")

    length_m = plate_length_per_shell_mm * 0.001
    width_m = tl_tl_length_mm * 0.001

    return length_m * width_m * shell_thickness_mm * density_f2


# =============================================================================
# FORMULA STEP 3: Single Stock Plate Weight (wt_each_kg)
# =============================================================================
def calculate_wt_each(
    plate_width_mm: float,
    plate_length_h_mm: float,
    shell_thickness_mm: float,
    density_f2: float,
    single_plate_factor: float = SINGLE_PLATE_FACTOR,
) -> float:
    r"""Calculate the gross procurement weight of a single flat plate stock piece.

    Formula:
        wt_each_kg = (plate_width_mm * 0.001) * (plate_length_h_mm * 0.001)
                     * shell_thickness_mm * density_f2 * single_plate_factor

    Units:
        plate_width_mm: Flat stock plate width in mm (converted to m via * 0.001)
        plate_length_h_mm: Flat stock plate length H in mm (converted to m via * 0.001)
        shell_thickness_mm: Plate thickness in mm
        density_f2: Material plate density factor in kg/(m^2*mm)
        single_plate_factor: Plate multiplier (default: 1.0)

    Returns:
        float: Weight of single rectangular plate in kilograms (kg)
    """
    if plate_width_mm <= 0:
        raise ValueError(f"plate_width_mm must be > 0, got {plate_width_mm}")
    if plate_length_h_mm <= 0:
        raise ValueError(f"plate_length_h_mm must be > 0, got {plate_length_h_mm}")
    if shell_thickness_mm <= 0:
        raise ValueError(f"shell_thickness_mm must be > 0, got {shell_thickness_mm}")
    if density_f2 <= 0:
        raise ValueError(f"density_f2 must be > 0, got {density_f2}")

    width_m = plate_width_mm * 0.001
    length_m = plate_length_h_mm * 0.001

    return width_m * length_m * shell_thickness_mm * density_f2 * single_plate_factor


# =============================================================================
# FORMULA STEP 4: Total Material Weight for Shell Batch
# =============================================================================
def calculate_material_weight(qty: int, wt_each_kg: float) -> float:
    r"""Calculate total procurement material weight across all shell units.

    Formula:
        material_weight_kg = qty * wt_each_kg

    Units:
        qty: Number of vessels/shells (integer >= 1)
        wt_each_kg: Weight of single plate in kg

    Returns:
        float: Total procurement material weight in kilograms (kg)
    """
    if qty < 1:
        raise ValueError(f"qty must be >= 1, got {qty}")
    if wt_each_kg <= 0:
        raise ValueError(f"wt_each_kg must be > 0, got {wt_each_kg}")

    return float(qty * wt_each_kg)


# =============================================================================
# FORMULA STEP 5: Total Material Cost
# =============================================================================
def calculate_cost(material_rate_per_kg: float, material_weight_kg: float) -> float:
    r"""Calculate total material procurement cost.

    Formula:
        cost = material_rate_per_kg * material_weight_kg

    Units:
        material_rate_per_kg: Price rate per kilogram in local currency ($/kg, SAR/kg, etc.)
        material_weight_kg: Total procurement weight in kg

    Returns:
        float: Total material cost in currency units
    """
    if material_rate_per_kg < 0:
        raise ValueError(f"material_rate_per_kg must be >= 0, got {material_rate_per_kg}")
    if material_weight_kg <= 0:
        raise ValueError(f"material_weight_kg must be > 0, got {material_weight_kg}")

    return float(material_rate_per_kg * material_weight_kg)


# =============================================================================
# TOP-LEVEL COORDINATOR: calculate_shell_cost
# =============================================================================
def calculate_shell_cost(
    record: ShellCalculationInput | Mapping[str, Any],
    lookups: Optional[CalculatorLookups] = None,
) -> ShellCalculationResult:
    """Execute the full 5-step shell weight & cost calculation with dependency injection.

    Args:
        record: ShellCalculationInput model or dict of parameters.
        lookups: Optional CalculatorLookups instance for swappable charts/tables.

    Returns:
        ShellCalculationResult: Pydantic model containing all 5 calculated outputs.
    """
    # 1. Resolve Lookups
    if lookups is None:
        lookups = CalculatorLookups()

    # 2. Coerce to ShellCalculationInput if dict
    if isinstance(record, Mapping):
        # Allow automatic lookup resolution if fields omitted
        data = dict(record)
        thickness = float(data.get("shell_thickness_mm", 0.0))
        moc = str(data.get("moc", ""))

        if "bending_allowance_mm" not in data or data["bending_allowance_mm"] is None:
            data["bending_allowance_mm"] = lookups.get_bending_allowance(thickness)

        if "density_f2" not in data or data["density_f2"] is None:
            data["density_f2"] = lookups.get_material_density(moc)

        if "material_rate_per_kg" not in data or data["material_rate_per_kg"] is None:
            data["material_rate_per_kg"] = lookups.get_material_rate(moc)

        calc_input = ShellCalculationInput(**data)
    elif isinstance(record, ShellCalculationInput):
        calc_input = record
    else:
        raise TypeError(f"Expected ShellCalculationInput or dict, got {type(record).__name__}")

    # 3. Step 1: Plate length per shell (mm)
    plate_length_per_shell_mm = calculate_plate_length_per_shell(
        vessel_id_mm=calc_input.vessel_id_mm,
        shell_thickness_mm=calc_input.shell_thickness_mm,
        bending_allowance_mm=calc_input.bending_allowance_mm,
        bending_sides_factor=BENDING_SIDES_FACTOR,
    )

    # 4. Step 2: Total weight actual (kg)
    total_weight_actual_kg = calculate_total_weight_actual(
        plate_length_per_shell_mm=plate_length_per_shell_mm,
        tl_tl_length_mm=calc_input.tl_tl_length_mm,
        shell_thickness_mm=calc_input.shell_thickness_mm,
        density_f2=calc_input.density_f2,
    )

    # 5. Step 3: Single plate weight (kg)
    wt_each_kg = calculate_wt_each(
        plate_width_mm=calc_input.plate_width_mm,
        plate_length_h_mm=calc_input.plate_length_h_mm,
        shell_thickness_mm=calc_input.shell_thickness_mm,
        density_f2=calc_input.density_f2,
        single_plate_factor=SINGLE_PLATE_FACTOR,
    )

    # 6. Step 4: Material weight (kg)
    material_weight_kg = calculate_material_weight(
        qty=calc_input.qty,
        wt_each_kg=wt_each_kg,
    )

    # 7. Step 5: Total cost
    cost = calculate_cost(
        material_rate_per_kg=calc_input.material_rate_per_kg,
        material_weight_kg=material_weight_kg,
    )

    return ShellCalculationResult(
        plate_length_per_shell_mm=plate_length_per_shell_mm,
        total_weight_actual_kg=total_weight_actual_kg,
        wt_each_kg=wt_each_kg,
        material_weight_kg=material_weight_kg,
        cost=cost,
    )
