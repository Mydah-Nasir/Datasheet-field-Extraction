"""Streamlit application for Mechanical Datasheet Extraction."""

import uuid

import pandas as pd
import streamlit as st
from langgraph.types import Command

from src.annexure.export import export_to_csv, export_to_excel, export_to_json
from src.annexure.models import AnnexureRecord
from src.domain.schema import ExtractionResult, FieldStatus
from src.graph.workflow import build_graph

# --- Configuration and Initialization ---
st.set_page_config(
    page_title="Mechanical Datasheet Extractor",
    page_icon="📄",
    layout="wide",
)


# Cache the compiled LangGraph to ensure the MemorySaver persists across reruns
@st.cache_resource
def get_graph():
    return build_graph()


graph = get_graph()


# Initialize Session State
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "file_uploaded" not in st.session_state:
    st.session_state.file_uploaded = False

config = {"configurable": {"thread_id": st.session_state.thread_id}}


# --- UI Flow Helpers ---
def get_current_graph_state():
    return graph.get_state(config)

current_state = get_current_graph_state()
next_node = current_state.next[0] if current_state.next else None
is_interrupted = len(current_state.tasks) > 0 and bool(current_state.tasks[0].interrupts)
is_completed = not next_node and current_state.values.get("final_annex")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    if st.button("Reset Session"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.file_uploaded = False
        st.rerun()

    st.divider()

    # Stage 1: Upload Document
    if not current_state.values.get("document_path") and not is_interrupted and not is_completed:
        st.subheader("1. Upload Document")
        uploaded_file = st.file_uploader(
            "Upload a Mechanical Datasheet (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"]
        )

        if uploaded_file is not None:
            tmp_path = f"scratch/{uploaded_file.name}"
            import os

            os.makedirs("scratch", exist_ok=True)
            with open(tmp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            if st.button("Start Extraction", type="primary"):
                from src.config import settings

                api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")

                if not api_key:
                    st.error("❌ GEMINI_API_KEY is not set. Please set it in your .env file.")
                    st.stop()

                with st.spinner("Initializing workflow..."):
                    st.session_state.file_uploaded = True
                    graph.invoke(
                        {"document_path": tmp_path, "workflow_id": st.session_state.thread_id},
                        config,
                    )
                st.rerun()


# --- Title & Header ---
st.title("📄 Mechanical Datasheet Extractor")
st.markdown("Extract, validate, and construct Annex MDS records from Mechanical Datasheets.")



def get_field_status_icon(status: FieldStatus) -> str:
    if status in (
        FieldStatus.EXTRACTED,
        FieldStatus.NORMALIZED,
        FieldStatus.USER_CONFIRMED,
        FieldStatus.USER_CORRECTED,
    ):
        return "✅"
    elif status == FieldStatus.MISSING:
        return "⚠️"
    elif status == FieldStatus.AMBIGUOUS:
        return "❓"
    elif status in (FieldStatus.INVALID, FieldStatus.CONFLICT):
        return "❌"
    return "⚪"






# Check for unrecoverable errors
if current_state.values.get("error"):
    st.error(f"Workflow encountered a fatal error: {current_state.values.get('error')}")
    st.stop()


# Stage 2: Human Review (Interrupt)
if is_interrupted:
    st.subheader("2. Human-in-the-Loop Review")

    # We retrieve the interrupt payload directly from the graph tasks
    interrupt_payload = current_state.tasks[0].interrupts[0].value
    flagged_fields = {f["field"]: f for f in interrupt_payload["fields"]}

    # Get validation issues
    val_result = current_state.values.get("validation_result")
    val_issues = {}
    if val_result and hasattr(val_result, 'issues'):
        for issue in val_result.issues:
            if issue.field not in val_issues:
                val_issues[issue.field] = []
            val_issues[issue.field].append(f"[{issue.code}] {issue.message}")

    # Get the normalized extraction state to display all 19 fields
    normalized: ExtractionResult = current_state.values["normalized_extraction"]

    # Count issues
    n_flagged = len(flagged_fields)
    n_val_issues = len(val_issues)
    
    if n_flagged > 0 or n_val_issues > 0:
        st.warning(
            f"⚠️ **{n_flagged} fields flagged for review** and **{n_val_issues} validation issues** detected. "
            f"Review all fields below. You can edit the **Corrected Value** column for any field."
        )
    else:
        st.info(
            "✅ All fields passed validation. Please verify the extracted values below before finalizing. "
            "You can still edit any field in the **Corrected Value** column."
        )

    all_field_attrs = [
        "tag_no", "description", "ref_data_sheet", "design_code", "moc",
        "qty", "orientation", "vessel_id_mm", "vessel_tl_tl_length_mm",
        "shell_min_thk_mm", "head_min_thk_mm", "head_type", "nozzle_type",
        "impact_tested", "rt", "pwht", "support_type", "weight_tons_each",
    ]

    data_rows = []

    for attr in all_field_attrs:
        field = getattr(normalized, attr)
        is_flagged = attr in flagged_fields
        has_val_issue = attr in val_issues
        flag_info = flagged_fields.get(attr, {})

        # Determine review icon priority
        if is_flagged or has_val_issue:
            review_icon = "🚩"
        elif field.confidence < 0.8:
            review_icon = "⚠️"
        else:
            review_icon = "✅"

        display_val = "" if field.value is None else str(field.value)
        
        # Combine all issues
        all_issues = []
        if is_flagged:
            all_issues.extend(flag_info.get("issues", []))
        if has_val_issue:
            all_issues.extend(val_issues[attr])

        data_rows.append(
            {
                "Review": review_icon,
                "Field": attr.upper(),
                "Extracted Value": display_val,
                "Corrected Value": display_val,
                "Confidence": f"{field.confidence:.0%}",
                "Status": field.status.value,
                "Issues": "; ".join(all_issues) if all_issues else "",
                "Evidence": field.evidence[0].text[:80] if field.evidence else "N/A",
                "_attr_name": attr,
            }
        )

    # Handle painting
    for p_attr in ["external", "internal"]:
        p_field = getattr(normalized.painting, p_attr)
        full_attr = f"painting_{p_attr}"
        is_flagged = full_attr in flagged_fields
        has_val_issue = full_attr in val_issues
        flag_info = flagged_fields.get(full_attr, {})

        if is_flagged or has_val_issue:
            review_icon = "🚩"
        elif p_field.confidence < 0.8:
            review_icon = "⚠️"
        else:
            review_icon = "✅"

        p_display_val = "" if p_field.value is None else str(p_field.value)
        
        all_issues = []
        if is_flagged:
            all_issues.extend(flag_info.get("issues", []))
        if has_val_issue:
            all_issues.extend(val_issues[full_attr])

        data_rows.append(
            {
                "Review": review_icon,
                "Field": f"PAINTING ({p_attr.upper()})",
                "Extracted Value": p_display_val,
                "Corrected Value": p_display_val,
                "Confidence": f"{p_field.confidence:.0%}",
                "Status": p_field.status.value,
                "Issues": "; ".join(all_issues) if all_issues else "",
                "Evidence": p_field.evidence[0].text[:80] if p_field.evidence else "N/A",
                "_attr_name": full_attr,
            }
        )

    # Sort: flagged/warning items first, then by confidence ascending
    priority_order = {"🚩": 0, "⚠️": 1, "✅": 2}
    data_rows.sort(key=lambda r: (priority_order.get(r["Review"], 3), r["Confidence"]))

    df = pd.DataFrame(data_rows)

    st.markdown("Edit the **Corrected Value** column to fix any field. Fields needing attention are sorted to the top.")

    edited_df = st.data_editor(
        df,
        column_config={
            "Review": st.column_config.TextColumn("🔍", disabled=True, width="small"),
            "Field": st.column_config.TextColumn("Field", disabled=True),
            "Extracted Value": st.column_config.TextColumn("Extracted", disabled=True),
            "Corrected Value": st.column_config.TextColumn("✏️ Corrected", disabled=False),
            "Confidence": st.column_config.TextColumn("Conf.", disabled=True, width="small"),
            "Status": st.column_config.TextColumn("Status", disabled=True),
            "Issues": st.column_config.TextColumn("Issues", disabled=True),
            "Evidence": st.column_config.TextColumn("Evidence", disabled=True),
            "_attr_name": None,
        },
        disabled=["Review", "Field", "Extracted Value", "Confidence", "Status", "Issues", "Evidence"],
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
    )

    col_approve, col_skip = st.columns(2)
    
    with col_approve:
        if st.button("✅ Approve & Submit Corrections", type="primary", use_container_width=True):
            decisions = []
            for i, row in edited_df.iterrows():
                orig_val = df.iloc[i]["Corrected Value"]
                new_val = row["Corrected Value"]

                import math

                def is_different(v1, v2):
                    if pd.isna(v1) and pd.isna(v2):
                        return False
                    return v1 != v2

                if is_different(orig_val, new_val) or (
                    row["Review"] == "🚩" and pd.notna(new_val) and new_val != ""
                ):
                    decisions.append({"field": row["_attr_name"], "value": new_val})

            with st.spinner("Submitting corrections and re-validating..."):
                graph.invoke(Command(resume=decisions), config)
            st.rerun()


# Stage 3: Finalization
if is_completed:
    st.subheader("3. Final Validated Annex")
    st.success("The extraction has been fully validated and successfully processed.")

    final_annex = current_state.values["final_annex"]
    # Reconstruct AnnexureRecord for export
    record = AnnexureRecord(**final_annex)

    col1, col2 = st.columns([2, 1])

    with col1:
        # Show nice JSON view
        st.json(final_annex)

    with col2:
        st.metric("Total Parameters", len(final_annex))
        st.metric("Workflow State", "COMPLETED")

        st.markdown("### Export")

        # Download buttons
        json_bytes = export_to_json([record])
        csv_bytes = export_to_csv([record])
        excel_bytes = export_to_excel([record])

        st.download_button(
            label="Download Excel (.xlsx)",
            data=excel_bytes,
            file_name=f"annex_{st.session_state.thread_id}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
        st.download_button(
            label="Download CSV",
            data=csv_bytes,
            file_name=f"annex_{st.session_state.thread_id}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            label="Download JSON",
            data=json_bytes,
            file_name=f"annex_{st.session_state.thread_id}.json",
            mime="application/json",
            use_container_width=True,
        )
