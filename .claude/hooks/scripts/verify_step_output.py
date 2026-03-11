#!/usr/bin/env python3
"""verify_step_output.py — P1 Deterministic Step Output Verification.

Replaces the Orchestrator's LLM-based output file verification (E5 Post-
execution) with a deterministic validation pipeline. Integrates L0 Anti-Skip
Guard with content quality checks that were previously missing.

This eliminates:
  - V-1: Output File Path Verification (LLM glob interpretation)
  - GAP-3: Claim prefix mismatch (wrong agent claims pass through)
  - GAP-4: Missing content validation (placeholder output passes)
  - GAP-DW: Non-doctoral writing quality escapes detection

Usage:
    python3 verify_step_output.py --step 42 --project-dir thesis-output/my-thesis
    python3 verify_step_output.py --step 125 --project-dir thesis-output/my-thesis \
        --research-type quantitative

Output: JSON to stdout
    {
        "valid": true,
        "step": 42,
        "file_path": "wave-results/wave-1/step-042-literature-search.md",
        "file_size": 12345,
        "checks": {
            "VO1_exists": "PASS",
            "VO2_utf8": "PASS",
            "VO3_no_placeholder": "PASS",
            "VO4_has_claims": "PASS",
            "VO5_prefix_match": "PASS"
        },
        "errors": [],
        "warnings": [],
        "claim_count": 15,
        "expected_prefix": "LS"
    }

Checks:
    VO-1: File exists AND size >= min_output_bytes (from query_step.py)
    VO-2: File is valid UTF-8
    VO-3: No placeholder content (Lorem ipsum, TODO, FIXME, [insert], etc.)
    VO-4: Tier A steps (has_grounded_claims) → at least 1 GroundedClaim
    VO-5: Claim prefix matches expected agent prefix
    VO-6: No banned academic expressions (WARNING, non-blocking)
    VO-7: Heading structure present for files >2000 bytes (FAIL)

Exit codes:
    0 — always (P1 compliant, non-blocking)

P1 Compliance: Glob, regex, file size — zero LLM.
SOT Compliance: Read-only access to project dir and query_step.py registry.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Any

# Add script directory to path for shared library import
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from _claim_patterns import CLAIM_ID_INLINE_RE, extract_claim_ids  # noqa: E402
from checklist_manager import AGENT_CLAIM_PREFIXES  # noqa: E402

# Lazy import to avoid circular dependency at module level
_query_step_module = None


def _get_query_step():
    """Lazy-load query_step module."""
    global _query_step_module
    if _query_step_module is None:
        import query_step as qs
        _query_step_module = qs
    return _query_step_module


# =============================================================================
# Placeholder Detection Patterns (P1 deterministic)
# =============================================================================

_PLACEHOLDER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\blorem\s+ipsum\b",
        r"\bTODO\s*:",
        r"\bFIXME\s*:",
        r"\bXXX\s*:",
        r"\[insert\b",
        r"\[placeholder\b",
        r"\[fill\s+in\b",
        r"\[TBD\]",
        r"\[to\s+be\s+(?:added|completed|written|determined)\]",
        r"\bwork\s+in\s+progress\b",
        r"\bdraft\s+(?:only|placeholder)\b",
    ]
]

# Minimum non-whitespace content ratio (prevent mostly-whitespace files)
_MIN_CONTENT_RATIO = 0.3

# =============================================================================
# Banned Academic Expressions (VO-6, P1 deterministic — WARNING only)
# =============================================================================
# These wordy/filler expressions indicate non-doctoral writing quality.
# Based on .claude/skills/doctoral-writing/references/common-issues.md

_BANNED_EXPRESSION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bit is important to note that\b",
        r"\bit goes without saying\b",
        r"\bneedless to say\b",
        r"\bit should be noted that\b",
        r"\bit is worth mentioning that\b",
        r"\bin order to\b",
        r"\bdue to the fact that\b",
        r"\bin spite of the fact that\b",
        r"\bfor the purpose of\b",
        r"\bat this point in time\b",
        r"\bin the event that\b",
        r"\bfirst and foremost\b",
        r"\beach and every\b",
        r"\blast but not least\b",
    ]
]

# Agents exempt from VO-6/VO-7 (non-text-producing or special roles)
_DW_CHECK_EXEMPT_AGENTS: set[str] = {
    "_orchestrator", "translator",
}

# Minimum heading threshold (VO-7)
_HEADING_MIN_BYTES = 2000


def _detect_banned_expressions(content: str) -> list[str]:
    """Detect banned academic expressions. Returns list of matched patterns."""
    found: list[str] = []
    for pattern in _BANNED_EXPRESSION_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            found.append(matches[0])
    return found


def _has_heading_structure(content: str) -> bool:
    """Check if content has at least one markdown heading (## or deeper)."""
    return bool(re.search(r'^#{2,}\s+\S', content, re.MULTILINE))


def _detect_placeholders(content: str) -> list[str]:
    """Detect placeholder patterns in content. Returns list of matched patterns."""
    found: list[str] = []
    for pattern in _PLACEHOLDER_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            found.append(matches[0])
    return found


# =============================================================================
# Output File Resolution (P1 deterministic)
# =============================================================================

def _resolve_output_file(
    project_dir: str,
    output_pattern: str,
) -> str | None:
    """Resolve output pattern to actual file path.

    Uses glob matching and selects the most recently modified file
    if multiple matches exist. This eliminates LLM ambiguity in
    file selection (V-1).

    Returns: absolute file path, or None if no match.
    """
    # Build full glob path
    full_pattern = os.path.join(project_dir, output_pattern)
    matches = glob.glob(full_pattern)

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0]

    # Multiple matches: select most recently modified (deterministic tiebreak)
    matches.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return matches[0]


