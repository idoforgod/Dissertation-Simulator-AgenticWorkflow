#!/usr/bin/env python3
"""Self-Improvement Insight P1 Validation — validate_self_improvement.py

Deterministic validation for KBSI (Knowledge-Based Self-Improvement) insights.
Verifies that an insight meets quality and safety criteria before application:

  SI-1: Rule format validation (required fields with non-empty values)
  SI-2: Immutable boundary keyword detection → auto-STRUCTURAL override
  SI-3: Hub file change detection → auto-STRUCTURAL override
  SI-4: §11 marker boundary verification in AGENTS.md
  SI-5: Bigram duplicate detection against existing applied insights
  SI-6: ID uniqueness verification against SOT

This is the P1 validation layer of the KBSI P1 Sandwich:
  Phase A: P1 fact extraction (this script) → Phase B: LLM analysis →
  Phase C: P1 validation (this script) → Phase D: P1 application (self_improve_manager.py)

Usage:
    # Validate a single pending insight file
    python3 validate_self_improvement.py \\
      --insight-file self-improvement-logs/pending/SI-001.json \\
      --si-dir self-improvement-logs

    # Validate AGENTS.md §11 markers only
    python3 validate_self_improvement.py \\
      --check-markers --agents-md AGENTS.md

    # Validate all pending insights
    python3 validate_self_improvement.py \\
      --validate-all --si-dir self-improvement-logs

Output: JSON to stdout
    {
      "insight_id": "SI-001",
      "results": [
        {"check": "SI-1", "status": "PASS", "detail": "..."},
        {"check": "SI-2", "status": "WARN", "detail": "auto-STRUCTURAL: ..."},
        ...
      ],
      "passed": true,
      "warnings": []
    }

Exit codes:
    0 — always (non-blocking, P1 compliant)

Architecture:
    - Pure Python, stdlib only (no external dependencies)
    - Deterministic: same input → same output, every time
    - P1 Compliance: zero heuristic inference, zero LLM
    - SOT Compliance: read-only (reads insight files and SOT)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Constants (duplicated from self_improve_manager.py — P1 independence)
# ---------------------------------------------------------------------------

SI_SOT_FILENAME = "state.json"

# AGENTS.md protection markers
AGENTS_MD_START_MARKER = "<!-- SELF-IMPROVEMENT-START -->"
AGENTS_MD_END_MARKER = "<!-- SELF-IMPROVEMENT-END -->"

# Required insight fields
REQUIRED_FIELDS = {"id", "title", "condition", "rule", "rationale", "type", "status"}

# Valid types and statuses
VALID_TYPES = {"SAFE", "STRUCTURAL"}
VALID_STATUSES = {"pending", "applied", "rejected"}

# Immutable boundary keywords — must match self_improve_manager.py
IMMUTABLE_KEYWORDS = [
    "absolute standard",
    "절대 기준",
    "p1 sandwich",
    "sot single-writer",
    "5-layer quality",
    "safety hook exit 2",
    "dna inheritance",
    "hub-spoke",
    "rlm pattern",
    "3-stage workflow",
    "_context_lib.py",
    "soul.md",
    "guard_sot_write",
]

# Hub files — changes to these are always STRUCTURAL
HUB_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "soul.md",
    "_context_lib.py",
]

# SI-5: Bigram duplicate detection threshold.
# If an insight shares ≥ this many bigrams with an existing applied insight,
# it's flagged as a potential duplicate.
SI5_MIN_BIGRAM_OVERLAP = 5

# Stopwords for bigram extraction (academic/generic terms)
_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "that", "this", "with", "from", "have", "been",
    "were", "more", "than", "both", "each", "such", "when", "then",
    "them", "they", "their", "these", "those", "while", "which",
    "would", "could", "should", "must", "will", "not", "are", "was",
    "has", "had", "does", "did", "but", "all", "any", "can",
    "into", "over", "also", "thus", "may", "use", "used", "using",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_bigrams(text: str) -> Set[Tuple[str, str]]:
    """Extract word bigrams from text, filtering stopwords.

    P1 Compliance: deterministic tokenization + frozenset filtering.
    """
    # Normalize: lowercase, split on non-word chars
    words = re.findall(r"[a-z]+", text.lower())
    # Filter stopwords
    filtered = [w for w in words if w not in _STOPWORDS and len(w) > 2]
    # Build bigrams
    bigrams: Set[Tuple[str, str]] = set()
    for i in range(len(filtered) - 1):
        bigrams.add((filtered[i], filtered[i + 1]))
    return bigrams


def _result(check: str, status: str, detail: str) -> Dict[str, str]:
    """Create a structured validation result."""
    return {"check": check, "status": status, "detail": detail}


# ---------------------------------------------------------------------------
# SI-1: Rule Format Validation
# ---------------------------------------------------------------------------

def _check_si1_format(insight: dict) -> List[Dict[str, str]]:
    """SI-1: Validate required fields are present and non-empty."""
    results: List[Dict[str, str]] = []

    missing = REQUIRED_FIELDS - set(insight.keys())
    if missing:
        results.append(_result("SI-1", "FAIL", f"Missing fields: {sorted(missing)}"))
        return results

    # Check non-empty
    empty_fields = []
    for field in REQUIRED_FIELDS:
        val = insight.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            empty_fields.append(field)

    if empty_fields:
        results.append(_result("SI-1", "FAIL", f"Empty fields: {sorted(empty_fields)}"))
    else:
        results.append(_result("SI-1", "PASS", "All required fields present and non-empty"))

    # Validate type
    itype = insight.get("type")
    if itype and itype not in VALID_TYPES:
        results.append(_result("SI-1", "FAIL", f"Invalid type: '{itype}', must be SAFE or STRUCTURAL"))

    # Validate status
    istatus = insight.get("status")
    if istatus and istatus not in VALID_STATUSES:
        results.append(_result("SI-1", "FAIL", f"Invalid status: '{istatus}'"))

    # Validate ID format
    insight_id = insight.get("id", "")
    if insight_id and not re.match(r"^SI-\d{3,}$", insight_id):
        results.append(_result("SI-1", "FAIL", f"Invalid ID format: '{insight_id}', expected SI-NNN"))

    return results


# ---------------------------------------------------------------------------
# SI-2: Immutable Boundary Detection
# ---------------------------------------------------------------------------

def _check_si2_immutable(insight: dict) -> List[Dict[str, str]]:
    """SI-2: Detect immutable boundary keywords → auto-STRUCTURAL."""
    combined_text = " ".join([
        insight.get("condition", ""),
        insight.get("rule", ""),
        insight.get("rationale", ""),
    ])
    text_lower = combined_text.lower()

    matched = [kw for kw in IMMUTABLE_KEYWORDS if kw.lower() in text_lower]

    if matched:
        current_type = insight.get("type", "SAFE")
        if current_type != "STRUCTURAL":
            return [_result(
                "SI-2", "WARN",
                f"Immutable boundary keywords detected: {matched}. "
                f"Type should be STRUCTURAL (currently '{current_type}'). "
                f"P1 auto-upgrade will apply.",
            )]
        else:
            return [_result(
                "SI-2", "PASS",
                f"Immutable keywords detected ({len(matched)}), correctly typed STRUCTURAL",
            )]
    return [_result("SI-2", "PASS", "No immutable boundary keywords detected")]


# ---------------------------------------------------------------------------
# SI-3: Hub File Detection
# ---------------------------------------------------------------------------

def _check_si3_hub_files(insight: dict) -> List[Dict[str, str]]:
    """SI-3: Detect hub file references → auto-STRUCTURAL."""
    combined_text = " ".join([
        insight.get("condition", ""),
        insight.get("rule", ""),
        insight.get("rationale", ""),
    ])

    matched = [hf for hf in HUB_FILES if hf in combined_text]

    if matched:
        current_type = insight.get("type", "SAFE")
        if current_type != "STRUCTURAL":
            return [_result(
                "SI-3", "WARN",
                f"Hub file references detected: {matched}. "
                f"Type should be STRUCTURAL (currently '{current_type}'). "
                f"P1 auto-upgrade will apply.",
            )]
        else:
            return [_result(
                "SI-3", "PASS",
                f"Hub file references detected ({len(matched)}), correctly typed STRUCTURAL",
            )]
    return [_result("SI-3", "PASS", "No hub file references detected")]


# ---------------------------------------------------------------------------
# SI-4: Marker Boundary Verification
# ---------------------------------------------------------------------------

def _check_si4_markers(agents_md_path: str) -> List[Dict[str, str]]:
    """SI-4: Verify §11 marker boundaries in AGENTS.md."""
    if not agents_md_path or not os.path.exists(agents_md_path):
        return [_result("SI-4", "SKIP", f"AGENTS.md not found: {agents_md_path}")]

    with open(agents_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    results: List[Dict[str, str]] = []

    start_idx = content.find(AGENTS_MD_START_MARKER)
    end_idx = content.find(AGENTS_MD_END_MARKER)

    if start_idx == -1:
        results.append(_result("SI-4", "FAIL", "SELF-IMPROVEMENT-START marker not found"))
        return results

    if end_idx == -1:
        results.append(_result("SI-4", "FAIL", "SELF-IMPROVEMENT-END marker not found"))
        return results

    if start_idx >= end_idx:
        results.append(_result("SI-4", "FAIL", "START marker must appear before END marker"))
        return results

    # Check that markers are on their own lines
    lines = content.splitlines()
    start_line = None
    end_line = None
    for i, line in enumerate(lines):
        if AGENTS_MD_START_MARKER in line:
            start_line = i + 1
        if AGENTS_MD_END_MARKER in line:
            end_line = i + 1

    # Section content size
    section_content = content[start_idx + len(AGENTS_MD_START_MARKER):end_idx]
    section_size = len(section_content.strip())

    results.append(_result(
        "SI-4", "PASS",
        f"Markers valid: START at line {start_line}, END at line {end_line}, "
        f"section size {section_size} chars",
    ))

    # Count existing insights in section
    insight_count = len(re.findall(r"####\s+SI-\d+", section_content))
    if insight_count > 0:
        results.append(_result(
            "SI-4", "INFO",
            f"{insight_count} insights currently in §11",
        ))

    return results


# ---------------------------------------------------------------------------
# SI-5: Bigram Duplicate Detection
# ---------------------------------------------------------------------------

def _check_si5_duplicates(
    insight: dict,
    si_dir: Optional[str] = None,
) -> List[Dict[str, str]]:
    """SI-5: Detect potential duplicates via bigram overlap with applied insights."""
    if not si_dir:
        return [_result("SI-5", "SKIP", "No si-dir provided for duplicate check")]

    sot_path = Path(si_dir) / SI_SOT_FILENAME
    if not sot_path.exists():
        return [_result("SI-5", "SKIP", "SOT not found, cannot check duplicates")]

    try:
        with open(sot_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, IOError):
        return [_result("SI-5", "SKIP", "Cannot read SOT")]

    applied_insights = {
        k: v for k, v in state.get("insights", {}).items()
        if v.get("status") == "applied"
    }

    if not applied_insights:
        return [_result("SI-5", "PASS", "No applied insights to check against")]

    # Extract bigrams from new insight
    new_text = " ".join([
        insight.get("condition", ""),
        insight.get("rule", ""),
    ])
    new_bigrams = _extract_bigrams(new_text)

    if not new_bigrams:
        return [_result("SI-5", "WARN", "No bigrams extracted from insight (too short?)")]

    # Compare against each applied insight
    duplicates: List[Dict[str, Any]] = []
    for existing_id, existing in applied_insights.items():
        if existing_id == insight.get("id"):
            continue  # Skip self

        existing_text = " ".join([
            existing.get("condition", ""),
            existing.get("rule", ""),
        ])
        existing_bigrams = _extract_bigrams(existing_text)

        overlap = new_bigrams & existing_bigrams
        if len(overlap) >= SI5_MIN_BIGRAM_OVERLAP:
            duplicates.append({
                "existing_id": existing_id,
                "overlap_count": len(overlap),
                "sample_bigrams": [f"{a} {b}" for a, b in list(overlap)[:3]],
            })

    if duplicates:
        dup_ids = [d["existing_id"] for d in duplicates]
        return [_result(
            "SI-5", "WARN",
            f"Potential duplicates: {dup_ids} "
            f"(≥{SI5_MIN_BIGRAM_OVERLAP} bigram overlap). "
            f"Review before applying.",
        )]

    return [_result("SI-5", "PASS", f"No duplicates found ({len(new_bigrams)} bigrams checked)")]


# ---------------------------------------------------------------------------
# SI-6: ID Uniqueness
# ---------------------------------------------------------------------------

def _check_si6_uniqueness(
    insight: dict,
    si_dir: Optional[str] = None,
) -> List[Dict[str, str]]:
    """SI-6: Verify insight ID is unique in SOT."""
    insight_id = insight.get("id")
    if not insight_id:
        return [_result("SI-6", "FAIL", "No insight ID provided")]

    if not si_dir:
        return [_result("SI-6", "SKIP", "No si-dir provided for uniqueness check")]

    sot_path = Path(si_dir) / SI_SOT_FILENAME
    if not sot_path.exists():
        return [_result("SI-6", "PASS", "SOT not found (new system), ID is unique")]

    try:
        with open(sot_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, IOError):
        return [_result("SI-6", "SKIP", "Cannot read SOT")]

    existing_ids = set(state.get("insights", {}).keys())
    if insight_id in existing_ids:
        existing_status = state["insights"][insight_id].get("status", "?")
        return [_result(
            "SI-6", "FAIL",
            f"ID '{insight_id}' already exists in SOT (status: {existing_status})",
        )]

    return [_result("SI-6", "PASS", f"ID '{insight_id}' is unique")]


# ---------------------------------------------------------------------------
# Main Validation
# ---------------------------------------------------------------------------

def validate_insight(
    insight: dict,
    si_dir: Optional[str] = None,
    agents_md_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all SI-1~SI-6 checks on an insight.

    Returns structured result dict with overall pass/fail.
    """
    all_results: List[Dict[str, str]] = []
    warnings: List[str] = []

    # SI-1: Format
    all_results.extend(_check_si1_format(insight))

    # SI-2: Immutable boundaries
    all_results.extend(_check_si2_immutable(insight))

    # SI-3: Hub files
    all_results.extend(_check_si3_hub_files(insight))

    # SI-4: Markers (only if agents_md_path provided)
    if agents_md_path:
        all_results.extend(_check_si4_markers(agents_md_path))

    # SI-5: Duplicates
    all_results.extend(_check_si5_duplicates(insight, si_dir))

    # SI-6: Uniqueness
    all_results.extend(_check_si6_uniqueness(insight, si_dir))

    # Aggregate
    passed = all(r["status"] != "FAIL" for r in all_results)
    warnings = [r["detail"] for r in all_results if r["status"] == "WARN"]

    return {
        "insight_id": insight.get("id", "?"),
        "results": all_results,
        "passed": passed,
        "warnings": warnings,
    }


