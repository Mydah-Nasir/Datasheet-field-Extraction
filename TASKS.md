# Tasks — Mechanical Datasheet Annex Extraction

## Phase 0 — Project Setup

- [ ] Create repository structure.
- [ ] Create Python environment.
- [ ] Add dependency management.
- [ ] Configure linting/formatting.
- [ ] Configure pytest.
- [ ] Add `.env.example`.
- [ ] Add initial README.
- [ ] Verify LangGraph installation.
- [ ] Verify PDF/OCR dependencies.
- [ ] Create initial CI/test command.

---

# Phase 1 — Define the Contract

- [ ] Implement canonical 19-parameter schema.
- [ ] Define field statuses.
- [ ] Define evidence schema.
- [ ] Define confidence format.
- [ ] Define normalized units.
- [ ] Define validation error format.
- [ ] Define human-review payload.
- [ ] Define final Annex response contract.

### Acceptance

A sample extraction can be represented completely by the schema without arbitrary keys.

---

# Phase 2 — Document Ingestion

- [ ] Implement file upload.
- [ ] Validate extension.
- [ ] Validate file size.
- [ ] Generate document ID.
- [ ] Store source document.
- [ ] Implement page counting.
- [ ] Detect text-based vs scanned PDF.
- [ ] Add page metadata.

### Tests

- [ ] valid PDF
- [ ] invalid file
- [ ] empty file
- [ ] unsupported format
- [ ] multi-page PDF

---

# Phase 3 — Native PDF Extraction

- [ ] Extract text with coordinates.
- [ ] Preserve page numbers.
- [ ] Preserve blocks/words.
- [ ] Preserve bounding boxes.
- [ ] Detect tables/regions where practical.
- [ ] Create normalized `DocumentPage` representation.

### Tests

- [ ] known PDF
- [ ] multi-page PDF
- [ ] table-heavy PDF
- [ ] coordinate preservation

---

# Phase 4 — OCR

- [ ] Implement scanned-page detection.
- [ ] Render PDF pages.
- [ ] Preprocess images.
- [ ] Run OCR.
- [ ] Preserve OCR bounding boxes.
- [ ] Normalize OCR output.
- [ ] Merge OCR output into common document representation.

### Tests

- [ ] scanned page
- [ ] low-quality scan
- [ ] rotated page
- [ ] table extraction
- [ ] numeric extraction

---

# Phase 5 — Evidence Builder

- [ ] Group text by page.
- [ ] Build nearby label-value candidates.
- [ ] Preserve coordinates.
- [ ] Identify likely tables.
- [ ] Create compact evidence context for LLM.
- [ ] Prevent irrelevant pages from overwhelming the prompt.

### Acceptance

The extraction model receives structured evidence rather than an unbounded raw document dump.

---

# Phase 6 — LLM Extraction

- [ ] Create canonical extraction prompt.
- [ ] Define field descriptions.
- [ ] Define terminology aliases.
- [ ] Use structured output/schema validation.
- [ ] Require evidence for extracted values.
- [ ] Require null for missing values.
- [ ] Reject unsupported guesses.
- [ ] Store model/prompt version.

### Tests

- [ ] all fields present
- [ ] fields missing
- [ ] terminology variations
- [ ] conflicting values
- [ ] malformed model response

---

# Phase 7 — Normalization

- [ ] Normalize units.
- [ ] Normalize orientation.
- [ ] Normalize yes/no values.
- [ ] Normalize material names without losing original text.
- [ ] Normalize thickness.
- [ ] Normalize dimensions.
- [ ] Normalize quantity.
- [ ] Preserve original extraction.

### Tests

- [ ] mm/m conversion
- [ ] HOR/HORIZONTAL
- [ ] VERT/VERTICAL
- [ ] YES/NO variants
- [ ] material spelling variants

---

# Phase 8 — Deterministic Validation

