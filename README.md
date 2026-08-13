# Mechanical Datasheet Annex Extraction

AI-powered extraction of engineering parameters from Mechanical Datasheets for the BID PROJECT.

## Overview

This application accepts a Mechanical Datasheet (PDF or image) and extracts **19 logical engineering parameters** needed to populate the ANNEX MDS. The system uses:

- **Gemini** — primary OCR and document understanding engine
- **LangGraph** — stateful workflow orchestration with human-in-the-loop
- **Deterministic Python validation** — no LLM-based validation of engineering values

### Pipeline

```text
Mechanical Datasheet
        ↓
Gemini OCR / Document Understanding
        ↓
Text + Layout + Evidence
        ↓
19-Parameter Structured Extraction
        ↓
Normalization
        ↓
Deterministic Validation
        ↓
        ├── VALID → Final ANNEX
        └── NEEDS REVIEW → Human-in-the-Loop → Validate Again → ANNEX
```

## 19 Extracted Parameters

| # | Field | Canonical Key |
|---|-------|---------------|
| 1 | TAG NO. | `tag_no` |
| 2 | DESCRIPTION | `description` |
| 3 | Ref Data Sheet | `ref_data_sheet` |
| 4 | DESIGN CODE | `design_code` |
| 5 | MOC (Main Material) | `moc` |
| 6 | QTY. | `qty` |
| 7 | VERT / HOR | `orientation` |
| 8 | VESSEL ID (mm) | `vessel_id_mm` |
| 9 | VESSEL (TL-TL) LENGTH (mm) | `vessel_tl_tl_length_mm` |
| 10 | SHELL MIN. THK. (mm) | `shell_min_thk_mm` |
| 11 | HEAD MIN. THK. (mm) | `head_min_thk_mm` |
| 12 | HEAD TYPE | `head_type` |
| 13 | NOZZLE TYPE | `nozzle_type` |
| 14 | Impact Tested | `impact_tested` |
| 15 | RT (Radiography) | `rt` |
| 16 | PWHT | `pwht` |
| 17 | TYPE OF SUPPORT | `support_type` |
| 18 | PAINTING | `painting` (external + internal) |
| 19 | WT-Tons (Each) | `weight_tons_each` |

## Setup

### Prerequisites

- Python ≥ 3.11
- A Google Gemini API key

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd Datasheet-field-Extraction

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Copy environment template and configure
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Running Tests

```bash
pytest
```

### Linting

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Project Structure

```text
Datasheet-field-Extraction/
├── src/
│   ├── api/          # FastAPI routes
│   ├── domain/       # Schema, statuses, validation rules
│   ├── document/     # Ingestion, PDF extraction, OCR, layout
│   ├── extraction/   # LLM prompts, structured extraction, normalization
│   ├── graph/        # LangGraph state, nodes, routing, workflow
│   ├── persistence/  # Checkpointer configuration
│   └── config.py     # Environment configuration
├── tests/
│   ├── unit/         # Unit tests
│   ├── integration/  # Integration tests
│   └── conftest.py   # Shared fixtures
├── ARCHITECTURE.md   # System architecture specification
├── REQUIREMENTS.md   # Functional requirements
├── TASKS.md          # Phased task list
├── LOOP.md           # Loop engineering process
└── pyproject.toml    # Project configuration
```

## Documentation

- [REQUIREMENTS.md](REQUIREMENTS.md) — functional requirements and acceptance criteria
- [ARCHITECTURE.md](ARCHITECTURE.md) — system architecture and component design
- [TASKS.md](TASKS.md) — phased implementation task list
- [LOOP.md](LOOP.md) — loop engineering development process

## Key Principles

1. **No hallucination** — missing values are `null` with status `MISSING`, never fabricated
2. **Evidence-based** — every extracted value preserves page, text, bbox, and confidence
3. **Deterministic validation** — Python validates; the LLM does not judge correctness
4. **Human-in-the-loop** — LangGraph `interrupt()` / `Command(resume=...)` for uncertain values
5. **Resumable workflows** — checkpointed state survives restarts