# =============================================================================
# Prefix Extraction (P1 deterministic)
# =============================================================================

def _extract_prefix(claim_id: str) -> str:
    """Extract the prefix from a claim ID.

    Examples:
        "LS-001" → "LS"
        "EMP-NEURO-001" → "EMP-NEURO"
        "VRA-H-003" → "VRA-H"
        "SA-TA-001" → "SA-TA"

    Rule: everything before the final digit sequence.
    """
    # Remove trailing digits (and optional preceding hyphen)
    match = re.match(r'^(.*?)-?\d+$', claim_id)
    return match.group(1) if match else claim_id


# =============================================================================
# Main Verification
# =============================================================================

def verify_step_output(
    step: int,
    project_dir: str,
    research_type: str = "undecided",
) -> dict[str, Any]:
    """P1 deterministic step output verification.

    Integrates L0 Anti-Skip Guard with content quality checks.
    The Orchestrator MUST call this after every step execution
    and refuse to advance if valid==False.

    Args:
        step: Thesis workflow step number
        project_dir: Project root directory
        research_type: For Phase 2 agent resolution

    Returns:
        dict with verification results (valid, checks, errors, warnings)
    """
    qs = _get_query_step()
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, str] = {}

    # Get step info from P1 registry (function is query_step.query_step)
    step_info = qs.query_step(step, research_type)
    if "error" in step_info:
        return {
            "valid": False,
            "step": step,
            "file_path": None,
            "file_size": 0,
            "checks": {},
            "errors": [f"query_step.py error: {step_info['error']}"],
            "warnings": [],
            "claim_count": 0,
            "expected_prefix": None,
        }

    output_pattern = step_info.get("output_path", "")
    agent = step_info.get("agent", "")
    min_bytes = step_info.get("min_output_bytes", 100)
    has_claims = step_info.get("has_grounded_claims", False)
    expected_prefix = AGENT_CLAIM_PREFIXES.get(agent)

    # Resolve output file path
    file_path = _resolve_output_file(project_dir, output_pattern)

    # ===================================================================
    # VO-1: File exists AND size >= min_output_bytes
    # ===================================================================
    if file_path is None:
        checks["VO1_exists"] = "FAIL"
        errors.append(
            f"VO-1: No file matches pattern '{output_pattern}' in {project_dir}"
        )
        return {
            "valid": False,
            "step": step,
            "file_path": None,
            "file_size": 0,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "claim_count": 0,
            "expected_prefix": expected_prefix,
        }

    file_size = os.path.getsize(file_path)
    if file_size < min_bytes:
        checks["VO1_exists"] = "FAIL"
        errors.append(
            f"VO-1: File size ({file_size} bytes) below minimum ({min_bytes} bytes)"
        )
    else:
        checks["VO1_exists"] = "PASS"

    # ===================================================================
    # VO-2: Valid UTF-8
    # ===================================================================
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        checks["VO2_utf8"] = "PASS"
    except UnicodeDecodeError as e:
        checks["VO2_utf8"] = "FAIL"
        errors.append(f"VO-2: File is not valid UTF-8: {e}")
        content = ""
    except OSError as e:
        checks["VO2_utf8"] = "FAIL"
        errors.append(f"VO-2: Cannot read file: {e}")
        content = ""

    # ===================================================================
    # VO-3: No placeholder content
    # ===================================================================
    placeholders = _detect_placeholders(content) if content else []
    if placeholders:
        checks["VO3_no_placeholder"] = "FAIL"
        errors.append(
            f"VO-3: Placeholder content detected: {', '.join(placeholders[:5])}"
        )
    else:
        checks["VO3_no_placeholder"] = "PASS"

    # ===================================================================
    # VO-4: Tier A steps → at least 1 GroundedClaim
    # ===================================================================
    claim_ids = extract_claim_ids(content) if content else []
    claim_count = len(claim_ids)

    if has_claims:
        if claim_count >= 1:
            checks["VO4_has_claims"] = "PASS"
        else:
            checks["VO4_has_claims"] = "FAIL"
            errors.append(
                f"VO-4: Step {step} requires GroundedClaims but found 0"
            )
    else:
        checks["VO4_has_claims"] = "SKIP (Tier B — no claims expected)"

    # ===================================================================
    # VO-5: Claim prefix matches expected agent prefix
    # ===================================================================
    if has_claims and expected_prefix and claim_ids:
        # Extract prefixes from all claim IDs
        found_prefixes = set(_extract_prefix(cid) for cid in claim_ids)
        # Check if expected prefix appears in found prefixes
        prefix_match = any(
            fp == expected_prefix or fp.startswith(expected_prefix + "-")
            for fp in found_prefixes
        )
        if prefix_match:
            checks["VO5_prefix_match"] = "PASS"
        else:
            checks["VO5_prefix_match"] = "FAIL"
            errors.append(
                f"VO-5: Expected prefix '{expected_prefix}' (agent={agent}) "
                f"but found: {', '.join(sorted(found_prefixes))}"
            )
    elif has_claims and not expected_prefix:
        checks["VO5_prefix_match"] = f"SKIP (no prefix mapping for agent '{agent}')"
        warnings.append(
            f"VO-5: Agent '{agent}' has no AGENT_CLAIM_PREFIXES entry — "
            f"prefix validation skipped"
        )
    else:
        checks["VO5_prefix_match"] = "SKIP (no claims to verify)"

    # ===================================================================
    # VO-6: No banned academic expressions (WARNING — non-blocking)
    # ===================================================================
    if agent not in _DW_CHECK_EXEMPT_AGENTS and content:
        banned = _detect_banned_expressions(content)
        if banned:
            checks["VO6_no_banned_expr"] = "WARN"
            warnings.append(
                f"VO-6: Banned academic expressions detected (doctoral writing "
                f"quality): {', '.join(repr(b) for b in banned[:5])}"
            )
        else:
            checks["VO6_no_banned_expr"] = "PASS"
    else:
        checks["VO6_no_banned_expr"] = f"SKIP (agent '{agent}' exempt)"

    # ===================================================================
    # VO-7: Heading structure for files >2000 bytes (FAIL)
    # ===================================================================
    if agent not in _DW_CHECK_EXEMPT_AGENTS and content and file_size >= _HEADING_MIN_BYTES:
        if _has_heading_structure(content):
            checks["VO7_heading_structure"] = "PASS"
        else:
            checks["VO7_heading_structure"] = "FAIL"
            errors.append(
                f"VO-7: File is {file_size} bytes but has no heading structure "
                f"(expected at least one ## heading)"
            )
    elif agent in _DW_CHECK_EXEMPT_AGENTS:
        checks["VO7_heading_structure"] = f"SKIP (agent '{agent}' exempt)"
    else:
        checks["VO7_heading_structure"] = "SKIP (file < 2000 bytes)"

    # Compute overall result
    is_valid = not any(v == "FAIL" for v in checks.values())

    # Relative path for cleaner output
    rel_path = os.path.relpath(file_path, project_dir) if file_path else None

    return {
        "valid": is_valid,
        "step": step,
        "file_path": rel_path,
        "file_size": file_size,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "claim_count": claim_count,
        "expected_prefix": expected_prefix,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P1 Deterministic Step Output Verification (L0+ Anti-Skip Guard)"
    )
    parser.add_argument("--step", type=int, required=True, help="Step number")
    parser.add_argument("--project-dir", type=str, required=True,
                        help="Project root directory")
    parser.add_argument("--research-type", type=str, default="undecided",
                        help="Research type for Phase 2 agent resolution")
    args = parser.parse_args()

    result = verify_step_output(
        args.step,
        os.path.abspath(args.project_dir),
        args.research_type,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as e:
        error_output = {
            "valid": False,
            "error": str(e),
            "errors": [f"Fatal error in verify_step_output: {e}"],
        }
        print(json.dumps(error_output, indent=2, ensure_ascii=False))
        sys.exit(0)  # P1: never block
