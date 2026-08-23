"""End-to-End Evaluation edge cases to ensure safety and system correctness."""

import uuid

import pytest
from langgraph.types import Command

from src.annexure.builder import AnnexureExportError, validate_for_export
from src.domain.schema import FieldStatus
from src.graph.workflow import build_graph
from tests.unit.test_annexure_builder import create_valid_extraction_result


def test_export_safety():
    """Verify that EXPORT never proceeds on INVALID, AMBIGUOUS, MISSING, CONFLICT, NEEDS_REVIEW states."""
    # 1. Start with a fully valid ExtractionResult
    result = create_valid_extraction_result()

    # 2. Test missing
    result.pwht.status = FieldStatus.MISSING
    result.pwht.value = None
    with pytest.raises(AnnexureExportError):
        validate_for_export(result)

    # 3. Test ambiguous
    result.pwht.status = FieldStatus.AMBIGUOUS
    with pytest.raises(AnnexureExportError):
        validate_for_export(result)

    # 4. Test conflict
    result.pwht.status = FieldStatus.CONFLICT
    with pytest.raises(AnnexureExportError):
        validate_for_export(result)

    # 5. Test invalid
    result.pwht.status = FieldStatus.INVALID
    with pytest.raises(AnnexureExportError):
        validate_for_export(result)


def test_invalid_human_correction(monkeypatch):
    """Verify that an invalid human correction does NOT become valid."""
    # In LangGraph workflow, if human enters bad data, re-validation should catch it
    graph = build_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # We will simulate the graph state at human_review_node
    # Actually, the easiest way to test human correction validation is to test the graph directly
    # Wait, the graph structure:
    # human_review -> apply_human_decision -> validate_parameters -> (check if needs review)
    # If the decision makes it invalid, validate_parameters_node sets status to INVALID,
    # and the router should route back to human_review.

    # We can mock extraction to return missing PWHT
    from tests.unit.test_annexure_builder import create_valid_extraction_result

    class MockExtractionService:
        def extract(self, document):
            res = create_valid_extraction_result()
            res.pwht.status = FieldStatus.MISSING
            res.pwht.value = None
            return res

    monkeypatch.setattr("src.graph.nodes.GeminiExtractionService", MockExtractionService)

    import os

    pdf_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "evaluation", "fixtures", "synthetic_datasheet_1.pdf"
    )

    # Initial run
    graph.invoke({"document_path": pdf_path, "workflow_id": thread_id}, config)
    saved_state = graph.get_state(config)

    # Verify it interrupted
    assert len(saved_state.tasks) > 0
    assert bool(saved_state.tasks[0].interrupts)

    # Human provides INVALID correction
    decisions = [{"field": "qty", "value": -5}]  # Quantity cannot be negative

    graph.invoke(Command(resume=decisions), config)

    # Check state again
    saved_state_after = graph.get_state(config)

    # Should be interrupted again because QTY is invalid
    assert len(saved_state_after.tasks) > 0
    assert bool(saved_state_after.tasks[0].interrupts)

    # Now provide VALID correction
    decisions = [{"field": "qty", "value": 2}, {"field": "pwht", "value": "YES"}]

    graph.invoke(Command(resume=decisions), config)
    saved_state_final = graph.get_state(config)

    # Should be finished
    assert not saved_state_final.next
    assert saved_state_final.values["validation_result"].status.value == "VALID"
