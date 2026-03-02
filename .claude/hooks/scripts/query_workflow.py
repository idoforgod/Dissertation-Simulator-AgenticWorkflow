#!/usr/bin/env python3
"""
Workflow Observability Tool — query_workflow.py

Single entry point for querying workflow execution state.
NOT a Hook — manually invoked by Orchestrator or user during workflow execution.

Usage:
    python3 .claude/hooks/scripts/query_workflow.py --project-dir . --dashboard
    python3 .claude/hooks/scripts/query_workflow.py --project-dir . --weakest-step
    python3 .claude/hooks/scripts/query_workflow.py --project-dir . --retry-summary
    python3 .claude/hooks/scripts/query_workflow.py --project-dir . --blocked

Output: JSON to stdout

Modes:
    --dashboard      Overview: current step, pACS history, pending validations
    --weakest-step   Step with lowest pACS score and its weak dimension
    --retry-summary  Retry budget usage across all gates
    --blocked        Identify what's blocking progress (failed gates, missing files)

P1 Compliance: All data extraction is deterministic (regex + file-system checks).
    SOT schema validated via validate_sot_schema() before any query.
    PyYAML required for YAML parsing — setup_init.py guarantees availability.
    pACS score extraction uses min()-formula-first strategy (same as _context_lib.py).
    All file read errors reported as typed errors in JSON output.
SOT Compliance: Read-only — no file writes.
"""

import argparse
import glob
import json
import os
import re
import sys

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _context_lib import validate_sot_schema

# ---------------------------------------------------------------------------
# SOT discovery — D-7: must match _context_lib.py:SOT_FILENAMES
# ---------------------------------------------------------------------------
_SOT_FILENAMES = ("state.yaml", "state.yml", "state.json")

# ---------------------------------------------------------------------------
# pACS score extraction — context-aware, min()-formula-first strategy
# Same logic as _context_lib.py verify_pacs_arithmetic() to avoid hallucination.
# ---------------------------------------------------------------------------
# D-7: Must match _context_lib.py:_PACS_WITH_MIN_RE / _PACS_SIMPLE_RE
_PACS_MIN_FORMULA_RE = re.compile(
    r"pACS\s*=\s*min\s*\([^)]+\)\s*=\s*(\d{1,3})", re.IGNORECASE
)
_PACS_SIMPLE_RE = re.compile(
    r"pACS\s*=\s*(\d{1,3})\b", re.IGNORECASE
)
_WEAK_DIM_RE = re.compile(
    r"^[#*\s]*weak(?:est)?\s*dimension\s*[=:]\s*([FCL])",
    re.MULTILINE | re.IGNORECASE,
)


def _extract_pacs_score(content):
    """Extract pACS score from log content. Returns int or None.

    D-7: Patterns aligned with _context_lib.py:_PACS_WITH_MIN_RE/_PACS_SIMPLE_RE.
    Strategy:
      1. Prefer explicit min() formula (e.g., "pACS = min(F,C,L) = 75")
      2. Fallback to "pACS = N" if exactly 1 match (= separator only, no colon)
      3. Return None if ambiguous (0 or multiple matches without min formula)
    """
    min_match = _PACS_MIN_FORMULA_RE.search(content)
    if min_match:
        score = int(min_match.group(1))
        # Range validation: pACS must be 0-100 (D-7: matches verify_pacs_arithmetic)
        return score if 0 <= score <= 100 else None
    simple_matches = _PACS_SIMPLE_RE.findall(content)
    if len(simple_matches) == 1:
        score = int(simple_matches[0])
        return score if 0 <= score <= 100 else None
    return None  # Ambiguous — refuse to guess


def _extract_weak_dimension(content):
    """Extract weak dimension from log content. Returns 'F', 'C', 'L', or None.

    Only matches explicit 'Weak dimension: X' patterns at heading level
    to avoid false positives from body text.
    """
    m = _WEAK_DIM_RE.search(content)
    # .upper() normalizes case — IGNORECASE makes [FCL] match lowercase,
    # but downstream S7c expects uppercase ("F","C","L") only
    return m.group(1).upper() if m else None


def _read_file_safe(path):
    """Read file content with typed error reporting. Returns (content, error_dict).

    P1 Compliance: Never returns silent None — always either content or error.
    """
    if not os.path.isfile(path):
        return None, {"type": "file_not_found", "path": path}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), None
    except PermissionError:
        return None, {"type": "permission_denied", "path": path}
    except UnicodeDecodeError:
        return None, {"type": "encoding_error", "path": path}
    except OSError as e:
        return None, {"type": "os_error", "path": path, "detail": str(e)}


