#!/usr/bin/env python3
"""
Context Preservation System — restore_context.py

Triggered by: SessionStart (all sources: clear, compact, resume, startup)

RLM Pattern Implementation:
  - Outputs a POINTER to the full snapshot file + brief summary
  - Does NOT inject the full snapshot content into stdout
  - Claude uses Read tool to load the external file when needed
  - This treats the snapshot as an "external environment object" (RLM)
  - Knowledge Archive: includes pointers to knowledge-index.jsonl and sessions/
  - Claude can Grep knowledge-index.jsonl for programmatic probing (RLM pattern)

Output (stdout, exit 0):
  [CONTEXT RECOVERY]
  pointer to .claude/context-snapshots/latest.md
  + brief summary (≤500 chars)
  + knowledge archive pointers (if available)

SOT Compliance:
  - Read-only: reads latest.md and state.yaml, never modifies
  - Verifies SOT consistency between snapshot and current state
"""

import os
import sys
import json
import time
from datetime import datetime

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _context_lib import (
    read_stdin_json, get_snapshot_dir, read_autopilot_state,
    validate_step_output, validate_sot_schema, sot_paths,
    extract_path_tags, aggregate_risk_scores, atomic_write,
)


# Maximum age (seconds) for snapshot restoration per source type
RESTORE_THRESHOLDS = {
    "clear": float("inf"),    # Always restore after /clear
    "compact": float("inf"),  # Always restore after compression
    "resume": 3600,           # 1 hour for resume
    "startup": 1800,          # 30 minutes for fresh startup
}


def main():
    input_data = read_stdin_json()

    # Determine source type
    source = input_data.get("source", "startup")

    # Determine project directory
    project_dir = os.environ.get(
        "CLAUDE_PROJECT_DIR",
        input_data.get("cwd", os.getcwd()),
    )

    snapshot_dir = get_snapshot_dir(project_dir)
    latest_path = os.path.join(snapshot_dir, "latest.md")

    # Check if snapshot exists
    if not os.path.exists(latest_path):
        sys.exit(0)  # No snapshot to restore — silent exit

    # Check age threshold
    snapshot_age = time.time() - os.path.getmtime(latest_path)
    max_age = RESTORE_THRESHOLDS.get(source, 1800)
    if snapshot_age > max_age:
        sys.exit(0)  # Snapshot too old for this source type

    # E6: Find best available snapshot (fallback if latest.md is inadequate)
    best_path, best_size = _find_best_snapshot(snapshot_dir, latest_path)
    fallback_note = ""
    if best_path != latest_path:
        latest_size = 0
        try:
            latest_size = os.path.getsize(latest_path)
        except OSError:
            pass
        fallback_note = (
            f"⚠️ latest.md ({latest_size}B)가 빈약하여 "
            f"더 풍부한 아카이브({best_size}B)를 참조합니다."
        )

    # Read snapshot for summary extraction
    try:
        with open(best_path, "r", encoding="utf-8") as f:
            snapshot_content = f.read()
    except Exception:
        sys.exit(0)

    if not snapshot_content.strip():
        sys.exit(0)

    # Extract brief summary from snapshot
    summary = _extract_brief_summary(snapshot_content)

    # Verify SOT consistency
    sot_warning = _verify_sot_consistency(snapshot_content, project_dir)

    # Predictive Debugging: Aggregate risk scores from Knowledge Archive
    # Runs once per SessionStart — writes cache for PreToolUse hook
    risk_data = _generate_risk_scores_cache(project_dir, snapshot_dir)

    # Build RLM-style recovery output (pointer + summary)
    recovery_output = _build_recovery_output(
        source=source,
        latest_path=best_path,  # E6: point to best available snapshot
        summary=summary,
        sot_warning=sot_warning,
        snapshot_age=snapshot_age,
        fallback_note=fallback_note,
        project_dir=project_dir,
        snapshot_content=snapshot_content,
        risk_data=risk_data,
    )

    # Output to stdout — Claude receives this as session context
    print(recovery_output)
    sys.exit(0)


