"""Gemini Document Extraction Service."""

import json
import logging
import re
import time
from tenacity import retry, stop_after_attempt, wait_exponential

# We are using the recommended google-genai SDK
import google.genai as genai
from google.genai import types
from pydantic import ValidationError

from src.config import settings
from src.document import IngestedDocument
from src.domain.schema import ExtractionResult, FieldStatus
from src.extraction.errors import (
    ExtractionAuthError,
    ExtractionParseError,
    ExtractionTimeoutError,
    GeminiExtractionError,
)
from src.extraction.prompt import EXTRACTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Second-pass prompt for verifying boolean checkbox fields.
# This prompt is deliberately long and repetitive to force the model to
# reason carefully about each checkbox row independently.
BOOLEAN_VERIFICATION_PROMPT = """You are a precision inspector verifying checkbox and radio-button values on an engineering mechanical datasheet.

CRITICAL CONTEXT:
Engineering datasheets have a section (often titled "DESIGN CONDITIONS" or similar) that contains
multiple YES/NO selections arranged in SEPARATE, INDEPENDENT rows. Each row is a DIFFERENT field.
You MUST read each row's selection INDEPENDENTLY. The value of one row tells you NOTHING about another row.

COMMON ROWS (each is independent):
- PWHT (Post Weld Heat Treatment)
- IMPACT TESTING (or "IT" or "IMPACT TEST")
- WET H2S / SOUR SERVICE (or "WET SOUR")
- RADIOGRAPHY (or "RT")
- STRESS RELIEF

CRITICAL: RADIO BUTTONS VS CHECKBOXES
Many datasheets (e.g. Saudi Aramco, JGC) use circular RADIO BUTTONS for the YES/NO options:
- `◯` = EMPTY / UNSELECTED circle.
- `◉` (or circle with a solid black dot/bullet in center, or filled circle) = SELECTED / MARKED.
- `☐` = UNCHECKED square box.
- `☑` / `☒` = CHECKED square box.

MANDATORY PROCEDURE — Follow these steps IN ORDER:

STEP 1: Locate the design conditions / checkbox section on the datasheet.
STEP 2: Identify the column layout above the YES/NO options (typically LEFT=YES, RIGHT=NO).
STEP 3: For EACH row in that section:
   a) Read the LABEL text on the left side of the row (e.g., "PWHT", "IMPACT TESTING (IT):", etc.)
   b) Trace HORIZONTALLY across THAT ROW ONLY from the label to the YES and NO circles/boxes
   c) Identify the symbol at YES: is it `◯` (empty circle) or `◉` (circle with dot)?
   d) Identify the symbol at NO: is it `◯` (empty circle) or `◉` (circle with dot)?
   e) Note: If you see `◯ YES` and `◉ NO`, then NO is selected!
   f) Note: If you see `◉ YES` and `◯ NO`, then YES is selected!
   g) Note: A square checkbox like `☑ CODE` on the same row does NOT mean "YES" to impact testing.
   h) Write it out as: "Row: [LABEL] → YES is [◯ empty / ◉ dot], NO is [◯ empty / ◉ dot] → Winner is [YES or NO]"
STEP 4: Answer the specific questions below.

ABSOLUTE RULES:
- Each row is COMPLETELY INDEPENDENT.
- "PWHT: YES" does NOT imply "IMPACT TESTING: YES". On many vessels, PWHT is YES but IMPACT TESTING is NO.
- "WET SOUR: YES" does NOT imply "IMPACT TESTING: YES".
- If the dot is inside the NO circle (`◉ NO`), then impact_tested = "NO".
- If the dot is inside the YES circle (`◉ YES`), then impact_tested = "YES".
- Do NOT mistake the square `☑ CODE` checkbox as "YES".

Respond ONLY in this exact JSON format:
{
  "column_layout": "describe which column is YES and which is NO (e.g., LEFT=YES, RIGHT=NO)",
  "step_by_step_rows": [
    {
      "row_label": "exact label text",
      "yes_symbol": "◯ empty or ◉ dot or other",
      "no_symbol": "◯ empty or ◉ dot or other",
      "marked_column": "YES or NO",
      "mark_description": "describe exact visual appearance (e.g., ◯ empty circle before YES, ◉ circle with black center dot before NO, ☑ checked box for CODE)"
    }
  ],
  "impact_tested": "YES or NO",
  "impact_tested_reasoning": "I traced the IMPACT TESTING row horizontally: YES has [symbol], NO has [symbol], so impact_tested is [YES/NO]",
  "pwht": "YES or NO",
  "pwht_reasoning": "I traced the PWHT row horizontally: YES has [symbol], NO has [symbol], so pwht is [YES/NO]"
}"""

