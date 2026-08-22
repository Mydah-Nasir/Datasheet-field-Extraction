"""Lookup table stubs and dependency-injection container for shell calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


# Standard thickness-to-bending allowance lookup chart stub
# (Thick plates >= 40mm require bending allowance compensation)
DEFAULT_BENDING_ALLOWANCE_CHART: dict[float, float] = {
    40.0: 15.0,
    50.0: 20.0,
    60.0: 25.0,
    70.0: 30.0,
    80.0: 35.0,
    90.0: 40.0,
    100.0: 50.0,
}

# Standard material density table stub (in kg/(m^2*mm) == g/cm^3)
DEFAULT_MATERIAL_DENSITY_TABLE: dict[str, float] = {
    "SA 516 GR 70N": 7.85,
    "SA 516 GR. 70N": 7.85,
    "SA 516 GR 70N-HIC": 7.85,
    "SA 516 GR. 70N HIC": 7.85,
    "SA 516 GR 60": 7.85,
    "SA 240 TP 304": 7.93,
    "SA 240 TP 316L": 8.00,
    "SA 387 GR 11": 7.85,
    "SA 387 GR 22": 7.85,
    "CARBON STEEL": 7.85,
    "STAINLESS STEEL": 8.00,
}

# Default material pricing rate stub (USD/SAR per kg)
DEFAULT_MATERIAL_RATE_TABLE: dict[str, float] = {
    "SA 516 GR 70N": 2.50,
    "SA 516 GR. 70N": 2.50,
    "SA 516 GR 70N-HIC": 3.20,
    "SA 516 GR. 70N HIC": 3.20,
    "SA 516 GR 60": 2.40,
    "SA 240 TP 304": 5.80,
    "SA 240 TP 316L": 7.20,
    "CARBON STEEL": 2.50,
    "STAINLESS STEEL": 6.50,
}


def get_bending_allowance(thickness_mm: float) -> float:
    """Stub lookup for bending allowance by thickness.

    If shell_thickness_mm >= 40 mm, looks up chart allowance;
    otherwise returns 1.0 mm (standard default multiplier / thin plate case).
    """
    if thickness_mm < 40.0:
        return 1.0

    # Match exact or nearest upper tier in chart
    for t_tier in sorted(DEFAULT_BENDING_ALLOWANCE_CHART.keys()):
        if thickness_mm <= t_tier:
            return DEFAULT_BENDING_ALLOWANCE_CHART[t_tier]

    # For ultra-thick plates beyond max key
    return DEFAULT_BENDING_ALLOWANCE_CHART[max(DEFAULT_BENDING_ALLOWANCE_CHART.keys())]


def get_material_density(moc: str) -> float:
    """Stub lookup for material density in kg/(m^2*mm) based on MOC string."""
    norm = moc.strip().upper()
    # Sort keys by length descending for longest/most-specific match first
    for key in sorted(DEFAULT_MATERIAL_DENSITY_TABLE.keys(), key=len, reverse=True):
        if key in norm or norm in key:
            return DEFAULT_MATERIAL_DENSITY_TABLE[key]
    return 7.85  # Default steel density constant


def get_material_rate(moc: str, uom: str = "kg") -> float:
    """Stub lookup for unit pricing rate per kg based on MOC string."""
    norm = moc.strip().upper()
    # Sort keys by length descending for longest/most-specific match first
    for key in sorted(DEFAULT_MATERIAL_RATE_TABLE.keys(), key=len, reverse=True):
        if key in norm or norm in key:
            return DEFAULT_MATERIAL_RATE_TABLE[key]
    return 2.50  # Default base carbon steel rate


@dataclass
class CalculatorLookups:
    """Dependency injection container for swappable external lookup functions."""

    get_bending_allowance: Callable[[float], float] = get_bending_allowance
    get_material_density: Callable[[str], float] = get_material_density
    get_material_rate: Callable[[str], float] = get_material_rate