def _extract_brief_summary(content):
    """Extract key information from snapshot for brief summary.

    Deterministic extraction from snapshot structure:
      - 현재 작업 (Current Task): first content line
      - 수정된 파일 (Modified Files): count of table rows
      - 참조된 파일 (Referenced Files): count of table rows
      - 대화 통계: numeric stats lines
    """
    summary_parts = []

    lines = content.split("\n")
    current_section = ""
    files_count = 0
    read_count = 0

    for line in lines:
        # Section header detection
        if line.startswith("## 현재 작업"):
            current_section = "task"
            continue
        elif line.startswith("## 결정론적 완료 상태"):
            current_section = "completion"
            continue
        elif line.startswith("## Git 변경 상태"):
            current_section = "git"
            continue
        elif line.startswith("## 수정된 파일"):
            current_section = "files"
            continue
        elif line.startswith("## 참조된 파일"):
            current_section = "reads"
            continue
        elif line.startswith("## 대화 통계"):
            current_section = "stats"
            continue
        elif line.startswith("## "):
            current_section = ""
            continue

        line = line.strip()
        if not line or line.startswith(">"):
            continue

        if current_section == "task":
            if line.startswith("**마지막 사용자 지시:**"):
                instruction = line.replace("**마지막 사용자 지시:**", "").strip()
                summary_parts.append(("최근 지시", instruction[:200]))
            elif len(summary_parts) < 1:
                summary_parts.append(("현재 작업", line[:200]))
        elif current_section == "completion" and line.startswith("- "):
            # "- Edit: 18회 호출 → 18 성공, 0 실패" 형태
            if "실패" in line or "성공" in line:
                summary_parts.append(("완료상태", line[:150]))
        elif current_section == "git" and line.startswith("```"):
            pass  # skip code block markers
        elif current_section == "git" and (line.startswith("M ") or line.startswith(" M") or line.startswith("A ") or line.startswith("??")):
            summary_parts.append(("git", line[:100]))
        elif current_section == "files" and (line.startswith("| `") or line.startswith("### `")):
            files_count += 1
            # C1: Extract file path for dynamic RLM hints
            if '`' in line:
                backtick_parts = line.split('`')
                if len(backtick_parts) >= 2 and backtick_parts[1]:
                    summary_parts.append(("수정_파일_경로", backtick_parts[1]))
        elif current_section == "reads" and line.startswith("| `"):
            read_count += 1
        elif current_section == "stats" and line.startswith("- "):
            summary_parts.append(("통계", line[:100]))
        # C1: Detect recent errors from completion state
        elif current_section == "completion" and "ERROR" in line:
            summary_parts.append(("에러", line[:200]))
        # C1: Detect recent tool errors from 최근 도구 활동 section
        elif "← ERROR" in line:
            summary_parts.append(("에러", line.strip()[:200]))

    # C1: Extract Autopilot section presence
    if "AUTOPILOT MODE ACTIVE" in content or "autopilot" in content.lower():
        for line in lines:
            if "현재 단계:" in line:
                summary_parts.append(("autopilot", line.strip()[:100]))
                break

    # C1: Extract ULW mode presence
    # D-7: ULW detection pattern must match _context_lib.py + validate_retry_budget.py
    if "ULW 상태" in content or "Ultrawork Mode State" in content:
        summary_parts.append(("ulw", "ULW (Ultrawork) Mode Active"))

    # C1: Extract active team info
    if "Agent Team" in content or "active_team" in content:
        for line in lines:
            if "tasks_pending" in line.lower() or "tasks_completed" in line.lower():
                summary_parts.append(("team", line.strip()[:100]))
                break

    # Add file counts as summary entries
    if files_count > 0:
        summary_parts.append(("수정 파일", f"{files_count}개 파일 수정됨"))
    if read_count > 0:
        summary_parts.append(("참조 파일", f"{read_count}개 파일 참조됨"))

    return summary_parts


def _verify_sot_consistency(snapshot_content, project_dir):
    """Check if current SOT matches snapshot's recorded SOT."""
    paths = sot_paths(project_dir)
    current_sot_exists = any(os.path.exists(p) for p in paths)

    if "SOT 파일 없음" in snapshot_content and not current_sot_exists:
        return None  # Consistent: both have no SOT

    if current_sot_exists:
        # Read current SOT modification time
        for sot_path in paths:
            if os.path.exists(sot_path):
                sot_mtime = datetime.fromtimestamp(
                    os.path.getmtime(sot_path)
                ).isoformat()

                # Check if snapshot recorded an older mtime
                if "수정 시각:" in snapshot_content:
                    for line in snapshot_content.split("\n"):
                        if "수정 시각:" in line:
                            recorded_time = line.split("수정 시각:")[1].strip()
                            if recorded_time != sot_mtime:
                                return (
                                    f"SOT가 snapshot 저장 이후 변경되었습니다. "
                                    f"기록: {recorded_time} → 현재: {sot_mtime}"
                                )
                break

    return None


