#!/usr/bin/env python3
"""
Abductive Diagnosis P1 Validation — validate_diagnosis.py

Standalone script called by Orchestrator after LLM writes a diagnosis log.
NOT a Hook — manually invoked during workflow execution.

Usage:
    python3 .claude/hooks/scripts/validate_diagnosis.py --step 3 --gate verification --project-dir .
    python3 .claude/hooks/scripts/validate_diagnosis.py --step 3 --gate pacs --project-dir .
    python3 .claude/hooks/scripts/validate_diagnosis.py --step 3 --gate review --project-dir .

Output: JSON to stdout
    {"valid": true, "warnings": [], ...}

Exit codes:
    0 — validation completed (check "valid" field for result)
    1 — argument error or fatal failure

Checks (AD1-AD10):
    AD1: Diagnosis log file exists
    AD2: Minimum file size (≥ 100 bytes)
    AD3: Gate field matches expected gate
    AD4: Selected hypothesis present (H1/H2/H3/H4)
    AD5: Evidence section present (≥ 1 item)
    AD6: Action plan section present
    AD7: No forward step references
    AD8: Hypothesis count ≥ 2
    AD9: Selected hypothesis consistency
    AD10: Previous diagnosis referenced (if retry > 0)

P1 Compliance: All validation is deterministic (delegates to _context_lib).
SOT Compliance: Read-only — no file writes.
"""

import argparse
import json
import os
import sys

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _context_lib import extract_remediations, validate_diagnosis_log


def main():
    parser = argparse.ArgumentParser(
        description="P1 Validation for Abductive Diagnosis logs"
    )
    parser.add_argument(
        "--step", type=int, required=True,
        help="Step number to validate"
    )
    parser.add_argument(
        "--gate", type=str, required=True,
        choices=["verification", "pacs", "review"],
        help="Which quality gate the diagnosis is for"
    )
    parser.add_argument(
        "--project-dir", type=str, default=".",
        help="Project root directory (default: current directory)"
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    step = args.step
    gate = args.gate

    # Core validation: AD1-AD10
    is_valid, warnings = validate_diagnosis_log(project_dir, step, gate)

    # Remediation mapping — AD1-AD10 fix instructions
    _REMEDIATIONS = {
        "AD1": f"Diagnosis log missing — run: python3 .claude/hooks/scripts/diagnose_context.py --step {step} --gate {gate} --project-dir . then write diagnosis log",
        "AD2": "Diagnosis log too small (< 100 bytes) — include evidence, hypotheses, selected hypothesis, and action plan",
        "AD3": f"Gate field mismatch — diagnosis must specify gate: {gate}",
        "AD4": "Selected hypothesis missing — explicitly state which hypothesis (H1/H2/H3/H4) was chosen",
        "AD5": "Evidence section missing or empty — include at least 1 evidence item from diagnose_context.py output",
        "AD6": "Action Plan section missing — describe concrete steps to fix the identified issue",
        "AD7": "Forward step reference detected — diagnosis must only reference current and prior steps",
        "AD8": "Fewer than 2 hypotheses — compare at least 2 candidate root causes before selecting one",
        "AD9": "Selected hypothesis inconsistency — the chosen H-label must match one of the listed hypotheses",
        "AD10": f"Previous diagnosis not referenced — retry > 0 requires referencing prior diagnosis for step {step}",
    }

    # Build output
    output = {
        "valid": is_valid,
        "step": step,
        "gate": gate,
        "warnings": list(warnings),
    }

    # Extract remediation for failed checks (P1-B: central function + P1-F: self-check)
    remediations = extract_remediations(warnings, _REMEDIATIONS)
    if remediations:
        output["remediations"] = remediations

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "valid": False,
        }), file=sys.stdout)
        sys.exit(1)
