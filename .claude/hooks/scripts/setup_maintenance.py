#!/usr/bin/env python3
"""
AgenticWorkflow Setup Maintenance Hook — Deterministic Health Check

Triggered by: claude --maintenance
Location: .claude/settings.json (Project)

SOT Compliance: NO ACCESS to SOT (state.yaml).
  Maintenance operates on Context Preservation System artifacts only.

Design Principle: This script REPORTS but does NOT DELETE.
  Deletion decisions are made by the /maintenance slash command
  with user confirmation via the agent.

Quality Impact Path (절대 기준 1):
  Periodic health checks → data integrity maintenance →
  Knowledge Archive reliability → session recovery quality →
  long-term workflow continuity
"""

import ast
import json
import os
import re
import sys
import time
from datetime import datetime


# =============================================================================
# Constants
# =============================================================================

# Age threshold for session archive staleness (30 days)
STALE_ARCHIVE_DAYS = 30
STALE_ARCHIVE_SECONDS = STALE_ARCHIVE_DAYS * 24 * 3600

# work_log.jsonl size warning threshold (1MB)
WORK_LOG_SIZE_WARN = 1_000_000

# Hook scripts to re-validate (20 scripts)
# NOTE: setup_init.py and setup_maintenance.py are NOT in this list — they are
# the validators themselves (self-validating).
# D-7: Intentionally duplicated in setup_init.py — setup scripts are
# independent from _context_lib.py by design (no import dependency).
REQUIRED_SCRIPTS = [
    "_context_lib.py",
    "block_destructive_commands.py",
    "block_test_file_edit.py",
    "context_guard.py",
    "output_secret_filter.py",
    "security_sensitive_file_guard.py",
    "diagnose_context.py",
    "generate_context_summary.py",
    "predictive_debug_guard.py",
    "query_workflow.py",
    "restore_context.py",
    "save_context.py",
    "update_work_log.py",
    "validate_diagnosis.py",
    "validate_domain_knowledge.py",
    "validate_pacs.py",
    "validate_retry_budget.py",
    "validate_review.py",
    "validate_traceability.py",
    "validate_translation.py",
    "validate_verification.py",
    "validate_workflow.py",
]

# Severity levels
WARNING = "WARNING"
INFO = "INFO"


# =============================================================================
# Main
# =============================================================================

def main():
    """Run all maintenance checks."""
    input_data = _read_stdin_json()
    project_dir = os.environ.get(
        "CLAUDE_PROJECT_DIR",
        input_data.get("cwd", os.getcwd()),
    )

    results = []

    # 1. Stale session archives (report only — no deletion)
    results.append(_check_stale_archives(project_dir))

    # 2. knowledge-index.jsonl integrity
    results.append(_check_knowledge_index(project_dir))

    # 3. work_log.jsonl size
    results.append(_check_work_log_size(project_dir))

    # 4. Hook scripts syntax re-validation
    scripts_dir = os.path.join(project_dir, ".claude", "hooks", "scripts")
    for script_name in REQUIRED_SCRIPTS:
        results.append(_check_script_syntax(scripts_dir, script_name))

    # 5. Documentation-code synchronization (P1 drift prevention)
    results.extend(_check_doc_code_sync(project_dir))

    # Write log file
    log_path = os.path.join(
        project_dir, ".claude", "hooks", "setup.maintenance.log"
    )
    _write_log(log_path, results)

    # Build summary
    issues = sum(1 for r in results if r["status"] != "PASS")
    summary = f"Maintenance check: {len(results) - issues}/{len(results)} healthy"
    if issues > 0:
        summary += f" ({issues} issue(s) found — see /maintenance for details)"

    # Output structured JSON for Claude Code
    output = {
        "hookSpecificOutput": {
            "hookEventName": "Setup",
            "additionalContext": summary,
        }
    }
    print(json.dumps(output))

    # Maintenance never blocks the session (always exit 0)
    # Issues are informational, not blocking
    sys.exit(0)


# =============================================================================
# Maintenance Checks
# =============================================================================

