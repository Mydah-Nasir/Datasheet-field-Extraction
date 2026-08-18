# Mechanical Datasheet Annex Extraction

AI-powered extraction of engineering parameters from Mechanical Datasheets for the BID PROJECT.

## Overview

This application accepts Mechanical Datasheets (PDFs or images) — individually or in batches — and extracts canonical engineering parameters to populate the **ANNEXURE-1 (REV.04) - EQUIPMENT SUMMARY**. The system uses:

- **Gemini** — OCR, visual layout understanding, and structured parameter extraction
- **Multi-Pass Boolean Verification** — Independent majority voting for checkbox & radio-button fields (`PWHT`, `Impact Tested`)
- **LangGraph** — Stateful workflow orchestration with Human-in-the-Loop review
- **Deterministic Normalization & Validation** — Strict rule-based unit conversions and physical checks
- **Streamlit Web UI** — Interactive multi-datasheet batch processing, full-screen Annexure-1 inspection, and Excel/CSV/JSON export

### Pipeline

```text
Mechanical Datasheet(s)
        ↓
Gemini OCR / Document Understanding & Extraction
        ↓
Multi-Pass Checkbox Self-Verification & Evidence Cross-Check
        ↓
Deterministic Normalization & Physical Validation
        ↓
        ├── PASSED → Automated Annexure Record
        └── NEEDS REVIEW → Human-in-the-Loop Inspection & Interactive Correction
                ↓
ANNEXURE-1 (REV.04) Equipment Summary (UI Table & Excel / CSV / JSON Export)
```

## Extracted Parameters (Annexure-1 Columns)

| # | Column Name | Canonical Key | Description / Format |
|---|-------------|---------------|----------------------|
| 1 | S/N | `idx` | Sequential item index |
| 2 | TAG NO. | `tag_no` | Equipment tag identifier(s) |
| 3 | DESCRIPTION | `description` | Equipment service / description |
| 4 | Ref Data sheet | `ref_data_sheet` | Reference document number (e.g. SD-xxx) |
| 5 | DESIGN CODE | `design_code` | Applicable design code (e.g. ASME Sec VIII Div 1) |
| 6 | MOC | `moc` | Main material of construction (e.g. SA-516 Gr. 70N) |
| 7 | QTY. | `qty` | Quantity of identical units |
| 8 | VERT / HOR | `orientation` | Vessel orientation (`VERTICAL` / `HORIZONTAL`) |
| 9 | VESSEL ID (mm) | `vessel_id_mm` | Inside diameter in mm |
| 10 | VESSEL (TL-TL) LENGTH mm | `vessel_tl_tl_length_mm` | Tangent-to-tangent length in mm |
| 11 | SHELL MIN. THK - mm | `shell_min_thk_mm` | Minimum shell thickness in mm |
| 12 | HEAD MIN. THK. mm | `head_min_thk_mm` | Minimum head thickness in mm |
| 13 | HEAD TYPE | `head_type` | Head type (e.g. 2:1 Ellipsoidal, Hemispherical) |
| 14 | NOZZLE TYPE | `nozzle_type` | Complete nozzle types, pressure ratings, and flanges |
| 15 | Impact Tested | `impact_tested` | `YES` / `NO` verified from radio buttons |
| 16 | RT | `rt` | Radiography requirement (e.g. FULL, SPOT) |
| 17 | PWHT | `pwht` | Post-Weld Heat Treatment (`YES` / `NO`) |
| 18 | TYPE OF SUPPORT | `support_type` | Full support description (e.g. SKIRT, SADDLE & PAD) |
| 19 | EXTERNAL PAINTING | `painting.external` | External coating spec (e.g. APCS-11A / APCS-2A) |
| 20 | INTERNAL PAINTING | `painting.internal` | Internal coating spec (or `NONE` / `N/A`) |
| 21 | Pickling & Passivation | `pickling_passivation` | Pickling, passivation, or preservation specs (or `N/A`) |
| 22 | WT-Tons (Each) (Approx.) | `weight_tons_each` | Total weight per vessel in metric tons |

## Setup & Usage

### Prerequisites

- Python ≥ 3.11
- A Google Gemini API key (`GEMINI_API_KEY` or `GOOGLE_API_KEY`)

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

# Install dependencies
pip install -e ".[dev]"

# Configure environment
# Copy .streamlit/secrets.toml.example to .streamlit/secrets.toml and add your GEMINI_API_KEY
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

### Running the Web Application

Launch the Streamlit interactive dashboard:

```bash
streamlit run app.py
```

### Running Tests

```bash
pytest tests/unit
```

## Project Structure

```text
Datasheet-field-Extraction/
├── app.py            # Streamlit web application
├── requirements.txt  # Project dependencies
├── pyproject.toml    # Tool and package configuration
├── src/
│   ├── annexure/     # AnnexureRecord models, builder, and multi-format exporters (Excel, CSV, JSON)
│   ├── api/          # FastAPI REST endpoints
│   ├── document/     # Document ingestion, PyMuPDF rendering, page layout
│   ├── domain/       # Canonical ExtractionResult schema, field statuses, validation rules
│   ├── extraction/   # Gemini multi-modal extraction service, prompts, and deterministic normalizers
│   ├── graph/        # LangGraph stateful graph, HITL checkpoints, nodes, and routing
│   ├── persistence/  # Checkpointer memory configuration
│   └── config.py     # Application and secrets configuration
│   ├── app.py        # Streamlit web application
│   └── config.py     # Pydantic environment configuration
├── tests/
│   ├── unit/         # Unit test suite
│   ├── integration/  # Integration test suite
│   └── conftest.py   # Shared test fixtures
└── pyproject.toml    # Project dependencies and configuration
```

## Key Principles

1. **No hallucination** — Missing parameters are marked as `null` with status `MISSING`, never fabricated.
2. **Evidence-based** — Every extracted field preserves source page, raw text, bounding box coordinates, and confidence score.
3. **Deterministic validation** — Python enforces engineering rules and physical checks; the LLM is not used to grade itself.
4. **Human-in-the-loop** — Low-confidence or flagged fields route to the interactive inspector for human review and single-click correction before final export.
5. **Multi-File Batch Extraction** — Supports bulk uploads with live sequential progress tracking.