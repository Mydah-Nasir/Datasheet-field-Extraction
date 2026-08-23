"""Builder for transforming ExtractionResults into AnnexureRecords."""

from src.annexure.models import AnnexureRecord
from src.domain.schema import ExtractionResult, FieldStatus


class AnnexureExportError(Exception):
    """Raised when an ExtractionResult is not eligible for export."""

    pass


def validate_for_export(result: ExtractionResult) -> None:
    """Check if the final result is eligible for export.

    Raises:
        AnnexureExportError: If any field is MISSING, AMBIGUOUS, INVALID, or CONFLICT.
    """
    fields_to_check = [
        ("tag_no", result.tag_no),
        ("description", result.description),
        ("ref_data_sheet", result.ref_data_sheet),
        ("design_code", result.design_code),
        ("moc", result.moc),
        ("qty", result.qty),
        ("orientation", result.orientation),
        ("vessel_id_mm", result.vessel_id_mm),
        ("vessel_tl_tl_length_mm", result.vessel_tl_tl_length_mm),
        ("shell_min_thk_mm", result.shell_min_thk_mm),
        ("head_min_thk_mm", result.head_min_thk_mm),
        ("head_type", result.head_type),
        ("nozzle_type", result.nozzle_type),
        ("impact_tested", result.impact_tested),
        ("rt", result.rt),
        ("pwht", result.pwht),
        ("support_type", result.support_type),
        ("weight_tons_each", result.weight_tons_each),
        ("painting_external", result.painting.external),
        ("painting_internal", result.painting.internal),
    ]

    invalid_statuses = {
        FieldStatus.MISSING,
        FieldStatus.AMBIGUOUS,
        FieldStatus.INVALID,
        FieldStatus.CONFLICT,
    }

    for name, field in fields_to_check:
        if field.status in invalid_statuses:
            raise AnnexureExportError(f"Field '{name}' has unresolved status: {field.status}")
        if field.value is None:
            raise AnnexureExportError(f"Field '{name}' has a null value")


def build_annexure(result: ExtractionResult) -> AnnexureRecord:
    """Build a final AnnexureRecord from a validated ExtractionResult."""
    validate_for_export(result)

    pickling_field = getattr(result, "pickling_passivation", None)
    pickling_val = pickling_field.value if (pickling_field and pickling_field.value) else "N/A"

    return AnnexureRecord(
        tag_no=result.tag_no.value,
        description=result.description.value,
        ref_data_sheet=result.ref_data_sheet.value,
        design_code=result.design_code.value,
        moc=result.moc.value,
        qty=result.qty.value,
        orientation=result.orientation.value,
        vessel_id_mm=result.vessel_id_mm.value,
        vessel_tl_tl_length_mm=result.vessel_tl_tl_length_mm.value,
        shell_min_thk_mm=result.shell_min_thk_mm.value,
        head_min_thk_mm=result.head_min_thk_mm.value,
        head_type=result.head_type.value,
        nozzle_type=result.nozzle_type.value,
        impact_tested=result.impact_tested.value,
        rt=result.rt.value,
        pwht=result.pwht.value,
        support_type=result.support_type.value,
        painting_external=result.painting.external.value,
        painting_internal=result.painting.internal.value,
        pickling_passivation=pickling_val,
        weight_tons_each=result.weight_tons_each.value,
    )


def build_annexures(results: list[ExtractionResult]) -> list[AnnexureRecord]:
    """Build multiple AnnexureRecords from a list of validated ExtractionResults."""
    return [build_annexure(r) for r in results]