def _check_stale_archives(project_dir):
    """List session archives older than 30 days.

    Does NOT delete — reports only. Deletion is performed by /maintenance
    slash command with user confirmation.
    """
    sessions_dir = os.path.join(
        project_dir, ".claude", "context-snapshots", "sessions"
    )

    if not os.path.isdir(sessions_dir):
        return _result(
            INFO, "PASS", "Session archives",
            "sessions/ directory not found (OK — no archives yet)",
        )

    now = time.time()
    stale_files = []
    total_files = 0
    total_size = 0

    try:
        for fname in sorted(os.listdir(sessions_dir)):
            if not fname.endswith(".md"):
                continue
            total_files += 1
            fpath = os.path.join(sessions_dir, fname)
            fsize = os.path.getsize(fpath)
            total_size += fsize
            age_seconds = now - os.path.getmtime(fpath)
            if age_seconds > STALE_ARCHIVE_SECONDS:
                age_days = int(age_seconds / 86400)
                stale_files.append((fname, age_days, fsize))
    except Exception as e:
        return _result(WARNING, "FAIL", "Session archives", f"cannot scan: {e}")

    if stale_files:
        stale_size = sum(f[2] for f in stale_files)
        names = ", ".join(
            f"{f[0]} ({f[1]}d)" for f in stale_files[:5]
        )
        extra = f" +{len(stale_files) - 5} more" if len(stale_files) > 5 else ""
        return _result(
            WARNING, "WARN", "Session archives",
            f"{len(stale_files)}/{total_files} archives older than {STALE_ARCHIVE_DAYS} days "
            f"({stale_size / 1024:.0f}KB reclaimable): {names}{extra}",
        )

    size_kb = total_size / 1024
    return _result(
        INFO, "PASS", "Session archives",
        f"{total_files} archives ({size_kb:.0f}KB), all within {STALE_ARCHIVE_DAYS} days",
    )