def _find_sot(project_dir):
    """Find and parse the SOT file. Returns (data, path, error).

    P1 Compliance:
      - PyYAML required (no fallback that truncates nested values).
      - Parse errors reported as typed errors, never silently swallowed.
    """
    for name in _SOT_FILENAMES:
        p = os.path.join(project_dir, name)
        if not os.path.isfile(p):
            continue
        try:
            if name.endswith(".json"):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    return None, p, f"SOT {name} parsed but is not a dict (got {type(data).__name__})"
                return data, p, None
            else:
                import yaml
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data is None:
                    data = {}
                if not isinstance(data, dict):
                    return None, p, f"SOT {name} parsed but is not a dict (got {type(data).__name__})"
                return data, p, None
        except ImportError:
            return None, p, "PyYAML not installed — run: pip install pyyaml (setup_init.py should have caught this)"
        except json.JSONDecodeError as e:
            return None, p, f"SOT {name} JSON parse error: {e}"
        except Exception as e:
            return None, p, f"SOT {name} parse error: {type(e).__name__}: {e}"
    return None, None, "No SOT file found (state.yaml/state.yml/state.json)"


# ---------------------------------------------------------------------------
# Mode: --dashboard
# ---------------------------------------------------------------------------
def _dashboard(project_dir, sot):
    """Overview: current step, pACS history, pending validations."""
    current_step = sot.get("current_step", 0)
    total_steps = sot.get("total_steps", "?")
    workflow_status = sot.get("workflow_status", "unknown")

    # Collect pACS history with typed errors
    pacs_history = {}
    pacs_errors = []
    pacs_dir = os.path.join(project_dir, "pacs-logs")
    if os.path.isdir(pacs_dir):
        for f in sorted(glob.glob(os.path.join(pacs_dir, "step-*-pacs.md"))):
            m = re.search(r"step-(\d+)-pacs\.md$", f)
            if not m:
                continue
            step_num = int(m.group(1))
            content, err = _read_file_safe(f)
            if err:
                pacs_errors.append(err)
                continue
            score = _extract_pacs_score(content)
            if score is not None:
                pacs_history[f"step-{step_num}"] = score

    # Check pending validations
    pending = []
    outputs = sot.get("outputs", {})
    if isinstance(outputs, dict):
        for key in outputs:
            m = re.match(r"step-(\d+)$", str(key))
            if not m:
                continue
            s = int(m.group(1))
            vlog = os.path.join(project_dir, "verification-logs", f"step-{s}-verify.md")
            if not os.path.isfile(vlog):
                pending.append(f"step-{s}: verification log missing")
            plog = os.path.join(project_dir, "pacs-logs", f"step-{s}-pacs.md")
            if not os.path.isfile(plog):
                pending.append(f"step-{s}: pACS log missing")

    # Autopilot status
    autopilot = sot.get("autopilot", {})
    autopilot_enabled = autopilot.get("enabled", False) if isinstance(autopilot, dict) else False

    result = {
        "mode": "dashboard",
        "current_step": current_step,
        "total_steps": total_steps,
        "workflow_status": workflow_status,
        "autopilot_enabled": autopilot_enabled,
        "pacs_history": pacs_history,
        "pending_validations": pending,
        "completed_steps": current_step - 1 if isinstance(current_step, int) and current_step > 0 else 0,
    }
    if pacs_errors:
        result["pacs_read_errors"] = pacs_errors
    return result


# ---------------------------------------------------------------------------
# Mode: --weakest-step
# ---------------------------------------------------------------------------
def _weakest_step(project_dir, sot):
    """Step with lowest pACS score and its weak dimension."""
    pacs_dir = os.path.join(project_dir, "pacs-logs")
    if not os.path.isdir(pacs_dir):
        return {"mode": "weakest_step", "found": False, "reason": "No pacs-logs directory"}

    weakest = None
    weakest_score = 101
    read_errors = []

    for f in sorted(glob.glob(os.path.join(pacs_dir, "step-*-pacs.md"))):
        m = re.search(r"step-(\d+)-pacs\.md$", f)
        if not m:
            continue
        step_num = int(m.group(1))
        content, err = _read_file_safe(f)
        if err:
            read_errors.append(err)
            continue
        score = _extract_pacs_score(content)
        if score is None:
            continue
        weak_dim = _extract_weak_dimension(content)
        if score < weakest_score:
            weakest_score = score
            weakest = {
                "step": step_num,
                "pacs_score": score,
                "weak_dimension": weak_dim,
                "zone": "RED" if score < 50 else "YELLOW" if score < 70 else "GREEN",
                "file": f,
            }

    result = {"mode": "weakest_step"}
    if weakest:
        result.update({"found": True, **weakest})
    else:
        result.update({"found": False, "reason": "No pACS logs found"})
    if read_errors:
        result["read_errors"] = read_errors
    return result


# ---------------------------------------------------------------------------
# Mode: --retry-summary
# ---------------------------------------------------------------------------
def _retry_summary(project_dir, sot):
    """Retry budget usage across all gates."""
    retries = []
    for gate_dir in ("verification-logs", "pacs-logs", "review-logs"):
        gate = gate_dir.replace("-logs", "")
        full_dir = os.path.join(project_dir, gate_dir)
        if not os.path.isdir(full_dir):
            continue
        for f in sorted(glob.glob(os.path.join(full_dir, ".step-*-retry-count"))):
            m = re.search(r"\.step-(\d+)-retry-count$", f)
            if not m:
                continue
            step_num = int(m.group(1))
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    count = int(fh.read().strip())
            except (ValueError, OSError):
                count = -1  # -1 signals unreadable counter
            retries.append({
                "step": step_num,
                "gate": gate,
                "retries_used": count,
            })

    return {
        "mode": "retry_summary",
        "total_retries": sum(r["retries_used"] for r in retries if r["retries_used"] > 0),
        "entries": retries,
    }