def _build_recovery_output(source, latest_path, summary, sot_warning, snapshot_age, fallback_note="", project_dir=None, snapshot_content="", risk_data=None):
    """Build the RLM-style recovery output for SessionStart injection."""
    age_str = _format_age(snapshot_age)

    # Build header
    output_lines = [
        "[CONTEXT RECOVERY]",
        f"이전 세션이 {'clear' if source == 'clear' else 'compact' if source == 'compact' else source}되었습니다.",
        f"전체 복원 파일: {latest_path}",
        "",
    ]

    # Brief summary
    task_info = ""
    latest_instruction = ""
    files_info = ""
    reads_info = ""
    stats_info = []
    completion_info = []
    git_info = []
    error_info = []
    autopilot_info = ""
    team_info = ""
    ulw_info = ""

    for label, content in summary:
        if label == "현재 작업":
            task_info = content
        elif label == "최근 지시":
            latest_instruction = content
        elif label == "수정 파일":
            files_info = content
        elif label == "참조 파일":
            reads_info = content
        elif label == "통계":
            stats_info.append(content)
        elif label == "완료상태":
            completion_info.append(content)
        elif label == "git":
            git_info.append(content)
        elif label == "에러":
            error_info.append(content)
        elif label == "autopilot":
            autopilot_info = content
        elif label == "team":
            team_info = content
        elif label == "ulw":
            ulw_info = content
        # "수정_파일_경로" labels are consumed below for dynamic RLM hints (C2)

    if task_info:
        output_lines.append(f"■ 현재 작업: {task_info}")
    if latest_instruction:
        output_lines.append(f"■ 최근 지시: {latest_instruction}")
    output_lines.append(f"■ 마지막 저장: {age_str} 전")

    if stats_info:
        for s in stats_info[:3]:
            output_lines.append(f"■ {s}")
    if files_info:
        output_lines.append(f"■ {files_info}")
    if reads_info:
        output_lines.append(f"■ {reads_info}")

    # Completion state and git status (Change 4)
    if completion_info:
        output_lines.append(f"■ 완료상태: {'; '.join(completion_info[:3])}")
    if git_info:
        output_lines.append(f"■ Git: {', '.join(git_info[:5])}")
    # C1: Surface errors, autopilot, team state for immediate awareness
    if error_info:
        output_lines.append(f"■ ⚠ 최근 에러: {'; '.join(error_info[:3])}")
    if autopilot_info:
        output_lines.append(f"■ Autopilot: {autopilot_info}")
    if team_info:
        output_lines.append(f"■ Team: {team_info}")
    if ulw_info:
        output_lines.append(f"■ ULW: {ulw_info}")

    # E6: Fallback note (if using archive instead of latest.md)
    if fallback_note:
        output_lines.append("")
        output_lines.append(fallback_note)

    # SOT warning
    if sot_warning:
        output_lines.append("")
        output_lines.append(f"⚠️ {sot_warning}")

    # Knowledge Archive pointers (Area 1: Cross-Session)
    # Use get_snapshot_dir(project_dir) — NOT os.path.dirname(latest_path)
    # (E6 fallback may point latest_path to sessions/ subdirectory, breaking path derivation)
    ka_snapshot_dir = get_snapshot_dir(project_dir) if project_dir else os.path.dirname(latest_path)
    ki_path = os.path.join(ka_snapshot_dir, "knowledge-index.jsonl")
    sessions_dir = os.path.join(ka_snapshot_dir, "sessions")

    has_archive = os.path.exists(ki_path) or os.path.isdir(sessions_dir)
    if has_archive:
        output_lines.append("")
        if os.path.exists(ki_path):
            output_lines.append(f"■ 과거 세션 인덱스: {ki_path}")
            recent = _get_recent_sessions(ki_path, 3)
            for s in recent:
                ts = s.get("timestamp", "")[:10]
                task = s.get("user_task", "(기록 없음)")[:80]
                output_lines.append(f"  - [{ts}] {task}")
            # CM-4: RLM query examples — activate programmatic probing
            output_lines.append("  RLM 쿼리 예시 (Grep tool 사용):")
            output_lines.append(f'  - Grep "design_decisions" {ki_path} → 설계 결정 포함 세션')
            output_lines.append(f'  - Grep "error_patterns" {ki_path} → 에러 패턴 포함 세션')
            output_lines.append(f'  - Grep "phase_flow.*implementation" {ki_path} → 구현 단계 세션')
            output_lines.append(f'  - Grep "ulw_active" {ki_path} → ULW 세션')
            output_lines.append(f'  - Grep "diagnosis_patterns" {ki_path} → 진단 패턴 포함 세션')
            # C2: Dynamic RLM query hints (context-aware)
            file_paths = [c for l, c in summary if l == "수정_파일_경로"]
            if file_paths:
                path_tags = extract_path_tags(file_paths)
                for tag in path_tags[:2]:
                    output_lines.append(f'  - Grep "tags.*{tag}" {ki_path} → {tag} 관련 세션')
            if error_info:
                output_lines.append(f'  - Grep "resolution" {ki_path} → 에러→해결 패턴 포함 세션')

            # P1-1: Proactive Error→Resolution surfacing
            # Surface recent error patterns + resolutions directly (no manual Grep)
            error_resolutions = _extract_recent_error_resolutions(recent)
            if error_resolutions:
                output_lines.append("")
                output_lines.append("■ 최근 에러→해결 패턴 (자동 표면화):")
                for er in error_resolutions[:3]:
                    output_lines.append(f"  - {er}")

            # P1-2: Proactive Diagnosis Pattern surfacing
            # Surface recent diagnosis patterns for cross-session learning
            diagnosis_hints = _extract_recent_diagnosis_patterns(recent)
            if diagnosis_hints:
                output_lines.append("")
                output_lines.append("■ 최근 진단 패턴 (자동 표면화):")
                for dh in diagnosis_hints[:3]:
                    output_lines.append(f"  - {dh}")

        if os.path.isdir(sessions_dir):
            output_lines.append(f"■ 세션 아카이브: {sessions_dir}")

    # Autopilot Mode context injection (conditional)
    # Uses project_dir passed from main() — NOT derived from snapshot path
    # (path derivation fails when best_path points to sessions/ subdirectory)
    if project_dir:
        try:
            ap_state = read_autopilot_state(project_dir)
            if ap_state:
                output_lines.append("")
                output_lines.append("━━━ AUTOPILOT MODE ACTIVE ━━━")
                wf_name = ap_state.get("workflow_name", "N/A")
                cur_step = ap_state.get("current_step", "?")
                approved = ap_state.get("auto_approved_steps", [])
                output_lines.append(f"워크플로우: {wf_name}")
                output_lines.append(f"현재 단계: Step {cur_step}")
                if approved:
                    output_lines.append(f"자동 승인된 단계: {approved}")
                output_lines.append("")
                output_lines.append("■ AUTOPILOT EXECUTION RULES (MANDATORY):")
                output_lines.append("  1. EVERY step must be FULLY executed — NO step skipping")
                output_lines.append("  2. EVERY output must be COMPLETE — NO abbreviation")
                output_lines.append("  3. (human) steps: auto-approve with QUALITY-MAXIMIZING default")
                output_lines.append("  4. (hook) exit code 2: STILL BLOCKS — autopilot does NOT override")
                output_lines.append("  5. BEFORE advancing: verify output EXISTS + NON-EMPTY → record in SOT")
                output_lines.append("  6. (human) step 완료 시: autopilot-logs/step-N-decision.md 생성")

                # SOT schema validation (P1 — structural integrity)
                schema_warnings = validate_sot_schema(ap_state)
                if schema_warnings:
                    output_lines.append("")
                    output_lines.append("■ SOT SCHEMA VALIDATION:")
                    for warning in schema_warnings:
                        output_lines.append(f"  [WARN] {warning}")

                # Previous step output validation
                outputs = ap_state.get("outputs", {})
                if outputs:
                    output_lines.append("")
                    output_lines.append("■ PREVIOUS STEP OUTPUT VALIDATION:")
                    for step_key in sorted(outputs.keys(), key=lambda k: int(k.replace("step-", "")) if k.startswith("step-") and k.replace("step-", "").isdigit() else 0):
                        step_num = int(step_key.replace("step-", "")) if step_key.startswith("step-") and step_key.replace("step-", "").isdigit() else 0
                        if step_num > 0:
                            is_valid, reason = validate_step_output(
                                project_dir, step_num, outputs
                            )
                            mark = "[OK]" if is_valid else "[FAIL]"
                            output_lines.append(f"  {mark} {reason}")
        except Exception:
            pass  # Non-blocking — autopilot injection is supplementary

    # ULW (Ultrawork) Mode context injection (conditional)
    # Detects from snapshot content — transcript not available at SessionStart
    # "startup" excluded: ULW deactivates implicitly in new sessions (design decision)
    # Only inject for clear/compact/resume where the same logical session continues
    if (snapshot_content
            and source != "startup"
            and ("ULW 상태" in snapshot_content or "Ultrawork Mode State" in snapshot_content)):
        output_lines.append("")
        output_lines.append("━━━ ULTRAWORK (ULW) MODE ACTIVE ━━━")
        output_lines.append("")
        output_lines.append("■ ULW INTENSIFIERS (MANDATORY — thoroughness overlay):")
        output_lines.append("  1. Sisyphus Persistence — 최대 3회 재시도, 각 시도는 다른 접근법. 100% 완료 또는 불가 사유 보고")
        output_lines.append("  2. Mandatory Task Decomposition — 요청을 TaskCreate로 분해, TaskUpdate로 추적, TaskList로 검증")
        output_lines.append("  3. Bounded Retry Escalation — 동일 대상 3회 초과 재시도 금지(품질 게이트는 별도 예산 적용), 초과 시 사용자 에스컬레이션")

        # Detect Autopilot combination state
        ap_state = read_autopilot_state(project_dir)
        if ap_state:
            output_lines.append("")
            output_lines.append("■ ULW + AUTOPILOT COMBINED: 품질 게이트 재시도 한도 10→15회 상향")

    # Predictive Debugging: Surface high-risk files
    if risk_data and isinstance(risk_data, dict):
        top_risk = risk_data.get("top_risk_files", [])
        files_map = risk_data.get("files", {})
        data_sessions = risk_data.get("data_sessions", 0)
        if top_risk and data_sessions >= 5:
            output_lines.append("")
            output_lines.append("■ PREDICTIVE DEBUGGING — 고위험 파일 (과거 에러 이력 기반):")
            for rf in top_risk[:5]:
                fdata = files_map.get(rf, {})
                score = fdata.get("risk_score", 0)
                ec = fdata.get("error_count", 0)
                types = fdata.get("error_types", {})
                types_str = ", ".join(
                    f"{k}:{v}" for k, v in sorted(
                        types.items(), key=lambda x: x[1], reverse=True
                    )[:3]
                )
                rr = fdata.get("resolution_rate", 0)
                output_lines.append(
                    f"  ⚠ {rf} — score:{score:.1f}, errors:{ec} ({types_str}), "
                    f"resolution:{rr:.0%}"
                )

    # Instruction for Claude
    output_lines.extend([
        "",
        "⚠️ 작업을 계속하기 전에 반드시 위 파일을 Read tool로 읽어",
        "   이전 세션의 전체 맥락을 복원하세요.",
    ])

    return "\n".join(output_lines)