def validate_all_pending(si_dir: str) -> Dict[str, Any]:
    """Validate all pending insights in si_dir/pending/."""
    pending_dir = Path(si_dir) / "pending"
    if not pending_dir.exists():
        return {"total": 0, "results": [], "all_passed": True}

    all_results: List[Dict[str, Any]] = []

    for f in sorted(pending_dir.glob("SI-*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                insight = json.load(fp)
            result = validate_insight(insight, si_dir=si_dir)
            all_results.append(result)
        except (json.JSONDecodeError, IOError) as e:
            all_results.append({
                "insight_id": f.stem,
                "results": [_result("SI-0", "FAIL", f"Cannot read file: {e}")],
                "passed": False,
                "warnings": [],
            })

    all_passed = all(r["passed"] for r in all_results)

    return {
        "total": len(all_results),
        "results": all_results,
        "all_passed": all_passed,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="KBSI Insight Validation (P1 deterministic, SI-1~SI-6)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--insight-file", help="Path to pending insight JSON file")
    group.add_argument("--check-markers", action="store_true", help="Check AGENTS.md markers only")
    group.add_argument("--validate-all", action="store_true", help="Validate all pending insights")

    parser.add_argument("--si-dir", help="Self-improvement logs directory")
    parser.add_argument("--agents-md", help="Path to AGENTS.md")

    return parser


def main() -> int:
    """Main entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.insight_file:
            return _cli_validate_file(args)
        elif args.check_markers:
            return _cli_check_markers(args)
        elif args.validate_all:
            return _cli_validate_all(args)
    except Exception as e:
        print(json.dumps({"error": str(e), "passed": False}))

    return 0


def _cli_validate_file(args: argparse.Namespace) -> int:
    """Validate a single insight file."""
    path = Path(args.insight_file)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {path}", "passed": False}))
        return 0  # P1: always exit 0

    with open(path, "r", encoding="utf-8") as f:
        insight = json.load(f)

    result = validate_insight(
        insight,
        si_dir=args.si_dir,
        agents_md_path=args.agents_md,
    )
    print(json.dumps(result, indent=2))
    return 0


def _cli_check_markers(args: argparse.Namespace) -> int:
    """Check AGENTS.md markers only."""
    if not args.agents_md:
        print(json.dumps({"error": "--check-markers requires --agents-md PATH", "passed": False}))
        return 0

    results = _check_si4_markers(args.agents_md)
    passed = all(r["status"] != "FAIL" for r in results)
    print(json.dumps({"results": results, "passed": passed}, indent=2))
    return 0


def _cli_validate_all(args: argparse.Namespace) -> int:
    """Validate all pending insights."""
    if not args.si_dir:
        print(json.dumps({"error": "--validate-all requires --si-dir PATH", "passed": False}))
        return 0

    result = validate_all_pending(args.si_dir)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
