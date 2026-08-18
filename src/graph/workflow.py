"""LangGraph setup and wiring for Phase 5 orchestration."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from src.domain.validation import ValidationStatus
from src.graph.nodes import (
    apply_human_decision_node,
    extract_parameters_node,
    finalize_annex_node,
    human_review_node,
    ingest_document_node,
    normalize_parameters_node,
    validate_parameters_node,
)
from src.graph.state import ExtractionState


def route_after_validation(state: ExtractionState) -> str:
    """Determine the next step based on validation status.
    
    Routes to human review on initial pass, and to finalize_annex once approved.
    """
    if state.get("error"):
        return "error"

    # If the user has reviewed and approved, route to finalize_annex
    if state.get("user_approved"):
        val_result = state.get("validation_result")
        if val_result:
            from src.domain.validation import ValidationSeverity
            has_fatal_error = any(i.severity == ValidationSeverity.ERROR for i in val_result.issues)
            if not has_fatal_error:
                return "valid"

    # Initial pass or unresolved issues -> human review
    return "needs_review"


def route_after_ingestion(state: ExtractionState) -> str:
    if state.get("error"):
        return "error"
    return "ok"


def route_after_extraction(state: ExtractionState) -> str:
    if state.get("error"):
        return "error"
    return "ok"


def build_graph():
    """Build and compile the LangGraph workflow."""
    builder = StateGraph(ExtractionState)

    # 1. Add Nodes
    builder.add_node("ingest_document", ingest_document_node)
    builder.add_node("extract_parameters", extract_parameters_node)
    builder.add_node("normalize_parameters", normalize_parameters_node)
    builder.add_node("validate_parameters", validate_parameters_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("apply_human_decision", apply_human_decision_node)
    builder.add_node("finalize_annex", finalize_annex_node)

    # 2. Add Edges
    builder.add_edge(START, "ingest_document")

    builder.add_conditional_edges(
        "ingest_document", route_after_ingestion, {"ok": "extract_parameters", "error": END}
    )

    builder.add_conditional_edges(
        "extract_parameters", route_after_extraction, {"ok": "normalize_parameters", "error": END}
    )

    builder.add_edge("normalize_parameters", "validate_parameters")

    # 3. Validation routing
    builder.add_conditional_edges(
        "validate_parameters",
        route_after_validation,
        {
            "valid": "finalize_annex",
            "needs_review": "human_review",
            "error": END,
        },
    )

    # 4. Human-in-the-loop loops back to validation
    builder.add_edge("human_review", "apply_human_decision")
    builder.add_edge("apply_human_decision", "validate_parameters")

    # 5. Finalize
    builder.add_edge("finalize_annex", END)

    # Compile with memory checkpointer for state persistence
    checkpointer = MemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=True))
    graph = builder.compile(checkpointer=checkpointer)

    return graph
