#!/usr/bin/env python3
"""Knowledge-Based Self-Improvement (KBSI) SOT Manager.

P1 Deterministic Script — manages the self-improvement lifecycle:
  - SOT (state.json) CRUD with atomic writes
  - Insight registration, application, rejection
  - AGENTS.md §11 marker-based deterministic append
  - CLAUDE.md KBSI marker-based deterministic sync
  - Effectiveness measurement via KI error-pattern counting
  - Queued changes for end-of-run application

IMPORTANT: This script does NOT import from _context_lib.py and does NOT
reference system SOT filenames to avoid triggering
_check_sot_write_safety() false positives (same as checklist_manager.py R6).

The self-improvement SOT is at self-improvement-logs/state.json — deliberately
separate from thesis SOT (session.json) and system SOT (state.yaml).

Usage:
  python3 self_improve_manager.py --register --si-dir <dir> --title <t> --condition <c> --rule <r> --rationale <rat> --type <SAFE|STRUCTURAL> [--error-type <et>]
  python3 self_improve_manager.py --apply --si-dir <dir> --id <SI-NNN>
  python3 self_improve_manager.py --reject --si-dir <dir> --id <SI-NNN> --reason <r>
  python3 self_improve_manager.py --status --si-dir <dir>
  python3 self_improve_manager.py --next-id --si-dir <dir>
  python3 self_improve_manager.py --compute-effectiveness --si-dir <dir> --id <SI-NNN> --ki-path <path>
  python3 self_improve_manager.py --apply-to-agents-md --si-dir <dir> --agents-md <path> --id <SI-NNN>
  python3 self_improve_manager.py --sync-claude-md --si-dir <dir> --claude-md <path>
  python3 self_improve_manager.py --validate-queued-changes --si-dir <dir>
  python3 self_improve_manager.py --queue-change --si-dir <dir> --target <path> --change-type <SAFE|STRUCTURAL> --description <desc>

Exit codes:
  0 — success (always for read-only operations)
  1 — validation/input error
  2 — permission denied (teammate SOT write)

Architecture:
  - Pure Python, stdlib only (no external dependencies)
  - Deterministic: same input → same output
  - P1 Compliance: zero heuristic inference, zero LLM
  - Independent from _context_lib.py (no import)
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SI_SOT_FILENAME = "state.json"
PENDING_DIR = "pending"
APPLIED_DIR = "applied"
QUEUED_DIR = "queued-changes"

# Valid insight statuses
VALID_STATUSES = {"pending", "applied", "rejected"}

# Valid insight types
VALID_TYPES = {"SAFE", "STRUCTURAL"}

# Valid change types for queued changes
VALID_CHANGE_TYPES = {"SAFE", "STRUCTURAL"}

# AGENTS.md protection markers
AGENTS_MD_START_MARKER = "<!-- SELF-IMPROVEMENT-START -->"
AGENTS_MD_END_MARKER = "<!-- SELF-IMPROVEMENT-END -->"

# CLAUDE.md protection markers
CLAUDE_MD_START_MARKER = "<!-- KBSI-START -->"
CLAUDE_MD_END_MARKER = "<!-- KBSI-END -->"

# Immutable boundary keywords — P1 deterministic detection.
# If any of these appear in an insight's condition or rule text,
# auto-classify as STRUCTURAL regardless of LLM classification.
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

# Error types (aligned with _context_lib.py _classify_error_patterns)
VALID_ERROR_TYPES = {
    "file_not_found", "edit_mismatch", "dependency",
    "syntax_error", "type_error", "runtime_error",
    "test_failure", "hook_failure", "sot_corruption",
    "timeout", "permission_denied", "unknown",
}

# Maximum insights in AGENTS.md §11 before warning
MAX_INSIGHTS_WARN = 50


# ---------------------------------------------------------------------------
# SOT Schema
# ---------------------------------------------------------------------------

def _validate_sot(data: dict) -> List[str]:
    """Validate self-improvement state.json schema. Returns list of errors.

    Validation rules (SS1-SS8):
      SS1: Root must be a dict
      SS2: Required keys present (version, insights, total_applied, total_rejected)
      SS3: version must be a string
      SS4: insights must be a dict
      SS5: Each insight must have required fields (id, title, condition, rule, rationale, type, status)
      SS6: Insight type must be SAFE or STRUCTURAL
      SS7: Insight status must be pending, applied, or rejected
      SS8: total_applied and total_rejected must be non-negative integers
    """
    errors: List[str] = []

    # SS1
    if not isinstance(data, dict):
        return ["SS1: Root must be a dict"]

    # SS2
    required_keys = {"version", "insights", "total_applied", "total_rejected"}
    missing = required_keys - set(data.keys())
    if missing:
        errors.append(f"SS2: Missing required keys: {sorted(missing)}")

    # SS3
    version = data.get("version")
    if version is not None and not isinstance(version, str):
        errors.append(f"SS3: version must be a string, got {type(version).__name__}")

    # SS4
    insights = data.get("insights")
    if insights is not None:
        if not isinstance(insights, dict):
            errors.append("SS4: insights must be a dict")
        else:
            # SS5, SS6, SS7
            insight_required = {"id", "title", "condition", "rule", "rationale", "type", "status"}
            for insight_id, insight in insights.items():
                if not isinstance(insight, dict):
                    errors.append(f"SS5: insights['{insight_id}'] must be a dict")
                    continue
                missing_fields = insight_required - set(insight.keys())
                if missing_fields:
                    errors.append(f"SS5: insights['{insight_id}'] missing: {sorted(missing_fields)}")
                # SS6
                itype = insight.get("type")
                if itype is not None and itype not in VALID_TYPES:
                    errors.append(f"SS6: insights['{insight_id}'].type invalid: '{itype}'")
                # SS7
                istatus = insight.get("status")
                if istatus is not None and istatus not in VALID_STATUSES:
                    errors.append(f"SS7: insights['{insight_id}'].status invalid: '{istatus}'")

    # SS8
    for counter_field in ("total_applied", "total_rejected"):
        val = data.get(counter_field)
        if val is not None:
            if not isinstance(val, int) or val < 0:
                errors.append(f"SS8: {counter_field} must be non-negative int, got {val}")

    return errors


# ---------------------------------------------------------------------------
# Atomic I/O
# ---------------------------------------------------------------------------

def _atomic_write_json(filepath: Path, data: dict) -> None:
    """Write JSON atomically using temp file + rename pattern."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(filepath.parent),
        prefix=f".{filepath.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(filepath))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _atomic_write_text(filepath: Path, content: str) -> None:
    """Write text atomically using temp file + rename pattern."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(filepath.parent),
        prefix=f".{filepath.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(filepath))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# SOT Read/Write
# ---------------------------------------------------------------------------

def _ensure_state(si_dir: Path) -> dict:
    """Auto-create state.json on first CLI call if missing (lazy init).

    Returns parsed state dict.
    """
    si_dir = Path(si_dir)
    sot_path = si_dir / SI_SOT_FILENAME

    if sot_path.exists():
        with open(sot_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        errors = _validate_sot(data)
        if errors:
            raise ValueError(
                f"KBSI SOT validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        return data

    # Create initial SOT
    initial: dict = {
        "version": "1.0",
        "insights": {},
        "total_applied": 0,
        "total_rejected": 0,
        "queued_changes": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _atomic_write_json(sot_path, initial)
    return initial


def _read_state(si_dir: Path) -> dict:
    """Read and validate KBSI SOT. Returns parsed dict."""
    si_dir = Path(si_dir)
    sot_path = si_dir / SI_SOT_FILENAME

    if not sot_path.exists():
        raise FileNotFoundError(f"KBSI SOT not found: {sot_path}")

    with open(sot_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = _validate_sot(data)
    if errors:
        raise ValueError(
            f"KBSI SOT validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    return data


def _write_state(si_dir: Path, data: dict) -> None:
    """Validate and atomically write KBSI SOT.

    Authorization: teammates cannot write (defense-in-depth).
    """
    is_teammate = os.environ.get("CLAUDE_AGENT_TEAMS_TEAMMATE", "") != ""
    if is_teammate:
        raise PermissionError(
            "KBSI SOT write denied: teammates cannot write self-improvement SOT directly."
        )

    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    errors = _validate_sot(data)
    if errors:
        raise ValueError(
            f"Cannot write invalid KBSI SOT:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    _atomic_write_json(Path(si_dir) / SI_SOT_FILENAME, data)


# ---------------------------------------------------------------------------
# ID Generation
# ---------------------------------------------------------------------------

def _next_id(state: dict) -> str:
    """Generate next insight ID: SI-NNN (P1 deterministic: max existing + 1)."""
    insights = state.get("insights", {})
    if not insights:
        return "SI-001"

    max_num = 0
    for key in insights:
        match = re.match(r"SI-(\d+)", key)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    return f"SI-{max_num + 1:03d}"


# ---------------------------------------------------------------------------
# Immutable Boundary Detection (P1)
# ---------------------------------------------------------------------------

def _detect_immutable_keywords(text: str) -> List[str]:
    """P1: Detect immutable boundary keywords in text.

    Returns list of matched keywords. If any match, insight must be STRUCTURAL.
    """
    text_lower = text.lower()
    matched: List[str] = []
    for keyword in IMMUTABLE_KEYWORDS:
        if keyword.lower() in text_lower:
            matched.append(keyword)
    return matched


def _detect_hub_file_references(text: str) -> List[str]:
    """P1: Detect hub file references in text.

    Returns list of matched hub files. If any match, insight must be STRUCTURAL.
    """
    matched: List[str] = []
    for hub_file in HUB_FILES:
        if hub_file in text:
            matched.append(hub_file)
    return matched


# ---------------------------------------------------------------------------
# Core Operations
# ---------------------------------------------------------------------------

def register_insight(
    si_dir: Path,
    title: str,
    condition: str,
    rule: str,
    rationale: str,
    insight_type: str,
    error_type: Optional[str] = None,
    source_step: Optional[int] = None,
    source_session: Optional[str] = None,
) -> Tuple[str, dict]:
    """Register a new insight in SOT.

    P1 Safety: Auto-upgrades SAFE → STRUCTURAL if immutable keywords or
    hub file references are detected.

    Returns (insight_id, updated_state).
    """
    state = _ensure_state(si_dir)

    insight_id = _next_id(state)

    # P1: Auto-classify as STRUCTURAL if immutable boundaries detected
    combined_text = f"{condition} {rule} {rationale}"
    immutable_matches = _detect_immutable_keywords(combined_text)
    hub_matches = _detect_hub_file_references(combined_text)

    auto_structural = bool(immutable_matches or hub_matches)
    final_type = "STRUCTURAL" if auto_structural else insight_type

    # Validate error_type if provided
    if error_type and error_type not in VALID_ERROR_TYPES:
        raise ValueError(f"Invalid error_type: '{error_type}'. Valid: {sorted(VALID_ERROR_TYPES)}")

    now = datetime.now(timezone.utc).isoformat()

    insight: Dict[str, Any] = {
        "id": insight_id,
        "title": title,
        "condition": condition,
        "rule": rule,
        "rationale": rationale,
        "type": final_type,
        "status": "pending",
        "created_at": now,
        "applied_at": None,
        "rejected_at": None,
        "rejection_reason": None,
        "error_type": error_type,
        "source_step": source_step,
        "source_session": source_session,
        "auto_structural": auto_structural,
        "immutable_matches": immutable_matches if immutable_matches else None,
        "hub_matches": hub_matches if hub_matches else None,
        "effectiveness": None,
    }

    state["insights"][insight_id] = insight

    # Also write to pending/ for review
    pending_dir = Path(si_dir) / PENDING_DIR
    pending_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(pending_dir / f"{insight_id}.json", insight)

    _write_state(si_dir, state)
    return insight_id, state


def apply_insight(si_dir: Path, insight_id: str) -> dict:
    """Mark insight as applied in SOT. Move from pending/ to applied/."""
    state = _read_state(si_dir)

    if insight_id not in state["insights"]:
        raise ValueError(f"Insight not found: {insight_id}")

    insight = state["insights"][insight_id]
    if insight["status"] != "pending":
        raise ValueError(f"Cannot apply {insight_id}: status is '{insight['status']}', expected 'pending'")

    now = datetime.now(timezone.utc).isoformat()
    insight["status"] = "applied"
    insight["applied_at"] = now
    state["total_applied"] += 1

    # Move file: pending/ → applied/
    si_dir = Path(si_dir)
    pending_file = si_dir / PENDING_DIR / f"{insight_id}.json"
    applied_dir = si_dir / APPLIED_DIR
    applied_dir.mkdir(parents=True, exist_ok=True)

    _atomic_write_json(applied_dir / f"{insight_id}.json", insight)
    if pending_file.exists():
        pending_file.unlink()

    _write_state(si_dir, state)
    return state


def reject_insight(si_dir: Path, insight_id: str, reason: str) -> dict:
    """Mark insight as rejected in SOT with reason."""
    state = _read_state(si_dir)

    if insight_id not in state["insights"]:
        raise ValueError(f"Insight not found: {insight_id}")

    insight = state["insights"][insight_id]
    if insight["status"] != "pending":
        raise ValueError(f"Cannot reject {insight_id}: status is '{insight['status']}', expected 'pending'")

    now = datetime.now(timezone.utc).isoformat()
    insight["status"] = "rejected"
    insight["rejected_at"] = now
    insight["rejection_reason"] = reason
    state["total_rejected"] += 1

    # Move file: pending/ → applied/ (archive even rejected ones)
    si_dir = Path(si_dir)
    pending_file = si_dir / PENDING_DIR / f"{insight_id}.json"
    applied_dir = si_dir / APPLIED_DIR
    applied_dir.mkdir(parents=True, exist_ok=True)

    _atomic_write_json(applied_dir / f"{insight_id}.json", insight)
    if pending_file.exists():
        pending_file.unlink()

    _write_state(si_dir, state)
    return state


# ---------------------------------------------------------------------------
# Effectiveness Measurement
# ---------------------------------------------------------------------------

def compute_effectiveness(
    si_dir: Path,
    insight_id: str,
    ki_path: str,
) -> Dict[str, Any]:
    """P1: Measure insight effectiveness by counting error_type in KI before/after.

    Reads knowledge-index.jsonl, filters sessions by timestamp relative to
    insight application date, counts error_type occurrences.

    Returns dict with before_count, after_count, delta, effectiveness_pct.
    """
    state = _read_state(si_dir)

    if insight_id not in state["insights"]:
        raise ValueError(f"Insight not found: {insight_id}")

    insight = state["insights"][insight_id]
    if insight["status"] != "applied":
        return {"error": f"{insight_id} not applied yet — cannot measure effectiveness"}

    error_type = insight.get("error_type")
    if not error_type:
        return {"error": f"{insight_id} has no error_type — cannot measure effectiveness"}

    applied_at = insight.get("applied_at")
    if not applied_at:
        return {"error": f"{insight_id} has no applied_at timestamp"}

    # Parse KI (knowledge-index.jsonl)
    before_count = 0
    after_count = 0

    ki_file = Path(ki_path)
    if not ki_file.exists():
        return {
            "error": f"KI file not found: {ki_path}",
            "before_count": 0,
            "after_count": 0,
        }

    with open(ki_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Check if this session has the target error_type
            error_patterns = entry.get("error_patterns", [])
            has_error = False
            for pattern in error_patterns:
                if isinstance(pattern, dict):
                    if pattern.get("type") == error_type or pattern.get("error_type") == error_type:
                        has_error = True
                        break
                elif isinstance(pattern, str) and error_type in pattern:
                    has_error = True
                    break

            if not has_error:
                continue

            # Compare timestamps
            session_ts = entry.get("timestamp") or entry.get("created_at") or ""
            if session_ts and session_ts < applied_at:
                before_count += 1
            elif session_ts:
                after_count += 1

    # Calculate effectiveness
    if before_count == 0:
        effectiveness_pct = None  # Cannot measure without baseline
    else:
        # Reduction percentage: 100% = error completely eliminated
        reduction = before_count - after_count
        effectiveness_pct = round((reduction / before_count) * 100, 1)

    result = {
        "insight_id": insight_id,
        "error_type": error_type,
        "applied_at": applied_at,
        "before_count": before_count,
        "after_count": after_count,
        "effectiveness_pct": effectiveness_pct,
    }

    # Update SOT with effectiveness
    insight["effectiveness"] = result
    _write_state(si_dir, state)

    return result


# ---------------------------------------------------------------------------
# AGENTS.md Marker-Based Append (P1)
# ---------------------------------------------------------------------------

def apply_to_agents_md(agents_md_path: str, insight: dict) -> Dict[str, Any]:
    """P1: Append insight to AGENTS.md §11 within markers.

    Safety guarantees:
      0. Teammate write blocked (defense-in-depth — Hub file protection)
      1. Read AGENTS.md
      2. Find SELF-IMPROVEMENT-START marker
      3. Verify §1-§10 byte preservation (before_marker bytes unchanged)
      4. Format insight as markdown rule
      5. Insert before END marker
      6. Atomic write

    Returns dict with status, byte verification result.
    """
    # Defense-in-depth: teammates must not modify Hub files
    is_teammate = os.environ.get("CLAUDE_AGENT_TEAMS_TEAMMATE", "") != ""
    if is_teammate:
        return {"status": "FAIL", "error": "Hub file write denied: teammates cannot modify AGENTS.md"}

    path = Path(agents_md_path)
    if not path.exists():
        return {"status": "FAIL", "error": f"AGENTS.md not found: {agents_md_path}"}

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find markers
    start_idx = content.find(AGENTS_MD_START_MARKER)
    end_idx = content.find(AGENTS_MD_END_MARKER)

    if start_idx == -1:
        return {"status": "FAIL", "error": "SELF-IMPROVEMENT-START marker not found in AGENTS.md"}
    if end_idx == -1:
        return {"status": "FAIL", "error": "SELF-IMPROVEMENT-END marker not found in AGENTS.md"}
    if start_idx >= end_idx:
        return {"status": "FAIL", "error": "START marker must appear before END marker"}

    # §1-§10 byte preservation check
    before_marker = content[:start_idx]
    before_marker_bytes = len(before_marker.encode("utf-8"))

    # Format the insight as markdown
    insight_id = insight.get("id", "SI-???")
    title = insight.get("title", "Untitled")
    condition = insight.get("condition", "")
    rule = insight.get("rule", "")
    rationale = insight.get("rationale", "")
    error_type = insight.get("error_type", "")
    applied_at = insight.get("applied_at", "")

    entry = (
        f"\n#### {insight_id}: {title}\n"
        f"- **Condition**: {condition}\n"
        f"- **Rule**: {rule}\n"
        f"- **Rationale**: {rationale}\n"
    )
    if error_type:
        entry += f"- **Error Type**: {error_type}\n"
    if applied_at:
        entry += f"- **Applied**: {applied_at}\n"

    # Insert before END marker
    after_start = content[start_idx + len(AGENTS_MD_START_MARKER):end_idx]
    new_section = after_start.rstrip("\n") + "\n" + entry + "\n"

    new_content = (
        content[:start_idx + len(AGENTS_MD_START_MARKER)]
        + new_section
        + content[end_idx:]
    )

    # Verify §1-§10 preservation after modification
    new_before_marker = new_content[:start_idx]
    new_before_bytes = len(new_before_marker.encode("utf-8"))

    if before_marker_bytes != new_before_bytes:
        return {
            "status": "FAIL",
            "error": f"§1-§10 byte mismatch: {before_marker_bytes} → {new_before_bytes}",
        }

    # Atomic write
    _atomic_write_text(path, new_content)

    return {
        "status": "PASS",
        "insight_id": insight_id,
        "before_marker_bytes": before_marker_bytes,
        "section_size": len(new_section),
    }


# ---------------------------------------------------------------------------
# CLAUDE.md Marker-Based Sync (P1)
# ---------------------------------------------------------------------------

def sync_claude_md(si_dir: Path, claude_md_path: str) -> Dict[str, Any]:
    """P1: Sync KBSI summary to CLAUDE.md within markers.

    Reads state.json, generates a summary of applied insights,
    replaces content between KBSI-START and KBSI-END markers.

    Safety: content outside markers is byte-preserved.
    Teammate blocked: defense-in-depth for Hub file protection.
    """
    # Defense-in-depth: teammates must not modify Hub files
    is_teammate = os.environ.get("CLAUDE_AGENT_TEAMS_TEAMMATE", "") != ""
    if is_teammate:
        return {"status": "FAIL", "error": "Hub file write denied: teammates cannot modify CLAUDE.md"}

    path = Path(claude_md_path)
    if not path.exists():
        return {"status": "FAIL", "error": f"CLAUDE.md not found: {claude_md_path}"}

    state = _read_state(si_dir)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    start_idx = content.find(CLAUDE_MD_START_MARKER)
    end_idx = content.find(CLAUDE_MD_END_MARKER)

    if start_idx == -1:
        return {"status": "FAIL", "error": "KBSI-START marker not found in CLAUDE.md"}
    if end_idx == -1:
        return {"status": "FAIL", "error": "KBSI-END marker not found in CLAUDE.md"}
    if start_idx >= end_idx:
        return {"status": "FAIL", "error": "START marker must appear before END marker"}

    # Content before and after markers — must be byte-preserved
    before_marker = content[:start_idx]
    after_marker = content[end_idx + len(CLAUDE_MD_END_MARKER):]
    before_bytes = len(before_marker.encode("utf-8"))
    after_bytes = len(after_marker.encode("utf-8"))

    # Generate summary
    applied_insights = {
        k: v for k, v in state.get("insights", {}).items()
        if v.get("status") == "applied"
    }
    total_applied = state.get("total_applied", 0)
    total_rejected = state.get("total_rejected", 0)
    pending_count = sum(
        1 for v in state.get("insights", {}).values()
        if v.get("status") == "pending"
    )

    summary_lines = [
        "",
        f"Active: {total_applied} applied, {pending_count} pending, {total_rejected} rejected.",
    ]

    if applied_insights:
        summary_lines.append("")
        # Show last 5 applied insights (most recent first)
        sorted_applied = sorted(
            applied_insights.items(),
            key=lambda x: x[1].get("applied_at", ""),
            reverse=True,
        )[:5]
        for insight_id, insight in sorted_applied:
            title = insight.get("title", "")
            summary_lines.append(f"- **{insight_id}**: {title}")

    summary_lines.append("")

    new_section = "\n".join(summary_lines)

    new_content = (
        before_marker
        + CLAUDE_MD_START_MARKER
        + new_section
        + CLAUDE_MD_END_MARKER
        + after_marker
    )

    # Verify byte preservation using computed indices (not find() — avoids
    # false match if new_section contains END marker text)
    new_before = new_content[:start_idx]
    end_marker_start = len(before_marker) + len(CLAUDE_MD_START_MARKER) + len(new_section)
    new_after = new_content[end_marker_start + len(CLAUDE_MD_END_MARKER):]
    if len(new_before.encode("utf-8")) != before_bytes:
        return {"status": "FAIL", "error": "Content before KBSI markers corrupted"}
    if len(new_after.encode("utf-8")) != after_bytes:
        return {"status": "FAIL", "error": "Content after KBSI markers corrupted"}

    _atomic_write_text(path, new_content)

    return {
        "status": "PASS",
        "applied_count": total_applied,
        "pending_count": pending_count,
        "rejected_count": total_rejected,
    }


# ---------------------------------------------------------------------------
# Queued Changes (Track 2)
# ---------------------------------------------------------------------------

def queue_change(
    si_dir: Path,
    target: str,
    change_type: str,
    description: str,
) -> dict:
    """Queue a component change for end-of-run application.

    Hook .py changes are queued (not applied immediately) to avoid
    mid-run instability. Agent .md changes are immediate after test.

    P1: Auto-upgrades SAFE → STRUCTURAL for _context_lib.py changes.
    """
    state = _ensure_state(si_dir)

    # P1: _context_lib.py is ALWAYS STRUCTURAL (57 dependents)
    if "_context_lib.py" in target:
        change_type = "STRUCTURAL"

    # Detect hub file references
    hub_matches = _detect_hub_file_references(target)
    if hub_matches:
        change_type = "STRUCTURAL"

    now = datetime.now(timezone.utc).isoformat()
    change_entry = {
        "target": target,
        "change_type": change_type,
        "description": description,
        "queued_at": now,
        "applied": False,
    }

    if "queued_changes" not in state:
        state["queued_changes"] = []

    state["queued_changes"].append(change_entry)

    # Also write to queued-changes/ directory
    queued_dir = Path(si_dir) / QUEUED_DIR
    queued_dir.mkdir(parents=True, exist_ok=True)
    change_idx = len(state["queued_changes"])
    _atomic_write_json(
        queued_dir / f"change-{change_idx:03d}.json",
        change_entry,
    )

    _write_state(si_dir, state)
    return state


def validate_queued_changes(si_dir: Path) -> Dict[str, Any]:
    """P1: Validate all queued changes before end-of-run application.

    Checks:
      - Target file exists
      - Change type is valid
      - STRUCTURAL changes flagged for user approval
    """
    state = _ensure_state(si_dir)
    queued = state.get("queued_changes", [])

    results: List[Dict[str, Any]] = []
    structural_count = 0
    safe_count = 0

    for i, change in enumerate(queued):
        if change.get("applied"):
            continue

        target = change.get("target", "")
        change_type = change.get("change_type", "")

        entry: Dict[str, Any] = {
            "index": i,
            "target": target,
            "change_type": change_type,
            "checks": [],
        }

        # Check target exists
        if target and os.path.exists(target):
            entry["checks"].append({"check": "target_exists", "status": "PASS"})
        elif target:
            entry["checks"].append({
                "check": "target_exists",
                "status": "WARN",
                "detail": f"Target not found: {target}",
            })

        # Check type validity
        if change_type in VALID_CHANGE_TYPES:
            entry["checks"].append({"check": "valid_type", "status": "PASS"})
        else:
            entry["checks"].append({
                "check": "valid_type",
                "status": "FAIL",
                "detail": f"Invalid type: {change_type}",
            })

        if change_type == "STRUCTURAL":
            structural_count += 1
            entry["requires_approval"] = True
        else:
            safe_count += 1
            entry["requires_approval"] = False

        results.append(entry)

    return {
        "total": len(results),
        "safe": safe_count,
        "structural": structural_count,
        "requires_user_approval": structural_count > 0,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def get_status(si_dir: Path) -> Dict[str, Any]:
    """Get KBSI system status summary."""
    state = _ensure_state(si_dir)

    insights = state.get("insights", {})
    by_status: Dict[str, int] = {"pending": 0, "applied": 0, "rejected": 0}
    by_type: Dict[str, int] = {"SAFE": 0, "STRUCTURAL": 0}
    error_types_seen: Dict[str, int] = {}

    for insight in insights.values():
        status = insight.get("status", "pending")
        by_status[status] = by_status.get(status, 0) + 1

        itype = insight.get("type", "SAFE")
        by_type[itype] = by_type.get(itype, 0) + 1

        et = insight.get("error_type")
        if et:
            error_types_seen[et] = error_types_seen.get(et, 0) + 1

    queued = state.get("queued_changes", [])
    queued_pending = sum(1 for q in queued if not q.get("applied"))

    return {
        "total_insights": len(insights),
        "by_status": by_status,
        "by_type": by_type,
        "error_types": error_types_seen,
        "queued_changes_pending": queued_pending,
        "version": state.get("version", "?"),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="KBSI Self-Improvement Manager (P1 deterministic)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--si-dir", required=True, help="Self-improvement logs directory")

    # Modes (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--register", action="store_true", help="Register new insight")
    group.add_argument("--apply", action="store_true", help="Apply insight")
    group.add_argument("--reject", action="store_true", help="Reject insight")
    group.add_argument("--status", action="store_true", help="Show status")
    group.add_argument("--next-id", action="store_true", help="Show next insight ID")
    group.add_argument("--compute-effectiveness", action="store_true", help="Measure effectiveness")
    group.add_argument("--apply-to-agents-md", action="store_true", help="Append insight to AGENTS.md")
    group.add_argument("--sync-claude-md", action="store_true", help="Sync KBSI summary to CLAUDE.md")
    group.add_argument("--validate-queued-changes", action="store_true", help="Validate queued changes")
    group.add_argument("--queue-change", action="store_true", help="Queue component change")

    # Register parameters
    parser.add_argument("--title", help="Insight title")
    parser.add_argument("--condition", help="When this rule applies")
    parser.add_argument("--rule", help="What to do")
    parser.add_argument("--rationale", help="Why this rule exists")
    parser.add_argument("--type", dest="insight_type", choices=["SAFE", "STRUCTURAL"], help="Change type")
    parser.add_argument("--error-type", help="Associated error type")
    parser.add_argument("--source-step", type=int, help="Thesis step where insight originated")
    parser.add_argument("--source-session", help="Session ID where insight originated")

    # Apply/Reject parameters
    parser.add_argument("--id", dest="insight_id", help="Insight ID (SI-NNN)")
    parser.add_argument("--reason", help="Rejection reason")

    # Effectiveness parameters
    parser.add_argument("--ki-path", help="Path to knowledge-index.jsonl")

    # AGENTS.md / CLAUDE.md parameters
    parser.add_argument("--agents-md", help="Path to AGENTS.md")
    parser.add_argument("--claude-md", help="Path to CLAUDE.md")

    # Queue-change parameters
    parser.add_argument("--target", help="Target file for queued change")
    parser.add_argument("--change-type", choices=["SAFE", "STRUCTURAL"], help="Change type")
    parser.add_argument("--description", help="Change description")

    return parser


def main() -> int:
    """Main entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    si_dir = Path(args.si_dir)

    try:
        if args.register:
            return _cli_register(args, si_dir)
        elif args.apply:
            return _cli_apply(args, si_dir)
        elif args.reject:
            return _cli_reject(args, si_dir)
        elif args.status:
            return _cli_status(si_dir)
        elif args.next_id:
            return _cli_next_id(si_dir)
        elif args.compute_effectiveness:
            return _cli_compute_effectiveness(args, si_dir)
        elif args.apply_to_agents_md:
            return _cli_apply_to_agents_md(args, si_dir)
        elif args.sync_claude_md:
            return _cli_sync_claude_md(args, si_dir)
        elif args.validate_queued_changes:
            return _cli_validate_queued_changes(si_dir)
        elif args.queue_change:
            return _cli_queue_change(args, si_dir)
    except PermissionError as e:
        print(f"PERMISSION DENIED: {e}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 0


# ---------------------------------------------------------------------------
# CLI Handlers
# ---------------------------------------------------------------------------

def _cli_register(args: argparse.Namespace, si_dir: Path) -> int:
    """Handle --register command."""
    required = ["title", "condition", "rule", "rationale", "insight_type"]
    for field in required:
        if not getattr(args, field, None):
            print(f"ERROR: --register requires --{field.replace('_', '-')}", file=sys.stderr)
            return 1

    insight_id, state = register_insight(
        si_dir=si_dir,
        title=args.title,
        condition=args.condition,
        rule=args.rule,
        rationale=args.rationale,
        insight_type=args.insight_type,
        error_type=args.error_type,
        source_step=args.source_step,
        source_session=args.source_session,
    )

    output = {
        "insight_id": insight_id,
        "type": state["insights"][insight_id]["type"],
        "auto_structural": state["insights"][insight_id].get("auto_structural", False),
        "status": "registered",
    }
    print(json.dumps(output, indent=2))
    return 0


def _cli_apply(args: argparse.Namespace, si_dir: Path) -> int:
    """Handle --apply command."""
    if not args.insight_id:
        print("ERROR: --apply requires --id SI-NNN", file=sys.stderr)
        return 1

    state = apply_insight(si_dir, args.insight_id)
    print(json.dumps({"insight_id": args.insight_id, "status": "applied"}, indent=2))
    return 0


def _cli_reject(args: argparse.Namespace, si_dir: Path) -> int:
    """Handle --reject command."""
    if not args.insight_id:
        print("ERROR: --reject requires --id SI-NNN", file=sys.stderr)
        return 1
    if not args.reason:
        print("ERROR: --reject requires --reason", file=sys.stderr)
        return 1

    state = reject_insight(si_dir, args.insight_id, args.reason)
    print(json.dumps({"insight_id": args.insight_id, "status": "rejected"}, indent=2))
    return 0


def _cli_status(si_dir: Path) -> int:
    """Handle --status command."""
    status = get_status(si_dir)
    print(json.dumps(status, indent=2))
    return 0


def _cli_next_id(si_dir: Path) -> int:
    """Handle --next-id command."""
    state = _ensure_state(si_dir)
    next_id = _next_id(state)
    print(json.dumps({"next_id": next_id}))
    return 0


def _cli_compute_effectiveness(args: argparse.Namespace, si_dir: Path) -> int:
    """Handle --compute-effectiveness command."""
    if not args.insight_id:
        print("ERROR: --compute-effectiveness requires --id SI-NNN", file=sys.stderr)
        return 1
    if not args.ki_path:
        print("ERROR: --compute-effectiveness requires --ki-path", file=sys.stderr)
        return 1

    result = compute_effectiveness(si_dir, args.insight_id, args.ki_path)
    print(json.dumps(result, indent=2))
    return 0


def _cli_apply_to_agents_md(args: argparse.Namespace, si_dir: Path) -> int:
    """Handle --apply-to-agents-md command."""
    if not args.insight_id:
        print("ERROR: --apply-to-agents-md requires --id SI-NNN", file=sys.stderr)
        return 1
    if not args.agents_md:
        print("ERROR: --apply-to-agents-md requires --agents-md PATH", file=sys.stderr)
        return 1

    state = _read_state(si_dir)
    if args.insight_id not in state["insights"]:
        print(f"ERROR: Insight not found: {args.insight_id}", file=sys.stderr)
        return 1

    insight = state["insights"][args.insight_id]
    result = apply_to_agents_md(args.agents_md, insight)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


def _cli_sync_claude_md(args: argparse.Namespace, si_dir: Path) -> int:
    """Handle --sync-claude-md command."""
    if not args.claude_md:
        print("ERROR: --sync-claude-md requires --claude-md PATH", file=sys.stderr)
        return 1

    result = sync_claude_md(si_dir, args.claude_md)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


def _cli_validate_queued_changes(si_dir: Path) -> int:
    """Handle --validate-queued-changes command."""
    result = validate_queued_changes(si_dir)
    print(json.dumps(result, indent=2))
    return 0


def _cli_queue_change(args: argparse.Namespace, si_dir: Path) -> int:
    """Handle --queue-change command."""
    if not args.target:
        print("ERROR: --queue-change requires --target PATH", file=sys.stderr)
        return 1
    if not args.change_type:
        print("ERROR: --queue-change requires --change-type SAFE|STRUCTURAL", file=sys.stderr)
        return 1
    if not args.description:
        print("ERROR: --queue-change requires --description TEXT", file=sys.stderr)
        return 1

    state = queue_change(si_dir, args.target, args.change_type, args.description)
    print(json.dumps({"status": "queued", "target": args.target, "type": args.change_type}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
