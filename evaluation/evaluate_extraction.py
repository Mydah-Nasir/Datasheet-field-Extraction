"""Evaluate the accuracy of the Gemini extraction against ground truth."""

import glob
import json
import os
import uuid
import time
import argparse
from typing import Any

from src.graph.workflow import build_graph
from src.domain.schema import ExtractionResult, FieldStatus


def load_ground_truth(json_path: str) -> dict:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_compare(gt_val: Any, ext_val: Any, status: FieldStatus) -> str:
    """Compare ground truth to extracted value and return result label."""
    if gt_val == "MISSING":
        if status == FieldStatus.MISSING or ext_val is None:
            return "CORRECT_MISSING"
        else:
            return "FALSE_EXTRACTION"
    
    if gt_val == "AMBIGUOUS":
        if status == FieldStatus.AMBIGUOUS:
            return "CORRECT_AMBIGUOUS"
        else:
            return "INCORRECT_AMBIGUOUS"

    if status == FieldStatus.MISSING or ext_val is None:
        return "MISSING"

    # String comparison (case insensitive, strip whitespace)
    if isinstance(gt_val, str) and isinstance(ext_val, str):
        if gt_val.strip().lower() == ext_val.strip().lower():
            return "CORRECT"
        else:
            return "INCORRECT"
            
    # Float/Int comparison
    if isinstance(gt_val, (int, float)) and isinstance(ext_val, (int, float)):
        if abs(gt_val - ext_val) < 0.001:
            return "CORRECT"
        else:
            return "INCORRECT"

    if str(gt_val) == str(ext_val):
        return "CORRECT"
        
    return "INCORRECT"