# Number of independent verification calls for majority voting
_BOOLEAN_VERIFY_VOTES = 3


class GeminiExtractionService:
    """Service to extract 19 engineering parameters using Google Gemini."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        """Initialize the Gemini extraction service.

        Args:
            api_key: Gemini API key. Defaults to settings.GEMINI_API_KEY.
            model_name: Gemini model name. Defaults to settings.GEMINI_MODEL.
        """
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model_name = model_name if model_name is not None else settings.GEMINI_MODEL

        if not self.api_key:
            raise ExtractionAuthError("GEMINI_API_KEY is missing or empty.")

        # Initialize the synchronous google-genai client
        # NOTE: timeout is in MILLISECONDS for the google-genai SDK
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                api_version="v1beta",
                timeout=600_000,  # 600 seconds = 10 minutes
            ),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=20),
        reraise=True
    )
    def extract(self, document: IngestedDocument) -> ExtractionResult:
        """Extract parameters from an ingested document using Gemini."""
        start_time = time.time()
        logger.info(f"Starting Gemini extraction for document: {document.metadata.document_id}")

        uploaded_file = None
        try:
            # 1. Upload original document directly to Gemini File API
            logger.debug(f"Uploading file to Gemini: {document.file_path}")
            uploaded_file = self.client.files.upload(
                file=document.file_path,
                config=types.UploadFileConfig(
                    mime_type="application/pdf"
                    if document.metadata.file_extension.lower() == "pdf"
                    else None
                ),
            )

            # 1.5 Wait for file processing (crucial for multi-page PDFs)
            logger.debug(f"Waiting for Gemini file {uploaded_file.name} to process...")
            while "PROCESSING" in str(uploaded_file.state):
                time.sleep(2)
                uploaded_file = self.client.files.get(name=uploaded_file.name)

            if "FAILED" in str(uploaded_file.state):
                raise GeminiExtractionError("Gemini failed to process the uploaded file.")

            logger.debug(f"File ready: {uploaded_file.name}")

            # 2. Configure generation with strict structured output (JSON Schema via Pydantic)
            config = types.GenerateContentConfig(
                system_instruction=EXTRACTION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=ExtractionResult,
                temperature=0.0,  # Deterministic extraction
                thinking_config=types.ThinkingConfig(
                    thinking_budget=1024,
                ),
            )

            # 3. Call the model for full extraction
            logger.debug(f"Calling Gemini model: {self.model_name}")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[uploaded_file],
                config=config,
            )

            # 4. Parse the structured Pydantic response
            if not response.text:
                raise ExtractionParseError("Gemini returned an empty response.")

            if hasattr(response, "parsed") and response.parsed:
                result = response.parsed
                if not isinstance(result, ExtractionResult):
                    result = ExtractionResult.model_validate(result)
            else:
                result = ExtractionResult.model_validate_json(response.text)

            # 5. Multi-pass verification of boolean checkbox fields
            # The model frequently confuses adjacent checkboxes on engineering drawings.
            # We run multiple independent verification calls and use majority voting
            # combined with evidence cross-checking.
            result = self._verify_boolean_fields(uploaded_file, result)

            duration = time.time() - start_time
            logger.info(
                f"Extraction successful for {document.metadata.document_id} in {duration:.2f}s"
            )

            return result

        except genai.errors.APIError as e:
            # Handle standard GenAI API errors (auth, timeouts, etc)
            err_msg = str(e).lower()
            if "key" in err_msg or "auth" in err_msg:
                raise ExtractionAuthError(f"Gemini authentication failed: {e}") from e
            elif "timeout" in err_msg or "deadline" in err_msg:
                raise ExtractionTimeoutError(f"Gemini API timed out: {e}") from e
            else:
                raise GeminiExtractionError(f"Gemini API error: {e}") from e

        except ValidationError as e:
            # Handle Pydantic parse failures if Gemini hallucinates an invalid JSON shape
            raise ExtractionParseError(f"Failed to parse Gemini output into schema: {e}") from e

        except Exception as e:
            # Catch-all
            if isinstance(e, (GeminiExtractionError, ExtractionParseError)):
                raise
            raise GeminiExtractionError(f"Unexpected extraction error: {e}") from e

        finally:
            # 6. Cleanup: Always delete the uploaded file from Gemini storage
            if uploaded_file:
                try:
                    self.client.files.delete(name=uploaded_file.name)
                    logger.debug(f"Cleaned up Gemini file: {uploaded_file.name}")
                except Exception as cleanup_err:
                    logger.warning(
                        f"Failed to clean up Gemini file {uploaded_file.name}: {cleanup_err}"
                    )

    @staticmethod
    def _check_evidence_contradiction(field) -> str | None:
        """Check if a boolean field's evidence text contradicts its extracted value.

        Returns the value the evidence suggests ('YES' or 'NO'), or None if inconclusive.
        """
        if not field.evidence or not field.value:
            return None

        value_upper = field.value.strip().upper()
        # Combine all evidence text
        evidence_text = " ".join(e.text for e in field.evidence)

        import re

        # Strict radio-button / checkbox pair patterns
        # 1. (empty YES) followed by (selected NO) -> unequivocally NO
        no_pair_pattern = (
            r"(?:◯|○|□|\[\s*\]|\(\s*\))\s*YES\b[^\n\r]*(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))\s*NO\b"
        )
        # 2. (selected YES) followed by (empty NO) -> unequivocally YES
        yes_pair_pattern = (
            r"(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))\s*YES\b[^\n\r]*(?:◯|○|□|\[\s*\]|\(\s*\))\s*NO\b"
        )

        is_no_pair = bool(re.search(no_pair_pattern, evidence_text, re.IGNORECASE))
        is_yes_pair = bool(re.search(yes_pair_pattern, evidence_text, re.IGNORECASE))

        if is_no_pair and not is_yes_pair:
            return "NO" if value_upper != "NO" else None
        if is_yes_pair and not is_no_pair:
            return "YES" if value_upper != "YES" else None

        # Direct explicit markers (e.g. "◉ NO", "☑ NO", "IMPACT TEST: NO")
        no_direct = (
            r"(?:(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))\s*NO\b|\bNO\s*(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))|(?<!\()\b(?:IT|IMPACT\s*TEST(?:ING|ED)?|PWHT)\s*[:=\-]\s*NO\b)"
        )
        yes_direct = (
            r"(?:(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))\s*YES\b|\bYES\s*(?:◉|●|⦿|☑|☒|\[[xX•*]\]|\([•*xX]\))|(?<!\()\b(?:IT|IMPACT\s*TEST(?:ING|ED)?|PWHT)\s*[:=\-]\s*YES\b)"
        )

        evidence_suggests_no = bool(re.search(no_direct, evidence_text, re.IGNORECASE))
        evidence_suggests_yes = bool(re.search(yes_direct, evidence_text, re.IGNORECASE))

        if value_upper == "YES" and evidence_suggests_no and not evidence_suggests_yes:
            return "NO"
        if value_upper == "NO" and evidence_suggests_yes and not evidence_suggests_no:
            return "YES"

        return None

    def _run_single_verification(self, uploaded_file, vote_index: int) -> dict | None:
        """Run a single boolean verification call. Returns parsed dict or None on failure."""
        try:
            # Use slightly varied temperature for vote diversity (0.0, 0.1, 0.2)
            temp = min(vote_index * 0.1, 0.3)
            verify_response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    uploaded_file,
                    BOOLEAN_VERIFICATION_PROMPT,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=temp,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=4096,
                    ),
                ),
            )
            if verify_response.text:
                raw_text = verify_response.text.strip()
                parsed = None
                try:
                    parsed = json.loads(raw_text)
                except Exception:
                    # If direct parsing fails due to markdown wrapping or extra data, use raw_decode
                    start_idx = raw_text.find("{")
                    while start_idx != -1:
                        try:
                            data, _ = json.JSONDecoder().raw_decode(raw_text[start_idx:])
                            if isinstance(data, dict):
                                parsed = data
                                break
                        except Exception:
                            pass
                        start_idx = raw_text.find("{", start_idx + 1)

                if isinstance(parsed, dict):
                    logger.info(
                        f"Boolean verification vote {vote_index + 1}: "
                        f"impact_tested={parsed.get('impact_tested')}, "
                        f"pwht={parsed.get('pwht')}, "
                        f"reasoning={parsed.get('impact_tested_reasoning', 'N/A')}"
                    )
                    return parsed
        except Exception as e:
            logger.warning(f"Boolean verification vote {vote_index + 1} failed: {e}")
        return None

    @staticmethod
    def _majority_vote(votes: list[str]) -> tuple[str, float]:
        """Compute majority vote from a list of YES/NO strings.

        Returns (winner, agreement_ratio).
        """
        if not votes:
            return ("", 0.0)
        from collections import Counter
        counts = Counter(str(v).strip().upper() for v in votes if v and str(v).strip().upper() in ("YES", "NO"))
        if not counts:
            return ("", 0.0)
        winner, winner_count = counts.most_common(1)[0]
        agreement = winner_count / len(votes)
        return (winner, agreement)

    def _verify_boolean_fields(
        self, uploaded_file, result: ExtractionResult
    ) -> ExtractionResult:
        """Run multi-pass verification on impact_tested and pwht.

        1. Checks evidence text for direct contradictions with extracted value
        2. Runs 3 independent targeted verification calls
        3. Uses majority vote (2/3 or 3/3) to resolve true value
        4. Adjusts confidence: boost if unanimous, lower to trigger review if split
        """
        try:
            logger.info(
                f"Running multi-pass boolean verification "
                f"({_BOOLEAN_VERIFY_VOTES} votes)..."
            )

            # --- Step 1: Evidence cross-check ---
            evidence_suggests_impact = self._check_evidence_contradiction(
                result.impact_tested
            )
            evidence_suggests_pwht = self._check_evidence_contradiction(result.pwht)

            if evidence_suggests_impact:
                logger.warning(
                    f"Evidence cross-check: impact_tested evidence text suggests "
                    f"'{evidence_suggests_impact}' but extracted value is "
                    f"'{result.impact_tested.value}'"
                )
            if evidence_suggests_pwht:
                logger.warning(
                    f"Evidence cross-check: pwht evidence text suggests "
                    f"'{evidence_suggests_pwht}' but extracted value is "
                    f"'{result.pwht.value}'"
                )

            # --- Step 2: Run N independent verification calls ---
            impact_votes: list[str] = []
            pwht_votes: list[str] = []
            all_reasoning: list[str] = []

            for i in range(_BOOLEAN_VERIFY_VOTES):
                parsed = self._run_single_verification(uploaded_file, i)
                if parsed and isinstance(parsed, dict):
                    raw_impact = parsed.get("impact_tested")
                    raw_pwht = parsed.get("pwht")
                    impact_val = str(raw_impact).strip().upper() if raw_impact is not None else ""
                    pwht_val = str(raw_pwht).strip().upper() if raw_pwht is not None else ""
                    if impact_val in ("YES", "NO"):
                        impact_votes.append(impact_val)
                    if pwht_val in ("YES", "NO"):
                        pwht_votes.append(pwht_val)
                    # Collect reasoning for logging
                    reasoning = parsed.get("impact_tested_reasoning", "")
                    if reasoning:
                        all_reasoning.append(f"Vote {i+1}: {reasoning}")

            logger.info(
                f"Verification votes — impact_tested: {impact_votes}, pwht: {pwht_votes}"
            )

            # --- Step 3: Majority vote ---
            impact_winner, impact_agreement = self._majority_vote(impact_votes)
            pwht_winner, pwht_agreement = self._majority_vote(pwht_votes)

            # --- Step 4: Resolve impact_tested ---
            current_impact = str(result.impact_tested.value or "").strip().upper()
            result = self._resolve_boolean_field(
                result=result,
                field_name="impact_tested",
                current_value=current_impact,
                vote_winner=impact_winner,
                vote_agreement=impact_agreement,
                evidence_suggestion=evidence_suggests_impact,
                vote_count=len(impact_votes),
                reasoning_log="; ".join(all_reasoning),
            )

            # --- Step 5: Resolve pwht ---
            current_pwht = str(result.pwht.value or "").strip().upper()
            result = self._resolve_boolean_field(
                result=result,
                field_name="pwht",
                current_value=current_pwht,
                vote_winner=pwht_winner,
                vote_agreement=pwht_agreement,
                evidence_suggestion=evidence_suggests_pwht,
                vote_count=len(pwht_votes),
                reasoning_log="",
            )

        except Exception as e:
            # If verification fails entirely, lower confidence on boolean fields
            # to force human review rather than silently passing wrong values
            logger.warning(
                f"Boolean verification failed — lowering confidence to force "
                f"human review: {e}"
            )
            result.impact_tested.confidence = min(result.impact_tested.confidence, 0.5)
            result.pwht.confidence = min(result.pwht.confidence, 0.5)

        return result

    @staticmethod
    def _resolve_boolean_field(
        result: ExtractionResult,
        field_name: str,
        current_value: str,
        vote_winner: str,
        vote_agreement: float,
        evidence_suggestion: str | None,
        vote_count: int,
        reasoning_log: str,
    ) -> ExtractionResult:
        """Resolve a single boolean field using evidence + majority vote.

        Decision matrix:
        - If evidence cross-check AND majority vote both disagree with first-pass → correct the value
        - If only majority vote disagrees (unanimous) → correct the value
        - If majority vote disagrees (not unanimous) → correct but flag as AMBIGUOUS
        - If evidence cross-check disagrees but votes agree with first-pass → flag as AMBIGUOUS
        - If everything agrees → keep value, maintain confidence
        """
        field = getattr(result, field_name)

        if not vote_winner or not current_value:
            # Not enough data to verify — lower confidence to be safe
            if current_value:
                field.confidence = min(field.confidence, 0.5)
                logger.warning(
                    f"Insufficient verification data for {field_name} "
                    f"(got {vote_count} valid votes) — lowering confidence"
                )
            return result

        votes_agree_with_first_pass = (vote_winner == current_value)
        evidence_disagrees = (evidence_suggestion is not None and
                              evidence_suggestion != current_value)

        if votes_agree_with_first_pass and not evidence_disagrees:
            # All signals agree — high confidence in original value
            # Boost confidence slightly if unanimous votes confirm
            if vote_agreement == 1.0 and vote_count >= 2:
                field.confidence = min(field.confidence + 0.05, 1.0)
                logger.info(
                    f"{field_name}: All {vote_count} verification votes "
                    f"unanimously confirm '{current_value}'"
                )
            return result

        if not votes_agree_with_first_pass:
            # Majority vote disagrees with first-pass extraction
            if evidence_disagrees:
                # STRONGEST signal: both evidence AND votes disagree → definitely correct
                # Both independent signals (text evidence + multi-pass visual verification)
                # agree on the correction — this is the highest-confidence correction.
                logger.info(
                    f"Auto-correcting {field_name}: '{current_value}' → '{vote_winner}' "
                    f"(evidence cross-check AND {vote_count} verification votes "
                    f"({vote_agreement:.0%} agreement) both disagree with first-pass)"
                )
                field.value = vote_winner
                field.confidence = 0.90
                field.status = FieldStatus.EXTRACTED
            elif vote_agreement >= 1.0:
                # Unanimous vote disagreement — strong correction signal
                logger.info(
                    f"Auto-correcting {field_name}: '{current_value}' → '{vote_winner}' "
                    f"(all {vote_count} verification votes unanimously disagree "
                    f"with first-pass). {reasoning_log}"
                )
                field.value = vote_winner
                field.confidence = 0.85
                field.status = FieldStatus.EXTRACTED
            elif vote_agreement >= 0.67:
                # Majority (but not unanimous) vote disagreement — correct but mild flag
                logger.info(
                    f"Auto-correcting {field_name}: '{current_value}' → '{vote_winner}' "
                    f"(majority {vote_agreement:.0%} of {vote_count} votes disagree "
                    f"with first-pass). {reasoning_log}"
                )
                field.value = vote_winner
                field.confidence = 0.70
                field.status = FieldStatus.EXTRACTED
            else:
                # Split vote — no clear winner, flag as ambiguous
                logger.info(
                    f"Flagging {field_name} as AMBIGUOUS: votes split "
                    f"({vote_agreement:.0%} agreement on '{vote_winner}' vs "
                    f"first-pass '{current_value}') for human review."
                )
                field.confidence = 0.30
                field.status = FieldStatus.AMBIGUOUS
        elif evidence_disagrees:
            # Evidence disagrees but votes agree with first pass
            # Keep value but lower confidence to flag for human attention
            logger.info(
                f"Flagging {field_name}: evidence text suggests "
                f"'{evidence_suggestion}' but verification votes confirm "
                f"'{current_value}'"
            )
            field.confidence = min(field.confidence, 0.65)

        return result

