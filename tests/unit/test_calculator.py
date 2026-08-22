"""Unit tests for Shell Weight & Cost Calculator module."""

import math
import pytest
from pydantic import ValidationError

from src.calculator import (
    BENDING_SIDES_FACTOR,
    SINGLE_PLATE_FACTOR,
    CalculatorLookups,
    ShellCalculationInput,
    ShellCalculationResult,
    calculate_cost,
    calculate_material_weight,
    calculate_plate_length_per_shell,
    calculate_shell_cost,
    calculate_total_weight_actual,
    calculate_wt_each,
    get_bending_allowance,
    get_material_density,
    get_material_rate,
)


class TestWorkedVerificationCase:
    """Test using the exact known-good values provided by the specification."""

    def test_worked_example_verification(self):
        """
        Verification test:
        ID = 5800 mm
        Thickness = 30 mm
        T/T Length = 54870 mm
        Bending Allowance = 1.0 (multiplier factor)
        -> plate_length_per_shell = (5800 + 30) * pi * 1.0 * 2 = 36,630.97 mm
        """
        # Step 1: Plate length per shell
        plate_length = calculate_plate_length_per_shell(
            vessel_id_mm=5800.0,
            shell_thickness_mm=30.0,
            bending_allowance_mm=1.0,
        )
        expected_len = (5800.0 + 30.0) * math.pi * 1.0 * 2.0
        assert pytest.approx(plate_length, rel=1e-4) == expected_len

        # Step 2: Total actual weight (using standard steel density 7.85)
        total_weight = calculate_total_weight_actual(
            plate_length_per_shell_mm=plate_length,
            tl_tl_length_mm=54870.0,
            shell_thickness_mm=30.0,
            density_f2=7.85,
        )
        expected_wt = (plate_length * 0.001) * (54870.0 * 0.001) * 30.0 * 7.85
        assert pytest.approx(total_weight, rel=1e-4) == expected_wt


class TestFormulaFunctions:
    """Test individual calculation formula functions."""

    def test_calculate_plate_length_with_bending_allowance(self):
        """Test plate length calculation: (ID + thk) * pi * allowance * 2."""
        # ID=4000, thk=50, allowance=20, sides=2
        # (4000 + 50) * pi * 20 * 2 = 4050 * pi * 40
        res = calculate_plate_length_per_shell(
            vessel_id_mm=4000.0,
            shell_thickness_mm=50.0,
            bending_allowance_mm=20.0,
            bending_sides_factor=2.0,
        )
        expected = (4050.0 * math.pi) * 20.0 * 2.0
        assert pytest.approx(res, rel=1e-5) == expected

    def test_calculate_wt_each(self):
        """Test flat stock plate weight calculation."""
        # Plate 2500 mm x 8000 mm x 30 mm, density 7.85
        # 2.5 m * 8.0 m * 30 mm * 7.85 = 4710 kg
        res = calculate_wt_each(
            plate_width_mm=2500.0,
            plate_length_h_mm=8000.0,
            shell_thickness_mm=30.0,
            density_f2=7.85,
            single_plate_factor=1.0,
        )
        assert pytest.approx(res, rel=1e-5) == 4710.0

    def test_calculate_material_weight(self):
        """Test total procurement material weight across units."""
        res = calculate_material_weight(qty=3, wt_each_kg=4710.0)
        assert res == 14130.0

    def test_calculate_cost(self):
        """Test cost calculation."""
        res = calculate_cost(material_rate_per_kg=3.50, material_weight_kg=14130.0)
        assert pytest.approx(res, rel=1e-5) == 49455.0


class TestLookupsAndDependencyInjection:
    """Test lookup tables and dependency injection support."""

    def test_get_bending_allowance_rules(self):
        """Thin plates (<40mm) return 1.0 default, thick plates (>=40mm) return chart value."""
        assert get_bending_allowance(30.0) == 1.0
        assert get_bending_allowance(39.9) == 1.0
        assert get_bending_allowance(40.0) == 15.0
        assert get_bending_allowance(50.0) == 20.0
        assert get_bending_allowance(120.0) == 50.0

    def test_get_material_density_lookup(self):
        """MOC lookup returns correct density."""
        assert get_material_density("SA 516 Gr 70N") == 7.85
        assert get_material_density("SA 240 TP 316L") == 8.00
        assert get_material_density("Unknown Alloy") == 7.85

    def test_get_material_rate_lookup(self):
        """MOC lookup returns default rate."""
        assert get_material_rate("SA 516 Gr 70N-HIC") == 3.20
        assert get_material_rate("SA 240 TP 304") == 5.80

    def test_calculate_shell_cost_with_custom_lookups(self):
        """Test dependency injection with custom lookup callbacks."""
        custom_lookups = CalculatorLookups(
            get_bending_allowance=lambda thk: 100.0,
            get_material_density=lambda moc: 8.50,
            get_material_rate=lambda moc: 10.0,
        )

        record = {
            "vessel_id_mm": 5000.0,
            "tl_tl_length_mm": 10000.0,
            "shell_thickness_mm": 25.0,
            "moc": "CUSTOM ALLOY",
            "qty": 2,
            "plate_width_mm": 2000.0,
            "plate_length_h_mm": 6000.0,
        }

        result = calculate_shell_cost(record, lookups=custom_lookups)

        assert isinstance(result, ShellCalculationResult)
        # Bending allowance should have used 100 * 2 = 200 mm
        expected_len = (5000.0 + 25.0) * math.pi * 100.0 * 2.0
        assert pytest.approx(result.plate_length_per_shell_mm, rel=1e-4) == expected_len
        # Cost should have used rate=10.0
        expected_wt_each = 2.0 * 6.0 * 25.0 * 8.50
        expected_mat_wt = 2 * expected_wt_each
        assert pytest.approx(result.material_weight_kg, rel=1e-4) == expected_mat_wt
        assert pytest.approx(result.cost, rel=1e-4) == expected_mat_wt * 10.0


class TestInputValidations:
    """Test division-by-zero, missing, and negative input guards."""

    def test_negative_or_zero_dimensions(self):
        with pytest.raises(ValueError, match="vessel_id_mm must be > 0"):
            calculate_plate_length_per_shell(vessel_id_mm=0, shell_thickness_mm=30)

        with pytest.raises(ValueError, match="shell_thickness_mm must be > 0"):
            calculate_plate_length_per_shell(vessel_id_mm=5000, shell_thickness_mm=-5)

        with pytest.raises(ValueError, match="tl_tl_length_mm must be > 0"):
            calculate_total_weight_actual(
                plate_length_per_shell_mm=10000,
                tl_tl_length_mm=0,
                shell_thickness_mm=30,
                density_f2=7.85,
            )

        with pytest.raises(ValueError, match="qty must be >= 1"):
            calculate_material_weight(qty=0, wt_each_kg=500)

        with pytest.raises(ValueError, match="material_rate_per_kg must be >= 0"):
            calculate_cost(material_rate_per_kg=-1.0, material_weight_kg=1000)

    def test_pydantic_schema_validation(self):
        with pytest.raises(ValidationError):
            ShellCalculationInput(
                vessel_id_mm=-100,
                tl_tl_length_mm=1000,
                shell_thickness_mm=30,
                moc="",
                qty=0,
                plate_width_mm=2000,
                plate_length_h_mm=6000,
                material_rate_per_kg=2.5,
            )