def evaluate_document(gt_path: str, pdf_path: str, use_mock: bool = False) -> dict:
    """Run the extraction pipeline on the PDF and compare against ground truth."""
    gt_data = load_ground_truth(gt_path)
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    if use_mock:
        import os
        os.environ["GEMINI_API_KEY"] = "mock_key"
        from tests.unit.test_annexure_builder import create_valid_extraction_result
        from src.graph import nodes
        class MockExtractionService:
            def extract(self, document):
                return create_valid_extraction_result()
        nodes.GeminiExtractionService = MockExtractionService
        
    graph = build_graph()
    
    print(f"Evaluating {pdf_path}...")
    start_time = time.time()
    
    # We invoke the graph. It will likely interrupt due to missing/ambiguous fields.
    state = graph.invoke({"document_path": pdf_path, "workflow_id": thread_id}, config)
    end_time = time.time()
    
    # Get the state to retrieve the normalized extraction
    saved_state = graph.get_state(config)
    normalized: ExtractionResult | None = saved_state.values.get("normalized_extraction")
    
    if not normalized:
        print(f"  Error: No normalized extraction found. Pipeline failed? Error: {saved_state.values.get('error')}")
        return {"error": saved_state.values.get("error")}
        
    fields = [
        ("tag_no", normalized.tag_no),
        ("description", normalized.description),
        ("ref_data_sheet", normalized.ref_data_sheet),
        ("design_code", normalized.design_code),
        ("moc", normalized.moc),
        ("qty", normalized.qty),
        ("orientation", normalized.orientation),
        ("vessel_id_mm", normalized.vessel_id_mm),
        ("vessel_tl_tl_length_mm", normalized.vessel_tl_tl_length_mm),
        ("shell_min_thk_mm", normalized.shell_min_thk_mm),
        ("head_min_thk_mm", normalized.head_min_thk_mm),
        ("head_type", normalized.head_type),
        ("nozzle_type", normalized.nozzle_type),
        ("impact_tested", normalized.impact_tested),
        ("rt", normalized.rt),
        ("pwht", normalized.pwht),
        ("support_type", normalized.support_type),
        ("weight_tons_each", normalized.weight_tons_each),
        ("painting_external", normalized.painting.external),
        ("painting_internal", normalized.painting.internal),
    ]
    
    results = {}
    for name, field in fields:
        gt_val = gt_data.get(name)
        result = safe_compare(gt_val, field.value, field.status)
        results[name] = {
            "ground_truth": gt_val,
            "extracted": field.value,
            "status": field.status.value,
            "result": result
        }
        
    return {
        "document": pdf_path,
        "duration_sec": end_time - start_time,
        "field_results": results
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Use mock extraction service")
    args = parser.parse_args()
    
    os.makedirs("evaluation/reports", exist_ok=True)
    
    gt_files = glob.glob("evaluation/ground_truth/*.json")
    
    all_results = []
    
    for gt_path in gt_files:
        basename = os.path.basename(gt_path)
        pdf_name = basename.replace(".json", ".pdf")
        pdf_path = os.path.join("evaluation", "fixtures", pdf_name)
        
        if not os.path.exists(pdf_path):
            print(f"Warning: PDF not found for {gt_path} at {pdf_path}")
            continue
            
        doc_result = evaluate_document(gt_path, pdf_path, use_mock=args.mock)
        all_results.append(doc_result)
        
    # Aggregate metrics
    total_fields = 0
    total_correct = 0
    total_false_extraction = 0
    total_missing = 0
    total_incorrect = 0
    total_correct_missing = 0
    total_correct_ambiguous = 0
    
    field_metrics = {}
    
    for doc in all_results:
        if "error" in doc:
            continue
            
        for field_name, data in doc["field_results"].items():
            if field_name not in field_metrics:
                field_metrics[field_name] = {"total": 0, "correct": 0, "false_ext": 0, "missing": 0, "incorrect": 0}
                
            field_metrics[field_name]["total"] += 1
            total_fields += 1
            
            res = data["result"]
            if res in ("CORRECT", "CORRECT_MISSING", "CORRECT_AMBIGUOUS"):
                total_correct += 1
                field_metrics[field_name]["correct"] += 1
                if res == "CORRECT_MISSING":
                    total_correct_missing += 1
                elif res == "CORRECT_AMBIGUOUS":
                    total_correct_ambiguous += 1
            elif res == "FALSE_EXTRACTION":
                total_false_extraction += 1
                field_metrics[field_name]["false_ext"] += 1
            elif res == "MISSING":
                total_missing += 1
                field_metrics[field_name]["missing"] += 1
            else:
                total_incorrect += 1
                field_metrics[field_name]["incorrect"] += 1
                
    accuracy = (total_correct / total_fields) * 100 if total_fields > 0 else 0
    
    report_json = {
        "metrics": {
            "total_documents": len(all_results),
            "total_fields": total_fields,
            "overall_accuracy_percent": accuracy,
            "total_correct": total_correct,
            "total_correct_missing": total_correct_missing,
            "total_correct_ambiguous": total_correct_ambiguous,
            "total_false_extraction": total_false_extraction,
            "total_missing": total_missing,
            "total_incorrect": total_incorrect
        },
        "field_metrics": field_metrics,
        "document_results": all_results
    }
    
    with open("evaluation/reports/accuracy_report.json", "w", encoding="utf-8") as f:
        json.dump(report_json, f, indent=2)
        
    # Generate Markdown Report
    with open("evaluation/reports/accuracy_report.md", "w", encoding="utf-8") as f:
        f.write("# Accuracy Evaluation Report\n\n")
        f.write(f"- **Total Documents:** {len(all_results)}\n")
        f.write(f"- **Total Parameters Evaluated:** {total_fields}\n")
        f.write(f"- **Correct (including correctly identified missing/ambiguous):** {total_correct}\n")
        f.write(f"- **Incorrect Extraction:** {total_incorrect}\n")
        f.write(f"- **False Extractions (Hallucinations):** {total_false_extraction}\n")
        f.write(f"- **Missed Fields:** {total_missing}\n")
        f.write(f"- **Overall Accuracy:** {accuracy:.2f}%\n\n")
        
        f.write("## Field-Level Accuracy\n\n")
        f.write("| Field | Accuracy | Total | Correct | False Ext | Missing | Incorrect |\n")
        f.write("|-------|----------|-------|---------|-----------|---------|-----------|\n")
        for fname, mets in field_metrics.items():
            f_acc = (mets["correct"] / mets["total"]) * 100 if mets["total"] > 0 else 0
            f.write(f"| {fname} | {f_acc:.1f}% | {mets['total']} | {mets['correct']} | {mets['false_ext']} | {mets['missing']} | {mets['incorrect']} |\n")
            
        f.write("\n## Detailed Results\n")
        for doc in all_results:
            if "error" in doc:
                f.write(f"\n### {os.path.basename(doc['document'])} - ERROR\n")
                f.write(f"{doc['error']}\n")
                continue
                
            f.write(f"\n### {os.path.basename(doc['document'])} (Duration: {doc['duration_sec']:.2f}s)\n\n")
            f.write("| Field | Ground Truth | Extracted | Status | Result |\n")
            f.write("|-------|--------------|-----------|--------|--------|\n")
            for fname, data in doc["field_results"].items():
                gt = str(data['ground_truth']).replace('\n', ' ')
                ext = str(data['extracted']).replace('\n', ' ')
                f.write(f"| {fname} | {gt} | {ext} | {data['status']} | {data['result']} |\n")


if __name__ == "__main__":
    main()
