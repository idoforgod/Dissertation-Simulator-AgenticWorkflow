#!/usr/bin/env python3
"""
Context Preservation System — generate_context_summary.py

Triggered by: Stop (every time Claude finishes a response)

v2 Design: COMPREHENSIVE full snapshot, not lightweight.
  - Quality First (절대 기준 1): Every save is comprehensive.
  - The Stop hook is the last automatic save point before /clear.
  - If SessionEnd fails, this is the safety net.

Incremental approach:
  - Tracks last save byte offset in .last_save_offset
  - Only processes new transcript entries since last save
  - Regenerates full MD from accumulated data
  - Updates latest.md atomically

Architecture:
  - Reuses save_context.py's core logic via _context_lib
  - SOT: Read-only
  - Writes: .claude/context-snapshots/ (snapshots, knowledge archive)
  - Writes: autopilot-logs/ (Decision Log safety net — only when autopilot active)
"""

import os
import re
import sys
import json
from datetime import datetime

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _context_lib import (
    read_stdin_json,
    parse_transcript,
    capture_sot,
    load_work_log,
    generate_snapshot_md,
    atomic_write,
    cleanup_snapshots,
    should_skip_save,
    get_snapshot_dir,
    read_autopilot_state,
    update_latest_with_guard,
    archive_and_index_session,
    detect_ulw_mode,
    check_ulw_compliance,
)


