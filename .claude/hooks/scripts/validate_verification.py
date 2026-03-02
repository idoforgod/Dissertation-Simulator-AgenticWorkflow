#!/usr/bin/env python3
"""
Verification Log P1 Validation — validate_verification.py

Standalone script called by Orchestrator after Verification Gate completes.
NOT a Hook — manually invoked during workflow execution.

Usage:
    python3 .claude/hooks/scripts/validate_verification.py --step 3 --project-dir .

Output: JSON to stdout
    {"valid": true, "warnings": [], ...}

Exit codes:
    0 — validation completed (check "valid" field for result)
    1 — argument error or fatal failure

P1 Compliance: All validation is deterministic (delegates to _context_lib).
SOT Compliance: Read-only — no file writes.
"""

import argparse
import json
import os
import sys

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _context_lib import (
    extract_remediations,
    validate_verification_log,
    verify_pacs_arithmetic,
)


def main():
    parser = argparse.ArgumentParser(
        description="P1 Validation for Verification Gate outputs"
    )
    parser.add_argument(
        "--step", type=int, required=True,
        help="Step number to validate"
    )
    parser.add_argument(
        "--project-dir", type=str, default=".",
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "--check-pacs", action="store_true",
        help="Also validate step pACS arithmetic (T9)"
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    step = args.step

    # Core validation: V1a-V1c
    is_valid, warnings = validate_verification_log(project_dir, step)

    # Remediation mapping — OpenAI harness pattern: inject fix instructions
    _REMEDIATIONS = {
        "V1a": f"Create verification log: verify each criterion → record PASS/FAIL with evidence → save to verification-logs/step-{step}-verify.md",
        "V1b": "Add per-criterion results: each Verification criterion must have explicit PASS or FAIL with evidence",
        "V1c": "Fix logical inconsistency: if any criterion is FAIL, overall result cannot be PASS. Correct the failed criteria or change overall to FAIL",
    }

    # Build output
    output = {
        "valid": is_valid,
        "step": step,
        "warnings": list(warnings),
    }

    # Extract remediation for failed checks (P1-B: central function + P1-F: self-check)
    remediations = extract_remediations(warnings, _REMEDIATIONS)
    if remediations:
        output["remediations"] = remediations

    # Optional: T9 — pACS arithmetic check for this step
    if args.check_pacs:
        pacs_path = os.path.join(
            project_dir, "pacs-logs", f"step-{step}-pacs.md"
        )
        pacs_valid, pacs_warning = verify_pacs_arithmetic(pacs_path)
        output["pacs_arithmetic_valid"] = pacs_valid
        if pacs_warning:
            output["warnings"].append(pacs_warning)
            if not pacs_valid:
                output["valid"] = False

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_output = {
            "valid": False,
            "error": str(e),
            "warnings": [f"Fatal error: {e}"],
        }
        print(json.dumps(error_output, indent=2, ensure_ascii=False))
        sys.exit(1)
