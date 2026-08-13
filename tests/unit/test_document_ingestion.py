"""Unit tests for Document Ingestion and Analysis."""

import os
import shutil
import tempfile
from unittest import mock

import pytest

from src.document import (
    CorruptDocumentError,
    DocumentIngestionService,
    DocumentKind,
    DocumentTooLargeError,
    EmptyDocumentError,
    InvalidImageError,
    UnsupportedFileTypeError,
)


@pytest.fixture
def temp_workspace():
    """Provides a temporary directory for file manipulation during tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def service(temp_workspace):
    """Provides a DocumentIngestionService using the temp_workspace."""
    return DocumentIngestionService(temp_dir=temp_workspace)


class TestFileValidation:
    def test_unsupported_extension(self, service, temp_workspace):
        file_path = os.path.join(temp_workspace, "test.docx")
        with open(file_path, "wb") as f:
            f.write(b"fake word doc")

        with pytest.raises(UnsupportedFileTypeError):
            service.ingest_file(file_path, "test.docx")

    def test_empty_file(self, service, temp_workspace):
        file_path = os.path.join(temp_workspace, "empty.pdf")
        with open(file_path, "wb"):
            pass

        with pytest.raises(EmptyDocumentError, match="File is empty"):
            service.ingest_file(file_path, "empty.pdf")

    def test_oversized_file(self, service, temp_workspace, monkeypatch):
        file_path = os.path.join(temp_workspace, "large.pdf")
        with open(file_path, "wb") as f:
            f.write(b"data")

        with (
            mock.patch("os.path.getsize", return_value=100 * 1024 * 1024),
            pytest.raises(DocumentTooLargeError),
        ):
            service.ingest_file(file_path, "large.pdf")

    def test_missing_file(self, service, temp_workspace):
        file_path = os.path.join(temp_workspace, "nonexistent.pdf")
        with pytest.raises(FileNotFoundError):
            service.ingest_file(file_path, "nonexistent.pdf")


class TestDocumentID:
    def test_deterministic_id(self, service, temp_workspace):
        file1 = os.path.join(temp_workspace, "test1.pdf")
        file2 = os.path.join(temp_workspace, "test2.pdf")

        data = b"identical bytes"
        with open(file1, "wb") as f:
            f.write(data)
        with open(file2, "wb") as f:
            f.write(data)

        # We need to mock PyMuPDF since "identical bytes" isn't a valid PDF
        with mock.patch.object(
            service, "_analyze_pdf", return_value=(1, DocumentKind.TEXT_PDF, [])
        ):
            res1 = service.ingest_file(file1, "test1.pdf")
            res2 = service.ingest_file(file2, "test2.pdf")

            assert res1.metadata.document_id == res2.metadata.document_id

    def test_different_id_for_different_content(self, service, temp_workspace):
        file1 = os.path.join(temp_workspace, "test1.pdf")
        file2 = os.path.join(temp_workspace, "test2.pdf")

        with open(file1, "wb") as f:
            f.write(b"data 1")
        with open(file2, "wb") as f:
            f.write(b"data 2")

        with mock.patch.object(
            service, "_analyze_pdf", return_value=(1, DocumentKind.TEXT_PDF, [])
        ):
            res1 = service.ingest_file(file1, "test1.pdf")
            res2 = service.ingest_file(file2, "test2.pdf")

            assert res1.metadata.document_id != res2.metadata.document_id


class TestPDFValidationAndClassification:
    def test_corrupt_pdf(self, service, temp_workspace):
        file_path = os.path.join(temp_workspace, "corrupt.pdf")
        with open(file_path, "wb") as f:
            f.write(b"not a real pdf but not empty")

        with pytest.raises(CorruptDocumentError):
            service.ingest_file(file_path, "corrupt.pdf")

    def test_empty_pages_pdf(self, service, temp_workspace):
        file_path = os.path.join(temp_workspace, "empty_pages.pdf")
        with open(file_path, "wb") as f:
            f.write(b"data")

        # Mock PyMuPDF to return 0 pages
        with (
            mock.patch.object(service, "_analyze_pdf", return_value=(0, DocumentKind.IMAGE, [])),
            pytest.raises(EmptyDocumentError, match="Document has 0 pages"),
        ):
            service.ingest_file(file_path, "empty_pages.pdf")

    # MOCK Tests for classification heuristic
    def _create_mock_pdf_service(self, service, temp_workspace, mock_pages, return_kind):
        file_path = os.path.join(temp_workspace, "mock.pdf")
        with open(file_path, "wb") as f:
            f.write(b"mock pdf bytes")

        with mock.patch.object(
            service, "_analyze_pdf", return_value=(len(mock_pages), return_kind, mock_pages)
        ):
            return service.ingest_file(file_path, "mock.pdf")

    def test_classification_metadata_mapping(self, service, temp_workspace):
        from src.document.models import PageAnalysis

        mock_pages = [
            PageAnalysis(
                page_number=1,
                has_text=True,
                text_character_count=100,
                has_images=False,
                page_kind=DocumentKind.TEXT_PDF,
            ),
            PageAnalysis(
                page_number=2,
                has_text=False,
                text_character_count=0,
                has_images=True,
                page_kind=DocumentKind.SCANNED_PDF,
            ),
            PageAnalysis(
                page_number=3,
                has_text=True,
                text_character_count=50,
                has_images=True,
                page_kind=DocumentKind.MIXED_PDF,
            ),
            PageAnalysis(
                page_number=4,
                has_text=False,
                text_character_count=0,
                has_images=False,
                page_kind=DocumentKind.IMAGE,
            ),  # Empty/unknown
        ]

        res = self._create_mock_pdf_service(
            service, temp_workspace, mock_pages, DocumentKind.MIXED_PDF
        )

        # Verify metadata
        assert res.metadata.page_count == 4
        assert res.metadata.document_kind == DocumentKind.MIXED_PDF
        assert res.metadata.text_page_count == 1
        assert res.metadata.image_page_count == 1
        assert res.metadata.mixed_page_count == 1
        assert res.metadata.empty_page_count == 1


class TestImageValidation:
    def test_corrupt_image(self, service, temp_workspace):
        file_path = os.path.join(temp_workspace, "corrupt.png")
        with open(file_path, "wb") as f:
            f.write(b"not a real image")

        with pytest.raises(InvalidImageError):
            service.ingest_file(file_path, "corrupt.png")

    def test_valid_image_mocked(self, service, temp_workspace):
        file_path = os.path.join(temp_workspace, "valid.jpg")
        with open(file_path, "wb") as f:
            f.write(b"\xff\xd8\xff mock image bytes")

        with mock.patch.object(service, "_analyze_image", return_value=(1, DocumentKind.IMAGE, [])):
            res = service.ingest_file(file_path, "valid.jpg")
            assert res.metadata.document_kind == DocumentKind.IMAGE
            assert res.metadata.file_extension == "jpg"


class TestSecurity:
    def test_path_traversal_filename(self, service, temp_workspace):
        file_path = os.path.join(temp_workspace, "safe.pdf")
        with open(file_path, "wb") as f:
            f.write(b"data")

        malicious_filename = "../../../etc/passwd.pdf"

        with mock.patch.object(
            service, "_analyze_pdf", return_value=(1, DocumentKind.TEXT_PDF, [])
        ):
            res = service.ingest_file(file_path, malicious_filename)

            # The service should have basename'd the filename
            assert res.metadata.original_filename == "passwd.pdf"
            assert "/" not in res.metadata.original_filename
            assert "\\" not in res.metadata.original_filename

    def test_misleading_extension(self, service, temp_workspace):
        file_path = os.path.join(temp_workspace, "malicious.exe")
        with open(file_path, "wb") as f:
            f.write(b"data")

        # Someone renamed it to .pdf when sending to the API, but our Ingest Service
        # uses the original_filename parameter provided by the API to check the intended extension,
        # or checks the actual bytes via PyMuPDF.
        # If the API says it's a "file.pdf" but the bytes are an exe, PyMuPDF will fail.
        with pytest.raises(CorruptDocumentError):
            service.ingest_file(file_path, "file.pdf")
