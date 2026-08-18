"""Deterministic normalization of extracted engineering fields."""

import copy
import re

from src.domain.schema import ExtractionField, ExtractionResult, FieldStatus, PaintingField


class Normalizer:
    """Idempotent normalizer for extraction results."""

    def normalize(self, extraction: ExtractionResult) -> ExtractionResult:
        """Deep copy and normalize all parameters in the extraction result."""
        result = copy.deepcopy(extraction)

        self._normalize_string_field(result.tag_no)
        self._normalize_string_field(result.description)
        self._normalize_string_field(result.ref_data_sheet)
        self._normalize_string_field(result.design_code)
        self._normalize_string_field(result.moc)

        self._normalize_numeric(result.qty, "unit")
        self._normalize_numeric(result.vessel_id_mm, "mm")
        self._normalize_numeric(result.vessel_tl_tl_length_mm, "mm")
        self._normalize_thickness(result.shell_min_thk_mm)
        self._normalize_thickness(result.head_min_thk_mm)
        self._normalize_numeric(result.weight_tons_each, "ton")

        self._normalize_string_field(result.head_type)
        self._normalize_nozzle_type(result.nozzle_type)

        self._normalize_boolean(result.impact_tested)
        self._normalize_boolean(result.pwht)

        self._normalize_orientation(result.orientation)

        self._normalize_string_field(result.rt)
        self._normalize_string_field(result.support_type)

        self._normalize_painting(result.painting)
        if hasattr(result, "pickling_passivation") and result.pickling_passivation is not None:
            self._normalize_pickling_passivation(result.pickling_passivation)

        return result

    def _normalize_string_field(self, field: ExtractionField[str]) -> None:
        """Normalize a generic string field (e.g. tag number)."""
        if field.status != FieldStatus.EXTRACTED and field.status != FieldStatus.NORMALIZED:
            return

        if not field.value or not isinstance(field.value, str):
            return

        # Strip leading/trailing whitespace
        normalized_str = field.value.strip()
        # Collapse multiple spaces
        normalized_str = re.sub(r"\s+", " ", normalized_str)

        if field.value != normalized_str:
            field.value = normalized_str
            field.status = FieldStatus.NORMALIZED
        elif field.status == FieldStatus.EXTRACTED:
            # Even if value hasn't changed textually, mark as NORMALIZED to show it passed this gate
            field.status = FieldStatus.NORMALIZED

    def _normalize_nozzle_type(self, field: ExtractionField[str]) -> None:
        """Normalize nozzle type specifications, preserving pressure classes, designations, and standards while removing formatting noise and duplicates."""
        if field.status != FieldStatus.EXTRACTED and field.status != FieldStatus.NORMALIZED:
            return

        if not field.value or not isinstance(field.value, str):
            return

        # Split on commas, semicolons, or newlines
        raw_items = re.split(r"[,;\n\r]+", field.value)
        cleaned_items = []
        seen_lower = set()

        for item in raw_items:
            # Strip whitespace and collapse multiple internal spaces
            cleaned = re.sub(r"\s+", " ", item).strip(" \t\n\r,-•*")
            if not cleaned:
                continue

            # Case-insensitive deduplication while preserving original casing and order
            key = cleaned.lower()
            if key not in seen_lower:
                seen_lower.add(key)
                cleaned_items.append(cleaned)

        if cleaned_items:
            normalized_str = ", ".join(cleaned_items)
        else:
            normalized_str = field.value.strip()

        if field.value != normalized_str:
            field.value = normalized_str
            field.status = FieldStatus.NORMALIZED
        elif field.status == FieldStatus.EXTRACTED:
            field.status = FieldStatus.NORMALIZED

    def _normalize_thickness(self, field: ExtractionField[float]) -> None:
        """Normalize thickness fields, ensuring the MINIMUM thickness is extracted."""
        # Idempotency check
        if field.status == FieldStatus.NORMALIZED:
            return

        if field.status != FieldStatus.EXTRACTED:
            return

        if field.value is None and not field.evidence:
            return

        evidence_text = ""
        if field.evidence:
            evidence_text = " ".join([e.text for e in field.evidence])

        val_str = str(field.value) if field.value is not None else ""

        # Pattern to match MIN / MINIMUM thickness: e.g. "HEAD TH. 29 (MIN. 22.88)" -> 22.88
        min_pattern = r"(?:\bMIN\.?|\bMINIMUM)(?:\s*(?:THK\.?|THICKNESS|TH\.?))?\s*:?\s*(\d+(?:\.\d+)?)"

        # Check field value string (in case LLM passed unparsed string like "29 (MIN. 22.88)")
        m_val = re.search(min_pattern, val_str, re.IGNORECASE)
        if m_val:
            field.value = float(m_val.group(1))
            field.status = FieldStatus.NORMALIZED
            return

        # Check evidence text (in case LLM extracted nominal 29 but evidence has "MIN. 22.88")
        if evidence_text:
            m_evi = re.search(min_pattern, evidence_text, re.IGNORECASE)
            if m_evi:
                field.value = float(m_evi.group(1))
                field.status = FieldStatus.NORMALIZED
                return

        # Fallback to standard numeric normalization in mm
        self._normalize_numeric(field, "mm")

    def _normalize_numeric(self, field: ExtractionField, target_unit: str) -> None:
        """Normalize a numeric field, examining evidence for units to convert if necessary."""
        # Idempotency check: do not apply mathematical scaling to an already normalized field
        if field.status == FieldStatus.NORMALIZED:
            return

        if field.status != FieldStatus.EXTRACTED:
            return

        if field.value is None:
            return

        original_value = field.value
        normalized_value = original_value

        # We rely on evidence to find units if the field value is already a pure number
        # Or if the field value is a string that Gemini accidentally provided
        evidence_text = ""
        if field.evidence:
            evidence_text = " ".join([e.text for e in field.evidence]).lower()

        # Parse value if it was provided as string from LLM
        if isinstance(normalized_value, str):
            # Clean commas and extract digits
            cleaned = normalized_value.replace(",", "").strip()
            match = re.search(r"[-+]?\d*\.\d+|\d+", cleaned)
            if match:
                normalized_value = float(match.group())
            else:
                return  # Cannot normalize

        # Convert numeric values safely
        try:
            val_float = float(normalized_value)
        except (ValueError, TypeError):
            return

        # Perform unit conversions based on evidence
        # Length conversions
        if target_unit == "mm":
            if " mm" in evidence_text or "mm " in evidence_text:
                pass  # Already mm
            elif " cm" in evidence_text or "cm " in evidence_text:
                val_float *= 10
            elif (" m" in evidence_text or "m " in evidence_text) and re.search(
                r"\bm\b", evidence_text
            ):
                val_float *= 1000

        # Weight conversions
        elif target_unit == "ton":
            if "ton" in evidence_text:
                pass  # Already tons
            elif "kg" in evidence_text:
                # Guard against double-conversion: if the model already converted
                # from kg to tons (e.g., 337,000 kg → 337), don't divide again.
                # If value >= 500, it is unconverted kg and needs division by 1000.
                if val_float >= 500:
                    val_float /= 1000

        # Attempt to retain integer type for qty
        if target_unit == "unit":
            try:
                normalized_value = int(val_float) if val_float.is_integer() else val_float
            except Exception:
                normalized_value = val_float
        else:
            normalized_value = val_float

        if field.value != normalized_value:
            field.value = normalized_value
            field.status = FieldStatus.NORMALIZED
        elif field.status == FieldStatus.EXTRACTED:
            field.status = FieldStatus.NORMALIZED

    def _normalize_boolean(self, field: ExtractionField[str]) -> None:
        """Normalize yes/no style boolean text."""
        if field.status != FieldStatus.EXTRACTED and field.status != FieldStatus.NORMALIZED:
            return

        if not field.value or not isinstance(field.value, str):
            return

        val_upper = field.value.strip().upper()

        normalized = field.value
        if val_upper in ("YES", "Y", "TRUE"):
            normalized = "YES"
        elif val_upper in ("NO", "N", "FALSE"):
            normalized = "NO"

        if field.value != normalized:
            field.value = normalized
            field.status = FieldStatus.NORMALIZED
        elif field.status == FieldStatus.EXTRACTED:
            field.status = FieldStatus.NORMALIZED

    def _normalize_orientation(self, field: ExtractionField[str]) -> None:
        """Normalize orientation enumerations."""
        if field.status != FieldStatus.EXTRACTED and field.status != FieldStatus.NORMALIZED:
            return

        if not field.value or not isinstance(field.value, str):
            return

        val_upper = field.value.strip().upper()

        normalized = field.value
        if val_upper in ("VERT", "VERTICAL", "V"):
            normalized = "VERTICAL"
        elif val_upper in ("HOR", "HORIZONTAL", "H"):
            normalized = "HORIZONTAL"

        if field.value != normalized:
            field.value = normalized
            field.status = FieldStatus.NORMALIZED
        elif field.status == FieldStatus.EXTRACTED:
            field.status = FieldStatus.NORMALIZED

    def _normalize_painting(self, painting: PaintingField) -> None:
        """Normalize painting sub-fields."""
        self._normalize_string_field(painting.external)
        self._normalize_string_field(painting.internal)

    def _normalize_pickling_passivation(self, field: ExtractionField[str]) -> None:
        """Normalize Pickling & Passivation specifications."""
        if not field.value or not isinstance(field.value, str):
            field.value = "N/A"
            field.status = FieldStatus.NORMALIZED
            return

        stripped = field.value.strip()
        if not stripped or stripped.upper() in ("NA", "N/A", "NONE", "NOT APPLICABLE", "-", "N.A."):
            field.value = "N/A"
            field.status = FieldStatus.NORMALIZED
        else:
            self._normalize_string_field(field)
