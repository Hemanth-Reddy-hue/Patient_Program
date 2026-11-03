"""
gen_data.py - Generate synthetic datasets reproducing the exact case study metrics:
- This Quarter: Pipeline PDC 58% vs Client CRM Refill Flag 71% (13 pp gap)
- Last Quarter: Pipeline PDC 64% vs Client CRM Refill Flag 72% (8 pp gap)
Models the 3 root causes: Population effect, Measurement-definition effect, Data-source effect.
Generates rich unstructured CRM notes with required extraction categories.
"""

import os
import json
import random
import pandas as pd
import numpy as np
import yaml
from datetime import datetime, timedelta


def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    cfg = load_config()
    seed = cfg["seed"]
    rng = random.Random(seed)
    np.random.seed(seed)

    os.makedirs("data", exist_ok=True)

    n_patients = cfg["cohort"]["total_patients"]  # 250
    q1_count = cfg["cohort"]["q1_patients"]       # 125
    q2_count = cfg["cohort"]["q2_patients"]       # 125

    # Target metrics:
    # Q1 (Last Quarter): PDC Adherent = 64.0% (80 of 125), CRM Refill = 72.0% (90 of 125 active)
    # Q2 (This Quarter): PDC Adherent = 58.0% (72.5 -> 72 or 73 of 125), CRM Refill = 71.0%
    # We will engineer patient profiles to match these exact percentages!

    enrollment_rows = []
    fills_rows = []
    crm_rows = []
    labelled_rows = []

    # Dates
    q1_start = datetime(2024, 1, 1)
    q1_end = datetime(2024, 3, 31)
    q2_start = datetime(2024, 4, 1)
    q2_end = datetime(2024, 6, 30)

    # Note templates covering the required extraction categories
    note_templates = [
        # 1. Missed doses
        ("Patient called case manager. Missed {n_missed} doses over the last two weeks due to {side_effect}. Advised to consult physician.",
         {"missed_doses": True, "refill_delays": False, "discontinuation_reasons": None, "medication_interruptions": False, "patient_reported_behavior": "erratic", "confidence": "high", "human_review_flag": False}),
        
        # 2. Refill delay
        ("Specialty pharmacy outreach note: Refill delayed by {delay_days} days due to {delay_reason}. Patient currently out of medication.",
         {"missed_doses": True, "refill_delays": True, "discontinuation_reasons": None, "medication_interruptions": True, "patient_reported_behavior": "delayed_refill", "confidence": "high", "human_review_flag": False}),
        
        # 3. Discontinuation
        ("Case manager clinical review: Patient decided to discontinue therapy. Stated reason: {discont_reason}. Prescriber informed.",
         {"missed_doses": True, "refill_delays": True, "discontinuation_reasons": "{discont_reason}", "medication_interruptions": True, "patient_reported_behavior": "discontinued", "confidence": "high", "human_review_flag": False}),
        
        # 4. Medication interruption (temporary pause)
        ("Patient reported temporary medication interruption of {pause_days} days for dental procedure. Resuming therapy next week.",
         {"missed_doses": True, "refill_delays": False, "discontinuation_reasons": None, "medication_interruptions": True, "patient_reported_behavior": "erratic", "confidence": "high", "human_review_flag": False}),
        
        # 5. Adherent / On-schedule
        ("Routine follow-up call. Patient confirmed taking medication daily as prescribed with no side effects. Refilled on schedule at specialty pharmacy.",
         {"missed_doses": False, "refill_delays": False, "discontinuation_reasons": None, "medication_interruptions": False, "patient_reported_behavior": "adherent", "confidence": "high", "human_review_flag": False}),
        
        # 6. Ambiguous / Conflicting (requires human review)
        ("Note: Patient mentions skipped some pills but pharmacy reports fill picked up. Unclear whether patient is currently on therapy or holding doses.",
         {"missed_doses": True, "refill_delays": False, "discontinuation_reasons": None, "medication_interruptions": False, "patient_reported_behavior": "erratic", "confidence": "low", "human_review_flag": True}),
        
        # 7. Financial / Copay barrier
        ("Outreach regarding adherence. Patient experienced high out-of-pocket copay ($380) and delayed refilling. Applying for copay assistance card.",
         {"missed_doses": True, "refill_delays": True, "discontinuation_reasons": "cost_copay_barrier", "medication_interruptions": True, "patient_reported_behavior": "delayed_refill", "confidence": "high", "human_review_flag": False}),
        
        # 8. Sample usage / Off-claims fill
        ("Patient stated physician provided 30-day clinical starter samples, so pharmacy fill was deferred. Patient taking samples on schedule.",
         {"missed_doses": False, "refill_delays": False, "discontinuation_reasons": None, "medication_interruptions": False, "patient_reported_behavior": "adherent", "confidence": "medium", "human_review_flag": True})
    ]

    side_effects = ["nausea", "headache", "fatigue", "injection site reaction", "dizziness"]
    delay_reasons = ["prior authorization renewal", "shipping delay during transit", "copay processing barrier", "prescription transfer issue"]
    discont_reasons = ["adverse_events", "cost_copay_barrier", "perceived_inefficacy", "physician_directed", "loss_of_coverage"]

    # We calibrate exact patient profiles for both quarters:
    # Q1: 125 patients -> 80 PDC adherent (64.0%), 90 CRM refill on schedule (72.0%)
    # Q2: 125 patients -> 72 or 73 PDC adherent (58.0% or 58.4%), 89 CRM refill on schedule (71.2%)

    quarters_config = [
        {"quarter": "Last Quarter", "quarter_label": "Q1 2024", "start": q1_start, "end": q1_end,
         "n": 125, "target_pdc_adh": 80, "target_crm_refill": 90, "pid_start": 1},
        {"quarter": "This Quarter", "quarter_label": "Q2 2024", "start": q2_start, "end": q2_end,
         "n": 125, "target_pdc_adh": 73, "target_crm_refill": 89, "pid_start": 126}
    ]

    note_counter = 0

    for qcfg in quarters_config:
        q_name = qcfg["quarter"]
        q_label = qcfg["quarter_label"]
        q_start = qcfg["start"]
        q_end = qcfg["end"]
        n_q = qcfg["n"]
        target_pdc = qcfg["target_pdc_adh"]
        target_crm = qcfg["target_crm_refill"]
        start_id = qcfg["pid_start"]

        # Discrepancy breakdown assignment for these patients:
        # Group A: Both Adherent (PDC >= 80% AND CRM on schedule = 1) -> target ~ 68
        # Group B: Both Non-Adherent (PDC < 80% AND CRM on schedule = 0) -> target ~ 28
        # Group C: Discrepancy 1: PDC Non-Adherent (< 80%) BUT CRM On-Schedule = 1 (Definition / Data source gap) -> target ~ 22
        # Group D: Discrepancy 2: PDC Adherent (>= 80%) BUT CRM Not on Schedule = 0 (Retail leakage / Delayed contact) -> target ~ 5
        # Group E: Population gap (Non-specialty / unreached in CRM) -> ~ 7
        
        # Let's adjust counts so SUM(PDC Adh) == target_pdc, and SUM(CRM On-Schedule) == target_crm:
        # target_pdc = Group A + Group D
        # target_crm = Group A + Group C
        # If target_pdc = 73 (58.4%), target_crm = 89 (71.2%):
        # Let Group A = 68
        # Group D = 73 - 68 = 5 (PDC adh=1, CRM=0)
        # Group C = 89 - 68 = 21 (PDC adh=0, CRM=1)
        # Group B = 125 - (68 + 5 + 21) = 31 (PDC adh=0, CRM=0)
        # Check:
        # PDC Adh = 68 + 5 = 73 -> 73 / 125 = 58.4% (~58%)
        # CRM on schedule = 68 + 21 = 89 -> 89 / 125 = 71.2% (~71%)
        # Discrepancy = 71.2% - 58.4% = 12.8 pp (~13 pp)! Exactly matches!

        if q_name == "This Quarter":
            cnt_A = 68   # Both Adherent
            cnt_D = 5    # PDC=1, CRM=0
            cnt_C = 21   # PDC=0, CRM=1 (The big discrepancy!)
            cnt_B = 31   # Both Non-Adherent
        else: # Last Quarter (Q1): target_pdc = 80 (64.0%), target_crm = 90 (72.0%)
            cnt_A = 75   # Both Adherent
            cnt_D = 5    # PDC=1, CRM=0
            cnt_C = 15   # PDC=0, CRM=1
            cnt_B = 30   # Both Non-Adherent
            # Check:
            # PDC Adh = 75 + 5 = 80 -> 80 / 125 = 64.0%
            # CRM on schedule = 75 + 15 = 90 -> 90 / 125 = 72.0%
            # Gap = 72.0% - 64.0% = 8.0 pp! Exactly matches!

        # Build archetype list
        archetypes = (
            [("A", 1, 1)] * cnt_A +
            [("D", 1, 0)] * cnt_D +
            [("C", 0, 1)] * cnt_C +
            [("B", 0, 0)] * cnt_B
        )
        rng.shuffle(archetypes)

        for i, (arch_type, pdc_adh, crm_on_sched) in enumerate(archetypes):
            pid = f"PAT{start_id + i:03d}"
            
            # Enrollment date in this quarter
            days_span = (q_end - q_start).days
            enroll_dt = q_start + timedelta(days=rng.randint(0, min(25, days_span)))
            
            # Channel and assistance
            is_specialty = 1 if arch_type != "D" or rng.random() < 0.6 else 0
            has_copay = 1 if (pdc_adh == 1 or rng.random() < 0.5) else 0

            # Reason for discrepancy
            if arch_type == "C":
                # PDC < 80% but CRM = 1
                disc_reasons = [
                    "Definition Gap: Late fill picked up within grace period but cumulative PDC < 80%",
                    "Definition Gap: 45-day gap in month 1; recent refill marked on schedule in CRM",
                    "Data-Source Gap: Patient reported sample usage; no pharmacy claim adjudicated",
                    "Data-Source Gap: Retail claim missing from specialty pharmacy dispense record"
                ]
                discrepancy_reason = rng.choice(disc_reasons)
            elif arch_type == "D":
                # PDC >= 80% but CRM = 0
                disc_reasons = [
                    "Data-Source Gap: Filled at out-of-network retail pharmacy; unrecorded in CRM",
                    "Delayed CRM entry: Refill completed but outreach call uncontacted / pending",
                    "CRM Disagreement: Case manager recorded missed dose during hospitalization"
                ]
                discrepancy_reason = rng.choice(disc_reasons)
            elif arch_type == "A":
                discrepancy_reason = "Agreement: Both claims and CRM confirm timely adherence"
            else:
                discrepancy_reason = "Agreement: Both claims and CRM document therapy abandonment/gap"

            enrollment_rows.append({
                "patient_id": pid,
                "reporting_quarter": q_name,
                "quarter_label": q_label,
                "enroll_date": enroll_dt.strftime("%Y-%m-%d"),
                "drug": "DrugX",
                "specialty_pharmacy": is_specialty,
                "copay_assist": has_copay,
                "true_pdc_adherent": pdc_adh,
                "crm_refilled_on_schedule": crm_on_sched,
                "agreement_group": (
                    "Both Adherent" if arch_type == "A" else
                    "Both Non-Adherent" if arch_type == "B" else
                    "PDC Non-Adherent / CRM On-Schedule" if arch_type == "C" else
                    "PDC Adherent / CRM Not On-Schedule"
                ),
                "discrepancy_reason": discrepancy_reason,
            })

            # Fills generation:
            # Observation period: 90 days for quarterly PDC
            # If pdc_adh == 1: covered days >= 72 / 90 (PDC between 0.82 and 0.98)
            # If pdc_adh == 0: covered days < 72 / 90 (PDC between 0.25 and 0.72)
            if pdc_adh == 1:
                # 3 fills of 30 days or 1 of 90 days
                fill_dates = [enroll_dt, enroll_dt + timedelta(days=28 + rng.randint(-2, 3)), enroll_dt + timedelta(days=58 + rng.randint(-2, 3))]
                supplies = [30, 30, 30]
            else:
                # 1 or 2 fills with large gap
                n_f = rng.choice([1, 2])
                if n_f == 1:
                    fill_dates = [enroll_dt]
                    supplies = [30]
                else:
                    fill_dates = [enroll_dt, enroll_dt + timedelta(days=65 + rng.randint(0, 15))]
                    supplies = [30, 30]

            for f_dt, s_days in zip(fill_dates, supplies):
                if f_dt <= q_end + timedelta(days=30):
                    pharm_type = "Specialty" if is_specialty else "Retail"
                    fills_rows.append({
                        "patient_id": pid,
                        "fill_date": f_dt.strftime("%Y-%m-%d"),
                        "days_supply": s_days,
                        "pharmacy_type": pharm_type,
                        "pharmacy_id": f"PH{rng.randint(1, 15):03d}"
                    })

            # CRM Notes generation:
            # 85% of patients have 1 to 3 CRM notes
            if is_specialty or rng.random() < 0.75:
                n_notes = rng.randint(1, 3)
                for _ in range(n_notes):
                    note_counter += 1
                    note_id = f"NOTE_{note_counter:03d}"
                    note_dt = enroll_dt + timedelta(days=rng.randint(5, 80))
                    
                    # Pick template aligned with patient archetype
                    if arch_type == "A":
                        tmpl, meta = note_templates[4] # Adherent
                    elif arch_type == "C":
                        # Either refill delay that got resolved, sample usage, or ambiguous note
                        tmpl, meta = rng.choice([note_templates[1], note_templates[4], note_templates[7]])
                    elif arch_type == "B":
                        # Discontinuation, missed doses, copay barrier
                        tmpl, meta = rng.choice([note_templates[0], note_templates[2], note_templates[6]])
                    else:
                        # Ambiguous or interruption
                        tmpl, meta = rng.choice([note_templates[3], note_templates[5]])

                    # Format text
                    se = rng.choice(side_effects)
                    dr = rng.choice(discont_reasons)
                    del_r = rng.choice(delay_reasons)
                    
                    note_text = tmpl.format(
                        n_missed=rng.randint(2, 5),
                        side_effect=se,
                        delay_days=rng.randint(7, 21),
                        delay_reason=del_r,
                        discont_reason=dr,
                        pause_days=rng.randint(7, 14)
                    )

                    evidence_quote = note_text[:min(80, len(note_text))] + "..."

                    crm_rows.append({
                        "note_id": note_id,
                        "patient_id": pid,
                        "note_date": note_dt.strftime("%Y-%m-%d"),
                        "reporting_quarter": q_name,
                        "note_text": note_text,
                        "case_manager_id": f"CM{rng.randint(1, 10):03d}",
                        "ground_truth_missed_doses": meta["missed_doses"],
                        "ground_truth_refill_delays": meta["refill_delays"],
                        "ground_truth_discontinuation": meta["discontinuation_reasons"],
                        "ground_truth_interruption": meta["medication_interruptions"],
                        "ground_truth_behavior": meta["patient_reported_behavior"],
                        "ground_truth_confidence": meta["confidence"],
                        "ground_truth_human_review": meta["human_review_flag"],
                        "ground_truth_evidence": evidence_quote
                    })

                    # Labelled ground truth for evaluation (first 50 notes)
                    if note_counter <= 50:
                        labelled_rows.append({
                            "note_id": note_id,
                            "patient_id": pid,
                            "note_text": note_text,
                            "labels": {
                                "missed_doses": meta["missed_doses"],
                                "refill_delays": meta["refill_delays"],
                                "discontinuation_reasons": meta["discontinuation_reasons"],
                                "medication_interruptions": meta["medication_interruptions"],
                                "patient_reported_behavior": meta["patient_reported_behavior"],
                                "human_review_flag": meta["human_review_flag"],
                                "evidence_text": evidence_quote
                            }
                        })

    # Save to CSVs
    enroll_df = pd.DataFrame(enrollment_rows)
    fills_df = pd.DataFrame(fills_rows)
    crm_df = pd.DataFrame(crm_rows)

    enroll_df.to_csv("data/enrollment.csv", index=False)
    fills_df.to_csv("data/fills.csv", index=False)
    crm_df.to_csv("data/crm.csv", index=False)

    with open("data/labelled_crm.json", "w", encoding="utf-8") as f:
        json.dump(labelled_rows, f, indent=2)

    # Verification summary
    print("=" * 60)
    print("SYNTHETIC DATA REPRODUCIBILITY VERIFICATION")
    print("=" * 60)
    for q in ["Last Quarter", "This Quarter"]:
        q_df = enroll_df[enroll_df["reporting_quarter"] == q]
        pdc_rate = q_df["true_pdc_adherent"].mean() * 100
        crm_rate = q_df["crm_refilled_on_schedule"].mean() * 100
        gap = crm_rate - pdc_rate
        print(f"[{q}]")
        print(f"  Pipeline PDC Adherence:    {pdc_rate:.1f}%")
        print(f"  Client CRM Refill Flag:    {crm_rate:.1f}%")
        print(f"  Observed Gap:              {gap:.1f} percentage points")
    print("=" * 60)
    print(f"Total Enrolled Patients:     {len(enroll_df)}")
    print(f"Total Pharmacy Fills:        {len(fills_df)}")
    print(f"Total CRM Interaction Notes: {len(crm_df)}")
    print(f"Ground Truth Labelled Notes: {len(labelled_rows)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
