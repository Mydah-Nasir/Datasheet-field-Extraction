# Requirements — Mechanical Datasheet Annex Extraction

## 1. Project Goal

Build an application that accepts a Mechanical Datasheet and reliably extracts the required engineering constants needed to populate the **ANNEX MDS**.

The immediate MVP ends at:

**Mechanical Datasheet → Document/Text/Layout Extraction → 19-Field Structured Extraction → Validation → Human Review for Missing/Uncertain Values → Final Validated Annex Data**

The validated output must be structured so that the downstream Estimation module can consume it.

> **Important field-count clarification:** the Jira description names 20 individual columns if External Painting and Internal Painting are counted separately. For this project we treat **Painting as one logical parameter with `external` and `internal` subfields**, giving the required **19 logical parameters**. Do not silently remove either painting value.

---

## 2. Scope

### In Scope

- Upload PDF/image Mechanical Datasheets.
- Support text-based PDFs and scanned/image-based PDFs.
- Extract text and document layout/coordinates.
- Identify engineering labels and their corresponding values.
- Normalize equivalent terminology and units.
- Extract the 19 logical parameters.
- Attach source/evidence information to every extracted value.
- Assign extraction confidence.
- Run deterministic validation rules.
- Detect missing, ambiguous, invalid, or conflicting values.
- Pause the workflow for human input when required.
- Persist workflow state so a user can return later.
- Resume the exact workflow after human input.
- Generate a final validated Annex MDS dataset.
- Expose the final structured data through the application/API.
- Maintain automated tests for extraction, validation, interrupt/resume, and end-to-end flow.

### Out of Scope for MVP

- Full estimation/cost engine.
- Shell/head/nozzle/support costing.
- Material price calculations.
- Plate optimization.
- NDT/painting/hydrotest/transportation costing.
- Automatic engineering assumptions when the datasheet is missing information.
- Autonomous approval of questionable engineering values.

---

## 3. Required 19 Logical Parameters

The canonical schema is:

1. `tag_no`
2. `description`
3. `ref_data_sheet`
4. `design_code`
5. `moc`
6. `qty`
7. `orientation`
8. `vessel_id_mm`
9. `vessel_tl_tl_length_mm`
10. `shell_min_thk_mm`
11. `head_min_thk_mm`
12. `head_type`
13. `nozzle_type`
14. `impact_tested`
15. `rt`
16. `pwht`
17. `support_type`
18. `painting` — contains `external` and `internal`
19. `weight_tons_each`

If the business later requires External Painting and Internal Painting as separate top-level columns, split `painting` into two fields without changing the extraction semantics.

---

## 4. Canonical Output Contract

Every parameter must have a value/status/evidence structure.

Example:

```json
{
  "tag_no": {
    "value": "V-101",
    "status": "EXTRACTED",
    "confidence": 0.98,
    "evidence": [
      {
        "page": 1,
        "text": "TAG NO: V-101",
        "bbox": [100, 200, 260, 225]
      }
    ]
  }
}
```

Missing values must never be fabricated:

```json
{
  "pwht": {
    "value": null,
    "status": "MISSING",
    "confidence": 0.0,
    "evidence": []
  }
}
```

Possible statuses:

- `EXTRACTED`
- `NORMALIZED`
- `CALCULATED`
- `MISSING`
- `AMBIGUOUS`
- `INVALID`
- `CONFLICT`
- `USER_CONFIRMED`
- `USER_CORRECTED`

---

## 5. Extraction Requirements

### 5.1 Document ingestion

The application must accept:

- PDF
- scanned PDF
- PNG/JPEG where supported

The ingestion layer must preserve:

- file ID
- page number
- source document name
- page image
- extracted text
- coordinates/bounding boxes

### 5.2 Text extraction

Prefer native PDF text extraction when available.

Use OCR for scanned/image content.

The extraction layer should preserve coordinates because Mechanical Datasheets are spatial documents.

### 5.3 Semantic extraction

The system must understand terminology variations.

Examples:

- `MOC`, `Material`, `Material of Construction`
- `I.DIA`, `ID`, `Inside Diameter`, `Internal Diameter`
- `TL/TL`, `T/T`, `Tangent to Tangent Length`
- `PWHT`, `Post Weld Heat Treatment`
- `RT`, `Radiography`, `Radiographic Testing`
- `VER`, `VERT`, `Vertical`
- `HOR`, `HORIZ`, `Horizontal`

The LLM must extract into the canonical schema rather than returning arbitrary field names.

---

## 6. Validation Requirements

Validation must be deterministic wherever possible.

Examples:

### Numeric validation

- ID must be numeric and positive.
- Thickness must be numeric and positive.
- Quantity must be an integer and positive.
- Weight must be non-negative.
- Dimensions must use known units.

### Enum validation

Orientation:

- `VERTICAL`
- `HORIZONTAL`
- `UNKNOWN`

PWHT:

- `YES`
- `NO`
- `UNKNOWN`

Impact Test:

- `YES`
- `NO`
- `UNKNOWN`

### Cross-field validation

Examples:

- A populated shell thickness cannot be zero.
- Head thickness should be checked against expected engineering ranges when a business rule exists.
- Units must be normalized before validation.
- Conflicting values from different pages must be flagged rather than arbitrarily selected.

Do not create engineering limits without approval from the domain expert.

---

## 7. Human-in-the-Loop Requirements

The workflow must pause when:

- a required parameter is missing;
- multiple candidate values conflict;
- extraction confidence is below the configured threshold;
- a validation rule fails;
- a value requires explicit engineering confirmation.

The human-review screen should show:

- parameter name;
- extracted value;
- status;
- confidence;
- source page;
- source text;
- bounding box/highlight where possible;
- candidate values if there is a conflict;
- editable input;
- confirm/correct action.

The workflow must then resume from persisted state.

A human correction must be stored as a separate event/value rather than destroying the original extraction evidence.

---

## 8. No Hallucination Rule

The system must never infer a missing engineering constant solely from domain assumptions.

For example:

```text
Datasheet: PWHT = blank

Wrong:
PWHT = YES

Correct:
PWHT = MISSING
→ pause for human input
```

The same rule applies to material, thickness, dimensions, weight, design code, testing requirements, and other engineering constants.

---

## 9. Acceptance Criteria

The MVP is accepted when:

- A Mechanical Datasheet can be uploaded.
- Text/native PDF and OCR paths work.
- The system extracts the 19 logical parameters into a fixed schema.
- Every value has evidence and confidence.
- Missing/ambiguous values are detected.
- Invalid values are rejected or flagged.
- No missing value is silently hallucinated.
- The graph pauses for human input when necessary.
- The workflow survives application restarts when using a production checkpointer.
- The same `thread_id` resumes the same workflow.
- User corrections are persisted.
- The final validated Annex MDS is generated.
- Unit/integration tests cover the critical paths.
- An end-to-end test proves:

```text
Upload
→ Extract
→ Validate
→ Interrupt
→ Human Correction
→ Resume
→ Final Validated Annex
```

---

## 10. Definition of Done

A task is not complete merely because the code runs.

It is complete only when:

- implementation exists;
- tests exist;
- tests pass;
- failure cases are covered;
- relevant documentation is updated;
- no known regression is introduced;
- the output contract remains compatible.
