# Architecture — Mechanical Datasheet Annex Extraction

## 1. Architecture Goal

Build a deterministic, stateful document-extraction workflow where AI performs semantic extraction, deterministic code performs validation, and LangGraph controls orchestration, persistence, waiting, and human-in-the-loop recovery.

The architecture is intentionally split into:

```text
Document Processing
        ↓
Evidence/Structure
        ↓
LLM Extraction
        ↓
Deterministic Validation
        ↓
Human Review if Required
        ↓
Finalization
        ↓
Annex MDS
```

LangGraph is the orchestration layer, not the OCR engine and not the business-rule engine.

---

# 2. Recommended Project Structure

```text
your-project/
│
├── docs/
│   ├── REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   ├── TASKS.md
│   └── LOOP.md
│
├── tests/
│   ├── unit/
│   │   ├── test_schema.py
│   │   ├── test_normalization.py
│   │   ├── test_validation.py
│   │   ├── test_extraction.py
│   │   └── test_graph_nodes.py
│   └── integration/
│       ├── test_extraction_workflow.py
│       ├── test_human_review.py
│       └── test_resume_after_restart.py
│
├── src/
│   ├── api/
│   │   └── routes.py
│   ├── domain/
│   │   ├── schema.py
│   │   ├── statuses.py
│   │   └── validation.py
│   ├── document/
│   │   ├── ingestion.py
│   │   ├── pdf.py
│   │   ├── ocr.py
│   │   └── layout.py
│   ├── extraction/
│   │   ├── prompts.py
│   │   ├── extractor.py
│   │   └── normalization.py
│   ├── graph/
│   │   ├── state.py
│   │   ├── nodes.py
│   │   ├── routing.py
│   │   └── workflow.py
│   ├── persistence/
│   │   └── checkpointer.py
│   └── config.py
│
└── pyproject.toml
```

---

# 3. High-Level Components

## 3.1 API Layer

Responsibilities:

- accept document upload;
- create a workflow/thread ID;
- start the LangGraph run;
- return extraction progress;
- expose pending human-review requests;
- accept human corrections;
- resume the graph;
- return final Annex data.

The API must never contain extraction logic.

---

## 3.2 Document Processing Layer

Responsibilities:

1. Identify document type.
2. Extract native PDF text where available.
3. Render pages when OCR is required.
4. Run OCR.
5. Preserve bounding boxes.
6. Build a normalized document representation.

Example:

```python
DocumentPage(
    page_number=2,
    text="Inside Diameter: 5800 mm",
    blocks=[
        TextBlock(
            text="Inside Diameter",
            bbox=(100, 200, 220, 225)
        ),
        TextBlock(
            text="5800 mm",
            bbox=(240, 200, 310, 225)
        )
    ]
)
```

Do not throw away coordinates.

---

# 4. Extraction Architecture

The extraction pipeline should be hybrid.

```text
Raw Document
     ↓
Native PDF / OCR
     ↓
Layout + Coordinates
     ↓
Candidate Identification
     ↓
LLM Structured Extraction
     ↓
Normalization
     ↓
Deterministic Validation
```

### Why hybrid?

Pure LLM extraction can hallucinate or mis-associate nearby values.

Pure keyword extraction cannot reliably understand terminology variations and document layouts.

Use:

- deterministic parsing for what can be deterministic;
- spatial/layout information for label-value relationships;
- LLM structured output for semantic mapping;
- deterministic validation for correctness gates.

---

# 5. LangGraph Architecture

Use `StateGraph` with explicit nodes and conditional routing.

Recommended graph:

```text
START
  │
  ▼
ingest_document
  │
  ▼
extract_document_content
  │
  ▼
build_evidence_context
  │
  ▼
extract_parameters
  │
  ▼
normalize_parameters
  │
  ▼
validate_parameters
  │
  ├────────────── valid ──────────────┐
  │                                  │
  ├── missing/ambiguous/invalid ──► human_review
  │                                  │
  │                                  ▼
  │                           apply_human_decision
  │                                  │
  │                                  ▼
  │                           validate_parameters
  │                                  │
  │                                  └── repeat if required
  │
  ▼
finalize_annex
  │
  ▼
END
```