def _check_knowledge_index(project_dir):
    """Validate knowledge-index.jsonl — each line must be valid JSON.

    knowledge-index.jsonl is the RLM Knowledge Archive.
    Invalid entries degrade cross-session knowledge retrieval.
    """
    ki_path = os.path.join(
        project_dir, ".claude", "context-snapshots", "knowledge-index.jsonl"
    )

    if not os.path.exists(ki_path):
        return _result(
            INFO, "PASS", "Knowledge index",
            "file not found (OK — no sessions archived yet)",
        )

    total_lines = 0
    invalid_lines = []

    try:
        with open(ki_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                total_lines += 1
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    invalid_lines.append(line_num)
    except Exception as e:
        return _result(WARNING, "FAIL", "Knowledge index", f"cannot read: {e}")

    if invalid_lines:
        line_refs = ", ".join(str(n) for n in invalid_lines[:10])
        extra = f" +{len(invalid_lines) - 10} more" if len(invalid_lines) > 10 else ""
        return _result(
            WARNING, "WARN", "Knowledge index",
            f"{len(invalid_lines)}/{total_lines} lines have invalid JSON "
            f"(lines: {line_refs}{extra})",
        )

    size_kb = os.path.getsize(ki_path) / 1024
    return _result(
        INFO, "PASS", "Knowledge index",
        f"{total_lines} entries ({size_kb:.0f}KB), all valid JSON",
    )


def _check_work_log_size(project_dir):
    """Check work_log.jsonl size — warn if exceeds threshold."""
    log_path = os.path.join(
        project_dir, ".claude", "context-snapshots", "work_log.jsonl"
    )

    if not os.path.exists(log_path):
        return _result(INFO, "PASS", "Work log", "file not found (OK)")

    try:
        size = os.path.getsize(log_path)
        size_kb = size / 1024

        if size > WORK_LOG_SIZE_WARN:
            return _result(
                WARNING, "WARN", "Work log",
                f"{size_kb:.0f}KB — exceeds 1MB threshold. Consider cleanup.",
            )

        return _result(INFO, "PASS", "Work log", f"{size_kb:.0f}KB")
    except Exception as e:
        return _result(WARNING, "FAIL", "Work log", f"cannot check: {e}")


def _check_script_syntax(scripts_dir, script_name):
    """Re-validate hook script Python syntax."""
    script_path = os.path.join(scripts_dir, script_name)

    if not os.path.exists(script_path):
        return _result(
            WARNING, "FAIL", f"Script: {script_name}", "not found"
        )

    try:
        with open(script_path, "r", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source, filename=script_name)
        return _result(
            INFO, "PASS", f"Script: {script_name}", "syntax valid"
        )
    except SyntaxError as e:
        return _result(
            WARNING, "FAIL", f"Script: {script_name}",
            f"syntax error at line {e.lineno}: {e.msg}",
        )
    except Exception as e:
        return _result(
            WARNING, "FAIL", f"Script: {script_name}",
            f"cannot read: {e}",
        )


def _check_doc_code_sync(project_dir):
    """P1: Verify critical documentation-code synchronization points.

    Deterministic regex-based extraction and comparison.
    Prevents documentation drift where LLM follows outdated doc
    instead of correct code (NEVER DO override risk).

    DC-1: docs/protocols/autopilot-execution.md NEVER DO retry limits ↔ validate_retry_budget.py constants
    DC-2: D-7 Risk score constants (_context_lib.py ↔ predictive_debug_guard.py)
    DC-3: D-7 ULW detection pattern (validate_retry_budget.py ↔ _context_lib.py)
    DC-6: Hook configuration consistency (settings.json hook scripts ↔ CLAUDE.md Hook table)

    Read-only: no SOT access, no RLM data mutation, no atomic_write calls.
    Returns list of _result() dicts (extends results, not appends single).
    """
    results = []
    scripts_dir = os.path.join(project_dir, ".claude", "hooks", "scripts")

    # --- DC-1: NEVER DO retry limits ↔ code constants ---
    budget_path = os.path.join(scripts_dir, "validate_retry_budget.py")
    never_do_path = os.path.join(
        project_dir, "docs", "protocols", "autopilot-execution.md"
    )

    dc1_ok = True
    if os.path.isfile(budget_path) and os.path.isfile(never_do_path):
        try:
            with open(budget_path, "r", encoding="utf-8") as f:
                budget_src = f.read()
            with open(never_do_path, "r", encoding="utf-8") as f:
                never_do_src = f.read()

            # Extract code constants
            m_default = re.search(
                r"DEFAULT_MAX_RETRIES\s*=\s*(\d+)", budget_src
            )
            m_ulw = re.search(
                r"ULW_MAX_RETRIES\s*=\s*(\d+)", budget_src
            )

            if m_default and m_ulw:
                code_default = int(m_default.group(1))
                code_ulw = int(m_ulw.group(1))

                # Extract from autopilot-execution.md NEVER DO section
                # Pattern: "최대 N회(ULW 활성 시 M회) 재시도"
                m_doc = re.search(
                    r"최대\s*(\d+)회\s*\(ULW\s*활성\s*시\s*(\d+)회\)\s*재시도",
                    never_do_src,
                )

                if m_doc:
                    doc_default = int(m_doc.group(1))
                    doc_ulw = int(m_doc.group(2))

                    if doc_default != code_default or doc_ulw != code_ulw:
                        dc1_ok = False
                        results.append(_result(
                            WARNING, "WARN", "Doc-code sync: DC-1",
                            f"NEVER DO retry limits mismatch — "
                            f"doc: {doc_default}/{doc_ulw}, "
                            f"code: {code_default}/{code_ulw}",
                        ))
                else:
                    dc1_ok = False
                    results.append(_result(
                        WARNING, "WARN", "Doc-code sync: DC-1",
                        "cannot extract retry limits from autopilot-execution.md NEVER DO "
                        "(expected pattern: '최대 N회(ULW 활성 시 M회) 재시도')",
                    ))
            else:
                dc1_ok = False
                results.append(_result(
                    WARNING, "WARN", "Doc-code sync: DC-1",
                    "cannot extract DEFAULT_MAX_RETRIES or ULW_MAX_RETRIES "
                    "from validate_retry_budget.py",
                ))
        except Exception as e:
            dc1_ok = False
            results.append(_result(
                WARNING, "FAIL", "Doc-code sync: DC-1", f"read error: {e}"
            ))

    if dc1_ok and os.path.isfile(budget_path) and os.path.isfile(never_do_path):
        results.append(_result(
            INFO, "PASS", "Doc-code sync: DC-1",
            "NEVER DO retry limits match code constants",
        ))

    # --- DC-2: D-7 Risk score constants sync ---
    lib_path = os.path.join(scripts_dir, "_context_lib.py")
    guard_path = os.path.join(scripts_dir, "predictive_debug_guard.py")

    dc2_ok = True
    if os.path.isfile(lib_path) and os.path.isfile(guard_path):
        try:
            with open(lib_path, "r", encoding="utf-8") as f:
                lib_src = f.read()
            with open(guard_path, "r", encoding="utf-8") as f:
                guard_src = f.read()

            # _context_lib.py constants
            m_lib_thresh = re.search(
                r"_RISK_SCORE_THRESHOLD\s*=\s*([0-9.]+)", lib_src
            )
            m_lib_min = re.search(
                r"_RISK_MIN_SESSIONS\s*=\s*(\d+)", lib_src
            )

            # predictive_debug_guard.py constants
            m_guard_thresh = re.search(
                r"RISK_THRESHOLD\s*=\s*([0-9.]+)", guard_src
            )
            m_guard_min = re.search(
                r"MIN_SESSIONS\s*=\s*(\d+)", guard_src
            )

            if m_lib_thresh and m_lib_min and m_guard_thresh and m_guard_min:
                lib_thresh = float(m_lib_thresh.group(1))
                lib_min = int(m_lib_min.group(1))
                guard_thresh = float(m_guard_thresh.group(1))
                guard_min = int(m_guard_min.group(1))

                mismatches = []
                if lib_thresh != guard_thresh:
                    mismatches.append(
                        f"RISK_THRESHOLD: lib={lib_thresh}, guard={guard_thresh}"
                    )
                if lib_min != guard_min:
                    mismatches.append(
                        f"MIN_SESSIONS: lib={lib_min}, guard={guard_min}"
                    )

                if mismatches:
                    dc2_ok = False
                    results.append(_result(
                        WARNING, "WARN", "Doc-code sync: DC-2",
                        f"D-7 Risk constants out of sync — {'; '.join(mismatches)}",
                    ))
            else:
                dc2_ok = False
                results.append(_result(
                    WARNING, "WARN", "Doc-code sync: DC-2",
                    "cannot extract Risk constants from one or both scripts",
                ))
        except Exception as e:
            dc2_ok = False
            results.append(_result(
                WARNING, "FAIL", "Doc-code sync: DC-2", f"read error: {e}"
            ))

    if dc2_ok and os.path.isfile(lib_path) and os.path.isfile(guard_path):
        results.append(_result(
            INFO, "PASS", "Doc-code sync: DC-2",
            "D-7 Risk constants synchronized",
        ))

    # --- DC-3: D-7 ULW detection pattern sync ---
    # D-7 verifier: This canonical string must match the ULW detection pattern
    # in _context_lib.py and validate_retry_budget.py.
    # If those files change their pattern, this must change too.
    # We search for this exact substring rather than parsing quoted strings,
    # which avoids fragile quote-matching across r-strings and compiled patterns.
    _ULW_CANONICAL = "ULW 상태|Ultrawork Mode State"

    dc3_ok = True
    if os.path.isfile(budget_path) and os.path.isfile(lib_path):
        try:
            # budget_src and lib_src may already be loaded from DC-1/DC-2
            try:
                _ = budget_src  # noqa: F841
            except NameError:
                with open(budget_path, "r", encoding="utf-8") as f:
                    budget_src = f.read()
            try:
                _ = lib_src  # noqa: F841
            except NameError:
                with open(lib_path, "r", encoding="utf-8") as f:
                    lib_src = f.read()

            budget_has = _ULW_CANONICAL in budget_src
            lib_has = _ULW_CANONICAL in lib_src

            if not budget_has or not lib_has:
                dc3_ok = False
                missing = []
                if not budget_has:
                    missing.append("validate_retry_budget.py")
                if not lib_has:
                    missing.append("_context_lib.py")
                results.append(_result(
                    WARNING, "WARN", "Doc-code sync: DC-3",
                    f"D-7 ULW canonical pattern not found in: "
                    f"{', '.join(missing)}",
                ))
        except Exception as e:
            dc3_ok = False
            results.append(_result(
                WARNING, "FAIL", "Doc-code sync: DC-3", f"read error: {e}"
            ))

    if dc3_ok and os.path.isfile(budget_path) and os.path.isfile(lib_path):
        results.append(_result(
            INFO, "PASS", "Doc-code sync: DC-3",
            "D-7 ULW detection pattern synchronized",
        ))

    # --- DC-4: D-7 Retry limit constants sync ---
    # _context_lib.py has _DEFAULT_MAX_RETRIES / _ULW_MAX_RETRIES
    # that must match validate_retry_budget.py's constants.
    dc4_ok = True
    if os.path.isfile(budget_path) and os.path.isfile(lib_path):
        try:
            # budget_src / lib_src may already be loaded
            try:
                _ = budget_src  # noqa: F841
            except NameError:
                with open(budget_path, "r", encoding="utf-8") as f:
                    budget_src = f.read()
            try:
                _ = lib_src  # noqa: F841
            except NameError:
                with open(lib_path, "r", encoding="utf-8") as f:
                    lib_src = f.read()

            # Extract from validate_retry_budget.py
            m_b_default = re.search(
                r"DEFAULT_MAX_RETRIES\s*=\s*(\d+)", budget_src
            )
            m_b_ulw = re.search(
                r"ULW_MAX_RETRIES\s*=\s*(\d+)", budget_src
            )

            # Extract from _context_lib.py (_gather_retry_history locals)
            m_l_default = re.search(
                r"_DEFAULT_MAX_RETRIES\s*=\s*(\d+)", lib_src
            )
            m_l_ulw = re.search(
                r"_ULW_MAX_RETRIES\s*=\s*(\d+)", lib_src
            )

            if m_b_default and m_b_ulw and m_l_default and m_l_ulw:
                mismatches = []
                if int(m_b_default.group(1)) != int(m_l_default.group(1)):
                    mismatches.append(
                        f"DEFAULT: budget={m_b_default.group(1)}, "
                        f"lib={m_l_default.group(1)}"
                    )
                if int(m_b_ulw.group(1)) != int(m_l_ulw.group(1)):
                    mismatches.append(
                        f"ULW: budget={m_b_ulw.group(1)}, "
                        f"lib={m_l_ulw.group(1)}"
                    )
                if mismatches:
                    dc4_ok = False
                    results.append(_result(
                        WARNING, "WARN", "Doc-code sync: DC-4",
                        f"D-7 Retry limits out of sync — "
                        f"{'; '.join(mismatches)}",
                    ))
            else:
                dc4_ok = False
                results.append(_result(
                    WARNING, "WARN", "Doc-code sync: DC-4",
                    "cannot extract retry limit constants from one or both scripts",
                ))
        except Exception as e:
            dc4_ok = False
            results.append(_result(
                WARNING, "FAIL", "Doc-code sync: DC-4", f"read error: {e}"
            ))

    if dc4_ok and os.path.isfile(budget_path) and os.path.isfile(lib_path):
        results.append(_result(
            INFO, "PASS", "Doc-code sync: DC-4",
            "D-7 Retry limit constants synchronized",
        ))

    # --- DC-5: D-7 SOT_FILENAMES sync across 3 files ---
    # _context_lib.py:SOT_FILENAMES ↔ setup_init.py:SOT_FILENAMES ↔ query_workflow.py:_SOT_FILENAMES
    dc5_ok = True
    dc5_files = {
        "_context_lib.py": os.path.join(scripts_dir, "_context_lib.py"),
        "setup_init.py": os.path.join(scripts_dir, "setup_init.py"),
        "query_workflow.py": os.path.join(scripts_dir, "query_workflow.py"),
    }
    sot_filenames_values = {}
    _sot_re = re.compile(r'(?:SOT_FILENAMES|_SOT_FILENAMES)\s*=\s*\(([^)]+)\)')
    for label, fpath in dc5_files.items():
        try:
            if not os.path.isfile(fpath):
                dc5_ok = False
                results.append(_result(
                    WARNING, "WARN", "Doc-code sync: DC-5",
                    f"File not found: {label}",
                ))
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            matches = _sot_re.findall(content)
            if matches:
                # Normalize each match: strip whitespace, quotes
                normalized = []
                for raw in matches:
                    items = tuple(
                        s.strip().strip("\"'") for s in raw.split(",") if s.strip().strip("\"'")
                    )
                    normalized.append(items)
                # M-1: Verify all definitions in same file are identical
                if len(set(normalized)) > 1:
                    dc5_ok = False
                    results.append(_result(
                        WARNING, "WARN", "Doc-code sync: DC-5",
                        f"Multiple SOT_FILENAMES in {label} differ: {normalized}",
                    ))
                sot_filenames_values[label] = normalized[0]
            else:
                dc5_ok = False
                results.append(_result(
                    WARNING, "WARN", "Doc-code sync: DC-5",
                    f"SOT_FILENAMES pattern not found in {label}",
                ))
        except Exception as e:
            dc5_ok = False
            results.append(_result(
                WARNING, "FAIL", "Doc-code sync: DC-5", f"read error in {label}: {e}"
            ))

    if len(sot_filenames_values) >= 2:
        canonical = None
        for label, val in sot_filenames_values.items():
            if canonical is None:
                canonical = (label, val)
            elif val != canonical[1]:
                dc5_ok = False
                results.append(_result(
                    WARNING, "WARN", "Doc-code sync: DC-5",
                    f"SOT_FILENAMES mismatch: {canonical[0]}={canonical[1]} vs {label}={val}",
                ))

    if dc5_ok and len(sot_filenames_values) == len(dc5_files):
        results.append(_result(
            INFO, "PASS", "Doc-code sync: DC-5",
            f"D-7 SOT_FILENAMES synchronized across {len(dc5_files)} files",
        ))

    # --- DC-6: Hook configuration consistency ---
    # settings.json hook scripts ↔ CLAUDE.md Hook event table
    # Prevents: adding a hook script to settings.json but forgetting to
    # document it in CLAUDE.md (exactly the error found in ADR-050 reflection).
    #
    # Dispatcher handling: context_guard.py dispatches to child scripts
    # (generate_context_summary.py, update_work_log.py, etc.).
    # settings.json references context_guard.py, while CLAUDE.md documents
    # the dispatched scripts. DC-6 resolves this by reading context_guard.py's
    # DISPATCH dict to build the effective script set.
    dc6_ok = True
    settings_path = os.path.join(project_dir, ".claude", "settings.json")
    claude_md_path = os.path.join(project_dir, "CLAUDE.md")
    guard_path = os.path.join(scripts_dir, "context_guard.py")

    if os.path.isfile(settings_path) and os.path.isfile(claude_md_path):
        try:
            import json as _json
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = _json.load(f)

            # Extract all hook script filenames from settings.json
            settings_scripts = set()
            _script_re = re.compile(r'hooks/scripts/([a-zA-Z_]\w*\.py)')
            hooks_config = settings.get("hooks", {})
            for _hook_type, hook_groups in hooks_config.items():
                if not isinstance(hook_groups, list):
                    continue
                for group in hook_groups:
                    for hook in group.get("hooks", []):
                        cmd = hook.get("command", "")
                        for m in _script_re.finditer(cmd):
                            settings_scripts.add(m.group(1))

            # Resolve context_guard.py dispatcher → dispatched scripts
            # Read DISPATCH dict from context_guard.py to get child scripts
            dispatched_scripts = set()
            if "context_guard.py" in settings_scripts and os.path.isfile(guard_path):
                with open(guard_path, "r", encoding="utf-8") as f:
                    guard_src = f.read()
                # Extract script filenames from DISPATCH = { ... } entries
                # Pattern: ("script_name.py", [...])
                for m in re.finditer(
                    r'\("([a-zA-Z_]\w*\.py)"', guard_src
                ):
                    dispatched_scripts.add(m.group(1))

            # Build effective set: replace dispatcher with dispatched scripts
            effective_scripts = (
                (settings_scripts - {"context_guard.py"}) | dispatched_scripts
            )

            # Extract script filenames mentioned in CLAUDE.md Hook event table
            with open(claude_md_path, "r", encoding="utf-8") as f:
                claude_md = f.read()

            table_match = re.search(
                r'\|\s*Hook 이벤트.*?\n(.*?)(?=\n##|\n\*\*필수)',
                claude_md,
                re.DOTALL,
            )
            claude_scripts = set()
            if table_match:
                table_text = table_match.group(1)
                for m in re.finditer(r'`([a-zA-Z_]\w*\.py)`', table_text):
                    claude_scripts.add(m.group(1))

            # Compare: effective scripts NOT in CLAUDE.md
            missing_in_doc = effective_scripts - claude_scripts
            if missing_in_doc:
                dc6_ok = False
                results.append(_result(
                    WARNING, "WARN", "Doc-code sync: DC-6",
                    f"Hook scripts in settings.json but NOT in CLAUDE.md table: "
                    f"{', '.join(sorted(missing_in_doc))}",
                ))

            # Reverse: documented but not in effective settings
            extra_in_doc = claude_scripts - effective_scripts
            if extra_in_doc:
                dc6_ok = False
                results.append(_result(
                    WARNING, "WARN", "Doc-code sync: DC-6",
                    f"Scripts in CLAUDE.md table but NOT in settings.json: "
                    f"{', '.join(sorted(extra_in_doc))}",
                ))

        except Exception as e:
            dc6_ok = False
            results.append(_result(
                WARNING, "FAIL", "Doc-code sync: DC-6", f"read error: {e}"
            ))

    if dc6_ok and os.path.isfile(settings_path) and os.path.isfile(claude_md_path):
        results.append(_result(
            INFO, "PASS", "Doc-code sync: DC-6",
            f"Hook configuration consistent: {len(effective_scripts)} effective scripts "
            f"↔ {len(claude_scripts)} documented",
        ))

    return results


# =============================================================================
# Helpers
# =============================================================================

def _result(severity, status, check, message):
    """Create a structured check result."""
    return {
        "severity": severity,
        "status": status,
        "check": check,
        "message": message,
    }


def _read_stdin_json():
    """Read JSON from stdin (Claude Code hook protocol)."""
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, Exception):
        return {}


def _write_log(log_path, results):
    """Write maintenance results to log file.

    Log format is human-readable and machine-parseable by /maintenance command.
    """
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        timestamp = datetime.now().isoformat()
        lines = [
            "# AgenticWorkflow Setup Maintenance Log",
            f"# Timestamp: {timestamp}",
            f"# Python: {sys.version.split()[0]}",
            "",
        ]

        for r in results:
            if r["status"] == "PASS":
                marker = "PASS"
            elif r["status"] == "WARN":
                marker = "WARN"
            else:
                marker = "FAIL"
            lines.append(
                f"[{r['severity']}] [{marker}] {r['check']}: {r['message']}"
            )

        lines.append("")

        # Summary
        pass_count = sum(1 for r in results if r["status"] == "PASS")
        issue_count = sum(1 for r in results if r["status"] != "PASS")
        lines.append(
            f"# Summary: {pass_count} healthy, {issue_count} issues, "
            f"{len(results)} total"
        )
        lines.append("")

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        pass  # Log write failure is non-blocking


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Setup maintenance error: {e}", file=sys.stderr)
        sys.exit(0)  # Maintenance never blocks
