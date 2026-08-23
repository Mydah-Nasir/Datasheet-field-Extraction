"""Deterministic validation logic for normalized extraction results."""

from src.domain.schema import ExtractionField, ExtractionResult, FieldStatus
from src.domain.validation import (
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    ValidationStatus,
)


class Validator:
    """Validates an ExtractionResult deterministically."""

    def validate(self, extraction: ExtractionResult) -> ValidationResult:
        """Run all validation rules and return a ValidationResult."""
        issues: list[ValidationIssue] = []

        # 1. Required field checks
        # Based on typical engineering needs (tag, desc, dims)
        required_fields = {
            "tag_no": "Tag Number",
            "qty": "Quantity",
        }

        for field_attr, field_name in required_fields.items():
            field_obj: ExtractionField = getattr(extraction, field_attr)
            if field_obj.status == FieldStatus.MISSING or field_obj.value is None:
                issues.append(
                    ValidationIssue(
                        field=field_attr,
                        code="MISSING_REQUIRED_FIELD",
                        message=f"{field_name} is a required field but is missing.",
                        severity=ValidationSeverity.ERROR,
                    )
                )

        # 2. Positive value checks
        positive_numeric_fields = {
            "qty": "Quantity",
            "vessel_id_mm": "Vessel ID",
            "vessel_tl_tl_length_mm": "Vessel Length (TL-TL)",
            "shell_min_thk_mm": "Shell Min Thickness",
            "head_min_thk_mm": "Head Min Thickness",
            "weight_tons_each": "Weight",
        }

        for field_attr, field_name in positive_numeric_fields.items():
            field_obj: ExtractionField = getattr(extraction, field_attr)
            if field_obj.value is not None:
                try:
                    val = float(field_obj.value)
                    if val < 0:
                        issues.append(
                            ValidationIssue(
                                field=field_attr,
                                code="NEGATIVE_PHYSICAL_VALUE",
                                message=f"{field_name} must be a positive physical quantity.",
                                severity=ValidationSeverity.ERROR,
                            )
                        )
                except (ValueError, TypeError):
                    issues.append(
                        ValidationIssue(
                            field=field_attr,
                            code="INVALID_NUMERIC_VALUE",
                            message=f"{field_name} is not numeric.",
                            severity=ValidationSeverity.ERROR,
                        )
                    )

        # 2.5 Engineering plausibility checks (catch unit-conversion errors)
        engineering_ranges = {
            "weight_tons_each": (
                1,
                10000,
                "Weight in tons should be between 1 and 10,000 for pressure vessels. Possible unit-conversion error.",
            ),
            "vessel_id_mm": (
                100,
                20000,
                "Vessel ID should be between 100mm and 20,000mm for typical pressure vessels.",
            ),
            "vessel_tl_tl_length_mm": (
                500,
                200000,
                "Vessel length should be between 500mm and 200,000mm.",
            ),
            "shell_min_thk_mm": (1, 500, "Shell thickness should be between 1mm and 500mm."),
            "head_min_thk_mm": (1, 500, "Head thickness should be between 1mm and 500mm."),
        }

        for field_attr, (min_val, max_val, msg) in engineering_ranges.items():
            field_obj: ExtractionField = getattr(extraction, field_attr)
            if field_obj.value is not None:
                try:
                    val = float(field_obj.value)
                    if val > 0 and (val < min_val or val > max_val):
                        issues.append(
                            ValidationIssue(
                                field=field_attr,
                                code="ENGINEERING_RANGE_VIOLATION",
                                message=msg,
                                severity=ValidationSeverity.WARNING,
                            )
                        )
                except (ValueError, TypeError):
                    pass

        # 3. Overall status routing
        has_error_issues = any(i.severity == ValidationSeverity.ERROR for i in issues)

        # Check if any field is in a state requiring review (MISSING, AMBIGUOUS, CONFLICT)
        # Note: If a field is MISSING but not required, we still route to NEEDS_REVIEW so human can confirm.
        needs_review = False

        all_fields = [
            ("tag_no", extraction.tag_no),
            ("description", extraction.description),
            ("ref_data_sheet", extraction.ref_data_sheet),
            ("design_code", extraction.design_code),
            ("moc", extraction.moc),
            ("qty", extraction.qty),
            ("orientation", extraction.orientation),
            ("vessel_id_mm", extraction.vessel_id_mm),
            ("vessel_tl_tl_length_mm", extraction.vessel_tl_tl_length_mm),
            ("shell_min_thk_mm", extraction.shell_min_thk_mm),
            ("head_min_thk_mm", extraction.head_min_thk_mm),
            ("head_type", extraction.head_type),
            ("nozzle_type", extraction.nozzle_type),
            ("impact_tested", extraction.impact_tested),
            ("rt", extraction.rt),
            ("pwht", extraction.pwht),
            ("support_type", extraction.support_type),
            ("painting_external", extraction.painting.external),
            ("painting_internal", extraction.painting.internal),
            ("weight_tons_each", extraction.weight_tons_each),
        ]

        for field_attr, field in all_fields:
            if field.status in (FieldStatus.MISSING, FieldStatus.AMBIGUOUS, FieldStatus.CONFLICT):
                needs_review = True

            # Since validate_for_export requires all fields to be non-None, we must flag them here
            # to prevent bypassing the HITL loop and crashing the application.
            if field.value is None and field_attr not in required_fields:
                issues.append(
                    ValidationIssue(
                        field=field_attr,
                        code="MISSING_VALUE",
                        message=f"{field_attr} cannot be null for final export.",
                        severity=ValidationSeverity.ERROR,
                    )
                )

            # Check confidence scores (only for automated extractions, not user confirmed/corrected)
            from src.config import settings

            if (
                field.value is not None
                and field.status not in (FieldStatus.USER_CONFIRMED, FieldStatus.USER_CORRECTED)
                and field.confidence < settings.CONFIDENCE_THRESHOLD
            ):
                field.status = FieldStatus.AMBIGUOUS
                needs_review = True
                issues.append(
                    ValidationIssue(
                        field=field_attr,
                        code="LOW_CONFIDENCE",
                        message=f"Extraction confidence ({field.confidence}) is below threshold ({settings.CONFIDENCE_THRESHOLD}). Please verify.",
                        severity=ValidationSeverity.WARNING,
                    )
                )

        # Also, check if any field is INVALID directly in status
        if any(f.status == FieldStatus.INVALID for _, f in all_fields):
            needs_review = True

        if has_error_issues:
            # Depending on project routing, issues might mean NEEDS_REVIEW or INVALID.
            # We'll use NEEDS_REVIEW so HITL can correct it, per user prompt:
            # "INVALID → INVALID / NEEDS_REVIEW depending on the issue"
            # Since our issues are things a human can fix (e.g. wrong qty), route to review.
            status = ValidationStatus.NEEDS_REVIEW
        elif needs_review:
            status = ValidationStatus.NEEDS_REVIEW
        else:
            status = ValidationStatus.VALID

        return ValidationResult(
            status=status,
            normalized_extraction=extraction,
            issues=issues,
        )