The validation loop is deliberate.

A human correction must go back through validation. Never trust user input blindly.

---

# 6. LangGraph State

Use a typed state.

Conceptually:

```python
from typing import TypedDict, Any

class ExtractionState(TypedDict, total=False):
    workflow_id: str
    document_id: str
    document_path: str

    pages: list[dict]
    evidence: list[dict]

    extraction: dict
    normalized_extraction: dict
    validation: dict

    missing_fields: list[str]
    ambiguous_fields: list[str]
    invalid_fields: list[str]

    human_review: dict
    human_decisions: list[dict]

    status: str
    error: dict | None

    final_annex: dict
```

Keep state serializable.

Do not put open file handles, database connections, model objects, callbacks, or other non-serializable runtime objects into graph state.

---

# 7. LangGraph Nodes

## Node 1 — `ingest_document`

Input:

```text
document_id
document_path
```

Output:

```text
workflow_id
document metadata
```

Responsibilities:

- verify file;
- determine type;
- reject unsupported formats;
- create document metadata.

---

## Node 2 — `extract_document_content`

Responsibilities:

- native PDF text extraction;
- OCR fallback;
- page rendering;
- coordinate preservation.

Output:

```text
pages
```

---

## Node 3 — `build_evidence_context`

Responsibilities:

- organize text by page;
- identify tables/regions;
- create candidate label-value relationships;
- keep source coordinates.

Output:

```text
evidence
```

---

## Node 4 — `extract_parameters`

Use structured LLM output against the canonical schema.

The model receives:

- relevant document evidence;
- canonical field definitions;
- terminology aliases;
- strict instruction not to invent missing values.

Output:

```text
extraction
```

Every field should include:

- value;
- confidence;
- evidence;
- extraction status.

---

## Node 5 — `normalize_parameters`

Examples:

```text
HOR → HORIZONTAL
VERT → VERTICAL

5.8 m → 5800 mm
30 MM → 30 mm

SA 516 Gr 70N HIC
→ SA 516 Gr 70N-HIC
```

Normalization must preserve the original value/evidence.

---

# 8. Validation Node

The validation node must be deterministic.

Do not ask the LLM:

> "Is this data valid?"

Instead implement explicit validators.

Example:

```python
def validate_parameters(extraction):
    errors = []

    if extraction["vessel_id_mm"]["value"] is not None:
        if extraction["vessel_id_mm"]["value"] <= 0:
            errors.append("vessel_id_mm must be positive")

    if extraction["qty"]["value"] is not None:
        if extraction["qty"]["value"] <= 0:
            errors.append("qty must be positive")

    return errors
```

The LLM can assist with semantic extraction, but validation gates must be deterministic.

---

# 9. Routing Logic

After validation:

```text
if all fields valid:
    → finalize_annex

elif missing/ambiguous/invalid fields exist:
    → human_review

elif unrecoverable extraction error:
    → failure
```

Do not route directly from extraction to finalization.

The finalization node should only be reachable from a validated state.

---

# 10. Human-in-the-Loop with LangGraph

Use LangGraph's dynamic `interrupt()` mechanism for human review.

Current LangGraph documentation specifies that interrupts pause execution, persist graph state through a checkpointer, and resume with `Command(resume=...)`. A stable `thread_id` is required to locate the saved execution state. citeturn1search1turn1search0

Conceptual implementation:

```python
from langgraph.types import interrupt

def human_review(state: ExtractionState):
    review_request = {
        "type": "ANNEX_VALIDATION",
        "message": "Review the following fields.",
        "fields": state["missing_fields"]
                   + state["ambiguous_fields"]
                   + state["invalid_fields"],
        "extraction": state["normalized_extraction"],
    }

    decision = interrupt(review_request)

    return {
        "human_review": decision
    }
```

The frontend receives the interrupt payload and displays a review form.

---

# 11. Resuming the Graph

When the user submits a correction:

```python
from langgraph.types import Command

graph.invoke(
    Command(
        resume={
            "action": "correct",
            "values": {
                "pwht": "YES"
            }
        }
    ),
    config={
        "configurable": {
            "thread_id": workflow_id
        }
    }
)
```