# ---------------------------------------------------------------------------
# Mode: --blocked
# ---------------------------------------------------------------------------
def _blocked(project_dir, sot):
    """Identify what's blocking progress."""
    blockers = []
    current_step = sot.get("current_step", 0)
    if not isinstance(current_step, int):
        return {"mode": "blocked", "blockers": [{"type": "schema_error", "detail": "current_step is not an integer"}]}

    outputs = sot.get("outputs", {})
    if not isinstance(outputs, dict):
        outputs = {}

    # Check if current step output exists
    step_key = f"step-{current_step}"
    if step_key not in outputs:
        blockers.append({
            "type": "missing_output",
            "step": current_step,
            "detail": f"SOT outputs.{step_key} not recorded",
        })
    else:
        output_path = outputs[step_key]
        if isinstance(output_path, str):
            # Prevent absolute path bypass — SOT paths must be relative
            if os.path.isabs(output_path):
                blockers.append({
                    "type": "absolute_path",
                    "step": current_step,
                    "detail": f"SOT output path is absolute (must be relative): {output_path}",
                })
            elif not os.path.isfile(os.path.join(project_dir, output_path)):
                blockers.append({
                    "type": "missing_file",
                    "step": current_step,
                    "detail": f"Output file not found: {output_path}",
                })

    # Check for failed verification
    vlog = os.path.join(project_dir, "verification-logs", f"step-{current_step}-verify.md")
    content, err = _read_file_safe(vlog)
    if content is not None:
        if re.search(r"\bFAIL\b", content) and not re.search(r"Overall.*PASS", content):
            blockers.append({
                "type": "verification_fail",
                "step": current_step,
                "detail": "Verification log contains FAIL — criteria not met",
            })
    elif err and err["type"] != "file_not_found":
        blockers.append({
            "type": "verification_read_error",
            "step": current_step,
            "detail": f"Cannot read verification log: {err['type']}",
        })

    # Check for RED pACS
    plog = os.path.join(project_dir, "pacs-logs", f"step-{current_step}-pacs.md")
    content, err = _read_file_safe(plog)
    if content is not None:
        score = _extract_pacs_score(content)
        if score is not None and score < 50:
            blockers.append({
                "type": "pacs_red",
                "step": current_step,
                "detail": f"pACS = {score} (RED zone, < 50)",
            })
    elif err and err["type"] != "file_not_found":
        blockers.append({
            "type": "pacs_read_error",
            "step": current_step,
            "detail": f"Cannot read pACS log: {err['type']}",
        })

    # Check for review FAIL
    rlog = os.path.join(project_dir, "review-logs", f"step-{current_step}-review.md")
    content, err = _read_file_safe(rlog)
    if content is not None:
        if re.search(r"Verdict\s*:\s*FAIL", content, re.IGNORECASE):
            blockers.append({
                "type": "review_fail",
                "step": current_step,
                "detail": "Adversarial Review verdict is FAIL",
            })
    elif err and err["type"] != "file_not_found":
        blockers.append({
            "type": "review_read_error",
            "step": current_step,
            "detail": f"Cannot read review log: {err['type']}",
        })

    return {
        "mode": "blocked",
        "current_step": current_step,
        "blockers": blockers,
        "is_blocked": len(blockers) > 0,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Workflow Observability Tool")
    parser.add_argument("--project-dir", required=True, help="Project root directory")
    parser.add_argument("--dashboard", action="store_true", help="Overview dashboard")
    parser.add_argument("--weakest-step", action="store_true", help="Weakest pACS step")
    parser.add_argument("--retry-summary", action="store_true", help="Retry budget usage")
    parser.add_argument("--blocked", action="store_true", help="Progress blockers")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    sot, sot_path, sot_error = _find_sot(project_dir)

    if sot is None:
        print(json.dumps({
            "error": sot_error or "No SOT file found",
            "sot_path": sot_path,
            "project_dir": project_dir,
        }, indent=2))
        sys.exit(1)

    # P1: Validate SOT schema before any query
    schema_warnings = validate_sot_schema(sot)

    if args.dashboard:
        result = _dashboard(project_dir, sot)
    elif args.weakest_step:
        result = _weakest_step(project_dir, sot)
    elif args.retry_summary:
        result = _retry_summary(project_dir, sot)
    elif args.blocked:
        result = _blocked(project_dir, sot)
    else:
        result = _dashboard(project_dir, sot)  # default

    result["sot_path"] = sot_path
    if schema_warnings:
        result["sot_schema_warnings"] = schema_warnings

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"error": str(e), "error_type": type(e).__name__}, indent=2))
        sys.exit(1)