def _get_recent_sessions(ki_path, n=3):
    """Read last N entries from knowledge-index.jsonl.

    Deterministic: reads file, parses JSON lines, returns last N.
    Non-blocking: returns empty list on any error.
    """
    try:
        entries = []
        with open(ki_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-n:] if entries else []
    except Exception:
        return []


def _extract_recent_error_resolutions(recent_sessions):
    """P1-1: Extract error→resolution pairs from recent Knowledge Archive sessions.

    Proactively surfaces past error patterns and their resolutions at
    SessionStart, eliminating the need for manual Grep queries.

    P1 Compliance: Deterministic extraction from structured JSON data.
    Returns: list of human-readable strings (max 3).
    """
    results = []
    for session in reversed(recent_sessions):
        error_patterns = session.get("error_patterns", [])
        if not isinstance(error_patterns, list):
            continue
        for ep in error_patterns:
            if not isinstance(ep, dict):
                continue
            etype = ep.get("type", "unknown")
            tool = ep.get("tool", "?")
            efile = ep.get("file", "")
            resolution = ep.get("resolution")
            if isinstance(resolution, dict) and resolution:
                res_tool = resolution.get("tool", "?")
                res_file = resolution.get("file", "")
                loc = f" in {efile}" if efile else ""
                res_loc = f" on {res_file}" if res_file else ""
                results.append(
                    f"{etype}{loc} ({tool}) → 해결: {res_tool}{res_loc}"
                )
            elif etype != "unknown":
                loc = f" in {efile}" if efile else ""
                results.append(
                    f"{etype}{loc} ({tool}) → 해결: 미확인"
                )
        if len(results) >= 3:
            break
    return results[:3]


