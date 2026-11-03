"""
evaluate.py - Evaluate clinical CRM note extraction quality against labelled ground truth.
Computes Precision, Recall, F1, and Confusion Matrices for each required category:
- missed_doses
- refill_delays
- discontinuation_reasons
- medication_interruptions
- patient_reported_behavior
- human_review_flag
Output: data/evaluation_results.json
"""

import json
import os
import pandas as pd


def compute_metrics(tp, fp, fn, tn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4), round(accuracy, 4)


def main():
    extracted_path = "data/extracted_crm.json"
    labelled_path = "data/labelled_crm.json"

    with open(extracted_path, "r", encoding="utf-8") as f:
        extracted_list = json.load(f)
    with open(labelled_path, "r", encoding="utf-8") as f:
        labelled_list = json.load(f)

    extracted_map = {item["note_id"]: item["extracted"] for item in extracted_list}
    
    categories = [
        "missed_doses",
        "refill_delays",
        "discontinuation_reasons",
        "medication_interruptions",
        "patient_reported_behavior",
        "human_review_flag"
    ]

    cat_counts = {c: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for c in categories}
    n_evaluated = len(labelled_list)

    for item in labelled_list:
        nid = item["note_id"]
        true_labels = item["labels"]
        pred_labels = extracted_map.get(nid, {})

        for cat in categories:
            t_val = true_labels.get(cat)
            p_val = pred_labels.get(cat)

            # Normalization
            if isinstance(t_val, bool):
                p_bool = bool(p_val)
                if t_val is True and p_bool is True:
                    cat_counts[cat]["tp"] += 1
                elif t_val is False and p_bool is False:
                    cat_counts[cat]["tn"] += 1
                elif t_val is True and p_bool is False:
                    cat_counts[cat]["fn"] += 1
                else:
                    cat_counts[cat]["fp"] += 1
            else:
                # String / Categorical match
                t_str = str(t_val).strip().lower() if t_val is not None else None
                p_str = str(p_val).strip().lower() if p_val is not None else None

                if t_str is None and p_str is None:
                    cat_counts[cat]["tn"] += 1
                elif t_str is not None and p_str == t_str:
                    cat_counts[cat]["tp"] += 1
                elif t_str is not None and p_str != t_str:
                    cat_counts[cat]["fp"] += 1
                    cat_counts[cat]["fn"] += 1
                elif t_str is None and p_str is not None:
                    cat_counts[cat]["fp"] += 1

    per_category = {}
    total_tp = total_fp = total_fn = total_tn = 0

    for cat in categories:
        counts = cat_counts[cat]
        prec, rec, f1, acc = compute_metrics(counts["tp"], counts["fp"], counts["fn"], counts["tn"])
        per_category[cat] = {
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "accuracy": acc,
            "confusion_matrix": counts
        }
        total_tp += counts["tp"]
        total_fp += counts["fp"]
        total_fn += counts["fn"]
        total_tn += counts["tn"]

    micro_prec, micro_rec, micro_f1, micro_acc = compute_metrics(total_tp, total_fp, total_fn, total_tn)

    results = {
        "n_notes_evaluated": n_evaluated,
        "per_category": per_category,
        "overall_micro": {
            "precision": micro_prec,
            "recall": micro_rec,
            "f1": micro_f1,
            "accuracy": micro_acc
        }
    }

    os.makedirs("data", exist_ok=True)
    with open("data/evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("=" * 70)
    print("CLINICAL CRM NOTE EXTRACTION EVALUATION (GROUND-TRUTH BENCHMARK)")
    print("=" * 70)
    print(f"{'Category':<28} {'Precision':<10} {'Recall':<10} {'F1 Score':<10} {'Accuracy':<10}")
    print("-" * 70)
    for cat, m in per_category.items():
        print(f"{cat:<28} {m['precision']:<10.4f} {m['recall']:<10.4f} {m['f1']:<10.4f} {m['accuracy']:<10.4f}")
    print("-" * 70)
    print(f"{'MICRO-AVERAGED OVERALL':<28} {micro_prec:<10.4f} {micro_rec:<10.4f} {micro_f1:<10.4f} {micro_acc:<10.4f}")
    print("=" * 70)
    print("File written: data/evaluation_results.json")


if __name__ == "__main__":
    main()
