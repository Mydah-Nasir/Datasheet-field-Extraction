"""Gemini Document Extraction Service."""

import json
import logging
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

# Second-pass prompt for verifying boolean checkbox fields
BOOLEAN_VERIFICATION_PROMPT = """You are a quality inspector verifying checkbox values on a mechanical datasheet.

TASK: On the datasheet page that contains design conditions, there is a section with multiple YES/NO checkboxes.
These checkboxes are arranged in SEPARATE ROWS. Each row has a LABEL and a MARKED checkbox (YES or NO).

Common fields in this section include (but are not limited to):
- PWHT (Post Weld Heat Treatment)
- IMPACT TESTING (IT)
- WET H2S / SOUR SERVICE
- RADIOGRAPHY

STEP 1: Find the design conditions section on the datasheet.
STEP 2: List EVERY checkbox row you see, with its label and which box (YES or NO) is marked.
STEP 3: Based on your listing, report the values.

WARNING: "WET SOUR: YES" does NOT mean "IMPACT TESTING: YES". These are DIFFERENT rows.
WARNING: "PWHT: YES" does NOT mean "IMPACT TESTING: YES". These are DIFFERENT rows.

Respond in this exact JSON format:
{"all_checkboxes": [{"label": "...", "value": "YES or NO"}], "impact_tested": "YES or NO", "pwht": "YES or NO"}"""



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

            # 5. Second-pass: verify boolean checkbox fields (impact_tested, pwht)
            # The model frequently confuses adjacent checkboxes on engineering drawings
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

    def _verify_boolean_fields(
        self, uploaded_file, result: ExtractionResult
    ) -> ExtractionResult:
        """Run a focused second-pass to verify boolean checkbox fields.

        Vision models frequently confuse adjacent checkboxes on dense engineering
        drawings (e.g., IMPACT TESTING vs PWHT vs WET SOUR). This method makes
        a separate, focused API call to double-check those specific fields.
        """
        try:
            logger.info("Running second-pass boolean field verification...")
            verify_response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    uploaded_file,
                    BOOLEAN_VERIFICATION_PROMPT,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=2048,
                    ),
                ),
            )

            if verify_response.text:
                verified = json.loads(verify_response.text)
                logger.info(f"Boolean verification result: {verified}")

                # Compare and correct impact_tested
                verified_impact = verified.get("impact_tested", "").strip().upper()
                current_impact = (result.impact_tested.value or "").strip().upper()

                if verified_impact in ("YES", "NO") and verified_impact != current_impact:
                    logger.warning(
                        f"CORRECTING impact_tested: '{current_impact}' -> '{verified_impact}' "
                        f"(second-pass verification disagreed with first-pass)"
                    )
                    result.impact_tested.value = verified_impact
                    result.impact_tested.confidence = 0.6  # Lower confidence since passes disagreed
                    result.impact_tested.status = FieldStatus.EXTRACTED

                # Compare and correct pwht
                verified_pwht = verified.get("pwht", "").strip().upper()
                current_pwht = (result.pwht.value or "").strip().upper()

                if verified_pwht in ("YES", "NO") and verified_pwht != current_pwht:
                    logger.warning(
                        f"CORRECTING pwht: '{current_pwht}' -> '{verified_pwht}' "
                        f"(second-pass verification disagreed with first-pass)"
                    )
                    result.pwht.value = verified_pwht
                    result.pwht.confidence = 0.6
                    result.pwht.status = FieldStatus.EXTRACTED

        except Exception as e:
            # If verification fails, keep original results — don't crash
            logger.warning(f"Boolean verification failed (keeping original values): {e}")

        return result

