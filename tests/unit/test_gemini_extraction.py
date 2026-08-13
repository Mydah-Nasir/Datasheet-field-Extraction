"""Unit tests for Gemini extraction service.

These tests mock the Gemini SDK to ensure deterministic behavior without hitting the real API.
"""

from unittest.mock import MagicMock, patch

import google.genai as genai
import pytest

from src.document import DocumentKind, DocumentMetadata, IngestedDocument, PageAnalysis
from src.domain.schema import ExtractionResult, FieldStatus
from src.extraction import (
    ExtractionAuthError,
    ExtractionParseError,
    ExtractionTimeoutError,
    GeminiExtractionService,
)


@pytest.fixture
def mock_document():
    return IngestedDocument(
        metadata=DocumentMetadata(
            document_id="fake_id",
            original_filename="test.pdf",
            file_extension="pdf",
            size_bytes=1000,
            page_count=1,
            document_kind=DocumentKind.TEXT_PDF,
            text_page_count=1,
            image_page_count=0,
            mixed_page_count=0,
            empty_page_count=0,
        ),
        file_path="/fake/path/test.pdf",
        page_analysis=[
            PageAnalysis(
                page_number=1,
                has_text=True,
                text_character_count=100,
                has_images=False,
                page_kind=DocumentKind.TEXT_PDF,
            )
        ],
    )


@pytest.fixture
def extraction_service():
    """Service with a dummy API key."""
    return GeminiExtractionService(api_key="dummy_key", model_name="dummy-model")


class TestGeminiExtractionService:
    def test_missing_api_key(self):
        with pytest.raises(ExtractionAuthError, match="GEMINI_API_KEY is missing"):
            GeminiExtractionService(api_key="")

    @patch("src.extraction.service.genai.Client")
    def test_successful_extraction(self, mock_client_cls, extraction_service, mock_document):
        # Setup mock client
        mock_client = MagicMock()
        extraction_service.client = mock_client

        # Mock file upload
        mock_file = MagicMock()
        mock_file.name = "files/fake123"
        mock_client.files.upload.return_value = mock_file

        # Mock generate_content response
        mock_response = MagicMock()
        mock_response.text = '{"tag_no": {"value": "V-101", "status": "EXTRACTED", "confidence": 0.9, "evidence": [{"page": 1, "text": "Tag: V-101"}]}}'  # Incomplete JSON but we will mock parsed

        # Create a valid mock parsed ExtractionResult
        # To avoid writing a massive JSON string, we just set `parsed` to a valid model
        from src.domain.schema import ExtractionField, PaintingField

        mock_parsed = ExtractionResult(
            tag_no=ExtractionField(
                value="V-101", status=FieldStatus.EXTRACTED, confidence=0.9, evidence=[]
            ),
            description=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            ref_data_sheet=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            design_code=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            moc=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            qty=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            orientation=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            vessel_id_mm=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            vessel_tl_tl_length_mm=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            shell_min_thk_mm=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            head_min_thk_mm=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            head_type=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            nozzle_type=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            impact_tested=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            rt=ExtractionField(value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]),
            pwht=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            support_type=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
            painting=PaintingField(
                external=ExtractionField(
                    value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
                ),
                internal=ExtractionField(
                    value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
                ),
            ),
            weight_tons_each=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),
        )
        mock_response.parsed = mock_parsed
        mock_client.models.generate_content.return_value = mock_response

        # Execute
        result = extraction_service.extract(mock_document)

        # Verify
        assert isinstance(result, ExtractionResult)
        assert result.tag_no.value == "V-101"
        assert result.tag_no.status == FieldStatus.EXTRACTED

        # Verify cleanup was called
        mock_client.files.delete.assert_called_once_with(name="files/fake123")

    @patch("src.extraction.service.genai.Client")
    def test_parse_error_malformed_json(self, mock_client_cls, extraction_service, mock_document):
        mock_client = MagicMock()
        extraction_service.client = mock_client

        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = '{"tag_no": "invalid structure for schema"}'
        mock_client.models.generate_content.return_value = mock_response

        with pytest.raises(ExtractionParseError):
            extraction_service.extract(mock_document)

    @patch("src.extraction.service.genai.Client")
    def test_api_auth_error(self, mock_client_cls, extraction_service, mock_document):
        mock_client = MagicMock()
        extraction_service.client = mock_client

        mock_client.models.generate_content.side_effect = genai.errors.APIError(
            "API key not valid", {}
        )

        with pytest.raises(ExtractionAuthError):
            extraction_service.extract(mock_document)

    @patch("src.extraction.service.genai.Client")
    def test_api_timeout_error(self, mock_client_cls, extraction_service, mock_document):
        mock_client = MagicMock()
        extraction_service.client = mock_client

        mock_client.models.generate_content.side_effect = genai.errors.APIError(
            "deadline exceeded", {}
        )

        with pytest.raises(ExtractionTimeoutError):
            extraction_service.extract(mock_document)