def main():
    input_data = read_stdin_json()

    # Determine project directory
    project_dir = os.environ.get(
        "CLAUDE_PROJECT_DIR",
        input_data.get("cwd", os.getcwd()),
    )

    snapshot_dir = get_snapshot_dir(project_dir)
    os.makedirs(snapshot_dir, exist_ok=True)

    # Dedup guard — Stop hook uses 30s window to reduce noise
    if should_skip_save(snapshot_dir, trigger="stop"):
        sys.exit(0)

    # Parse transcript
    transcript_path = input_data.get("transcript_path", "")
    if not transcript_path or not os.path.exists(transcript_path):
        sys.exit(0)  # No transcript to process

    # Check if transcript has grown since last save (incremental check)
    offset_file = os.path.join(snapshot_dir, ".last_save_offset")
    current_size = os.path.getsize(transcript_path)
    last_size = _read_offset(offset_file)

    # Only save if transcript has grown by at least 5KB since last save
    # (5KB threshold ensures meaningful changes only — reduces noise)
    if last_size > 0 and (current_size - last_size) < 5120:
        sys.exit(0)

    # Full transcript parse (comprehensive — 절대 기준 1)
    entries = parse_transcript(transcript_path)

    if not entries:
        sys.exit(0)

    # Load accumulated work log
    work_log = load_work_log(snapshot_dir)

    # Capture SOT state (read-only)
    sot_content = capture_sot(project_dir)

    # Generate comprehensive MD snapshot
    session_id = input_data.get("session_id", "unknown")
    md_content = generate_snapshot_md(
        session_id=session_id,
        trigger="stop",
        project_dir=project_dir,
        entries=entries,
        work_log=work_log,
        sot_content=sot_content,
    )

    # Atomic write: timestamped snapshot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_stop.md"
    filepath = os.path.join(snapshot_dir, filename)
    atomic_write(filepath, md_content)

    # E5: Empty Snapshot Guard — update latest.md with rich content protection
    update_latest_with_guard(snapshot_dir, md_content, entries)

    # Update offset tracker
    _write_offset(offset_file, current_size)

    # Knowledge Archive: archive + index + cleanup (consolidated)
    archive_and_index_session(
        snapshot_dir, md_content, session_id, "stop",
        project_dir, entries, transcript_path,
    )

    # --- Autopilot Decision Log (supplementary safety net) ---
    # Primary: Claude generates Decision Log during execution.
    # Secondary: This hook detects auto-approve patterns and creates logs if missing.
    try:
        _generate_decision_log_if_needed(project_dir, entries)
    except Exception:
        pass  # Non-blocking — never fail the hook

    # --- Adversarial Review safety net ---
    # Detect steps with pACS logs but missing review reports.
    # Non-blocking: only logs warning, does not fail the hook.
    try:
        _check_missing_reviews(project_dir)
    except Exception:
        pass  # Non-blocking — never fail the hook

    # --- Translation safety net ---
    # Detect steps with translation pACS logs but missing translation files.
    # Non-blocking: only logs warning, does not fail the hook.
    try:
        _check_missing_translations(project_dir)
    except Exception:
        pass  # Non-blocking — never fail the hook

    # --- Verification safety net ---
    # Detect steps with pACS logs but no corresponding verification reports.
    # Non-blocking: only logs warning, does not fail the hook.
    try:
        _check_missing_verifications(project_dir)
    except Exception:
        pass  # Non-blocking — never fail the hook

    # --- Cross-Step Traceability safety net ---
    # Detect outputs with trace markers but no CT validation run.
    # Non-blocking: only logs warning, does not fail the hook.
    try:
        _check_missing_traceability(project_dir)
    except Exception:
        pass  # Non-blocking — never fail the hook

    # --- Domain Knowledge Structure safety net ---
    # Detect DKS file + DKS markers in outputs but no DK validation run.
    # Non-blocking: only logs warning, does not fail the hook.
    try:
        _check_missing_dks_validation(project_dir)
    except Exception:
        pass  # Non-blocking — never fail the hook

    # --- Abductive Diagnosis safety net ---
    # Detect retry-count files without corresponding diagnosis logs.
    # Non-blocking: only logs warning, does not fail the hook.
    try:
        _check_missing_diagnosis(project_dir)
    except Exception:
        pass  # Non-blocking — never fail the hook

    # --- ULW Compliance safety net ---
    # Check ULW Intensifier compliance and warn on violations.
    # Non-blocking: only logs warning to stderr, does not fail the hook.
    try:
        _check_ulw_compliance_safety_net(entries)
    except Exception:
        pass  # Non-blocking — never fail the hook

    # --- Context Budget Profiling ---
    # Estimate token consumption by category for observability.
    # Non-blocking: write budget report, never fail the hook.
    try:
        _update_context_budget(snapshot_dir, entries, work_log)
    except Exception:
        pass  # Non-blocking — never fail the hook

    # --- Lightweight Auto GC ---
    # Detect SOT drift, broken docs/ references, stale work_log.
    # Non-blocking: only logs warnings to stderr, never modifies SOT.
    try:
        _lightweight_gc(project_dir, snapshot_dir)
    except Exception:
        pass  # Non-blocking — never fail the hook

    # Cleanup old snapshots
    cleanup_snapshots(snapshot_dir)


def _read_offset(offset_file):
    """Read last saved transcript byte offset."""
    try:
        if os.path.exists(offset_file):
            with open(offset_file, "r") as f:
                return int(f.read().strip())
    except (ValueError, IOError):
        pass
    return 0


def _write_offset(offset_file, size):
    """Write current transcript byte offset."""
    try:
        with open(offset_file, "w") as f:
            f.write(str(size))
    except IOError:
        pass


