"""Integration tests for the complete annexure generation pipeline."""

from src.annexure.builder import build_annexure
from src.annexure.export import export_to_csv, export_to_excel, export_to_json
from tests.unit.test_annexure_builder import create_valid_extraction_result


def test_complete_annexure_pipeline():
    """Test the full flow from ExtractionResult to bytes."""
    # 1. Start with a fully valid ExtractionResult (simulating what comes out of LangGraph)
    extraction_result = create_valid_extraction_result()

    # 2. Build the AnnexureRecord
    record = build_annexure(extraction_result)
    assert record.tag_no == "V-101"

    # 3. Export to JSON
    json_bytes = export_to_json([record])
    assert b"V-101" in json_bytes

    # 4. Export to CSV
    csv_bytes = export_to_csv([record])
    assert b"TAG NO." in csv_bytes
    assert b"V-101" in csv_bytes

    # 5. Export to Excel
    excel_bytes = export_to_excel([record])
    assert len(excel_bytes) > 1000  # Should be a relatively large binary file