- [ ] Validate required fields.
- [ ] Validate numeric values.
- [ ] Validate positive dimensions.
- [ ] Validate quantity.
- [ ] Validate enum values.
- [ ] Validate units.
- [ ] Detect conflicts.
- [ ] Detect low-confidence fields.
- [ ] Produce structured validation errors.

### Acceptance

No unresolved validation error can reach `finalize_annex`.

---

# Phase 9 — LangGraph Workflow

- [ ] Implement `ExtractionState`.
- [ ] Implement `ingest_document`.
- [ ] Implement `extract_document_content`.
- [ ] Implement `build_evidence_context`.
- [ ] Implement `extract_parameters`.
- [ ] Implement `normalize_parameters`.
- [ ] Implement `validate_parameters`.
- [ ] Implement routing.
- [ ] Implement `finalize_annex`.
- [ ] Compile graph with checkpointer.

### Acceptance

A complete document can move from START to END without manual intervention when all fields are valid.

---

# Phase 10 — Human-in-the-Loop

- [ ] Implement `human_review`.
- [ ] Use `interrupt()` for pending review.
- [ ] Return JSON-serializable review payload.
- [ ] Expose pending fields.
- [ ] Implement frontend review form.
- [ ] Implement `Command(resume=...)`.
- [ ] Re-run validation after human correction.
- [ ] Store original extraction.
- [ ] Store human decision.
- [ ] Prevent unresolved values from finalization.

### Critical tests

- [ ] missing field → interrupt
- [ ] resume → validation
- [ ] invalid human input → interrupt again
- [ ] valid correction → finalization
- [ ] multiple fields in one review
- [ ] process restart → resume
- [ ] duplicate resume

---

# Phase 11 — Persistence

Development:

- [ ] In-memory checkpointer for local tests.

Production:

- [ ] Configure durable database-backed checkpointer.
- [ ] Persist workflow/thread state.
- [ ] Persist document status.
- [ ] Persist review status.
- [ ] Persist final Annex.
- [ ] Verify restart/resume behavior.

---

# Phase 12 — API

- [ ] `POST /documents`
- [ ] `POST /workflows/{id}/run`
- [ ] `GET /workflows/{id}`
- [ ] `GET /workflows/{id}/review`
- [ ] `POST /workflows/{id}/review`
- [ ] `GET /workflows/{id}/annex`

### Acceptance

Frontend can complete the entire workflow without directly accessing LangGraph internals.

---

# Phase 13 — UI

- [ ] Upload screen.
- [ ] Processing status.
- [ ] Extraction table.
- [ ] Confidence display.
- [ ] Source page display.
- [ ] Missing-field highlighting.
- [ ] Validation errors.
- [ ] Human review form.
- [ ] Correct/confirm actions.
- [ ] Final Annex MDS table.
- [ ] Export JSON/Excel if required.

---

# Phase 14 — End-to-End Testing

- [ ] Test known Mechanical Datasheet.
- [ ] Verify 19 parameters.
- [ ] Verify source evidence.
- [ ] Verify confidence.
- [ ] Verify missing values.
- [ ] Verify human interrupt.
- [ ] Verify resume.
- [ ] Verify final Annex.
- [ ] Verify no hallucinated values.
- [ ] Verify persistence.
- [ ] Verify restart recovery.

---

# Phase 15 — Estimation Integration Preparation

This phase starts only after extraction is reliable.

- [ ] Freeze Annex schema.
- [ ] Define versioned API contract.
- [ ] Expose validated values.
- [ ] Provide material/geometry constants to estimation.
- [ ] Do not implement cost calculations inside the extraction graph.
- [ ] Add integration contract tests.

---

# Priority Order

Implement in this order:

```text
1. Schema
2. Document ingestion
3. PDF/OCR extraction
4. Evidence/layout
5. LLM extraction
6. Normalization
7. Validation
8. LangGraph
9. Human interrupt/resume
10. Persistence
11. API
12. UI
13. End-to-end tests
14. Estimation integration
```

Do not jump to estimation before extraction and validation are reliable.
