"""
run_all.py - Master script that runs all pipeline steps in order.
"""

import subprocess
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

steps = [
    ("Generate Data", "gen_data.py"),
    ("Compute Metrics", "metrics.py"),
    ("Reconcile (Shapley)", "reconcile.py"),
    ("Extract CRM (Gemini)", "extract.py"),
    ("Evaluate Extraction", "evaluate.py"),
    ("Data Quality Checks", "dq_checks.py"),
    ("Build Dashboard", "build_dashboard.py"),
]

for name, script in steps:
    print(f"\n{'='*60}")
    print(f"STEP: {name}")
    print('='*60)
    result = subprocess.run([sys.executable, script], capture_output=False)
    if result.returncode != 0:
        print(f"ERROR: {name} failed with code {result.returncode}")
        print(f"[ERROR] {name} failed with code {result.returncode}")
        sys.exit(1)
    print(f"✓ {name} complete")
    print(f"[OK] {name} complete")

print("\n" + "="*60)
print("ALL STEPS COMPLETE. Open dashboard.html to view results.")
print("="*60)

