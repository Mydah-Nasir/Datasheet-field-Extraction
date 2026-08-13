"""Integration tests utilizing real example PDFs."""

import glob
import os
import shutil
import tempfile

import pytest

from src.document import DocumentIngestionService, DocumentKind

# Path to the actual PDFs
EXAMPLE_PDFS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "example_pdfs")


def get_example_pdfs():
    """Discover all PDFs in the example_pdfs directory."""
    if not os.path.exists(EXAMPLE_PDFS_DIR):
        return []
    return glob.glob(os.path.join(EXAMPLE_PDFS_DIR, "*.pdf"))


@pytest.fixture
def temp_workspace():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def service(temp_workspace):
    return DocumentIngestionService(temp_dir=temp_workspace)


@pytest.mark.parametrize("pdf_path", get_example_pdfs())
def test_ingest_example_pdfs(service, pdf_path):
    """Test that every example PDF can be successfully ingested and parsed."""

    filename = os.path.basename(pdf_path)

    # Ingest the real file
    result = service.ingest_file(pdf_path, original_filename=filename)

    # Verification
    metadata = result.metadata

    # Basic assertions
    assert metadata.original_filename == filename
    assert metadata.file_extension == "pdf"
    assert metadata.size_bytes > 0
    assert metadata.page_count > 0
    assert len(metadata.document_id) == 64  # SHA-256

    # Validate the file was actually copied to the safe internal path
    assert os.path.exists(result.file_path)
    assert os.path.getsize(result.file_path) == metadata.size_bytes

    # The actual classification may vary by PDF, but it must exist
    assert metadata.document_kind in [
        DocumentKind.TEXT_PDF,
        DocumentKind.SCANNED_PDF,
        DocumentKind.MIXED_PDF,
        DocumentKind.IMAGE,
    ]

    # Page analysis should be populated for every page
    assert len(result.page_analysis) == metadata.page_count

    # Print the specific values to stdout for the walkthrough report
    print(f"\n--- INSPECTION REPORT: {filename} ---")
    print(f"Size: {metadata.size_bytes} bytes")
    print(f"Pages: {metadata.page_count}")
    print(f"Text Pages: {metadata.text_page_count}")
    print(f"Image Pages: {metadata.image_page_count}")
    print(f"Mixed Pages: {metadata.mixed_page_count}")
    print(f"Classification: {metadata.document_kind.value}")
