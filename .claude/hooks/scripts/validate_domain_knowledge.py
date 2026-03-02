#!/usr/bin/env python3
"""
Domain Knowledge Structure P1 Validation — validate_domain_knowledge.py

Standalone script called by Orchestrator when a workflow uses DKS pattern.
NOT a Hook — manually invoked during workflow execution.

Usage:
    # DKS file self-validation
    python3 .claude/hooks/scripts/validate_domain_knowledge.py --project-dir .

    # DKS + output cross-validation
    python3 .claude/hooks/scripts/validate_domain_knowledge.py --project-dir . --check-output --step 7

Output: JSON to stdout
    {"valid": true, "entity_count": 15, "relation_count": 8, "warnings": [...]}

Exit codes:
    0 — validation completed (check "valid" field for result)
    1 — argument error or fatal failure

Checks (DK1-DK7):
    DK1: File exists and YAML is valid
    DK2: metadata contains required keys (domain, schema_version)
    DK3: entities structure (id unique + slug format, type string, attributes dict)
    DK4: relations referential integrity (subject/object -> entities.id, confidence valid)
    DK5: constraints structure (id, description, check present)
    DK6: (--check-output) Output DKS markers resolve to entity/relation IDs
    DK7: (--check-output) Constraint non-violation (best-effort numeric check)

P1 Compliance: All validation is deterministic (delegates to _context_lib).
SOT Compliance: Read-only — no file writes.
"""

import argparse
import json
import os
import re
import sys

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _context_lib import extract_remediations, validate_domain_knowledge


def main():
    parser = argparse.ArgumentParser(
        description="P1 Validation for Domain Knowledge Structure"
    )
    parser.add_argument(
        "--project-dir", type=str, default=".",
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "--check-output", action="store_true",
        help="Cross-check DKS references in step output"
    )
    parser.add_argument(
        "--step", type=int, default=None,
        help="Step number for --check-output cross-validation"
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)

    # Validate arguments
    if args.check_output and args.step is None:
        print(json.dumps({
            "valid": False,
            "error": "--check-output requires --step N",
            "warnings": ["Argument error: --check-output requires --step N"],
        }, indent=2))
        sys.exit(1)

    check_step = args.step if args.check_output else None

    # Core validation: DK1-DK7
    is_valid, warnings = validate_domain_knowledge(
        project_dir, check_output_step=check_step
    )

    # Extract counts from info warnings
    entity_count = 0
    relation_count = 0
    constraint_count = 0
    for w in warnings:
        if "DK INFO:" in w:
            ec_match = re.search(r'entity_count=(\d+)', w)
            rc_match = re.search(r'relation_count=(\d+)', w)
            cc_match = re.search(r'constraint_count=(\d+)', w)
            if ec_match:
                entity_count = int(ec_match.group(1))
            if rc_match:
                relation_count = int(rc_match.group(1))
            if cc_match:
                constraint_count = int(cc_match.group(1))

    # Remediation mapping — OpenAI harness pattern: inject fix instructions
    _REMEDIATIONS = {
        "DK1": "Create or fix domain-knowledge.yaml — must be valid YAML with proper structure",
        "DK2": "Add required metadata keys: domain (string) and schema_version (string) to metadata section",
        "DK3": "Fix entities structure: each entity needs unique id (slug format), type (string), attributes (dict)",
        "DK4": "Fix relations referential integrity: all subject/object must reference existing entity IDs, confidence 0-1",
        "DK5": "Fix constraints structure: each constraint needs id, description, and check fields",
        "DK6": "Fix DKS markers in output: all [dks:xxx] references must resolve to entity/relation IDs",
        "DK7": "Constraint violation detected — review and fix output to satisfy domain constraints",
    }

    # Build output
    output = {
        "valid": is_valid,
        "entity_count": entity_count,
        "relation_count": relation_count,
        "constraint_count": constraint_count,
        "warnings": list(warnings),
    }

    # Extract remediation for failed checks (P1-B: central function + P1-F: self-check)
    remediations = extract_remediations(warnings, _REMEDIATIONS)
    if remediations:
        output["remediations"] = remediations

    if check_step is not None:
        output["checked_step"] = check_step

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_output = {
            "valid": False,
            "entity_count": 0,
            "relation_count": 0,
            "constraint_count": 0,
            "error": str(e),
            "warnings": [f"Fatal error: {e}"],
        }
        print(json.dumps(error_output, indent=2, ensure_ascii=False))
        sys.exit(1)