def _extract_recent_diagnosis_patterns(recent_sessions):
    """P1-2: Extract diagnosis patterns from recent Knowledge Archive sessions.

    Proactively surfaces past diagnosis history (step, gate, hypothesis) at
    SessionStart, enabling cross-session learning for retry quality improvement.
    Symmetric with _extract_recent_error_resolutions (P1-1).

    P1 Compliance: Deterministic extraction from structured JSON data.
    Returns: list of human-readable strings (max 3).
    """
    results = []
    for session in reversed(recent_sessions):
        diagnosis_patterns = session.get("diagnosis_patterns", [])
        if not isinstance(diagnosis_patterns, list):
            continue
        for dp in diagnosis_patterns:
            if not isinstance(dp, dict):
                continue
            step = dp.get("step")
            gate = dp.get("gate", "?")
            hyp = dp.get("selected_hypothesis", "?")
            ev_count = dp.get("evidence_count", 0)
            step_str = f"Step {step}" if step else "Step ?"
            results.append(
                f"{step_str} {gate} → {hyp} (evidence: {ev_count}건)"
            )
        if len(results) >= 3:
            break
    return results[:3]


def _find_best_snapshot(snapshot_dir, latest_path):
    """E6: Find the best available snapshot when latest.md is inadequate.

    Quality criterion: file size (more structured data = larger file).
    P1 Compliance: file size is a deterministic metric.

    Falls back to sessions/ archive if latest.md has < 3KB of content
    (indicating a likely empty or minimal snapshot).
    """
    MIN_QUALITY_SIZE = 3000  # bytes

    latest_size = 0
    try:
        if os.path.exists(latest_path):
            latest_size = os.path.getsize(latest_path)
    except OSError:
        pass

    if latest_size >= MIN_QUALITY_SIZE:
        return latest_path, latest_size  # Sufficient quality

    # Scan sessions/ for a better recent archive
    sessions_dir = os.path.join(snapshot_dir, "sessions")
    if not os.path.isdir(sessions_dir):
        return latest_path, latest_size

    best_path = latest_path
    best_size = latest_size

    try:
        for fname in os.listdir(sessions_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(sessions_dir, fname)
            fsize = os.path.getsize(fpath)
            fmtime = os.path.getmtime(fpath)

            # Only consider archives from the last hour, larger than current best
            if (time.time() - fmtime) < 3600 and fsize > best_size:
                best_path = fpath
                best_size = fsize
    except Exception:
        pass

    return best_path, best_size


def _format_age(seconds):
    """Format age in seconds to human-readable string."""
    if seconds < 60:
        return f"{int(seconds)}초"
    elif seconds < 3600:
        return f"{int(seconds / 60)}분"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}시간"
    else:
        return f"{int(seconds / 86400)}일"


def _generate_risk_scores_cache(project_dir, snapshot_dir):
    """Generate risk-scores.json cache for PreToolUse hook.

    Called once per SessionStart. Writes cache to context-snapshots/.
    Non-blocking: returns empty dict on any error.

    P1 Compliance: Delegates to aggregate_risk_scores() which is
    deterministic arithmetic. Cache write uses atomic_write().
    """
    try:
        ki_path = os.path.join(snapshot_dir, "knowledge-index.jsonl")
        risk_data = aggregate_risk_scores(ki_path, project_dir)

        # Write cache for predictive_debug_guard.py
        cache_path = os.path.join(snapshot_dir, "risk-scores.json")
        cache_json = json.dumps(risk_data, ensure_ascii=False, indent=2)
        atomic_write(cache_path, cache_json)

        return risk_data
    except Exception:
        return {}


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Non-blocking: log error but don't crash the hook
        print(f"restore_context error: {e}", file=sys.stderr)
        sys.exit(0)