The same `thread_id` must be used.

LangGraph's documented behavior is that resuming with `Command(resume=...)` supplies the value back to the `interrupt()` call. The node containing the interrupt is restarted from its beginning, so code before the interrupt must be safe to run again. citeturn1search1turn1search3

---

# 12. Critical HITL Design Rule

Do not put irreversible side effects before `interrupt()`.

Bad:

```python
def human_review(state):
    save_to_final_database(state)
    answer = interrupt(...)
```

When resumed, the node can execute again.

Better:

```python
def human_review(state):
    answer = interrupt(...)
    return {"human_review": answer}
```

Then perform final database writes in a later idempotent node.

LangGraph explicitly warns that side effects before an interrupt must be idempotent because the node can restart when resumed. citeturn1search1

---

# 13. Multiple Human Corrections

Prefer one structured review interrupt containing all fields requiring review:

```json
{
  "fields": [
    {
      "name": "pwht",
      "current_value": null,
      "status": "MISSING"
    },
    {
      "name": "head_min_thk_mm",
      "current_value": 21.82,
      "status": "AMBIGUOUS"
    }
  ]
}
```

Then the user submits one structured response.

This avoids fragile multiple interrupts whose ordering can change.

LangGraph documents that multiple interrupts inside a node are matched by index and should not be conditionally reordered. citeturn1search1

---

# 14. Human Decision Model

Use explicit actions:

```text
CONFIRM
CORRECT
REJECT
```

Example:

```json
{
  "action": "CORRECT",
  "field": "pwht",
  "value": "YES",
  "reason": "Confirmed from engineering datasheet"
}
```

Store the decision separately:

```json
{
  "field": "pwht",
  "original": null,
  "human_value": "YES",
  "action": "CORRECT",
  "reviewer": "user_id",
  "timestamp": "..."
}
```

The original extraction evidence must remain available for auditability.

---

# 15. Checkpointing

Human-in-the-loop requires persistence.

For development/testing:

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
```

For production, use a durable database-backed checkpointer.

LangGraph's persistence documentation states that checkpoints save graph state at execution steps and are required for human-in-the-loop workflows; production deployments should use durable persistence. citeturn1search0

The graph should be compiled with:

```python
graph = builder.compile(
    checkpointer=checkpointer
)
```

Every invocation/resume must include:

```python
config = {
    "configurable": {
        "thread_id": workflow_id
    }
}
```

Never generate a new thread ID when resuming a review.

---

# 16. Failure and Retry Strategy

Separate:

### Recoverable infrastructure failures

Examples:

- OCR timeout;
- transient model/API error;
- temporary database error.

These may be retried.

### Data-quality failures

Examples:

- missing PWHT;
- conflicting thickness;
- unknown MOC.

These should go to human review, not automatic retry.

### Fatal failures

Examples:

- corrupted file;
- unsupported format;
- unrecoverable parser failure.

These should terminate the workflow with a clear error.

LangGraph supports node retry policies and fault-tolerant checkpointed execution, but `interrupt()` is intentionally not treated as an error/retry event. citeturn1search6

---

# 17. Idempotency

Nodes that can be replayed/resumed must be safe.

Especially:

- document extraction;
- normalization;
- validation;
- human review;
- final persistence.

Use stable identifiers:

```text
workflow_id
document_id
extraction_version
```

Do not create duplicate Annex records if a finalization node is executed again.

Use an idempotency key such as:

```text
document_id + extraction_version
```

---

# 18. Recommended Graph Implementation

Conceptual structure:

```python
from langgraph.graph import StateGraph, START, END

builder = StateGraph(ExtractionState)

builder.add_node("ingest_document", ingest_document)
builder.add_node("extract_document_content", extract_document_content)
builder.add_node("build_evidence_context", build_evidence_context)
builder.add_node("extract_parameters", extract_parameters)
builder.add_node("normalize_parameters", normalize_parameters)
builder.add_node("validate_parameters", validate_parameters)
builder.add_node("human_review", human_review)
builder.add_node("apply_human_decision", apply_human_decision)
builder.add_node("finalize_annex", finalize_annex)

