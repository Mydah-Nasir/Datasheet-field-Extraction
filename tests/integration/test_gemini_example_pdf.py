"""Integration tests utilizing real Gemini API on example PDFs."""

import os

import pytest

from src.document.service import DocumentIngestionService
from src.domain.schema import ExtractionResult
from src.extraction.service import GeminiExtractionService

# Skip the entire module if the API key is not present
pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY is not set in environment"
)

# Path to the actual PDF
EXAMPLE_PDFS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "example_pdfs")
PDF_PATH = os.path.join(EXAMPLE_PDFS_DIR, "(Datasheet WOSEP) SD-8500-13513-0001_0F1_001.pdf")


def test_gemini_extraction_on_real_pdf():
    """Run full extraction pipeline on the real example PDF."""

    # 1. Ingestion Phase
    ingestion_service = DocumentIngestionService()
    document = ingestion_service.ingest_file(PDF_PATH, os.path.basename(PDF_PATH))

    # 2. Extraction Phase
    extraction_service = GeminiExtractionService()
    result = extraction_service.extract(document)

    # 3. Verification of structural correctness
    assert isinstance(result, ExtractionResult)

    # Print a developer report as requested
    print(f"\n--- EXTRACTION REPORT: {document.metadata.original_filename} ---")
    print(f"Model: {extraction_service.model_name}")
    print(f"Document ID: {document.metadata.document_id}")

    fields = [
        ("TAG NO", result.tag_no),
        ("DESCRIPTION", result.description),
        ("REF DATA SHEET", result.ref_data_sheet),
        ("DESIGN CODE", result.design_code),
        ("MOC", result.moc),
        ("QTY", result.qty),
        ("ORIENTATION", result.orientation),
        ("VESSEL ID", result.vessel_id_mm),
        ("LENGTH", result.vessel_tl_tl_length_mm),
        ("SHELL THK", result.shell_min_thk_mm),
        ("HEAD THK", result.head_min_thk_mm),
        ("HEAD TYPE", result.head_type),
        ("NOZZLE TYPE", result.nozzle_type),
        ("IMPACT TESTED", result.impact_tested),
        ("RT", result.rt),
        ("PWHT", result.pwht),
        ("SUPPORT TYPE", result.support_type),
        ("EXT PAINT", result.painting.external),
        ("INT PAINT", result.painting.internal),
        ("WEIGHT", result.weight_tons_each),
    ]

    for name, field in fields:
        evidence_pages = [e.page for e in field.evidence]
        print(
            f"{name.ljust(15)} | {str(field.value).ljust(20)[:20]} | {field.status.value.ljust(12)} | {field.confidence:.2f} | P: {evidence_pages}"
        )

    # We don't hardcode specific engineering values in the first integration test,
    # as instructed by the user. The primary goal is structural correctness and evidence presence.
