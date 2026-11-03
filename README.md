# Patient Support Program (PSP) Adherence Reconciliation Analytics Platform

An end-to-end data analytics and clinical NLP platform designed to reconcile the discrepancy between pharmacy claims adherence (PDC 58%) and client CRM nurse outreach metrics (71%).

---

## 📌 Project Overview

Pharmaceutical manufacturers often observe conflicting adherence metrics across different vendor sources. This project provides:
1. **Mathematical Reconciliation Waterfall:** Explains the **58% vs. 71%** (This Quarter) and **64% vs. 72%** (Last Quarter) discrepancy across 3 root-cause drivers (Population, Definition, and Data-Source effects) with **zero unexplained residual**.
2. **Patient-Level Agreement Matrix:** Classifies patients into 4 clinical quadrants, isolating the specific subgroup causing metric divergence.
3. **Gemini 2.5 Flash Clinical Extraction:** Extracts structured clinical adherence categories from free-text CRM notes (missed doses, refill delays, discontinuation reasons, interruptions, and human review flags).
4. **Dynamic Data Quality & Metric Drift Monitoring:** Audits match rates, orphan claims, stale CRM updates (>45d), and quarter-over-quarter metric drift.
5. **Interactive Dashboard (`dashboard.html`):** Standalone Plotly-powered executive dashboard with quarter toggles, 4-quadrant matrices, and patient drill-down.
6. **Executive Solution Document (`Solution_doc.docx`):** Comprehensive business and technical presentation document.

---

## 🏗️ Architecture & Pipeline Flow

```text
config.yaml ──► gen_data.py ──► CSVs (enrollment, fills, crm)
                                    │
               metrics.py (PDC, CRM flag, 4 Quadrants) ──► reconcile.py (3-Effect Waterfall)
                                    │
         extract.py (Gemini 2.5 Flash + Circuit Breaker) ──► evaluate.py (Precision / Recall / F1)
                                    │
         dq_checks.py ──► report.json ──► build_dashboard.py ──► dashboard.html (Standalone UI)
```

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- Python 3.10+ or Python 3.11+
- Git

### 2. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd Patient_Program
```

### 3. Create and Activate a Virtual Environment
**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux / Git Bash:**
```bash
python -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env` and insert your Gemini API Key:
```bash
cp .env.example .env
```
Inside `.env`:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL_NAME=gemini-2.5-flash
```
*(Note: If no API key is provided or if quota limits are reached, the built-in circuit breaker automatically switches to high-fidelity deterministic clinical extraction, ensuring the pipeline completes without crashing).*

---

## ⚡ Running the Entire Pipeline

To execute all 7 stages sequentially:
```bash
python run_all.py
```

### What `run_all.py` does:
1. `gen_data.py`: Generates calibrated synthetic cohorts (250 patients, 606 fills, 490 CRM notes).
2. `metrics.py`: Computes continuous interval-merged PDC, CRM flags, and classifies the 4 concordance quadrants.
3. `reconcile.py`: Computes the 3-effect mathematical waterfall bridge (58.4% ➔ 71.2% and 64.0% ➔ 72.0%).
4. `extract.py`: Extracts clinical categories from CRM notes using Gemini 2.5 Flash with MD5 caching.
5. `evaluate.py`: Evaluates clinical categories against 50 ground-truth annotated notes.
6. `dq_checks.py`: Performs dynamic match-rate, orphan-claim, stale-update, and metric-drift audits.
7. `build_dashboard.py`: Renders the self-contained interactive dashboard to `dashboard.html`.

---

## 📊 Viewing the Output

### 1. Interactive Dashboard
Open `dashboard.html` in any web browser:
- **Windows:** Double-click `dashboard.html` or run:
  ```powershell
  Start-Process dashboard.html
  ```
- **macOS:**
  ```bash
  open dashboard.html
  ```
- **Linux:**
  ```bash
  xdg-open dashboard.html
  ```

### 2. Executive Solution Document
Open `Solution_doc.docx` in Microsoft Word or LibreOffice for the complete case-study report and governance framework.

---

## 📈 Key Verified Results

| Metric | This Quarter (Q2 2024) | Last Quarter (Q1 2024) | Description |
| :--- | :---: | :---: | :--- |
| **Pipeline PDC (Claims $\ge$ 80%)** | **58.4%** | **64.0%** | Continuous 90-day medication possession |
| **Client CRM Flag (Refilled on Schedule)** | **71.2%** | **72.0%** | Single recent refill within 7-day grace period |
| **Discrepancy Gap** | **+12.8 pp** | **+8.0 pp** | Client CRM overstatement |
| **Patient Agreement Rate** | **79.2%** | **84.0%** | Concordant classification between sources |
| **Reconciliation Residual** | **0.00 pp** | **0.00 pp** | Exact mathematical identity closure |
| **Gemini Extraction Micro F1** | **0.8800** | **0.8800** | Benchmarked across 8 clinical categories |
| **Pharmacy Claims Linkage** | **100.0%** | **100.0%** | Zero orphan claims, zero duplicate IDs |

---

## 📁 Repository Structure

```text
├── config.yaml              # Pipeline parameters, thresholds, and clinical vocabulary
├── gen_data.py              # Calibrated synthetic cohort generator
├── metrics.py               # Interval-merged PDC and 4-quadrant agreement engine
├── reconcile.py             # 3-effect mathematical reconciliation bridge
├── extract.py               # Gemini 2.5 Flash clinical extractor with circuit breaker
├── evaluate.py              # Strict category-level Precision, Recall, and F1 scoring
├── dq_checks.py             # Dynamic data quality, freshness, and drift auditing
├── build_dashboard.py       # Standalone Plotly HTML dashboard builder
├── run_all.py               # Master end-to-end execution script
├── create_solution_doc.py   # Generates formatted Word document (Solution_doc.docx)
├── requirements.txt         # Pinned Python package dependencies
├── .env.example             # Template for API credentials
├── .gitignore               # Excludes secrets, caches, and virtual environments
├── dashboard.html           # Generated standalone interactive dashboard
├── Solution_doc.docx        # Generated executive solution report
└── data/                    # Generated datasets, caches, and audit reports
    ├── enrollment.csv
    ├── fills.csv
    ├── crm.csv
    ├── patient_metrics.csv
    ├── shapley_values.json
    ├── extracted_crm.json
    ├── labelled_crm.json
    ├── evaluation_results.json
    ├── dq_report.json
    └── gemini_cache.json
```

---

## 📜 License
This project is open-source under the MIT License.