def _generate_decision_log_if_needed(project_dir, entries):
    """Detect auto-approved (human) steps and generate Decision Logs if missing.

    This is a SUPPLEMENTARY safety net. Claude itself should generate
    Decision Logs as primary. This hook catches any that were missed.

    P1 Compliance: Pattern detection is regex-based (deterministic).
    SOT Compliance: Only writes to autopilot-logs/ (not SOT).
    """
    import re

    ap_state = read_autopilot_state(project_dir)
    if not ap_state:
        return  # Autopilot not active — nothing to do

    # Search assistant texts for auto-approve patterns
    AUTO_APPROVE_PATTERNS = [
        re.compile(r'autopilot.*auto[\s-]?approv', re.IGNORECASE),
        re.compile(r'자동\s*승인', re.IGNORECASE),
        re.compile(r'\(human\).*단계.*자동', re.IGNORECASE),
        re.compile(r'auto[\s-]?approve.*step\s*(\d+)', re.IGNORECASE),
        re.compile(r'step[\s-]*(\d+).*auto[\s-]?approv', re.IGNORECASE),
        re.compile(r'autopilot-logs/step-(\d+)', re.IGNORECASE),
    ]

    assistant_texts = [
        e for e in entries
        if e.get("type") == "assistant_text"
    ]

    detected_steps = set()
    for text_entry in assistant_texts:
        content = text_entry.get("content", "")
        for pattern in AUTO_APPROVE_PATTERNS:
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, str) and match.isdigit():
                    detected_steps.add(int(match))

        # Also detect "step N" near auto-approve context
        if any(p.search(content) for p in AUTO_APPROVE_PATTERNS[:3]):
            step_nums = re.findall(r'step[\s-]*(\d+)', content, re.IGNORECASE)
            for sn in step_nums:
                detected_steps.add(int(sn))

    if not detected_steps:
        return

    # Create autopilot-logs directory
    logs_dir = os.path.join(project_dir, "autopilot-logs")
    os.makedirs(logs_dir, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for step_num in sorted(detected_steps):
        log_path = os.path.join(logs_dir, f"step-{step_num}-decision.md")
        if os.path.exists(log_path):
            continue  # Already exists — don't overwrite (Claude's version is primary)

        log_content = (
            f"# Decision Log — Step {step_num}\n\n"
            f"- **Step**: {step_num}\n"
            f"- **Checkpoint Type**: (human) — auto-approved\n"
            f"- **Decision**: Auto-approved (Autopilot mode)\n"
            f"- **Rationale**: Quality-maximizing default (절대 기준 1)\n"
            f"- **Timestamp**: {now}\n"
            f"- **Source**: Hook safety net (generate_context_summary.py)\n"
            f"\n"
            f"> Note: This log was generated by the Stop hook as a safety net.\n"
            f"> Claude's own Decision Log (if generated) takes precedence.\n"
        )
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(log_content)
        except Exception:
            pass  # Non-blocking


def _check_missing_reviews(project_dir):
    """Detect steps with pACS logs but no corresponding review reports.

    Safety net: If a step has pacs-logs/step-N-pacs.md but no
    review-logs/step-N-review.md, log a warning to stderr.
    This catches cases where the Adversarial Review was skipped
    for a step that has Review: specified in the workflow.

    P1 Compliance: File existence check (deterministic).
    SOT Compliance: Read-only.
    Non-blocking: Only logs to stderr, never fails.
    """
    pacs_dir = os.path.join(project_dir, "pacs-logs")
    review_dir = os.path.join(project_dir, "review-logs")

    if not os.path.isdir(pacs_dir):
        return

    step_pattern = re.compile(r"^step-(\d+)-pacs\.md$")

    for fname in os.listdir(pacs_dir):
        match = step_pattern.match(fname)
        if not match:
            continue
        step_num = match.group(1)
        review_file = os.path.join(review_dir, f"step-{step_num}-review.md")
        if not os.path.exists(review_file):
            print(
                f"[Review Safety Net] Step {step_num}: pACS log exists but "
                f"no review report found at review-logs/step-{step_num}-review.md",
                file=sys.stderr,
            )


def _check_missing_translations(project_dir):
    """Detect steps with translation pACS logs but no translation files.

    Safety net: If a step has pacs-logs/step-N-translation-pacs.md but no
    corresponding .ko.md file, log a warning to stderr.
    This catches cases where the Translation was started (pACS scored)
    but the output file is missing.

    P1 Compliance: File existence check (deterministic).
    SOT Compliance: Read-only.
    Non-blocking: Only logs to stderr, never fails.
    """
    pacs_dir = os.path.join(project_dir, "pacs-logs")
    translations_dir = os.path.join(project_dir, "translations")

    if not os.path.isdir(pacs_dir):
        return

    step_pattern = re.compile(r"^step-(\d+)-translation-pacs\.md$")

    for fname in os.listdir(pacs_dir):
        match = step_pattern.match(fname)
        if not match:
            continue
        step_num = match.group(1)

        # Check 3 possible locations for translation files
        found = False

        # Location 1: translations/step-N*.ko.md
        if os.path.isdir(translations_dir):
            try:
                for tf in os.listdir(translations_dir):
                    if tf.startswith(f"step-{step_num}") and tf.endswith(".ko.md"):
                        found = True
                        break
            except OSError:
                pass

        # Location 2: Any .ko.md in project (check SOT outputs)
        if not found:
            try:
                from _context_lib import _find_translation_files_for_step
                files = _find_translation_files_for_step(project_dir, int(step_num))
                if files:
                    found = True
            except Exception:
                pass  # Graceful fallback — already checked translations/ dir

        if not found:
            print(
                f"[Translation Safety Net] Step {step_num}: translation pACS log "
                f"exists but no .ko.md file found",
                file=sys.stderr,
            )


def _check_missing_verifications(project_dir):
    """Detect steps with pACS logs but no corresponding verification reports.

    Safety net: If a step has pacs-logs/step-N-pacs.md but no
    verification-logs/step-N-verify.md, log a warning to stderr.
    This catches cases where the Verification Gate was skipped
    but pACS was still scored (L1 should precede L1.5).

    P1 Compliance: File existence check (deterministic).
    SOT Compliance: Read-only.
    Non-blocking: Only logs to stderr, never fails.
    """
    pacs_dir = os.path.join(project_dir, "pacs-logs")
    verify_dir = os.path.join(project_dir, "verification-logs")

    if not os.path.isdir(pacs_dir):
        return

    step_pattern = re.compile(r"^step-(\d+)-pacs\.md$")

    for fname in os.listdir(pacs_dir):
        match = step_pattern.match(fname)
        if not match:
            continue
        step_num = match.group(1)
        verify_file = os.path.join(verify_dir, f"step-{step_num}-verify.md")
        if not os.path.exists(verify_file):
            print(
                f"[Verification Safety Net] Step {step_num}: pACS log exists but "
                f"no verification report found at verification-logs/step-{step_num}-verify.md",
                file=sys.stderr,
            )


def _check_missing_traceability(project_dir):
    """Detect outputs with trace markers but no CT validation evidence.

    Safety net: Scans SOT outputs for files containing [trace:step-N:...]
    markers. If trace markers exist in an output but no corresponding
    validate_traceability.py invocation is evident (checked via work_log
    or stdout capture), logs a warning.

    Simpler heuristic: If pacs-logs/step-N-pacs.md exists (step completed)
    AND the step's output contains [trace:step-...] markers, warn if the
    Orchestrator may have skipped CT validation. Since CT validation
    outputs to stdout (no log file), we check work_log for the command.

    P1 Compliance: File content regex scan (deterministic).
    SOT Compliance: Read-only.
    Non-blocking: Only logs to stderr, never fails.
    """
    pacs_dir = os.path.join(project_dir, "pacs-logs")
    if not os.path.isdir(pacs_dir):
        return

    # Import trace marker regex from shared library
    try:
        from _context_lib import _TRACE_MARKER_RE, sot_paths
    except ImportError:
        return

    # Load SOT to resolve output paths
    sot_data = None
    try:
        import yaml
        for sp in sot_paths(project_dir):
            if os.path.exists(sp):
                with open(sp, "r", encoding="utf-8") as f:
                    sot_data = yaml.safe_load(f) or {}
                break
    except Exception:
        return

    if not sot_data:
        return

    outputs = sot_data.get("outputs", {})
    if not outputs and isinstance(sot_data.get("workflow"), dict):
        outputs = sot_data["workflow"].get("outputs", {})

    step_pattern = re.compile(r"^step-(\d+)-pacs\.md$")

    for fname in os.listdir(pacs_dir):
        match = step_pattern.match(fname)
        if not match:
            continue
        step_num = match.group(1)
        step_key = f"step-{step_num}"

        # Get output path for this step
        output_path_raw = outputs.get(step_key)
        if not output_path_raw:
            continue

        output_path = os.path.join(project_dir, output_path_raw)
        if not os.path.exists(output_path):
            continue

        # Check if output contains trace markers
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            markers = _TRACE_MARKER_RE.findall(content)
            if len(markers) >= 3:
                # Output has trace markers — check if work_log has CT validation
                work_log = os.path.join(
                    project_dir, ".claude", "context-snapshots", "work_log.jsonl"
                )
                ct_validated = False
                if os.path.exists(work_log):
                    try:
                        with open(work_log, "r", encoding="utf-8") as wf:
                            for line in wf:
                                if "validate_traceability" in line and f"--step {step_num}" in line:
                                    ct_validated = True
                                    break
                    except Exception:
                        pass

                if not ct_validated:
                    print(
                        f"[Traceability Safety Net] Step {step_num}: output contains "
                        f"{len(markers)} trace markers but no CT validation detected. "
                        f"Run: python3 .claude/hooks/scripts/validate_traceability.py "
                        f"--step {step_num} --project-dir .",
                        file=sys.stderr,
                    )
        except (IOError, UnicodeDecodeError):
            pass  # Binary files or read errors — skip silently


def _check_missing_dks_validation(project_dir):
    """Detect DKS markers in outputs without DK validation.

    Safety net: If domain-knowledge.yaml exists AND any step output
    contains [dks:xxx] markers, warn if no DK validation evidence
    is found in work_log.

    P1 Compliance: File existence + regex scan (deterministic).
    SOT Compliance: Read-only.
    Non-blocking: Only logs to stderr, never fails.
    """
    dk_path = os.path.join(project_dir, "domain-knowledge.yaml")
    if not os.path.exists(dk_path):
        return  # No DKS file — nothing to validate

    # Import DKS regex from shared library
    try:
        from _context_lib import _DKS_REF_RE, sot_paths
    except ImportError:
        return

    # Load SOT
    sot_data = None
    try:
        import yaml
        for sp in sot_paths(project_dir):
            if os.path.exists(sp):
                with open(sp, "r", encoding="utf-8") as f:
                    sot_data = yaml.safe_load(f) or {}
                break
    except Exception:
        return

    if not sot_data:
        return

    outputs = sot_data.get("outputs", {})
    if not outputs and isinstance(sot_data.get("workflow"), dict):
        outputs = sot_data["workflow"].get("outputs", {})

    # Check work_log for any DK validation command
    work_log = os.path.join(
        project_dir, ".claude", "context-snapshots", "work_log.jsonl"
    )
    dk_validated = False
    if os.path.exists(work_log):
        try:
            with open(work_log, "r", encoding="utf-8") as wf:
                for line in wf:
                    if "validate_domain_knowledge" in line:
                        dk_validated = True
                        break
        except Exception:
            pass

    if dk_validated:
        return  # Already validated — no warning needed

    # Scan outputs for DKS markers (skip translation files — step-N-ko)
    for key, path_raw in outputs.items():
        if not key.startswith("step-") or not key.split("-")[1].isdigit():
            continue
        if key.endswith("-ko"):  # Skip Korean translation files
            continue

        output_path = os.path.join(project_dir, path_raw)
        if not os.path.exists(output_path):
            continue

        try:
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            dks_refs = _DKS_REF_RE.findall(content)
            if dks_refs:
                step_num = key.split("-")[1]
                print(
                    f"[DKS Safety Net] Step {step_num}: output contains "
                    f"{len(dks_refs)} [dks:...] markers but domain-knowledge.yaml "
                    f"validation not detected. Run: python3 .claude/hooks/scripts/"
                    f"validate_domain_knowledge.py --project-dir . --check-output "
                    f"--step {step_num}",
                    file=sys.stderr,
                )
                return  # One warning is enough — avoid spam
        except (IOError, UnicodeDecodeError):
            pass


def _check_missing_diagnosis(project_dir):
    """Detect retry-count files without corresponding diagnosis logs.

    Safety net: Scans gate-logs/ directories for .step-N-retry-count files.
    If a retry counter exists (retries > 0) but no corresponding diagnosis
    log is found in diagnosis-logs/, logs a warning to stderr.

    P1 Compliance: File existence checks (deterministic).
    SOT Compliance: Read-only.
    Non-blocking: Only logs to stderr, never fails.
    """
    gate_dirs = ["verification-logs", "pacs-logs", "review-logs"]
    gate_names = ["verification", "pacs", "review"]

    for gate_dir_name, gate_name in zip(gate_dirs, gate_names):
        gate_dir = os.path.join(project_dir, gate_dir_name)
        if not os.path.isdir(gate_dir):
            continue

        retry_pattern = re.compile(r"^\.step-(\d+)-retry-count$")
        try:
            for fname in os.listdir(gate_dir):
                match = retry_pattern.match(fname)
                if not match:
                    continue
                step_num = match.group(1)

                # Read retry count
                retry_path = os.path.join(gate_dir, fname)
                try:
                    with open(retry_path, "r", encoding="utf-8") as f:
                        retries = int(f.read().strip() or "0")
                except (ValueError, OSError):
                    retries = 0

                if retries <= 0:
                    continue

                # Check for corresponding diagnosis log
                diag_dir = os.path.join(project_dir, "diagnosis-logs")
                has_diagnosis = False
                if os.path.isdir(diag_dir):
                    for df in os.listdir(diag_dir):
                        if df.startswith(f"step-{step_num}-{gate_name}-") and df.endswith(".md"):
                            has_diagnosis = True
                            break

                if not has_diagnosis:
                    print(
                        f"[Diagnosis Safety Net] Step {step_num}: "
                        f"{gate_name} retry count={retries} but no diagnosis log "
                        f"found at diagnosis-logs/step-{step_num}-{gate_name}-*.md",
                        file=sys.stderr,
                    )
        except OSError:
            pass


def _check_ulw_compliance_safety_net(entries):
    """Check ULW Intensifier compliance and warn on violations.

    Safety net: If ULW is active and any of the 3 Intensifiers are violated,
    log a warning to stderr. This catches compliance issues that might not
    be visible in the snapshot alone.

    P1 Compliance: Delegates to check_ulw_compliance() (deterministic).
    Non-blocking: Only logs to stderr, never fails.
    """
    ulw_compliance = check_ulw_compliance(entries)
    if not ulw_compliance:
        return  # ULW not active

    warnings = ulw_compliance.get("warnings", [])
    for w in warnings:
        print(f"[ULW Compliance Safety Net] {w}", file=sys.stderr)


def _lightweight_gc(project_dir, snapshot_dir):
    """Lightweight garbage collection: detect drift and warn.

    Three checks, all read-only and non-blocking:
    1. SOT drift — outputs referencing non-existent files (+ absolute path detection)
    2. docs/ reference integrity — broken protocol file links across doc files
    3. Stale work_log — warn if work_log exceeds 500KB

    P1 Compliance: File-existence checks only (deterministic).
        - SOT parse failure explicitly reported (not silently skipped).
        - Absolute paths in SOT detected as drift.
        - docs/ regex covers backtick, markdown link, and bare path patterns.
        - gc-report.json validated after write (read-back check).
        - Write failure distinguished from "no issues" via stderr.
    SOT Compliance: Read-only — no file writes except gc-report.json.
    Non-blocking: Only logs to stderr; never raises exceptions to caller.
    """
    gc_issues = []

    # ── 1. SOT drift: outputs referencing non-existent files ──
    try:
        from _context_lib import sot_paths
        sot_data = None
        sot_found = False
        for sp in sot_paths(project_dir):
            if os.path.exists(sp):
                sot_found = True
                try:
                    if sp.endswith(".json"):
                        with open(sp, "r", encoding="utf-8") as f:
                            sot_data = json.load(f)
                    else:
                        import yaml
                        with open(sp, "r", encoding="utf-8") as f:
                            sot_data = yaml.safe_load(f) or {}
                except ImportError:
                    gc_issues.append({
                        "type": "sot_parse_error",
                        "detail": "PyYAML not installed — SOT drift check skipped",
                    })
                except Exception as e:
                    gc_issues.append({
                        "type": "sot_parse_error",
                        "detail": f"SOT parse failed ({type(e).__name__}) — drift check skipped",
                    })
                break

        if sot_data:
            outputs = sot_data.get("outputs", {})
            if isinstance(outputs, dict):
                for key, path_val in outputs.items():
                    if not isinstance(path_val, str):
                        gc_issues.append({
                            "type": "sot_drift",
                            "detail": f"outputs.{key} is {type(path_val).__name__}, expected string",
                        })
                        continue
                    # Detect absolute paths — SOT should use relative paths only
                    if os.path.isabs(path_val):
                        gc_issues.append({
                            "type": "sot_drift",
                            "detail": f"outputs.{key} → {path_val} (absolute path — must be relative)",
                        })
                        continue
                    full_path = os.path.join(project_dir, path_val)
                    if not os.path.exists(full_path):
                        gc_issues.append({
                            "type": "sot_drift",
                            "detail": f"outputs.{key} → {path_val} (file not found)",
                        })
            else:
                # outputs=None or non-dict type — both are SOT drift
                gc_issues.append({
                    "type": "sot_drift",
                    "detail": f"outputs is {type(outputs).__name__}, expected dict",
                })
    except Exception:
        pass  # sot_paths import failure — non-blocking

    # ── 2. docs/ reference integrity: protocol links in doc files ──
    # Covers: backtick `path`, markdown link (path), and bare path patterns
    _DOC_REF_RE = re.compile(r"(?:`|[\[(])(docs/protocols/[\w-]+\.md)(?:`|[\])])")
    try:
        claude_md = os.path.join(project_dir, "CLAUDE.md")
        if os.path.exists(claude_md):
            with open(claude_md, "r", encoding="utf-8") as f:
                claude_content = f.read()
            for match in _DOC_REF_RE.finditer(claude_content):
                ref_path = match.group(1)
                full_ref = os.path.join(project_dir, ref_path)
                if not os.path.exists(full_ref):
                    gc_issues.append({
                        "type": "broken_ref",
                        "detail": f"CLAUDE.md references {ref_path} (not found)",
                    })
    except Exception:
        pass

    # ── 3. Stale work_log: warn if > 500KB ──
    try:
        work_log_path = os.path.join(snapshot_dir, "work_log.jsonl")
        if os.path.exists(work_log_path):
            size_kb = os.path.getsize(work_log_path) / 1024
            if size_kb > 500:
                gc_issues.append({
                    "type": "large_work_log",
                    "detail": f"work_log.jsonl is {size_kb:.0f}KB (> 500KB threshold)",
                })
    except Exception:
        pass

    # ── Report ──
    report_path = os.path.join(snapshot_dir, "gc-report.json")
    if gc_issues:
        for issue in gc_issues:
            print(
                f"[Auto GC] {issue['type']}: {issue['detail']}",
                file=sys.stderr,
            )
        # Write gc-report.json with read-back validation
        try:
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "issues_count": len(gc_issues),
                "issues": gc_issues,
            }
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            # P1: Read-back validation — ensure write succeeded
            with open(report_path, "r", encoding="utf-8") as f:
                readback = json.load(f)
            if readback.get("issues_count") != len(gc_issues):
                print(
                    "[Auto GC] WARNING: gc-report.json read-back mismatch",
                    file=sys.stderr,
                )
        except Exception as e:
            print(
                f"[Auto GC] WARNING: gc-report.json write failed ({type(e).__name__})",
                file=sys.stderr,
            )
    else:
        # Clean up stale report if no issues
        if os.path.exists(report_path):
            try:
                os.remove(report_path)
            except Exception:
                pass


