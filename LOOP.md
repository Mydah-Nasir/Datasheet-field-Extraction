# LOOP.md — Loop Engineering Rules for Antigravity IDE

## 1. Purpose

This document defines how an AI coding agent working in Antigravity IDE must develop this project.

The agent must operate in a controlled engineering loop:

```text
UNDERSTAND
   ↓
PLAN
   ↓
IMPLEMENT
   ↓
TEST
   ↓
VERIFY
   ↓
REVIEW
   ↓
DOCUMENT
   ↓
NEXT TASK
```

Never treat code generation as completion.

---

# 2. Source of Truth

Before modifying code, read:

1. `docs/REQUIREMENTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/TASKS.md`
4. existing source code
5. relevant tests

If the requested change conflicts with the architecture, stop and explain the conflict before implementing it.

---

# 3. One Task at a Time

The agent should select the smallest unfinished task that produces a testable increment.

Bad:

```text
Build the entire AI extraction system.
```

Good:

```text
Implement the canonical ExtractionField schema and tests.
```

Then:

```text
Implement PDF text extraction with bounding boxes.
```

Then:

```text
Implement structured LLM extraction.
```

Then:

```text
Implement deterministic validation.
```

Then:

```text
Implement LangGraph routing.
```

---

# 4. Before Coding

For every task:

### Step 1 — Understand

Identify:

- current behavior;
- desired behavior;
- affected files;
- dependencies;
- acceptance criteria;
- failure cases.

### Step 2 — Plan

Write a short implementation plan:

```text
1. Modify X.
2. Add Y.
3. Add tests for Z.
4. Run test suite.
```

Do not start coding until the plan is internally consistent.

---

# 5. Implementation Rules

## Rule 1 — Prefer deterministic code

Use deterministic code for:

- schema validation;
- type validation;
- units;
- numeric validation;
- enum validation;
- required fields;
- routing conditions;
- persistence;
- idempotency.

Use the LLM for:

- semantic interpretation;
- terminology mapping;
- label/value understanding;
- extracting information from messy document context.

Do not use an LLM for something that can be implemented reliably as a normal function.

---

## Rule 2 — Never hallucinate engineering values

If the Mechanical Datasheet does not provide a value:

```text
value = null
status = MISSING
```

Do not create a value from "typical" engineering practice.

If uncertain:

```text
status = AMBIGUOUS
```

and route to human review.

---

## Rule 3 — Preserve Evidence

Never store only:

```json
{
  "moc": "SA 516 Gr 70"
}
```

Store:

```json
{
  "value": "SA 516 Gr 70",
  "status": "EXTRACTED",
  "confidence": 0.97,
  "evidence": {
    "page": 2,
    "text": "Material: SA 516 Gr 70",
    "bbox": [100, 200, 300, 230]
  }
}
```

Evidence is required for debugging and human review.

---

# 6. LangGraph Rules

## Rule 1 — LangGraph owns workflow state

Do not create custom global variables to track workflow progress.

Use LangGraph state.

```text
ExtractionState
```

must contain the information needed to resume the workflow.

---

## Rule 2 — Always use a stable thread ID

Every workflow has:

```text
workflow_id == thread_id
```

When starting:

```python
config = {
    "configurable": {
        "thread_id": workflow_id
    }
}
```

When resuming:

```python
graph.invoke(
    Command(resume=payload),
    config=config
)
```

Never create a new thread ID for a human-review resume.

---

## Rule 3 — Human review uses `interrupt()`

Use:

```python
from langgraph.types import interrupt
```

not ad-hoc polling loops inside the graph.

The graph should pause naturally:

```text
validate
   ↓
needs human?
   ↓
interrupt()
   ↓
WAIT
   ↓
Command(resume=...)
   ↓
validate again
```

---

## Rule 4 — Validate after human input

Never do:

```text
human input
   ↓
finalize
```

Always:

```text
human input
   ↓
apply correction
   ↓
validate
   ↓
finalize
```

The user can enter an invalid value.

---

## Rule 5 — Keep interrupts deterministic

Avoid multiple conditional interrupts in the same node.

Prefer one review payload containing all fields requiring attention.

Bad:

```python
if missing_a:
    interrupt(...)

if missing_b:
    interrupt(...)
```

Better:

```python
review_items = build_review_items(state)
decision = interrupt(review_items)
```

---

## Rule 6 — No irreversible side effects before interrupt

Do not:

```python
save_final_record()
interrupt(...)
```

because the node can restart when resumed.

Instead:

```python
decision = interrupt(...)
return {"human_review": decision}
```

Then perform the final idempotent write after validation.

---

# 7. Testing Loop

After every implementation:

```text
IMPLEMENT
   ↓
UNIT TEST
   ↓
INTEGRATION TEST
   ↓
FULL TEST SUITE
```

Minimum command:

```bash
pytest
```

If the test suite fails:

```text
FAIL
 ↓
READ ERROR
 ↓
IDENTIFY ROOT CAUSE
 ↓
FIX
 ↓
RETEST
```

Never hide or ignore a failing test.

---

# 8. Test-First Expectations

For critical logic, write the test before or together with implementation.

Especially:

- field schema;
- normalization;
- validation;
- routing;
- interrupt;
- resume;
- human correction;
- finalization.

Example:

```text
Given:
PWHT is missing

When:
validation runs

Then:
status = WAITING_FOR_HUMAN
and graph produces an interrupt
```

---

# 9. Required HITL Test

Every major change to HITL behavior must preserve this test:

```text
START
 ↓
extract
 ↓
missing PWHT
 ↓
validate
 ↓
interrupt
 ↓
WAITING_FOR_HUMAN
 ↓
resume(PWHT=YES)
 ↓
validate
 ↓
PASS
 ↓
finalize
 ↓
COMPLETED
```

Also test:

```text
resume(PWHT="INVALID")
 ↓
validate
 ↓
FAIL
 ↓
interrupt again
```

---

# 10. Regression Protection

Before changing extraction behavior:

1. Run existing tests.
2. Make the change.
3. Add/update tests.
4. Run tests again.
5. Compare extraction output against known fixtures.

Do not modify working extraction logic just to make one document pass unless the change is supported by a general rule.

---

# 11. Fixture-Based Development

Maintain representative Mechanical Datasheet fixtures.

Example:

```text
tests/fixtures/
├── complete_datasheet.pdf
├── missing_pwht.pdf
├── ambiguous_moc.pdf
├── scanned_datasheet.pdf
├── multi_page_datasheet.pdf
└── conflicting_values.pdf
```

Each fixture should have expected structured output.

This prevents model/prompt changes from silently breaking extraction.

---

# 12. LLM Changes

Whenever changing:

- model;
- prompt;
- temperature;
- structured schema;
- extraction strategy;

run the extraction regression suite.

Record:

```text
model
prompt_version
schema_version
fixture
expected
actual
pass/fail
```

Do not judge an extraction model only from one successful document.

---

# 13. Error Handling

Classify errors.

### User/data error

Example:

```text
Missing PWHT
```

→ human review.

### Model error

Example:

```text
Malformed structured output
```

→ retry or fail safely.

### Infrastructure error

Example:

```text
OCR service timeout
```

→ retry with bounded attempts.

### Fatal error

Example:

```text
Corrupted PDF
```

→ fail workflow with actionable message.

---

# 14. No Silent Fallbacks

Bad:

```python
if extraction_failed:
    value = "UNKNOWN"
```

if `UNKNOWN` is not explicitly part of the business schema.

Better:

```python
status = "EXTRACTION_FAILED"
```

and route appropriately.

Never silently replace missing engineering data with a guessed value.

---

# 15. Documentation Loop

Whenever architecture changes:

```text
CODE CHANGE
   ↓
TEST
   ↓
UPDATE ARCHITECTURE.md
```

Whenever requirements change:

```text
REQUIREMENTS.md
   ↓
TASKS.md
   ↓
CODE
   ↓
TESTS
```

Do not let documentation drift from implementation.

---

# 16. Completion Checklist

Before saying a task is complete:

- [ ] Requirement understood.
- [ ] Existing implementation inspected.
- [ ] Small implementation plan created.
- [ ] Code implemented.
- [ ] Unit tests added.
- [ ] Integration tests added where necessary.
- [ ] Existing tests pass.
- [ ] No silent fallback introduced.
- [ ] No engineering value hallucination introduced.
- [ ] Evidence is preserved.
- [ ] LangGraph state remains serializable.
- [ ] HITL uses `interrupt()`.
- [ ] Resume uses the same `thread_id`.
- [ ] Human input is validated again.
- [ ] Side effects are idempotent.
- [ ] Documentation updated if behavior changed.

Only then mark the task complete.

---

# 17. Agent Working Format

For each task, the Antigravity agent should internally follow:

```text
TASK
↓
READ REQUIREMENTS
↓
INSPECT REPOSITORY
↓
PLAN
↓
IMPLEMENT
↓
WRITE TESTS
↓
RUN TESTS
↓
FIX FAILURES
↓
RUN FULL SUITE
↓
REVIEW DIFF
↓
UPDATE DOCS
↓
MARK TASK COMPLETE
```

The agent should not move to the next task when the current task has failing tests unless the failure is explicitly documented as an external blocker.

---

# 18. Golden Rule

> **Never optimize for "the code looks complete." Optimize for "the workflow is correct, testable, resumable, auditable, and safe for engineering data."**

For this project, correctness means:

```text
Extract accurately
      +
Preserve evidence
      +
Validate deterministically
      +
Ask humans when uncertain
      +
Persist state
      +
Resume safely
      +
Never invent engineering values
```
