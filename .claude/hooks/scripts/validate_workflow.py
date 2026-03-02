#!/usr/bin/env python3
"""
Workflow.md DNA Inheritance P1 Validation — validate_workflow.py

Standalone script called after workflow-generator completes (SKILL.md Step 13).
NOT a Hook — manually invoked during workflow generation.

Usage:
    python3 .claude/hooks/scripts/validate_workflow.py --workflow-path ./workflow.md

Output: JSON to stdout
    {"valid": true, "warnings": [], ...}

Exit codes:
    0 — validation completed (check "valid" field for result)
    1 — argument error or fatal failure

Checks (W1-W8):
    W1: Workflow file exists and is readable
    W2: Minimum file size (≥ 500 bytes)
    W3: Inherited DNA header present
    W4: Inherited Patterns table present (≥ 3 data rows)
    W5: Constitutional Principles section present
    W6: Coding Anchor Points (CAP) reference present
    W7: Cross-step traceability Verification-Validator consistency
    W8: Domain knowledge Verification-Validator consistency

P1 Compliance: All validation is deterministic (delegates to _context_lib).
SOT Compliance: Read-only — no file writes.
"""

import argparse
import json
import os
import sys

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _context_lib import extract_remediations, validate_workflow_md


def main():
    parser = argparse.ArgumentParser(
        description="P1 Validation for generated workflow.md DNA inheritance"
    )
    parser.add_argument(
        "--workflow-path", type=str, required=True,
        help="Path to the generated workflow.md file"
    )
    args = parser.parse_args()

    workflow_path = os.path.abspath(args.workflow_path)
    is_valid, warnings = validate_workflow_md(workflow_path)

    # Remediation mapping — OpenAI harness pattern: inject fix instructions
    _REMEDIATIONS = {
        "W1": f"Workflow file not found at {workflow_path} — check path",
        "W2": "Workflow file is too small (< 500 bytes) — incomplete generation",
        "W3": "Add '## Inherited DNA' header to workflow.md — required for DNA inheritance verification",
        "W4": "Add Inherited Patterns table with ≥ 3 data rows under Inherited DNA section",
        "W5": "Add '## Constitutional Principles' or '## Absolute Criteria' section",
        "W6": "Add CAP (Coding Anchor Points) reference — mention CAP-1 through CAP-4",
        "W7": "CT Verification-Validator mismatch: if Verification has CT criteria, add validate_traceability Post-processing",
        "W8": "DKS Verification-Validator mismatch: if DKS references exist, add validate_domain_knowledge Post-processing",
    }

    output = {
        "valid": is_valid,
        "workflow_path": workflow_path,
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
            "error": str(e),
            "warnings": [f"Fatal error: {e}"],
        }
        print(json.dumps(error_output, indent=2, ensure_ascii=False))
        sys.exit(1)
