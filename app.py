"""Streamlit application for Multi-Datasheet Extraction and Annexure-1 Equipment Summary."""

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st
from langgraph.types import Command

from src.annexure.export import export_to_csv, export_to_excel, export_to_json
from src.annexure.models import AnnexureRecord
from src.config import settings
from src.domain.schema import ExtractionResult, FieldStatus
from src.graph.workflow import build_graph

# --- SVG Icons Collection (No Emojis) ---
SVG_ICONS = {
    "table": """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18"></path><rect width="18" height="18" x="3" y="3" rx="2"></rect><path d="M3 9h18"></path><path d="M3 15h18"></path></svg>""",
    "file": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>""",
    "download": """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>""",
    "settings": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>""",
    "layers": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>""",
    "check": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>""",
    "maximize": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"></polyline><polyline points="9 21 3 21 3 15"></polyline><line x1="21" y1="3" x2="14" y2="10"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>""",
}

# --- Page Configuration ---
st.set_page_config(
    page_title="ANNEXURE-1 - EQUIPMENT SUMMARY",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Global CSS Styling: Fullscreen Modal, Solid Blue Buttons, and Zero-Congestion Table
st.markdown(
    """
    <style>
    /* Fullscreen Modal Dialog Styling */
    div[data-testid="stDialog"] > div {
        width: 96vw !important;
        max-width: 96vw !important;
        margin: 0 auto !important;
        padding: 24px 28px !important;
        background: #ffffff !important;
        border-radius: 10px !important;
    }
    div[data-testid="stDialog"] > div > div {
        width: 100% !important;
        max-width: 100% !important;
    }

    /* All Buttons Blue Styling */
    button[data-testid="baseButton-primary"],
    button[data-testid="baseButton-secondary"],
    .stButton > button,
    .stDownloadButton > button {
        background-color: #1d4ed8 !important;
        color: #ffffff !important;
        border: 1px solid #3b82f6 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
    }
    button[data-testid="baseButton-primary"]:hover,
    button[data-testid="baseButton-secondary"]:hover,
    .stButton > button:hover,
    .stDownloadButton > button:hover {
        background-color: #1e40af !important;
        border-color: #60a5fa !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(29, 78, 216, 0.3) !important;
    }

    /* Metric Cards Styling */
    .metric-card-box {
        background: #1d4ed8 !important;
        border: 1px solid #3b82f6 !important;
        border-radius: 10px;
        padding: 14px 18px;
        color: #ffffff !important;
        display: flex;
        align-items: center;
        gap: 14px;
        box-shadow: 0 4px 12px rgba(29, 78, 216, 0.2);
    }
    .metric-title {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #eff6ff !important;
        font-weight: 600;
        margin: 0;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #ffffff !important;
        margin: 2px 0 0 0;
    }

    .annexure-title-header {
        text-align: center;
        font-size: 1.4rem;
        font-weight: 800;
        color: #1e3a8a;
        text-decoration: underline;
        margin: 10px 0 20px 0;
        letter-spacing: 0.04em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_graph():
    """Cache the compiled LangGraph workflow checkpointer."""
    return build_graph()


graph = get_graph()

# --- Initialize Multi-Document Session State ---
if "documents" not in st.session_state:
    st.session_state.documents = {}

if "selected_doc_id" not in st.session_state:
    st.session_state.selected_doc_id = None


def get_doc_state(thread_id: str):
    """Retrieve LangGraph state for a specific document thread."""
    config = {"configurable": {"thread_id": thread_id}}
    return graph.get_state(config)


def extract_single_doc(doc_id: str) -> None:
    """Execute the extraction workflow for a single document."""
    doc = st.session_state.documents.get(doc_id)
    if not doc:
        return

    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        doc["error"] = "GEMINI_API_KEY is not set. Please set it in your secrets.toml file."
        return

    config = {"configurable": {"thread_id": doc["thread_id"]}}
    try:
        graph.invoke(
            {"document_path": doc["file_path"], "workflow_id": doc["thread_id"]},
            config,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        doc["error"] = str(e)


def extract_all_documents(doc_ids: List[str], progress_placeholder=None) -> None:
    """Extract all specified documents sequentially within the active Streamlit context."""
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("GEMINI_API_KEY is not set. Please set it in your secrets.toml file.")
        st.stop()

    total = len(doc_ids)
    if total == 0:
        return

    for idx, d_id in enumerate(doc_ids):
        doc = st.session_state.documents.get(d_id)
        fname = doc["filename"] if doc else f"Document {idx+1}"
        if progress_placeholder:
            progress_placeholder.progress(
                (idx) / total,
                text=f"Extracting ({idx + 1}/{total}): {fname}...",
            )
        extract_single_doc(d_id)

    if progress_placeholder:
        progress_placeholder.progress(1.0, text="All datasheets extracted successfully!")


# --- Sidebar: Configuration & Document Management ---
with st.sidebar:
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
            {SVG_ICONS['settings']}
            <h3 style="margin:0; font-size:1.15rem; font-weight:600;">Control Panel</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Reset Session", width="stretch"):
        st.session_state.documents = {}
        st.session_state.selected_doc_id = None
        st.rerun()

    st.divider()

    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
            {SVG_ICONS['file']}
            <span style="font-weight:600; font-size:0.95rem;">Upload Datasheets</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "Upload Mechanical Datasheets (PDF / Images)",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help="Upload one or multiple datasheets simultaneously for batch extraction.",
        label_visibility="collapsed",
    )

    if uploaded_files:
        os.makedirs("scratch", exist_ok=True)
        for uf in uploaded_files:
            file_key = f"{uf.name}_{uf.size}"
            if file_key not in st.session_state.documents:
                tmp_path = os.path.join("scratch", uf.name)
                with open(tmp_path, "wb") as f:
                    f.write(uf.getbuffer())

                thread_id = str(uuid.uuid4())
                st.session_state.documents[file_key] = {
                    "id": file_key,
                    "filename": uf.name,
                    "file_path": tmp_path,
                    "size_bytes": uf.size,
                    "thread_id": thread_id,
                    "error": None,
                }
                if st.session_state.selected_doc_id is None:
                    st.session_state.selected_doc_id = file_key

    total_docs = len(st.session_state.documents)

    if total_docs > 0:
        pending_docs = []
        for d_id, d_info in st.session_state.documents.items():
            state = get_doc_state(d_info["thread_id"])
            if not state.values.get("document_path") and not d_info.get("error"):
                pending_docs.append(d_id)

        btn_label = (
            "Start Extraction" if total_docs == 1 else f"Start Extraction ({len(pending_docs) if pending_docs else total_docs} Files)"
        )

        if st.button(btn_label, type="primary", width="stretch"):
            api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                st.error("GEMINI_API_KEY is not set. Please set it in your secrets.toml file.")
                st.stop()

            target_ids = pending_docs if pending_docs else list(st.session_state.documents.keys())
            p_bar = st.progress(0, text="Starting batch extraction...")
            extract_all_documents(target_ids, p_bar)
            p_bar.progress(1.0, text="Extraction completed!")
            st.rerun()

        st.divider()
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                {SVG_ICONS['layers']}
                <span style="font-weight:600; font-size:0.95rem;">Uploaded Datasheets</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for d_id, d_info in list(st.session_state.documents.items()):
            state = get_doc_state(d_info["thread_id"])
            next_node = state.next[0] if state.next else None
            is_int = len(state.tasks) > 0 and bool(state.tasks[0].interrupts)
            is_comp = not next_node and bool(state.values.get("final_annex"))
            has_err = bool(state.values.get("error")) or bool(d_info.get("error"))

            if is_comp:
                badge = "[DONE]"
            elif is_int:
                badge = "[REVIEW]"
            elif has_err:
                badge = "[ERROR]"
            elif state.values.get("document_path"):
                badge = "[RUNNING]"
            else:
                badge = "[PENDING]"

            is_selected = st.session_state.selected_doc_id == d_id
            button_label = f"{badge} {d_info['filename']}"
            if st.button(
                button_label,
                key=f"btn_nav_{d_id}",
                width="stretch",
                type="secondary" if not is_selected else "primary",
            ):
                st.session_state.selected_doc_id = d_id
                st.rerun()


# --- Main Application Header ---
st.markdown(
    """
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
        <h2 style="margin:0; font-weight:700; color:#1e3a8a;">Mechanical Datasheet Extractor</h2>
    </div>
    <p style="color:#64748b; font-size:0.95rem; margin-top:-2px;">
        Automated multi-datasheet extraction, validation, and ANNEXURE-1 Equipment Summary generation.
    </p>
    """,
    unsafe_allow_html=True,
)

# --- Aggregate Document States & Data for Annexure Table ---
annex_table_rows = []
all_annex_records: List[AnnexureRecord] = []
total_count = len(st.session_state.documents)
completed_count = 0
review_count = 0
pending_count = 0
error_count = 0

doc_items = list(st.session_state.documents.items()) if st.session_state.documents else []

for idx, (d_id, d_info) in enumerate(doc_items, start=1):
    state = get_doc_state(d_info["thread_id"])
    next_node = state.next[0] if state.next else None
    is_int = len(state.tasks) > 0 and bool(state.tasks[0].interrupts)
    is_comp = not next_node and bool(state.values.get("final_annex"))
    has_err = bool(state.values.get("error")) or bool(d_info.get("error"))

    if is_comp:
        completed_count += 1
        final_annex = state.values.get("final_annex", {})
        try:
            rec = AnnexureRecord(**final_annex)
            all_annex_records.append(rec)
        except Exception:
            pass

        tag_no = final_annex.get("tag_no", "")
        description = final_annex.get("description", "")
        ref_ds = final_annex.get("ref_data_sheet", "")
        design_code = final_annex.get("design_code", "")
        moc = final_annex.get("moc", "")
        qty = final_annex.get("qty", "")
        orientation = final_annex.get("orientation", "")
        vessel_id = final_annex.get("vessel_id_mm", "")
        tl_tl = final_annex.get("vessel_tl_tl_length_mm", "")
        shell_thk = final_annex.get("shell_min_thk_mm", "")
        head_thk = final_annex.get("head_min_thk_mm", "")
        head_type = final_annex.get("head_type", "")
        nozzle_type = final_annex.get("nozzle_type", "")
        impact = final_annex.get("impact_tested", "")
        rt = final_annex.get("rt", "")
        pwht = final_annex.get("pwht", "")
        support = final_annex.get("support_type", "")
        ext_paint = final_annex.get("painting_external", "")
        int_paint = final_annex.get("painting_internal", "")
        pickling = final_annex.get("pickling_passivation", "N/A")
        weight = final_annex.get("weight_tons_each", "")

    elif is_int or state.values.get("normalized_extraction"):
        review_count += 1
        norm: Optional[ExtractionResult] = state.values.get("normalized_extraction")
        tag_no = norm.tag_no.value if norm and norm.tag_no.value is not None else ""
        description = norm.description.value if norm and norm.description.value is not None else ""
        ref_ds = norm.ref_data_sheet.value if norm and norm.ref_data_sheet.value is not None else ""
        design_code = norm.design_code.value if norm and norm.design_code.value is not None else ""
        moc = norm.moc.value if norm and norm.moc.value is not None else ""
        qty = norm.qty.value if norm and norm.qty.value is not None else ""
        orientation = norm.orientation.value if norm and norm.orientation.value is not None else ""
        vessel_id = norm.vessel_id_mm.value if norm and norm.vessel_id_mm.value is not None else ""
        tl_tl = norm.vessel_tl_tl_length_mm.value if norm and norm.vessel_tl_tl_length_mm.value is not None else ""
        shell_thk = norm.shell_min_thk_mm.value if norm and norm.shell_min_thk_mm.value is not None else ""
        head_thk = norm.head_min_thk_mm.value if norm and norm.head_min_thk_mm.value is not None else ""
        head_type = norm.head_type.value if norm and norm.head_type.value is not None else ""
        nozzle_type = norm.nozzle_type.value if norm and norm.nozzle_type.value is not None else ""
        impact = norm.impact_tested.value if norm and norm.impact_tested.value is not None else ""
        rt = norm.rt.value if norm and norm.rt.value is not None else ""
        pwht = norm.pwht.value if norm and norm.pwht.value is not None else ""
        support = norm.support_type.value if norm and norm.support_type.value is not None else ""
        ext_paint = norm.painting.external.value if norm and norm.painting.external.value is not None else ""
        int_paint = norm.painting.internal.value if norm and norm.painting.internal.value is not None else ""
        pickling_field = getattr(norm, "pickling_passivation", None) if norm else None
        pickling = pickling_field.value if (pickling_field and pickling_field.value is not None) else "N/A"
        weight = norm.weight_tons_each.value if norm and norm.weight_tons_each.value is not None else ""

    elif has_err:
        error_count += 1
        tag_no, description, ref_ds, design_code, moc, qty, orientation = "ERROR", "ERROR", "", "", "", "", ""
        vessel_id, tl_tl, shell_thk, head_thk, head_type, nozzle_type = "", "", "", "", "", ""
        impact, rt, pwht, support, ext_paint, int_paint, pickling, weight = "", "", "", "", "", "", "", ""
    else:
        pending_count += 1
        tag_no, description, ref_ds, design_code, moc, qty, orientation = "PENDING", "PENDING", "", "", "", "", ""
        vessel_id, tl_tl, shell_thk, head_thk, head_type, nozzle_type = "", "", "", "", "", ""
        impact, rt, pwht, support, ext_paint, int_paint, pickling, weight = "", "", "", "", "", "", "", ""

    # Format numbers cleanly
    vessel_id_str = f"{vessel_id:,.0f}" if isinstance(vessel_id, (int, float)) and vessel_id > 0 else str(vessel_id)
    tl_tl_str = f"{tl_tl:,.0f}" if isinstance(tl_tl, (int, float)) and tl_tl > 0 else str(tl_tl)
    weight_str = f"{weight:,.0f}" if isinstance(weight, (int, float)) and weight > 0 else str(weight)

    annex_table_rows.append(
        {
            "S/N": idx,
            "TAG NO.": str(tag_no),
            "DESCRIPTION": str(description),
            "Ref Data sheet": str(ref_ds),
            "DESIGN CODE": str(design_code),
            "MOC": str(moc),
            "QTY.": str(qty),
            "VERT / HOR": str(orientation),
            "VESSEL ID (mm)": vessel_id_str,
            "VESSEL (TL-TL) LENGTH mm": tl_tl_str,
            "SHELL MIN. THK - mm": str(shell_thk),
            "HEAD MIN. THK. mm": str(head_thk),
            "HEAD TYPE": str(head_type),
            "NOZZLE TYPE": str(nozzle_type),
            "Impact Tested": str(impact),
            "RT": str(rt),
            "PWHT": str(pwht),
            "TYPE OF SUPPORT": str(support),
            "EXTERNAL PAINTING": str(ext_paint),
            "INTERNAL PAINTING": str(int_paint),
            "Pickling & Passivation": str(pickling) if pickling else "N/A",
            "WT-Tons (Each) (Approx.)": weight_str,
            "_doc_id": d_id,
        }
    )


# --- Top Metrics Bar ---
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
with col_m1:
    st.markdown(
        f"""
        <div class="metric-card-box">
            <div>
                <p class="metric-title">Total Datasheets</p>
                <h3 class="metric-value">{total_count}</h3>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_m2:
    st.markdown(
        f"""
        <div class="metric-card-box">
            <div>
                <p class="metric-title">Completed</p>
                <h3 class="metric-value" style="color:#34d399;">{completed_count}</h3>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_m3:
    st.markdown(
        f"""
        <div class="metric-card-box">
            <div>
                <p class="metric-title">In Review</p>
                <h3 class="metric-value" style="color:#fde047;">{review_count}</h3>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_m4:
    st.markdown(
        f"""
        <div class="metric-card-box">
            <div>
                <p class="metric-title">Pending</p>
                <h3 class="metric-value" style="color:#cbd5e1;">{pending_count}</h3>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_m5:
    st.markdown(
        f"""
        <div class="metric-card-box">
            <div>
                <p class="metric-title">Errors</p>
                <h3 class="metric-value" style="color:#f87171;">{error_count}</h3>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

# Banner if unextracted files exist
if pending_count > 0:
    col_b1, col_b2 = st.columns([3, 1])
    with col_b1:
        st.info(f"{pending_count} datasheet(s) are ready for extraction. Click 'Start Batch Extraction' to process all files.")
    with col_b2:
        if st.button("Start Batch Extraction", type="primary", width="stretch"):
            target_ids = [d_id for d_id, d_info in st.session_state.documents.items() if not get_doc_state(d_info["thread_id"]).values.get("document_path")]
            p_bar_main = st.progress(0, text="Extracting all datasheets...")
            extract_all_documents(target_ids, p_bar_main)
            p_bar_main.progress(1.0, text="All datasheets processed!")
            st.rerun()

st.divider()

# --- Main Navigation Tabs ---
tab_table, tab_review = st.tabs(["Master Equipment Table", "Document Inspector & Review"])


def render_annexure_html_table(rows: List[Dict[str, Any]]) -> str:
    """Render the exact ANNEXURE-1 (REV.04) - EQUIPMENT SUMMARY table with minimal horizontal scroll and clear readability."""
    rows_html = ""
    for r in rows:
        tag_val = str(r.get("TAG NO.", "")).replace("\n", "<br>").replace(",", "<br>")
        rows_html += f"""<tr>
<td style="border:1px solid #000000; min-width:35px; padding:7px 3px; text-align:center; font-weight:bold; vertical-align:middle; font-size:11.5px;">{r.get('S/N', '')}</td>
<td style="border:1px solid #000000; min-width:130px; padding:7px 6px; text-align:left; vertical-align:middle; white-space:normal; font-size:11.5px; font-weight:600; line-height:1.35;">{tag_val}</td>
<td style="border:1px solid #000000; min-width:130px; padding:7px 6px; text-align:left; vertical-align:middle; font-size:11.5px; line-height:1.3;">{r.get('DESCRIPTION', '')}</td>
<td style="border:1px solid #000000; min-width:110px; padding:7px 6px; text-align:left; vertical-align:middle; font-size:11.5px; line-height:1.3;">{r.get('Ref Data sheet', '')}</td>
<td style="border:1px solid #000000; min-width:105px; padding:7px 5px; text-align:left; vertical-align:middle; font-size:11.5px; line-height:1.3;">{r.get('DESIGN CODE', '')}</td>
<td style="border:1px solid #000000; min-width:90px; padding:7px 4px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('MOC', '')}</td>
<td style="border:1px solid #000000; min-width:40px; padding:7px 2px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('QTY.', '')}</td>
<td style="border:1px solid #000000; min-width:55px; padding:7px 2px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('VERT / HOR', '')}</td>
<td style="border:1px solid #000000; min-width:70px; padding:7px 4px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('VESSEL ID (mm)', '')}</td>
<td style="border:1px solid #000000; min-width:80px; padding:7px 4px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('VESSEL (TL-TL) LENGTH mm', '')}</td>
<td style="border:1px solid #000000; min-width:70px; padding:7px 4px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('SHELL MIN. THK - mm', '')}</td>
<td style="border:1px solid #000000; min-width:70px; padding:7px 4px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('HEAD MIN. THK. mm', '')}</td>
<td style="border:1px solid #000000; min-width:80px; padding:7px 4px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('HEAD TYPE', '')}</td>
<td style="border:1px solid #000000; min-width:170px; padding:7px 6px; text-align:left; vertical-align:middle; font-size:11.5px; line-height:1.35; word-break:normal; overflow-wrap:break-word;">{r.get('NOZZLE TYPE', '')}</td>
<td style="border:1px solid #000000; min-width:55px; padding:7px 2px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('Impact Tested', '')}</td>
<td style="border:1px solid #000000; min-width:45px; padding:7px 2px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('RT', '')}</td>
<td style="border:1px solid #000000; min-width:55px; padding:7px 2px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('PWHT', '')}</td>
<td style="border:1px solid #000000; min-width:85px; padding:7px 4px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('TYPE OF SUPPORT', '')}</td>
<td style="border:1px solid #000000; min-width:100px; padding:7px 4px; text-align:center; vertical-align:middle; font-size:11.5px; line-height:1.3;">{r.get('EXTERNAL PAINTING', '')}</td>
<td style="border:1px solid #000000; min-width:90px; padding:7px 4px; text-align:center; vertical-align:middle; font-size:11.5px; line-height:1.3;">{r.get('INTERNAL PAINTING', '')}</td>
<td style="border:1px solid #000000; min-width:75px; padding:7px 3px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('Pickling & Passivation', 'N/A')}</td>
<td style="border:1px solid #000000; min-width:80px; padding:7px 4px; text-align:center; vertical-align:middle; font-size:11.5px;">{r.get('WT-Tons (Each) (Approx.)', '')}</td>
</tr>"""

    html = f"""<div style="width:100%; margin:0 0 15px 0; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; overflow-x:auto; -webkit-overflow-scrolling:touch; border:1px solid #e2e8f0; border-radius:6px; padding-bottom:4px;">
<div style="text-align:center; font-size:1.35rem; font-weight:800; color:#1e3a8a; text-decoration:underline; margin:12px 0 14px 0; letter-spacing:0.04em;">
ANNEXURE-1 (REV.04) - EQUIPMENT SUMMARY
</div>
<table style="min-width:1550px; width:100%; border-collapse:collapse; border:1.5px solid #000000; line-height:1.25; background:#ffffff; color:#000000;">
<thead>
<tr style="background-color:#dbeafe;">
<th style="border:1px solid #000000; min-width:35px; padding:8px 3px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">S/N</th>
<th style="border:1px solid #000000; min-width:130px; padding:8px 6px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">TAG NO.</th>
<th style="border:1px solid #000000; min-width:130px; padding:8px 6px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">DESCRIPTION</th>
<th style="border:1px solid #000000; min-width:110px; padding:8px 6px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">Ref Data sheet</th>
<th style="border:1px solid #000000; min-width:105px; padding:8px 5px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">DESIGN CODE</th>
<th style="border:1px solid #000000; min-width:90px; padding:8px 4px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">MOC</th>
<th style="border:1px solid #000000; min-width:40px; padding:8px 2px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">QTY.</th>
<th style="border:1px solid #000000; min-width:55px; padding:8px 2px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">VERT /<br>HOR</th>
<th style="border:1px solid #000000; min-width:70px; padding:8px 4px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">VESSEL ID<br>(mm)</th>
<th style="border:1px solid #000000; min-width:80px; padding:8px 4px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">VESSEL<br>(TL-TL)<br>LENGTH mm</th>
<th style="border:1px solid #000000; min-width:70px; padding:8px 4px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">SHELL MIN.<br>THK - mm</th>
<th style="border:1px solid #000000; min-width:70px; padding:8px 4px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">HEAD MIN.<br>Thk. mm</th>
<th style="border:1px solid #000000; min-width:80px; padding:8px 4px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">HEAD TYPE</th>
<th style="border:1px solid #000000; min-width:170px; padding:8px 6px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">NOZZLE<br>TYPE</th>
<th style="border:1px solid #000000; min-width:55px; padding:8px 2px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">Impact<br>Tested</th>
<th style="border:1px solid #000000; min-width:45px; padding:8px 2px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">RT</th>
<th style="border:1px solid #000000; min-width:55px; padding:8px 2px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">PWHT</th>
<th style="border:1px solid #000000; min-width:85px; padding:8px 4px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">TYPE OF<br>SUPPORT</th>
<th style="border:1px solid #000000; min-width:100px; padding:8px 4px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">EXTERNAL<br>PAINTING</th>
<th style="border:1px solid #000000; min-width:90px; padding:8px 4px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">INTERNAL<br>PAINTING</th>
<th style="border:1px solid #000000; min-width:75px; padding:8px 3px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">Pickling &<br>Passivation</th>
<th style="border:1px solid #000000; min-width:80px; padding:8px 4px; font-weight:bold; text-align:center; vertical-align:middle; font-size:11.5px;">WT-Tons<br>(Each)<br>(Approx.)</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>"""
    return html


@st.dialog("ANNEXURE-1 (REV.04) - EQUIPMENT SUMMARY", width="large")
def show_final_annexure_dialog():
    """Display the full screen modal with the exact Annexure-1 Equipment Summary table."""
    st.html(render_annexure_html_table(annex_table_rows))
    st.divider()
    st.markdown("### Export Options")
    c_exp1, c_exp2, c_exp3 = st.columns(3)
    excel_bytes = export_to_excel(all_annex_records)
    csv_bytes = export_to_csv(all_annex_records)
    json_bytes = export_to_json(all_annex_records)

    with c_exp1:
        st.download_button(
            label=f"Download Annexure Excel (.xlsx) [{len(all_annex_records)} Records]",
            data=excel_bytes,
            file_name="ANNEXURE-1_EQUIPMENT_SUMMARY.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            width="stretch",
        )
    with c_exp2:
        st.download_button(
            label="Download Annexure CSV",
            data=csv_bytes,
            file_name="ANNEXURE-1_EQUIPMENT_SUMMARY.csv",
            mime="text/csv",
            width="stretch",
        )
    with c_exp3:
        st.download_button(
            label="Download Annexure JSON",
            data=json_bytes,
            file_name="ANNEXURE-1_EQUIPMENT_SUMMARY.json",
            mime="application/json",
            width="stretch",
        )


# =========================================================================
# TAB 1: MASTER EQUIPMENT TABLE & FINAL FORMAT BUTTON
# =========================================================================
with tab_table:
    st.subheader("Master Equipment Table")
    table_columns = [
        "S/N",
        "TAG NO.",
        "DESCRIPTION",
        "Ref Data sheet",
        "DESIGN CODE",
        "MOC",
        "QTY.",
        "VERT / HOR",
        "VESSEL ID (mm)",
        "VESSEL (TL-TL) LENGTH mm",
        "SHELL MIN. THK - mm",
        "HEAD MIN. THK. mm",
        "HEAD TYPE",
        "NOZZLE TYPE",
        "Impact Tested",
        "RT",
        "PWHT",
        "TYPE OF SUPPORT",
        "EXTERNAL PAINTING",
        "INTERNAL PAINTING",
        "Pickling & Passivation",
        "WT-Tons (Each) (Approx.)",
    ]
    if annex_table_rows:
        df_annex = pd.DataFrame(annex_table_rows)[table_columns].astype(str)
    else:
        df_annex = pd.DataFrame(columns=table_columns)

    st.dataframe(
        df_annex,
        width="stretch",
        hide_index=True,
    )

    st.write("")
    if st.button("Display in Final Result Format", type="primary", width="stretch"):
        show_final_annexure_dialog()


# =========================================================================
# TAB 2: INDIVIDUAL DOCUMENT INSPECTOR & HITL REVIEW
# =========================================================================
with tab_review:
    doc_keys = list(st.session_state.documents.keys()) if st.session_state.documents else []
    if not doc_keys:
        st.info("No documents available to inspect. Upload datasheets from the sidebar to begin.")
    else:
        if st.session_state.selected_doc_id not in st.session_state.documents:
            st.session_state.selected_doc_id = doc_keys[0]

        selected_doc_name = st.selectbox(
            "Select Datasheet to Inspect & Review:",
            options=doc_keys,
            format_func=lambda k: f"{st.session_state.documents[k]['filename']}",
            index=doc_keys.index(st.session_state.selected_doc_id),
        )
        st.session_state.selected_doc_id = selected_doc_name
        current_doc = st.session_state.documents[selected_doc_name]

        current_state = get_doc_state(current_doc["thread_id"])
        next_node = current_state.next[0] if current_state.next else None
        is_interrupted = len(current_state.tasks) > 0 and bool(current_state.tasks[0].interrupts)
        is_completed = not next_node and bool(current_state.values.get("final_annex"))
        has_error = bool(current_state.values.get("error")) or bool(current_doc.get("error"))

        st.markdown(f"### Inspecting: `{current_doc['filename']}`")

        # Document Pending
        if not current_state.values.get("document_path") and not has_error and not is_interrupted and not is_completed:
            st.info("This document has not been extracted yet.")
            if st.button("Extract This Datasheet Now", type="primary"):
                extract_single_doc(selected_doc_name)
                st.rerun()

        # Document Error
        elif has_error:
            err_msg = current_state.values.get("error") or current_doc.get("error")
            st.error(f"Extraction error: {err_msg}")
            if st.button("Retry Extraction", type="secondary"):
                current_doc["error"] = None
                extract_single_doc(selected_doc_name)
                st.rerun()

        # Document In Human Review (Interrupt)
        elif is_interrupted:
            st.subheader("Human-in-the-Loop Review")

            interrupt_payload = current_state.tasks[0].interrupts[0].value
            flagged_fields = {f["field"]: f for f in interrupt_payload["fields"]}

            val_result = current_state.values.get("validation_result")
            val_issues = {}
            if val_result and hasattr(val_result, "issues"):
                for issue in val_result.issues:
                    if issue.field not in val_issues:
                        val_issues[issue.field] = []
                    val_issues[issue.field].append(f"[{issue.code}] {issue.message}")

            normalized: ExtractionResult = current_state.values["normalized_extraction"]

            n_flagged = len(flagged_fields)
            n_val_issues = len(val_issues)

            if n_flagged > 0 or n_val_issues > 0:
                st.warning(
                    f"{n_flagged} fields flagged for review and {n_val_issues} validation issues detected. "
                    "Review all fields below. You can edit the Corrected Value column for any field."
                )
            else:
                st.info(
                    "All fields passed validation. Verify the extracted values below before finalizing. "
                    "You can still edit any field in the Corrected Value column."
                )

            all_field_attrs = [
                "tag_no", "description", "ref_data_sheet", "design_code", "moc",
                "qty", "orientation", "vessel_id_mm", "vessel_tl_tl_length_mm",
                "shell_min_thk_mm", "head_min_thk_mm", "head_type", "nozzle_type",
                "impact_tested", "rt", "pwht", "support_type", "pickling_passivation", "weight_tons_each",
            ]

            data_rows = []

            for attr in all_field_attrs:
                field = getattr(normalized, attr)
                is_flagged = attr in flagged_fields
                has_val_issue = attr in val_issues
                flag_info = flagged_fields.get(attr, {})

                if is_flagged or has_val_issue:
                    review_tag = "FLAGGED"
                elif field.confidence < 0.8:
                    review_tag = "WARNING"
                else:
                    review_tag = "VALID"

                display_val = "" if field.value is None else str(field.value)

                all_issues = []
                if is_flagged:
                    all_issues.extend(flag_info.get("issues", []))
                if has_val_issue:
                    all_issues.extend(val_issues[attr])

                data_rows.append(
                    {
                        "Review": review_tag,
                        "Field": attr.upper(),
                        "Extracted Value": display_val,
                        "Corrected Value": display_val,
                        "Confidence": f"{field.confidence:.0%}",
                        "Status": field.status.value,
                        "Issues": "; ".join(all_issues) if all_issues else "",
                        "Evidence": field.evidence[0].text[:80] if field.evidence else "N/A",
                        "_attr_name": attr,
                        "_orig_val": display_val,
                    }
                )

            # Handle painting sub-fields
            for p_attr in ["external", "internal"]:
                p_field = getattr(normalized.painting, p_attr)
                full_attr = f"painting_{p_attr}"
                is_flagged = full_attr in flagged_fields
                has_val_issue = full_attr in val_issues
                flag_info = flagged_fields.get(full_attr, {})

                if is_flagged or has_val_issue:
                    review_tag = "FLAGGED"
                elif p_field.confidence < 0.8:
                    review_tag = "WARNING"
                else:
                    review_tag = "VALID"

                p_display_val = "" if p_field.value is None else str(p_field.value)

                all_issues = []
                if is_flagged:
                    all_issues.extend(flag_info.get("issues", []))
                if has_val_issue:
                    all_issues.extend(val_issues[full_attr])

                data_rows.append(
                    {
                        "Review": review_tag,
                        "Field": f"PAINTING ({p_attr.upper()})",
                        "Extracted Value": p_display_val,
                        "Corrected Value": p_display_val,
                        "Confidence": f"{p_field.confidence:.0%}",
                        "Status": p_field.status.value,
                        "Issues": "; ".join(all_issues) if all_issues else "",
                        "Evidence": p_field.evidence[0].text[:80] if p_field.evidence else "N/A",
                        "_attr_name": full_attr,
                        "_orig_val": p_display_val,
                    }
                )

            priority_order = {"FLAGGED": 0, "WARNING": 1, "VALID": 2}
            data_rows.sort(key=lambda r: (priority_order.get(r["Review"], 3), r["Confidence"]))

            df_editor = pd.DataFrame(data_rows)
            st.markdown("Edit the **Corrected Value** column to fix any field. Fields needing attention are sorted to the top.")

            edited_df = st.data_editor(
                df_editor,
                key=f"editor_{selected_doc_name}",
                column_config={
                    "Review": st.column_config.TextColumn("Review Status", disabled=True, width="small"),
                    "Field": st.column_config.TextColumn("Field", disabled=True),
                    "Extracted Value": st.column_config.TextColumn("Extracted", disabled=True),
                    "Corrected Value": st.column_config.TextColumn("Corrected Value", disabled=False),
                    "Confidence": st.column_config.TextColumn("Confidence", disabled=True, width="small"),
                    "Status": st.column_config.TextColumn("Status", disabled=True),
                    "Issues": st.column_config.TextColumn("Issues", disabled=True),
                    "Evidence": st.column_config.TextColumn("Evidence", disabled=True),
                    "_attr_name": None,
                    "_orig_val": None,
                },
                disabled=["Review", "Field", "Extracted Value", "Confidence", "Status", "Issues", "Evidence"],
                hide_index=True,
                width="stretch",
                num_rows="fixed",
            )

            col_approve, col_view = st.columns([1, 1])
            with col_approve:
                if st.button("Approve & Submit Corrections", type="primary", width="stretch"):
                    decisions = []
                    for _, row in edited_df.iterrows():
                        field_attr = row["_attr_name"]
                        orig_val = str(row.get("_orig_val", "")).strip()
                        new_val = str(row["Corrected Value"]).strip() if pd.notna(row["Corrected Value"]) else ""

                        if new_val != orig_val or (row["Review"] == "FLAGGED" and new_val != ""):
                            decisions.append({"field": field_attr, "value": new_val if new_val != "" else None})

                    with st.spinner("Submitting corrections and re-validating..."):
                        graph.invoke(Command(resume=decisions), {"configurable": {"thread_id": current_doc["thread_id"]}})
                    st.rerun()

            with col_view:
                if st.button("Display in Final Result Format", type="secondary", width="stretch"):
                    show_final_annexure_dialog()

        # Document Completed
        elif is_completed:
            st.success("This datasheet has been fully validated and finalized.")
            final_annex = current_state.values["final_annex"]
            record = AnnexureRecord(**final_annex)

            st.markdown("#### Validated Record Preview")
            single_row = [r for r in annex_table_rows if r.get("_doc_id") == selected_doc_name]
            if single_row:
                st.html(render_annexure_html_table(single_row))

            col1, col2, col3 = st.columns(3)
            json_bytes = export_to_json([record])
            csv_bytes = export_to_csv([record])
            excel_bytes = export_to_excel([record])

            with col1:
                st.download_button(
                    label="Download Excel (.xlsx)",
                    data=excel_bytes,
                    file_name=f"annex_{current_doc['filename']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    width="stretch",
                )
            with col2:
                st.download_button(
                    label="Download CSV",
                    data=csv_bytes,
                    file_name=f"annex_{current_doc['filename']}.csv",
                    mime="text/csv",
                    width="stretch",
                )
            with col3:
                st.download_button(
                    label="Download JSON",
                    data=json_bytes,
                    file_name=f"annex_{current_doc['filename']}.json",
                    mime="application/json",
                    width="stretch",
                )
