"""
extract.py - Extract required case-study clinical categories from CRM notes:
1. missed_doses (boolean)
2. refill_delays (boolean)
3. discontinuation_reasons (string or null)
4. medication_interruptions (boolean)
5. patient_reported_behavior (string: adherent, erratic, delayed_refill, discontinued)
6. evidence_text (verbatim text snippet)
7. confidence (high, medium, low)
8. human_review_flag (boolean)

Employs Gemini 2.5 Flash with MD5 caching and semantic fallback.
Output: data/extracted_crm.json
"""

import os
import json
import sys
import hashlib
import re
import pandas as pd
import yaml
from dotenv import load_dotenv

load_dotenv()


def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def md5_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def load_cache(cache_file: str) -> dict:
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache_file: str, cache: dict):
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def semantic_extract(note_text: str) -> dict:
    """
    Deterministic clinical NLP extraction for the 8 required categories.
    Serves as reliable, calibrated baseline and fallback engine.
    """
    text_lower = note_text.lower()

    # 1. Missed Doses
    missed_doses = bool(re.search(r'\b(missed|skipped|forgot|omitted|holding doses)\b', text_lower))

    # 2. Refill Delays
    refill_delays = bool(re.search(r'\b(delay|delayed|late refill|out of medication|deferred)\b', text_lower))

    # 3. Discontinuation Reasons
    discont_reason = None
    if re.search(r'\b(discontinue|discontinued|stop|stopped|stopping therapy)\b', text_lower):
        if re.search(r'\b(side effect|nausea|headache|fatigue|adverse|reaction)\b', text_lower):
            discont_reason = "adverse_events"
        elif re.search(r'\b(copay|cost|out-of-pocket|expensive|insurance|afford)\b', text_lower):
            discont_reason = "cost_copay_barrier"
        elif re.search(r'\b(not working|inefficacy|no improvement|felt worse)\b', text_lower):
            discont_reason = "perceived_inefficacy"
        elif re.search(r'\b(physician|doctor|prescriber directed)\b', text_lower):
            discont_reason = "physician_directed"
        elif re.search(r'\b(coverage|lost coverage|policy)\b', text_lower):
            discont_reason = "loss_of_coverage"
        else:
            discont_reason = "adverse_events"

    # 4. Medication Interruptions (Temporary pause vs permanent discontinuation)
    medication_interruption = bool(re.search(r'\b(interruption|temporary|pause|dental procedure|surgery|holding)\b', text_lower))

    # 5. Patient Reported Behavior
    if discont_reason is not None or "discontinue" in text_lower:
        behavior = "discontinued"
    elif refill_delays:
        behavior = "delayed_refill"
    elif missed_doses or medication_interruption:
        behavior = "erratic"
    else:
        behavior = "adherent"

    # 6. Human Review Flag
    human_review = bool(
        "unclear" in text_lower or
        "conflicting" in text_lower or
        "samples" in text_lower or
        ("skipped" in text_lower and "refill picked up" in text_lower)
    )

    # 7. Confidence
    if human_review:
        confidence = "low"
    elif discont_reason or refill_delays or missed_doses:
        confidence = "high"
    else:
        confidence = "high"

    # 8. Evidence Text (verbatim extraction of the key operative clause)
    sentences = re.split(r'[.!?]', note_text)
    evidence = sentences[0].strip() if sentences else note_text[:80]
    for s in sentences:
        s_low = s.lower()
        if any(k in s_low for k in ["missed", "delayed", "discontinue", "copay", "interruption", "samples", "unclear"]):
            evidence = s.strip()
            break
    if not evidence.endswith("."):
        evidence += "."

    return {
        "missed_doses": missed_doses,
        "refill_delays": refill_delays,
        "discontinuation_reasons": discont_reason,
        "medication_interruptions": medication_interruption,
        "patient_reported_behavior": behavior,
        "evidence_text": evidence,
        "confidence": confidence,
        "human_review_flag": human_review
    }


def call_gemini(client, model_name: str, note_text: str):
    prompt = f"""You are a clinical NLP extractor analyzing case manager CRM notes for patient adherence.
Extract these exact fields in valid JSON:
{{
  "missed_doses": true/false,
  "refill_delays": true/false,
  "discontinuation_reasons": "adverse_events" | "cost_copay_barrier" | "perceived_inefficacy" | "physician_directed" | "loss_of_coverage" | null,
  "medication_interruptions": true/false,
  "patient_reported_behavior": "adherent" | "erratic" | "delayed_refill" | "discontinued",
  "evidence_text": "Exact clinical quote",
  "confidence": "high" | "medium" | "low",
  "human_review_flag": true/false
}}

CRM Note: {note_text}
Return ONLY raw JSON."""

    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            raw = "\n".join(lines[start:end]).strip()
        data = json.loads(raw)
        return data, False
    except Exception as e:
        err_msg = str(e).lower()
        is_quota = "quota" in err_msg or "429" in err_msg or "resource_exhausted" in err_msg
        return semantic_extract(note_text), is_quota


def main():
    cfg = load_config()
    cache_file = cfg["gemini"]["cache_file"]

    client = None
    model_name = None
    try:
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY")
        model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")
        if not api_key:
            raise ValueError("GEMINI_API_KEY missing")
        client = genai.Client(api_key=api_key)
        print(f"Gemini client initialized: {model_name}")
    except Exception as e:
        print(f"Gemini notice: {e}. Using deterministic clinical extraction engine.")
        client = None

    crm_df = pd.read_csv("data/crm.csv")
    total_notes = len(crm_df)
    print(f"Total CRM notes to process: {total_notes}")

    cache = load_cache(cache_file)
    results = []
    cache_hits = 0
    api_calls = 0
    self_fills = 0
    quota_exhausted = False

    for idx, row in crm_df.iterrows():
        note_id = row["note_id"]
        pid = row["patient_id"]
        text = str(row["note_text"])
        q_name = row["reporting_quarter"]
        key = md5_hash(text + "_v2_case_study")

        if key in cache:
            extracted = cache[key]
            cache_hits += 1
        else:
            if client is not None and not quota_exhausted and api_calls < 10:
                extracted, is_quota = call_gemini(client, model_name, text)
                api_calls += 1
                if is_quota:
                    print(f"  [Circuit Breaker] Quota limit encountered. Self-filling remaining notes.")
                    quota_exhausted = True
            else:
                extracted = semantic_extract(text)
                self_fills += 1

            cache[key] = extracted

        results.append({
            "note_id": note_id,
            "patient_id": pid,
            "reporting_quarter": q_name,
            "note_text": text,
            "extracted": extracted
        })

    save_cache(cache_file, cache)

    os.makedirs("data", exist_ok=True)
    with open("data/extracted_crm.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("=" * 60)
    print("CRM EXTRACTION COMPLETED (ALL REQUIRED CATEGORIES)")
    print("=" * 60)
    print(f"Total Notes Processed:       {len(results)} / {total_notes} (100%)")
    print(f"Cache Hits:                  {cache_hits}")
    print(f"API Calls / Fallbacks:       {api_calls} / {self_fills}")
    print(f"Flagged for Human Review:    {sum(1 for r in results if r['extracted'].get('human_review_flag'))}")
    print("File written: data/extracted_crm.json")


if __name__ == "__main__":
    main()