def _update_context_budget(snapshot_dir, entries, work_log):
    """Estimate and record context consumption by tool category.

    Writes context-budget.json with per-category token estimates.
    Token estimation uses rough heuristics (chars / 4 ≈ tokens).

    Non-blocking: called from main(), failures silently ignored.
    """
    # Rough token estimate: 1 token ≈ 4 characters (English/mixed)
    CHARS_PER_TOKEN = 4

    # Category buckets
    categories = {
        "read_files": {"calls": 0, "chars": 0},
        "edit_write": {"calls": 0, "chars": 0},
        "bash": {"calls": 0, "chars": 0},
        "search": {"calls": 0, "chars": 0},
        "agent": {"calls": 0, "chars": 0},
        "web": {"calls": 0, "chars": 0},
        "other_tools": {"calls": 0, "chars": 0},
        "assistant_text": {"calls": 0, "chars": 0},
        "user_text": {"calls": 0, "chars": 0},
    }

    _TOOL_CATEGORY_MAP = {
        "Read": "read_files", "Glob": "search", "Grep": "search",
        "Edit": "edit_write", "Write": "edit_write", "NotebookEdit": "edit_write",
        "Bash": "bash",
        "Agent": "agent",
        "WebFetch": "web", "WebSearch": "web",
    }

    for entry in entries:
        role = entry.get("role", "")
        content = entry.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                str(c.get("text", "") if isinstance(c, dict) else c)
                for c in content
            )
        char_count = len(str(content))

        if role == "user":
            categories["user_text"]["calls"] += 1
            categories["user_text"]["chars"] += char_count
        elif role == "assistant":
            # Check if this is a tool call
            tool_name = entry.get("tool_name", "")
            if tool_name:
                cat = _TOOL_CATEGORY_MAP.get(tool_name, "other_tools")
                categories[cat]["calls"] += 1
                categories[cat]["chars"] += char_count
            else:
                categories["assistant_text"]["calls"] += 1
                categories["assistant_text"]["chars"] += char_count
        elif role == "tool_result":
            # Tool results consume the most context — attribute to tool category
            tool_name = entry.get("tool_name", "")
            cat = _TOOL_CATEGORY_MAP.get(tool_name, "other_tools")
            categories[cat]["chars"] += char_count

    # Build budget report
    total_chars = sum(c["chars"] for c in categories.values())
    total_tokens_est = total_chars // CHARS_PER_TOKEN

    budget = {
        "total_estimated_tokens": total_tokens_est,
        "total_tool_calls": sum(c["calls"] for c in categories.values()),
        "categories": {},
    }

    for cat_name, data in sorted(
        categories.items(), key=lambda x: x[1]["chars"], reverse=True
    ):
        if data["chars"] == 0:
            continue
        pct = round(data["chars"] / total_chars * 100, 1) if total_chars > 0 else 0
        budget["categories"][cat_name] = {
            "calls": data["calls"],
            "estimated_tokens": data["chars"] // CHARS_PER_TOKEN,
            "percentage": pct,
        }

    # Top consumer warning
    if budget["categories"]:
        top = next(iter(budget["categories"]))
        top_pct = budget["categories"][top]["percentage"]
        if top_pct > 60:
            budget["warning"] = (
                f"'{top}' consuming {top_pct}% of context — "
                f"consider sub-agent delegation or output truncation"
            )

    budget_path = os.path.join(snapshot_dir, "context-budget.json")
    with open(budget_path, "w", encoding="utf-8") as f:
        json.dump(budget, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Non-blocking: log error but don't crash
        print(f"generate_context_summary error: {e}", file=sys.stderr)
        sys.exit(0)