builder.add_edge(START, "ingest_document")
builder.add_edge("ingest_document", "extract_document_content")
builder.add_edge("extract_document_content", "build_evidence_context")
builder.add_edge("build_evidence_context", "extract_parameters")
builder.add_edge("extract_parameters", "normalize_parameters")
builder.add_edge("normalize_parameters", "validate_parameters")

builder.add_conditional_edges(
    "validate_parameters",
    route_after_validation,
    {
        "valid": "finalize_annex",
        "needs_human": "human_review",
        "failed": END,
    },
)

builder.add_edge("human_review", "apply_human_decision")
builder.add_edge("apply_human_decision", "validate_parameters")
builder.add_edge("finalize_annex", END)

graph = builder.compile(checkpointer=checkpointer)
```

The exact implementation should be adapted to the installed LangGraph version; do not copy old examples blindly.

---

# 19. Finalization

`finalize_annex` is the final gate.

It must assert:

```text
No required field is unresolved
AND
No validation errors remain
AND
All required human decisions are applied
```

Then create:

```json
{
  "document_id": "...",
  "status": "VALIDATED",
  "annex": {
    "tag_no": "...",
    "description": "...",
    "ref_data_sheet": "...",
    "design_code": "...",
    "moc": "...",
    "qty": 1,
    "orientation": "...",
    "vessel_id_mm": 5800,
    "vessel_tl_tl_length_mm": 54870,
    "shell_min_thk_mm": 30,
    "head_min_thk_mm": 21.82,
    "head_type": "...",
    "nozzle_type": "...",
    "impact_tested": "...",
    "rt": "...",
    "pwht": "...",
    "support_type": "...",
    "painting": {
      "external": "...",
      "internal": "..."
    },
    "weight_tons_each": "..."
  }
}
```

---

# 20. API Lifecycle

### Start

```text
POST /documents
```

→ creates `document_id` and `workflow_id`

### Process

```text
POST /workflows/{workflow_id}/run
```

### Check status

```text
GET /workflows/{workflow_id}
```

Possible states:

```text
PROCESSING
WAITING_FOR_HUMAN
VALIDATING
COMPLETED
FAILED
```

### Submit review

```text
POST /workflows/{workflow_id}/review
```

The backend converts the submitted review into:

```python
Command(resume=review_payload)
```

### Retrieve final result

```text
GET /workflows/{workflow_id}/annex
```

---

# 21. Security / Data Integrity

- Never expose raw internal filesystem paths to the frontend.
- Validate uploaded files.
- Limit file size and page count.
- Sanitize filenames.
- Store documents outside executable directories.
- Never trust LLM output without schema validation.
- Never trust user-entered engineering values without deterministic validation.
- Keep extraction evidence and human corrections auditable.
- Do not allow finalization when unresolved required fields exist.

---

# 22. Observability

Every workflow should have:

```text
workflow_id
document_id
node
status
started_at
completed_at
error
model
model_version
prompt_version
extraction_version
```

For each parameter, retain:

```text
value
confidence
source page
source text
bbox
status
validation result
human correction
```

This makes extraction errors debuggable and allows comparison between model/prompt versions.

---

# 23. Testing Strategy

Test the graph as a state machine, not only individual functions.

Critical integration test:

```text
start workflow
    ↓
extract
    ↓
validation detects missing PWHT
    ↓
graph interrupts
    ↓
assert status == WAITING_FOR_HUMAN
    ↓
resume with PWHT=YES
    ↓
validation passes
    ↓
finalize
    ↓
assert status == COMPLETED
```

Also test:

- invalid human value;
- conflicting values;
- multiple missing fields;
- resume after process restart;
- duplicate resume request;
- OCR failure;
- LLM malformed output;
- empty document;
- all fields present;
- no hallucinated defaults.

---

# 24. Architectural Principle

The most important separation is:

```text
LLM
↓
"Here is what I think the document says."

Deterministic Validator
↓
"Is that value structurally and logically acceptable?"

Human
↓
"Resolve what the system cannot safely determine."

Finalizer
↓
"Only validated data enters the Annex."
```

LangGraph controls the state transitions between these stages.

It should not be used as a substitute for validation logic.
