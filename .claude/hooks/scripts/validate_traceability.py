#!/usr/bin/env python3
"""
Cross-Step Traceability P1 Validation — validate_traceability.py

Standalone script called by Orchestrator when a step has Cross-Step
Traceability in its Verification criteria (5th verification type).
NOT a Hook — manually invoked during workflow execution.

Usage:
    python3 .claude/hooks/scripts/validate_traceability.py --step 5 --project-dir .

Output: JSON to stdout
    {"valid": true, "step": 5, "trace_count": 12, "verified_count": 11, "warnings": [...]}

Exit codes:
    0 — validation completed (check "valid" field for result)
    1 — argument error or fatal failure

Checks (CT1-CT5):
    CT1: Trace markers exist in output (>= 1)
    CT2: Referenced step outputs exist on disk
    CT3: Section IDs resolve to headings in source (Warning only)
    CT4: Minimum trace marker density (>= 3)
    CT5: No forward references (step-N where N >= current step)

P1 Compliance: All validation is deterministic (delegates to _context_lib).
SOT Compliance: Read-only — no file writes.
"""

import argparse
import json
import os
import sys

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _context_lib import extract_remediations, validate_cross_step_traceability


def main():
    parser = argparse.ArgumentParser(
        description="P1 Validation for Cross-Step Traceability markers"
    )
    parser.add_argument(
        "--step", type=int, required=True,
        help="Step number to validate traceability for"
    )
    parser.add_argument(
        "--project-dir", type=str, default=".",
        help="Project root directory (default: current directory)"
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    step = args.step

    # Core validation: CT1-CT5
    is_valid, warnings = validate_cross_step_traceability(project_dir, step)

    # Extract trace_count and verified_count from info warnings
    trace_count = 0
    verified_count = 0
    for w in warnings:
        if "CT INFO:" in w:
            import re
            tc_match = re.search(r'trace_count=(\d+)', w)
            vc_match = re.search(r'verified_count=(\d+)', w)
            if tc_match:
                trace_count = int(tc_match.group(1))
            if vc_match:
                verified_count = int(vc_match.group(1))

    # Remediation mapping — OpenAI harness pattern: inject fix instructions
    _REMEDIATIONS = {
        "CT1": f"Add [trace:step-N:section-id] markers to the output file for step {step}",
        "CT2": "Referenced step output file not found on disk — verify SOT outputs paths are correct",
        "CT4": f"Add more trace markers to step {step} output — minimum 3 required, found fewer",
        "CT5": f"Remove forward references — all [trace:step-N:...] markers must reference steps < {step}",
    }

    # Build output
    output = {
        "valid": is_valid,
        "step": step,
        "trace_count": trace_count,
        "verified_count": verified_count,
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
        error_output = {
            "valid": False,
            "step": None,
            "trace_count": 0,
            "verified_count": 0,
            "error": str(e),
            "warnings": [f"Fatal error: {e}"],
        }
        print(json.dumps(error_output, indent=2, ensure_ascii=False))
        sys.exit(1)
