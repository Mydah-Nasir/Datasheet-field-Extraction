"""Deterministic normalization of extracted engineering fields."""

import copy
import re

from src.domain.schema import ExtractionField, ExtractionResult, FieldStatus, PaintingField


class Normalizer:
    """Idempotent normalizer for extraction results."""

    def normalize(self, extraction: ExtractionResult) -> ExtractionResult:
        """Deep copy and normalize all parameters in the extraction result."""
        result = copy.deepcopy(extraction)

        self._normalize_string_field(result.tag_no, label_prefixes=["TAG NO\\.?", "TAG NUMBER", "TAG", "ITEM NO\\.?", "EQUIPMENT NO\\.?"])
        self._normalize_string_field(result.description, label_prefixes=["DESCRIPTION", "ITEM DESCRIPTION", "SERVICE", "EQUIPMENT NAME"])
        self._normalize_string_field(result.ref_data_sheet, label_prefixes=["REF DATA SHEET", "REFERENCE DATA SHEET", "DATA SHEET NO\\.?", "DS NO\\.?", "DWG NO\\.?", "DRAWING NO\\.?"])
        self._normalize_string_field(result.design_code, label_prefixes=["DESIGN CODE", "CODE", "DESIGN SPECIFICATION", "APPLICABLE CODE"])
        self._normalize_string_field(result.moc, label_prefixes=["MOC", "MATERIAL OF CONSTRUCTION", "MATERIAL", "SHELL MATERIAL"])

        self._normalize_numeric(result.qty, "unit")
        self._normalize_numeric(result.vessel_id_mm, "mm")
        self._normalize_numeric(result.vessel_tl_tl_length_mm, "mm")
        self._normalize_thickness(result.shell_min_thk_mm)
        self._normalize_thickness(result.head_min_thk_mm)
        self._normalize_weight(result.weight_tons_each)

        self._normalize_string_field(result.head_type, label_prefixes=["HEAD TYPE", "TYPE OF HEAD", "DISH TYPE", "CLOSURE TYPE"])
        self._normalize_nozzle_type(result.nozzle_type)

        self._normalize_boolean(result.impact_tested)
        self._normalize_boolean(result.pwht)

        self._normalize_orientation(result.orientation)

        self._normalize_string_field(result.rt, label_prefixes=["RT", "RADIOGRAPHY", "NDE", "NDT"])
        self._normalize_string_field(result.support_type, label_prefixes=["TYPE OF SUPPORT", "SUPPORT TYPE", "SUPPORT"])

        self._normalize_painting(result.painting)
        if hasattr(result, "pickling_passivation") and result.pickling_passivation is not None:
            self._normalize_pickling_passivation(result.pickling_passivation)

        return result

    def _normalize_string_field(self, field: ExtractionField[str], label_prefixes: list[str] | None = None) -> None:
        """Normalize a generic string field (e.g. tag number). If value is missing, attempt to extract from evidence."""
        if field.status == FieldStatus.NORMALIZED:
            return

        # If value is missing but evidence exists, try to recover value from evidence
        if (field.value is None or not str(field.value).strip()) and field.evidence:
            raw_evidence = " ".join([e.text for e in field.evidence if e.text]).strip()
            if raw_evidence:
                cleaned_val = raw_evidence
                if label_prefixes:
                    for prefix in label_prefixes:
                        cleaned_val = re.sub(rf"^(?:{prefix})\s*(?:[:=]\s*|\s+)", "", cleaned_val, flags=re.IGNORECASE).strip()
                if cleaned_val:
                    field.value = cleaned_val
                    field.status = FieldStatus.NORMALIZED

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
            field.status = FieldStatus.NORMALIZED

    def _normalize_nozzle_type(self, field: ExtractionField[str]) -> None:
        """Normalize nozzle type specifications, preserving pressure classes, designations, and standards while removing formatting noise and duplicates."""
        if field.status == FieldStatus.NORMALIZED:
            return

        # Recover from evidence if value is missing
        if (field.value is None or not str(field.value).strip()) and field.evidence:
            raw_evidence = " ".join([e.text for e in field.evidence if e.text]).strip()
            if raw_evidence:
                field.value = raw_evidence
                field.status = FieldStatus.NORMALIZED

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

        if field.value is None and not field.evidence:
            return

        evidence_text = ""
        if field.evidence:
            evidence_text = " ".join([e.text for e in field.evidence if e.text])

        val_str = str(field.value) if field.value is not None else ""

        # Pattern 1: Number before MIN. THK. e.g. "26 [1.024"] MIN. THK. AFTER FORMING" or "26 MIN. THK."
        pre_min_pattern = r"(\d+(?:\.\d+)?)\s*(?:\[[^\]]*\])?\s*(?:MIN\.?\s*THK\.?|MIN\.?\s*THICKNESS|MINIMUM\s*THK\.?)"
        for src in (val_str, evidence_text):
            if src:
                m = re.search(pre_min_pattern, src, re.IGNORECASE)
                if m:
                    field.value = float(m.group(1))
                    field.status = FieldStatus.NORMALIZED
                    return

        # Pattern 2: MIN / MINIMUM thickness e.g. "HEAD TH. 29 (MIN. 22.88)" -> 22.88
        min_pattern = r"(?:\bMIN\.?|\bMINIMUM)(?:\s*(?:THK\.?|THICKNESS|TH\.?))?\s*:?\s*(\d+(?:\.\d+)?)"
        for src in (val_str, evidence_text):
            if src:
                m = re.search(min_pattern, src, re.IGNORECASE)
                if m:
                    field.value = float(m.group(1))
                    field.status = FieldStatus.NORMALIZED
                    return

        # Pattern 3: Shell course dimension "<Length> x <Thickness> THK." e.g. "18607.2 [61'-0 5/8"] x 28.6 [1.126"] THK."
        course_pattern = r"x\s*(\d+(?:\.\d+)?)\s*(?:\[[^\]]*\])?\s*(?:THK\.?|THICKNESS|TH\.?)"
        for src in (val_str, evidence_text):
            if src:
                m = re.search(course_pattern, src, re.IGNORECASE)
                if m:
                    field.value = float(m.group(1))
                    field.status = FieldStatus.NORMALIZED
                    return

        # Pattern 4: General thickness callouts e.g. "THK. 28.6", "28.6 mm THK.", "TH. 25.0"
        if field.value is None and evidence_text:
            thk_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\[[^\]]*\])?\s*(?:mm\s*)?(?:THK\.?|THICKNESS)", evidence_text, re.IGNORECASE)
            if not thk_match:
                thk_match = re.search(r"(?:THK\.?|THICKNESS|TH\.?)\s*:?\s*(\d+(?:\.\d+)?)", evidence_text, re.IGNORECASE)
            if not thk_match:
                thk_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mm\b)", evidence_text, re.IGNORECASE)
            if not thk_match:
                thk_match = re.search(r"[-+]?\d*\.\d+|\d+", evidence_text)
            if thk_match:
                field.value = float(thk_match.group(1) if thk_match.lastindex else thk_match.group(0))
                field.status = FieldStatus.NORMALIZED
                return

        # Fallback to standard numeric normalization in mm
        self._normalize_numeric(field, "mm")

    def _normalize_weight(self, field: ExtractionField[float]) -> None:
        """Normalize vessel weight in metric tons according to client specification:
        1. Prioritize Fabricated Weight if present in evidence
        2. Fallback to Empty Weight if Fabricated Weight is not present
        3. Convert kg to metric tons (divide by 1000 if >= 500)
        """
        if field.status == FieldStatus.NORMALIZED:
            return

        evidence_text = ""
        if field.evidence:
            evidence_text = " ".join([e.text for e in field.evidence if e.text])

        # If evidence text is present, inspect for Fabricated Weight first, then Empty Weight
        if evidence_text:
            # 1. Search for Fabricated Weight: e.g. "FABRICATED: 418,000 KG" or "FABRICATED WT: 350 TONS"
            fab_pattern = r"(?:FABRICATED|FABRICATION|FAB\.?\s*WT\.?|FABRICATED\s*WEIGHT|SHOP\s*TEST\s*WEIGHT)\s*[:=\-]?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)"
            m_fab = re.search(fab_pattern, evidence_text, re.IGNORECASE)
            if m_fab:
                val_raw = float(m_fab.group(1).replace(",", ""))
                # If unit is kg or value >= 500, convert to metric tons
                if "kg" in evidence_text.lower() or val_raw >= 500:
                    val_raw /= 1000.0
                field.value = val_raw
                field.status = FieldStatus.NORMALIZED
                return

            # 2. Search for Empty Weight: e.g. "EMPTY: 380,000 KG" or "EMPTY WEIGHT: 85 TONS"
            empty_pattern = r"(?:EMPTY|EMPTY\s*WT\.?|EMPTY\s*WEIGHT|DRY\s*WEIGHT|ERECTED\s*WEIGHT|NET\s*WEIGHT)\s*[:=\-]?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)"
            m_empty = re.search(empty_pattern, evidence_text, re.IGNORECASE)
            if m_empty:
                val_raw = float(m_empty.group(1).replace(",", ""))
                if "kg" in evidence_text.lower() or val_raw >= 500:
                    val_raw /= 1000.0
                field.value = val_raw
                field.status = FieldStatus.NORMALIZED
                return

        # Fallback to standard numeric normalization for tons
        self._normalize_numeric(field, "ton")

    def _normalize_numeric(self, field: ExtractionField, target_unit: str) -> None:
        """Normalize a numeric field, examining evidence for units to convert if necessary or recovering value from evidence."""
        # Idempotency check: do not apply mathematical scaling to an already normalized field
        if field.status == FieldStatus.NORMALIZED:
            return

        evidence_text = ""
        if field.evidence:
            evidence_text = " ".join([e.text for e in field.evidence if e.text]).lower()

        # If field.value is None or empty, recover from evidence text
        if field.value is None or (isinstance(field.value, str) and not field.value.strip()):
            if not evidence_text:
                return
            match = re.search(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?|\d*\.\d+", evidence_text)
            if match:
                cleaned_num = match.group().replace(",", "")
                try:
                    field.value = float(cleaned_num)
                    field.status = FieldStatus.NORMALIZED
                except (ValueError, TypeError):
                    return
            else:
                return

        original_value = field.value
        normalized_value = original_value

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
            if " mm" in evidence_text or "mm " in evidence_text or "mm" in evidence_text:
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
        """Normalize yes/no style boolean text, recovering from evidence if value is missing."""
        if field.status == FieldStatus.NORMALIZED:
            return

        evidence_text = ""
        if field.evidence:
            evidence_text = " ".join([e.text for e in field.evidence if e.text])

        # If value is missing, check evidence for YES/NO patterns
        if not field.value or not str(field.value).strip():
            if evidence_text:
                no_pair_pattern = r"(?:◯|○|□|\[\s*\]|\(\s*\))\s*YES\b[^\n\r]*(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))\s*NO\b"
                yes_pair_pattern = r"(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))\s*YES\b[^\n\r]*(?:◯|○|□|\[\s*\]|\(\s*\))\s*NO\b"
                is_no_pair = bool(re.search(no_pair_pattern, evidence_text, re.IGNORECASE))
                is_yes_pair = bool(re.search(yes_pair_pattern, evidence_text, re.IGNORECASE))

                if is_no_pair and not is_yes_pair:
                    field.value = "NO"
                    field.status = FieldStatus.NORMALIZED
                    return
                if is_yes_pair and not is_no_pair:
                    field.value = "YES"
                    field.status = FieldStatus.NORMALIZED
                    return

                no_direct = r"(?:(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))\s*NO\b|\bNO\s*(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))|(?<!\()\b(?:IT|IMPACT\s*TEST(?:ING|ED)?|PWHT)\s*[:=\-]\s*NO\b)"
                yes_direct = r"(?:(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))\s*YES\b|\bYES\s*(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))|(?<!\()\b(?:IT|IMPACT\s*TEST(?:ING|ED)?|PWHT)\s*[:=\-]\s*YES\b)"
                if re.search(yes_direct, evidence_text, re.IGNORECASE) and not re.search(no_direct, evidence_text, re.IGNORECASE):
                    field.value = "YES"
                    field.status = FieldStatus.NORMALIZED
                    return
                if re.search(no_direct, evidence_text, re.IGNORECASE) and not re.search(yes_direct, evidence_text, re.IGNORECASE):
                    field.value = "NO"
                    field.status = FieldStatus.NORMALIZED
                    return
            return

        val_upper = str(field.value).strip().upper()

        normalized = str(field.value).strip()
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
        """Normalize orientation enumerations, recovering from evidence if value is missing."""
        if field.status == FieldStatus.NORMALIZED:
            return

        evidence_text = ""
        if field.evidence:
            evidence_text = " ".join([e.text for e in field.evidence if e.text]).upper()

        # Recover from evidence if value is missing
        if not field.value or not str(field.value).strip():
            if evidence_text:
                if re.search(r"\b(?:VERT|VERTICAL|V)\b", evidence_text):
                    field.value = "VERTICAL"
                    field.status = FieldStatus.NORMALIZED
                    return
                elif re.search(r"\b(?:HOR|HORIZ|HORIZONTAL|H)\b", evidence_text):
                    field.value = "HORIZONTAL"
                    field.status = FieldStatus.NORMALIZED
                    return
            return

        val_upper = str(field.value).strip().upper()

        normalized = str(field.value).strip()
        if val_upper in ("VERT", "VERTICAL", "V"):
            normalized = "VERTICAL"
        elif val_upper in ("HOR", "HORIZONTAL", "H", "HORIZ"):
            normalized = "HORIZONTAL"

        if field.value != normalized:
            field.value = normalized
            field.status = FieldStatus.NORMALIZED
        elif field.status == FieldStatus.EXTRACTED:
            field.status = FieldStatus.NORMALIZED

    def _normalize_painting(self, painting: PaintingField) -> None:
        """Normalize painting sub-fields."""
        self._normalize_string_field(painting.external, label_prefixes=["EXTERNAL PAINTING", "EXTERNAL", "PAINTING"])
        self._normalize_string_field(painting.internal, label_prefixes=["INTERNAL PAINTING", "INTERNAL", "LINING"])

    def _normalize_pickling_passivation(self, field: ExtractionField[str]) -> None:
        """Normalize Pickling & Passivation specifications."""
        if field.status == FieldStatus.NORMALIZED:
            return

        if not field.value or not isinstance(field.value, str):
            if field.evidence:
                evi_text = " ".join([e.text for e in field.evidence if e.text]).strip()
                if evi_text:
                    stripped_evi = evi_text.upper()
                    if stripped_evi in ("NA", "N/A", "NONE", "NOT APPLICABLE", "-", "N.A."):
                        field.value = "N/A"
                    else:
                        field.value = evi_text
                    field.status = FieldStatus.NORMALIZED
                    return
            field.value = "N/A"
            field.status = FieldStatus.NORMALIZED
            return

        stripped = field.value.strip()
        if not stripped or stripped.upper() in ("NA", "N/A", "NONE", "NOT APPLICABLE", "-", "N.A."):
            field.value = "N/A"
            field.status = FieldStatus.NORMALIZED
        else:
            self._normalize_string_field(field, label_prefixes=["PICKLING & PASSIVATION", "PRESERVATION", "PICKLING", "PASSIVATION"])
