"""Integration test for LangGraph Human-in-the-Loop workflow."""

from unittest.mock import patch

import pytest
from langgraph.types import Command

from src.domain.schema import (
    Evidence,
    ExtractionField,
    ExtractionResult,
    FieldStatus,
    PaintingField,
)
from src.graph.workflow import build_graph


# Reusing the realistic mock from Phase 4 tests
@pytest.fixture
def realistic_extraction() -> ExtractionResult:
    return ExtractionResult(
        tag_no=ExtractionField(
            value="V-101",
            status=FieldStatus.EXTRACTED,
            confidence=0.95,
            evidence=[Evidence(page=1, text="Tag No. V-101")],
        ),
        description=ExtractionField(
            value="Production Separator",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="Description: Production Separator")],
        ),
        ref_data_sheet=ExtractionField(
            value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
        ),
        design_code=ExtractionField(
            value="ASME Sec VIII Div 1",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="Code: ASME Sec VIII Div 1")],
        ),
        moc=ExtractionField(
            value="SA 516 Gr. 70",
            status=FieldStatus.EXTRACTED,
            confidence=0.8,
            evidence=[Evidence(page=1, text="Material: SA 516 Gr. 70")],
        ),
        qty=ExtractionField(
            value=1,
            status=FieldStatus.EXTRACTED,
            confidence=0.99,
            evidence=[Evidence(page=1, text="Quantity 1")],
        ),
        orientation=ExtractionField(
            value="HOR",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=1, text="Orientation: HOR")],
        ),
        vessel_id_mm=ExtractionField(
            value=2400.0,
            status=FieldStatus.EXTRACTED,
            confidence=0.85,
            evidence=[Evidence(page=2, text="ID 2400 mm")],
        ),
        vessel_tl_tl_length_mm=ExtractionField(
            value=5.8,
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=2, text="5.8 m")],
        ),
        shell_min_thk_mm=ExtractionField(
            value=25.0,
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=2, text="Thk 25mm")],
        ),
        head_min_thk_mm=ExtractionField(
            value=22.0,
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=2, text="22 mm")],
        ),
        head_type=ExtractionField(
            value="2:1 Elliptical",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=2, text="2:1 Elliptical")],
        ),
        nozzle_type=ExtractionField(
            value="Flanged",
            status=FieldStatus.EXTRACTED,
            confidence=0.7,
            evidence=[Evidence(page=2, text="Flanged")],
        ),
        impact_tested=ExtractionField(
            value="YES",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=3, text="Impact Tested: YES")],
        ),
        rt=ExtractionField(
            value="100%",
            status=FieldStatus.EXTRACTED,
            confidence=0.9,
            evidence=[Evidence(page=3, text="RT 100%")],
        ),
        pwht=ExtractionField(
            value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
        ),  # MISSING
        support_type=ExtractionField(
            value="Saddles",
            status=FieldStatus.EXTRACTED,
            confidence=0.8,
            evidence=[Evidence(page=3, text="Saddles")],
        ),
        painting=PaintingField(
            external=ExtractionField(
                value="System A",
                status=FieldStatus.EXTRACTED,
                confidence=0.9,
                evidence=[Evidence(page=4, text="Ext: System A")],
            ),
            internal=ExtractionField(
                value=None, status=FieldStatus.MISSING, confidence=0.0, evidence=[]
            ),  # MISSING
        ),
        weight_tons_each=ExtractionField(
            value=15000.0,
            status=FieldStatus.EXTRACTED,
            confidence=0.8,
            evidence=[Evidence(page=4, text="15000 kg")],
        ),
    )


def test_hitl_workflow(realistic_extraction):
    """
    Test the LangGraph orchestration end-to-end with an interrupt.
    Mocking DocumentIngestionService and GeminiExtractionService to avoid
    needing a real PDF file and a real Gemini API Key.
    """
    graph = build_graph()

    # 1. Setup config and thread id
    thread_id = "test-thread-123"
    config = {"configurable": {"thread_id": thread_id}}

    # Start input
    initial_state = {"workflow_id": thread_id, "document_path": "dummy.pdf"}

    # We mock Ingestion and Extraction to return the mock document and realistic_extraction.
    # The normalizer and validator are real and deterministic.
    with (
        patch("src.graph.nodes.DocumentIngestionService") as MockIngest,
        patch("src.graph.nodes.GeminiExtractionService") as MockExtract,
    ):
        # Setup mocks
        mock_ingest_instance = MockIngest.return_value
        mock_ingest_instance.ingest_file.return_value = {"mock_doc": True}

        mock_extract_instance = MockExtract.return_value
        mock_extract_instance.extract.return_value = realistic_extraction

        # 2. Invoke graph for the first time
        # It should run ingest -> extract -> normalize -> validate -> human_review
        # and pause inside human_review because of interrupt()
        graph.invoke(initial_state, config)

        # Check current state of the graph
        saved_state = graph.get_state(config)
        assert saved_state.next == ("human_review",)

        # Check the interrupt payload
        # tasks[0].interrupts[0].value contains the interrupt request
        interrupt_payload = saved_state.tasks[0].interrupts[0].value
        assert interrupt_payload["type"] == "ANNEX_VALIDATION"

        # Verify it flagged the right fields
        flagged_fields = [f["field"] for f in interrupt_payload["fields"]]
        assert "ref_data_sheet" in flagged_fields
        assert "pwht" in flagged_fields
        assert "painting_internal" in flagged_fields

        # 3. Simulate human correcting the missing fields
        human_decision = [
            {"field": "ref_data_sheet", "value": "DS-001"},
            {"field": "pwht", "value": "YES"},
            {"field": "painting_internal", "value": "System B"},
        ]

        # Resume the graph with the human decision
        # We pass the decision into Command(resume=...)
        graph.invoke(Command(resume=human_decision), config)

        # The graph should have looped back to validate, then finalize, then END
        saved_state_final = graph.get_state(config)
        assert not saved_state_final.next  # Empty tuple means reached END

        # 4. Verify Final State
        final_state = saved_state_final.values
        final_annex = final_state["final_annex"]

        # The human inputs should be in the final annex
        assert final_annex["ref_data_sheet"] == "DS-001"
        assert final_annex["pwht"] == "YES"
        assert final_annex["painting_internal"] == "System B"

        # Validated status should be updated
        assert final_state["validation_result"].status.value == "VALID"
        assert len(final_state["validation_result"].issues) == 0

        # Normalization conversions should still be present
        assert final_annex["vessel_tl_tl_length_mm"] == 5800.0
        assert final_annex["weight_tons_each"] == 15.0
        assert final_annex["orientation"] == "HORIZONTAL"
