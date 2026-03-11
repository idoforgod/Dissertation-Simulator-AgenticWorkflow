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
import re
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
    SNAPSHOT_SECTION_MARKERS,
    _extract_thesis_continuity,  # Phase 1-A: reuse from shared lib (no duplication)
)


# Module-level compiled regex (process-level singleton)
_SECTION_MARKER_RE = re.compile(r'<!-- SECTION:(\w+) -->')
_TOKENIZE_SPLIT_RE = re.compile(r'[^a-zA-Z0-9가-힣_\-./]+')


_ENGLISH_STOP_WORDS = frozenset({
    "is", "to", "do", "an", "if", "or", "in", "on", "at", "as",
    "be", "by", "no", "so", "up", "we", "it", "of", "am", "he",
    "me", "my", "us", "vs",
})

# A-2: Extended stop words for design decision token matching.
# _tokenize() filters 2-char stops, but decision sentences contain common
# 3+ char words (verbs, prepositions) that cause false relevance matches.
# Technical terms (P1, SOT, CCP, LLM, etc.) are preserved by _tokenize's
# acronym extraction and are NOT in this list.
_DECISION_EXTRA_STOP_WORDS = frozenset({
    "the", "for", "and", "but", "not", "with", "from", "that", "this",
    "was", "are", "were", "has", "had", "have", "been", "being",
    "did", "does", "will", "can", "may", "its", "all", "also",
    "into", "than", "then", "when", "which", "who", "how", "each",
    "use", "used", "using", "added", "add", "switched", "changed",
    "moved", "removed", "made", "new", "now", "based", "because",
    "instead", "more", "only", "after", "before", "between", "about",
    "over", "per", "via", "due",
})


def _tokenize(text):
    """Split text into keyword tokens for relevance scoring.

    P1 Compliance: Deterministic — regex split + filter.
    Preserves Korean characters, file path segments, and identifiers.
    M10: Minimum length reduced from 3 to 2; uppercase acronyms (2+ chars) preserved.
    Stop words filtered to prevent English 2-char noise from inflating scores.
    """
    if not text:
        return set()
    # M10: Extract uppercase acronyms (2+ chars) before lowercasing
    acronyms = {t for t in _TOKENIZE_SPLIT_RE.split(text) if len(t) >= 2 and t.isupper()}
    tokens = _TOKENIZE_SPLIT_RE.split(text.lower())
    # M10: Changed minimum token length from 3 to 2
    result = {t for t in tokens if len(t) > 1 and t not in _ENGLISH_STOP_WORDS}
    # M10: Merge back lowercase versions of acronyms (already included) + original case
    result.update(a.lower() for a in acronyms)
    return result


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

    # Extract compression audit trail (if snapshot was compressed)
    compression_note = _extract_compression_audit(snapshot_content)

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
        compression_note=compression_note,
    )

    # Output to stdout — Claude receives this as session context
    print(recovery_output)
    sys.exit(0)


def _extract_brief_summary(content):
    """Extract key information from snapshot for brief summary.

    P1-RLM Selective Peek: Uses SECTION markers for precise section extraction
    when available. Falls back to legacy line-by-line parsing for pre-P1 snapshots.

    Deterministic extraction from snapshot structure:
      - 현재 작업 (Current Task): first content line
      - 수정된 파일 (Modified Files): count of table rows
      - 참조된 파일 (Referenced Files): count of table rows
      - 대화 통계: numeric stats lines
    """
    # P1-RLM: Try section-marker-based extraction first
    sections = parse_snapshot_sections(content)
    if "_full" not in sections:
        return _extract_summary_from_sections(sections, content)

    # Fallback: legacy line-by-line parsing (pre-P1 snapshots without markers)
    return _extract_summary_legacy(content)


def _extract_summary_from_sections(sections, full_content):
    """P1-RLM: Extract summary using parsed SECTION markers.

    Direct section access eliminates line-by-line scanning.
    Each section's content is parsed independently, reducing
    cross-section interference and improving extraction accuracy.
    """
    summary_parts = []

    # Task section
    task_text = sections.get("task", "")
    if task_text:
        for line in task_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(">") or line.startswith("<!--"):
                continue
            if line.startswith("**최근 지시") or line.startswith("**Latest Instruction"):
                instruction = line.split(":**", 1)[-1].strip() if ":**" in line else line
                summary_parts.append(("최근 지시", instruction[:200]))
            elif not any(l == "현재 작업" for l, _ in summary_parts):
                summary_parts.append(("현재 작업", line[:200]))

    # Completion state section
    completion_text = sections.get("completion", "")
    if completion_text:
        for line in completion_text.split("\n"):
            line = line.strip()
            if line.startswith("- ") and ("실패" in line or "성공" in line):
                summary_parts.append(("완료상태", line[:150]))
            elif "ERROR" in line:
                summary_parts.append(("에러", line[:200]))

    # Git section
    git_text = sections.get("git", "")
    if git_text:
        in_code_block = False
        for line in git_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block and (stripped.startswith("M ") or stripped.startswith(" M") or
                                  stripped.startswith("A ") or stripped.startswith("??")):
                summary_parts.append(("git", stripped[:100]))

    # Modified files section
    files_count = 0
    files_text = sections.get("modified_files", "")
    if files_text:
        for line in files_text.split("\n"):
            line = line.strip()
            if line.startswith("| `") or line.startswith("### `"):
                files_count += 1
                if '`' in line:
                    backtick_parts = line.split('`')
                    if len(backtick_parts) >= 2 and backtick_parts[1]:
                        summary_parts.append(("수정_파일_경로", backtick_parts[1]))

    # Referenced files section
    read_count = 0
    refs_text = sections.get("referenced_files", "")
    if refs_text:
        for line in refs_text.split("\n"):
            if line.strip().startswith("| `"):
                read_count += 1

    # Statistics section
    stats_text = sections.get("statistics", "")
    if stats_text:
        for line in stats_text.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                summary_parts.append(("통계", line[:100]))

    # Error detection from recent tool activity (in completion or resume sections)
    for section_key in ("completion", "resume"):
        sec_text = sections.get(section_key, "")
        if "← ERROR" in sec_text:
            for line in sec_text.split("\n"):
                if "← ERROR" in line:
                    summary_parts.append(("에러", line.strip()[:200]))

    # Autopilot section (direct — no full-content scan needed)
    autopilot_text = sections.get("autopilot", "")
    if autopilot_text:
        for line in autopilot_text.split("\n"):
            if "현재 단계:" in line:
                summary_parts.append(("autopilot", line.strip()[:100]))
                break

    # ULW section (direct — no full-content scan needed)
    ulw_text = sections.get("ulw", "")
    if ulw_text:
        summary_parts.append(("ulw", "ULW (Ultrawork) Mode Active"))

    # Team section (direct)
    team_text = sections.get("team", "")
    if team_text:
        for line in team_text.split("\n"):
            if "tasks_pending" in line.lower() or "tasks_completed" in line.lower():
                summary_parts.append(("team", line.strip()[:100]))
                break

    # File counts
    if files_count > 0:
        summary_parts.append(("수정 파일", f"{files_count}개 파일 수정됨"))
    if read_count > 0:
        summary_parts.append(("참조 파일", f"{read_count}개 파일 참조됨"))

    return summary_parts


def _extract_summary_legacy(content):
    """Legacy line-by-line summary extraction for pre-P1 snapshots.

    Preserved for backward compatibility with snapshots that lack
    <!-- SECTION: --> markers.
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


# =============================================================================
# MEMORY.md Health Check (Improvement A — deterministic, P1 compliant)
# =============================================================================

# Pre-compiled regex for duplicate header detection
_MEMORY_HEADER_RE = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)


def _check_memory_health(project_dir):
    """Deterministic health check for MEMORY.md (auto memory file).

    P1 Compliance: All checks are string/regex operations — zero LLM inference.
    Returns: list of warning strings (empty if healthy).

    Checks:
      MH-1: Line count > 200 (system truncation threshold)
      MH-2: Duplicate ## headers (same header text appears 2+ times)
      MH-3: Empty sections (## header followed immediately by another ## header)
      MH-4: Nearly empty file (< 3 content lines)
    """
    warnings = []

    # Locate MEMORY.md — Claude's auto memory directory
    # Convention: ~/.claude-*/projects/{project-hash}/memory/MEMORY.md
    memory_path = _find_memory_md(project_dir)
    if not memory_path or not os.path.exists(memory_path):
        return warnings  # No MEMORY.md — not an error, just nothing to check

    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return warnings

    lines = content.split("\n")
    total_lines = len(lines)
    content_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]

    # MH-1: Line count > 200
    if total_lines > 200:
        warnings.append(
            f"MEMORY.md가 200줄을 초과 ({total_lines}줄). "
            "200줄 이후는 truncate됩니다. 정리를 권장합니다."
        )

    # MH-2: Duplicate headers
    headers = _MEMORY_HEADER_RE.findall(content)
    header_texts = [text.strip() for _, text in headers]
    seen = {}
    for ht in header_texts:
        seen[ht] = seen.get(ht, 0) + 1
    duplicates = [ht for ht, count in seen.items() if count > 1]
    if duplicates:
        warnings.append(
            f"중복 섹션 감지: {', '.join(duplicates[:3])}. 통합을 권장합니다."
        )

    # MH-3: Empty sections (## followed by ## with no content between)
    empty_sections = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            # Look ahead for next non-empty line
            for j in range(i + 1, min(i + 5, len(lines))):
                next_stripped = lines[j].strip()
                if not next_stripped:
                    continue
                if next_stripped.startswith("## ") or next_stripped.startswith("# "):
                    empty_sections.append(stripped)
                break
    if empty_sections:
        warnings.append(
            f"빈 섹션: {', '.join(s[:40] for s in empty_sections[:3])}. "
            "내용 추가 또는 섹션 삭제를 권장합니다."
        )

    # MH-4: Nearly empty file
    if len(content_lines) < 3 and total_lines > 0:
        warnings.append(
            "MEMORY.md가 거의 비어 있습니다. "
            "핵심 사실과 사용자 선호도를 기록하세요."
        )

    return warnings


def _find_memory_md(project_dir):
    """Locate the auto memory MEMORY.md file for this project.

    Convention: ~/.claude-*/projects/{project-hash}/memory/MEMORY.md
    The project hash is derived from the absolute project path.
    """
    if not project_dir:
        return None

    home = os.path.expanduser("~")
    abs_project = os.path.abspath(project_dir)

    # Search for claude insight directories
    try:
        for entry in os.listdir(home):
            if entry.startswith(".claude-") and os.path.isdir(os.path.join(home, entry)):
                projects_dir = os.path.join(home, entry, "projects")
                if not os.path.isdir(projects_dir):
                    continue
                # Project hash: path with / replaced by -
                project_hash = abs_project.replace("/", "-")
                memory_path = os.path.join(
                    projects_dir, project_hash, "memory", "MEMORY.md"
                )
                if os.path.exists(memory_path):
                    return memory_path
    except Exception:
        pass

    return None


# =============================================================================
# Today/Yesterday Session Summary (Improvement B — deterministic, P1 compliant)
# =============================================================================

def _get_today_yesterday_summary(ki_path):
    """Aggregate today's and yesterday's sessions from knowledge-index.jsonl.

    P1 Compliance: All operations are deterministic (timestamp string comparison,
    counting, set operations). Zero LLM inference.

    Returns: list of summary strings (empty if no sessions today/yesterday).
    """
    if not ki_path or not os.path.exists(ki_path):
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = datetime.fromtimestamp(
        datetime.now().timestamp() - 86400
    ).strftime("%Y-%m-%d")

    today_sessions = []
    yesterday_sessions = []

    try:
        with open(ki_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except (json.JSONDecodeError, ValueError):
                    continue
                ts = entry.get("timestamp", "")
                if ts.startswith(today):
                    today_sessions.append(entry)
                elif ts.startswith(yesterday):
                    yesterday_sessions.append(entry)
    except Exception:
        return []

    summaries = []

    if today_sessions:
        n_sessions = len(today_sessions)
        all_files = set()
        for s in today_sessions:
            for f in s.get("modified_files", []):
                all_files.add(os.path.basename(f) if f else "")
        all_files.discard("")
        n_files = len(all_files)
        first_task = (today_sessions[0].get("user_task", "") or "")[:80]
        summaries.append(
            f"오늘 작업: {n_sessions}개 세션, {n_files}개 파일 수정"
            + (f" | 첫 작업: {first_task}" if first_task else "")
        )

    if yesterday_sessions:
        n_sessions = len(yesterday_sessions)
        all_files = set()
        for s in yesterday_sessions:
            for f in s.get("modified_files", []):
                all_files.add(os.path.basename(f) if f else "")
        all_files.discard("")
        n_files = len(all_files)
        summaries.append(
            f"어제 작업: {n_sessions}개 세션, {n_files}개 파일 수정"
        )

    return summaries


# =============================================================================
# Phase 1-A: Thesis Continuity Markers
# =============================================================================
# Uses _extract_thesis_continuity() imported from _context_lib.py (DRY — no duplication).
# Both SessionStart (live display) and save_context (KI archival) use the same function.


# =============================================================================
# Phase 1-C: Quality Gate Trend (pass/fail history from knowledge-index)
# =============================================================================

def _get_quality_gate_trend(ki_path, max_sessions=10):
    """Extract quality gate pass/fail trend from recent knowledge-index sessions.

    Scans thesis_continuity.pending_gates across recent sessions to detect
    patterns like repeated gate failures (indicates systematic quality issues).

    P1 Compliance: Deterministic JSON extraction + counting.
    Returns: summary string or empty string.
    """
    if not ki_path or not os.path.exists(ki_path):
        return ""
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

        # Scan recent sessions with thesis_continuity data
        gate_history = {}  # gate_name → list of statuses ("pending" or "pass")
        recent = entries[-max_sessions:] if entries else []
        sessions_with_data = 0
        for sess in recent:
            tc = sess.get("thesis_continuity", {})
            if not tc:
                continue
            sessions_with_data += 1
            pending = set(tc.get("pending_gates", []))
            # Any gate mentioned as pending is "fail/pending" in that session
            for g in pending:
                gate_history.setdefault(g, []).append("pending")

        if sessions_with_data < 2:
            return ""

        # Detect repeated failures (same gate pending in 3+ consecutive sessions)
        repeated_failures = []
        for gate, statuses in gate_history.items():
            if len(statuses) >= 3:
                repeated_failures.append(f"{gate} ({len(statuses)}x pending)")

        if repeated_failures:
            return f"Repeated gate failures: {', '.join(repeated_failures)} — consider root cause analysis"
        elif gate_history:
            total_pending = sum(len(v) for v in gate_history.values())
            return f"{total_pending} gate-pending events across {sessions_with_data} sessions"
        return ""
    except Exception:
        return ""


def _read_active_thesis_sot(project_dir: str) -> tuple[str | None, dict]:
    """Shared SOT reader: find + read thesis session.json exactly ONCE.

    Returns (sot_path, sot_data). sot_path is None if no active thesis project
    found. sot_data is {} on any read error.

    SOT Compliance: Read-only, single-pass — all callers share this one read so
    they see a consistent snapshot of session.json (no per-function re-reads).
    DRY: eliminates the duplicated sot_path-finding logic across 4 functions.
    P1 Compliance: Deterministic JSON read, non-blocking.
    """
    if not project_dir:
        return None, {}

    # Search thesis-output/{proj}/session.json first (standard layout)
    thesis_output = os.path.join(project_dir, "thesis-output")
    if os.path.isdir(thesis_output):
        for entry in sorted(os.listdir(thesis_output)):  # sorted for determinism
            candidate = os.path.join(thesis_output, entry, "session.json")
            if os.path.exists(candidate):
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        return candidate, json.load(f)
                except Exception:
                    return candidate, {}

    # Fallback: session.json directly under project root
    root_candidate = os.path.join(project_dir, "session.json")
    if os.path.exists(root_candidate):
        try:
            with open(root_candidate, "r", encoding="utf-8") as f:
                return root_candidate, json.load(f)
        except Exception:
            return root_candidate, {}

    return None, {}


def _build_active_thesis_step_block(project_dir: str) -> list[str]:
    """CM-1: Build IMMORTAL Active Thesis Execution Context block.

    Extracts the current step, its verification criteria (from todo-checklist.md),
    retry budget consumption, and dialogue state from live session.json.

    This block survives context compression because it is regenerated fresh at every
    SessionStart — it does NOT rely on snapshot content.

    P1 Compliance: Pure file I/O + regex — deterministic, zero LLM.
    SOT Compliance: Read-only (session.json + todo-checklist.md).
    Returns: list of human-readable lines (empty if no active thesis step > 0).
    """
    if not project_dir:
        return []

    # Use shared SOT reader — single read, consistent snapshot
    sot_path, sot = _read_active_thesis_sot(project_dir)
    if not sot_path or not sot:
        return []

    current_step = sot.get("current_step", 0)
    total_steps = sot.get("total_steps", 210)
    if not isinstance(current_step, int) or current_step <= 0:
        return []  # No active step (step 0 = not started)

    project_name = sot.get("project_name", "?")
    exec_substep = sot.get("execution_substep")
    lines: list[str] = []
    lines.append(f"Project: {project_name} | Step: {current_step}/{total_steps}")

    if exec_substep:
        lines.append(f"→ Last substep recorded: {exec_substep} (resume from here)")
    else:
        lines.append("→ execution_substep: None (step advance completed or substep not yet recorded)")

    # Extract step description from todo-checklist.md
    checklist_path = os.path.join(os.path.dirname(sot_path), "todo-checklist.md")
    if os.path.exists(checklist_path):
        step_desc = _extract_step_description_from_checklist(checklist_path, current_step)
        if step_desc:
            lines.append(f"Step description: {step_desc}")

    # Dialogue state
    ds = sot.get("dialogue_state")
    if isinstance(ds, dict) and ds.get("status") == "in_progress":
        rounds_used = ds.get("rounds_used", "?")
        max_rounds = ds.get("max_rounds", "?")
        last_verdict = ds.get("last_verdict", "unknown")
        domain = ds.get("domain", "?")
        lines.append(
            f"Dialogue: ACTIVE (domain={domain}, Round {rounds_used}/{max_rounds}, "
            f"last verdict={last_verdict})"
        )
    elif isinstance(ds, dict) and ds.get("status") in ("consensus", "escalated"):
        lines.append(f"Dialogue: {ds['status'].upper()} (ended)")

    # Retry budget snapshot — read from counter files (non-blocking)
    budgets = _read_retry_budget_snapshot(os.path.dirname(sot_path), current_step)
    if budgets:
        lines.append(f"Retry budgets: {budgets}")

    # B-1: Invocation plan progress — surface which orchestrator invocation is active
    # P1 Compliance: Imports get_invocation_plan() from query_step.py (deterministic).
    # SOT Compliance: Read-only (uses current_step already read above).
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        from query_step import get_invocation_plan
        plan = get_invocation_plan(current_step)
        completed_inv = sum(1 for p in plan if p["status"] == "completed")
        in_progress = [p for p in plan if p["status"] == "in_progress"]
        total_inv = plan[0]["total"] if plan else 17
        lines.append(f"Invocation plan: {completed_inv}/{total_inv} completed")
        if in_progress:
            cur = in_progress[0]
            lines.append(
                f"→ Active invocation {cur['invocation']}/{total_inv}: "
                f"Steps {cur['start']}-{cur['end']} ({cur['label']})"
            )
    except Exception:
        pass  # Non-blocking: query_step.py may not exist in non-thesis projects

    # B-2 + QO-4: Consolidated group state with enhanced metadata.
    # P1 Compliance: Uses get_next_execution_step() + query_step() (deterministic).
    # QO-4: Also surfaces expected output path, min_output_bytes, and tier.
    # Eliminates LLM math — Orchestrator reads the result, doesn't compute.
    try:
        from query_step import get_next_execution_step, query_step as qs_query
        next_info = get_next_execution_step(current_step)
        ns = next_info.get("next_step")
        if ns is not None:
            reason = next_info.get("reason", "normal")
            cg = next_info.get("consolidated_group")
            agent_name = next_info.get("agent", "?")
            if reason == "restart_consolidated_group" and cg:
                lines.append(
                    f"→ RESTART consolidated group Steps {min(cg)}-{max(cg)} "
                    f"({agent_name}) — mid-group context reset detected"
                )
            elif cg:
                lines.append(
                    f"→ Next: consolidated group Steps {min(cg)}-{max(cg)} "
                    f"({agent_name})"
                )

            # QO-4: Surface execution metadata for the next step
            try:
                research_type = sot.get("research_type", "undecided")
                step_meta = qs_query(ns, research_type)
                if "error" not in step_meta:
                    output_path = step_meta.get("output_path", "?")
                    min_bytes = step_meta.get("min_output_bytes", "?")
                    tier = step_meta.get("tier", "?")
                    has_claims = step_meta.get("has_grounded_claims", False)
                    pccs_mode = step_meta.get("pccs_mode", "SKIP")
                    lines.append(
                        f"→ Step {ns} metadata: output={output_path}, "
                        f"min={min_bytes}B, tier={tier}, "
                        f"claims={'yes' if has_claims else 'no'}, pCCS={pccs_mode}"
                    )
            except Exception:
                pass  # Non-blocking
    except Exception:
        pass  # Non-blocking

    return lines


def _extract_step_description_from_checklist(checklist_path: str, step: int) -> str:
    """Extract step N description from todo-checklist.md.

    Pattern: '- [ ] Step N: description' or '- [x] Step N: description'
    P1 Compliance: Regex line match — deterministic.
    """
    _step_re = re.compile(
        rf"^-\s*\[[ xX]\]\s*Step\s+{step}\s*:\s*(.+)$", re.MULTILINE
    )
    try:
        with open(checklist_path, "r", encoding="utf-8") as f:
            content = f.read(50_000)  # Max 50KB to avoid huge reads
        m = _step_re.search(content)
        return m.group(1).strip()[:120] if m else ""
    except Exception:
        return ""


def _read_retry_budget_snapshot(project_dir: str, step: int) -> str:
    """Read retry budget counter files for a step (non-blocking).

    Counter files: verification-logs/.step-N-retry-count, dialogue-logs/.step-N-retry-count
    P1 Compliance: Plain text integer read — deterministic.
    """
    parts: list[str] = []
    for gate_subdir, gate_name in (
        ("verification-logs", "verification"),
        ("dialogue-logs", "dialogue"),
    ):
        counter_file = os.path.join(
            project_dir, gate_subdir, f".step-{step}-retry-count"
        )
        if os.path.exists(counter_file):
            try:
                with open(counter_file, "r", encoding="utf-8") as f:
                    count = f.read().strip()
                parts.append(f"{gate_name}={count}")
            except Exception:
                pass
    return ", ".join(parts) if parts else ""


def _detect_active_dialogue(project_dir: str) -> dict | None:
    """CM-2: Detect if an Adversarial Dialogue is currently in progress.

    Scans thesis-output/*/ project directories for dialogue-logs/ directories
    where rK critic files exist but step-N-summary.md does NOT exist
    (summary is written only when dialogue ends).

    P1 Compliance: Filesystem scan + regex — deterministic, zero LLM.
    SOT Compliance: Read-only (reads session.json and dialogue-logs/).
    Returns: dict with step, round, domain info if active dialogue found, else None.
    """
    if not project_dir or not os.path.isdir(project_dir):
        return None

    # Find thesis project directories (have session.json)
    thesis_dirs = []
    thesis_output = os.path.join(project_dir, "thesis-output")
    if os.path.isdir(thesis_output):
        for entry in os.listdir(thesis_output):
            candidate = os.path.join(thesis_output, entry)
            if os.path.isdir(candidate) and os.path.exists(
                os.path.join(candidate, "session.json")
            ):
                thesis_dirs.append(candidate)
    # Also check project root itself
    if os.path.exists(os.path.join(project_dir, "session.json")):
        thesis_dirs.append(project_dir)

    _critic_file_re = re.compile(
        r"step-(\d+)-r(\d+)-(fc|rv|cr)\.md$"
    )
    for tdir in thesis_dirs:
        dlg_dir = os.path.join(tdir, "dialogue-logs")
        if not os.path.isdir(dlg_dir):
            continue

        # Collect all critic files grouped by step
        step_rounds: dict[int, dict] = {}
        for fname in os.listdir(dlg_dir):
            m = _critic_file_re.match(fname)
            if not m:
                continue
            step_n = int(m.group(1))
            round_k = int(m.group(2))
            domain = "development" if m.group(3) == "cr" else "research"
            if step_n not in step_rounds:
                step_rounds[step_n] = {"max_round": 0, "domain": domain}
            if round_k > step_rounds[step_n]["max_round"]:
                step_rounds[step_n]["max_round"] = round_k

        # Read session.json ONCE per project for SOT cross-validation.
        # Two-signal detection: filesystem (no summary) AND SOT (not completed, not stale).
        sot_current_step = 0
        sot_raw_data: dict = {}
        try:
            sot_path = os.path.join(tdir, "session.json")
            with open(sot_path, "r", encoding="utf-8") as f:
                sot_raw_data = json.load(f)
            sot_current_step = sot_raw_data.get("current_step", 0)
            if not isinstance(sot_current_step, int):
                sot_current_step = 0
        except Exception:
            pass

        for step_n, info in step_rounds.items():
            # Dialogue is ACTIVE if no summary file exists yet
            summary_path = os.path.join(dlg_dir, f"step-{step_n}-summary.md")
            if not os.path.exists(summary_path):
                # SOT cross-validation: guard against stale/abandoned dialogues.
                # If step_n is more than 1 step behind current_step, the workflow
                # has already advanced past this step — the missing summary indicates
                # an abandoned dialogue (crash/skip), not an active one.
                # Also skip if SOT dialogue_state.status == "completed" (completed
                # but summary file wasn't written due to crash).
                ds = sot_raw_data.get("dialogue_state") or {}
                dialogue_sot_status = ds.get("status", "unknown")

                if dialogue_sot_status == "completed":
                    continue  # SOT says completed — filesystem artifact, not active

                if sot_current_step > 0 and step_n < sot_current_step - 1:
                    continue  # Workflow advanced past this step — abandoned dialogue

                sot_info = {
                    "status": dialogue_sot_status,
                    "max_rounds": ds.get("max_rounds", "?"),
                    "rounds_used": ds.get("rounds_used", "?"),
                    "last_verdict": ds.get("last_verdict", "unknown"),
                    "execution_substep": sot_raw_data.get("execution_substep"),
                }

                return {
                    "step": step_n,
                    "round": info["max_round"],
                    "domain": info["domain"],
                    "project": os.path.basename(tdir),
                    **sot_info,
                }
    return None


def _surface_failure_predictions(project_dir: str) -> list[str]:
    """Surface active failure predictions for RLM IMMORTAL section.

    Reads failure-predictions/active-risks.md (generated by generate_failure_report.py).
    Adds STALE warning if file is older than 7 days.
    Returns empty list if no predictions file exists.

    Design: Separate from existing PREDICTIVE DEBUGGING section (historical risk scores).
    - Historical: predictive_debug_guard.py ← risk-scores.json ← error history
    - Proactive: THIS function ← active-risks.md ← /predict-failures cross-domain scan
    """
    active_risks_path = os.path.join(project_dir, "failure-predictions", "active-risks.md")
    if not os.path.exists(active_risks_path):
        # Distinguish "no predictions" from "zero risk" — unknown ≠ safe
        return ["■ FAILURE PREDICTIONS UNAVAILABLE — run /predict-failures for cross-domain risk assessment"]

    try:
        import time
        age_seconds = time.time() - os.path.getmtime(active_risks_path)
        age_days = age_seconds / 86400
        stale = age_days > 7
        stale_prefix = "⚠ STALE " if stale else ""

        with open(active_risks_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract non-comment, non-empty lines
        meaningful_lines = [
            ln for ln in content.splitlines()
            if ln.strip() and not ln.strip().startswith("<!--")
        ]

        if not meaningful_lines:
            return []

        output: list[str] = []
        stale_note = f" (scan >{int(age_days)}d ago — run /predict-failures to refresh)" if stale else ""
        output.append(f"■ {stale_prefix}ACTIVE FAILURE PREDICTIONS{stale_note}:")
        # Surface up to 8 lines from active-risks.md
        for ln in meaningful_lines[:8]:
            output.append(f"  {ln.strip()}")

        return output

    except (IOError, OSError):
        return []


def _surface_active_team(project_dir: str) -> list[str]:
    """Surface active Agent Team state for IMMORTAL section.

    If an Agent Team was in progress when context reset occurred,
    the Orchestrator needs to know: team name, pending/completed tasks,
    current tier. Without this, Orchestrator may restart team from scratch
    or create duplicate teams.

    P1 Compliance: JSON read + dict formatting — deterministic.
    SOT Compliance: Read-only.
    Returns: list of lines (empty if no active team).
    """
    sot_path, sot = _read_active_thesis_sot(project_dir)
    if not sot_path or not sot:
        return []

    active_team = sot.get("active_team")
    if not active_team or not isinstance(active_team, dict):
        return []

    # Only surface if team is actually active (not completed/cancelled)
    status = active_team.get("status", "")
    if status in ("completed", "cancelled"):
        return []

    lines: list[str] = []
    name = active_team.get("name", "?")
    lines.append(f"■ ACTIVE AGENT TEAM (IMMORTAL — resume, do NOT recreate):")
    lines.append(f"  team: {name}, status: {status}")

    # Task summary
    pending = active_team.get("tasks_pending", [])
    completed = active_team.get("tasks_completed", [])
    if isinstance(pending, list):
        lines.append(f"  pending: {len(pending)} tasks")
        for t in pending[:3]:
            if isinstance(t, dict):
                agent = t.get("agent", "?")
                task_status = t.get("status", "?")
                lines.append(f"    - {agent}: {task_status}")
            elif isinstance(t, str):
                lines.append(f"    - {t}")
    if isinstance(completed, list) and completed:
        lines.append(f"  completed: {len(completed)} tasks")

    lines.append("  ⚠ Task IDs are session-scoped — re-query TaskList before resuming")
    return lines


def _surface_pccs_state(project_dir: str) -> list[str]:
    """Surface pCCS state from thesis SOT for IMMORTAL section.

    Reads session.json.pccs block to surface calibration delta and
    recent step scores. Enables Orchestrator to maintain pCCS context
    across compression boundaries.

    P1 Compliance: JSON read + dict formatting — deterministic.
    SOT Compliance: Read-only.
    Returns: list of lines (empty if no pCCS data).
    """
    sot_path, sot = _read_active_thesis_sot(project_dir)
    if not sot_path or not sot:
        return []

    pccs = sot.get("pccs")
    if not isinstance(pccs, dict):
        return []

    lines: list[str] = []
    cal_delta = pccs.get("cal_delta", 0.0)
    last_step = pccs.get("last_step")
    total_samples = pccs.get("total_cal_samples", 0)

    lines.append(f"■ pCCS STATE (IMMORTAL — per-claim confidence scoring):")
    lines.append(f"  cal_delta={cal_delta}, last_step={last_step}, cal_samples={total_samples}")

    # Surface last 3 step results from history + trend detection
    history = pccs.get("history")
    if isinstance(history, dict) and history:
        sorted_keys = sorted(history.keys(), reverse=True)[:3]
        means = []
        for key in sorted_keys:
            entry = history[key]
            if isinstance(entry, dict):
                mean = entry.get("mean_pccs", "?")
                action = entry.get("action", "?")
                green = entry.get("green", "?")
                red = entry.get("red", "?")
                mode = entry.get("mode", "?")
                lines.append(f"  {key}: mean={mean}, G={green}/R={red}, action={action}, mode={mode}")
                if isinstance(mean, (int, float)):
                    means.append(mean)

        # Trend detection: direction of mean_pccs across last 3 steps
        if len(means) >= 2:
            # means[0] = most recent, means[-1] = oldest
            delta = means[0] - means[-1]
            if delta > 3:
                trend = f"↑ improving (+{delta:.1f})"
            elif delta < -3:
                trend = f"↓ declining ({delta:.1f})"
            else:
                trend = f"→ stable ({delta:+.1f})"
            lines.append(f"  trend: {trend}")

            # Consecutive rewrite warning
            rewrite_actions = [
                history[k].get("action", "") for k in sorted_keys[:2]
                if isinstance(history.get(k), dict)
            ]
            if all(a in ("rewrite_claims", "rewrite_step") for a in rewrite_actions if a):
                lines.append(f"  ⚠ consecutive rewrites detected — possible systemic quality issue")

    return lines


def _surface_hypothesis_graveyard(project_dir: str) -> list[str]:
    """CM-OPT-2: Surface rejected hypotheses as IMMORTAL section.

    Extracts recent rejected hypotheses from knowledge-index.jsonl and
    surfaces them at SessionStart so the Orchestrator avoids re-trying
    failed approaches after context reset.

    IMMORTAL: This section survives compression — prevents circular exploration.
    P1 Compliance: deterministic extraction from structured JSON data.
    Non-blocking: returns empty list on any error.
    """
    try:
        snapshot_dir = get_snapshot_dir(project_dir)
        ki_path = os.path.join(snapshot_dir, "knowledge-index.jsonl")
        if not os.path.exists(ki_path):
            return []

        # Read recent 30 sessions (enough for hypothesis coverage)
        all_sessions: list[dict] = []
        with open(ki_path, "r", encoding="utf-8") as f:
            for line_text in f:
                line_text = line_text.strip()
                if line_text:
                    try:
                        all_sessions.append(json.loads(line_text))
                    except json.JSONDecodeError:
                        continue

        if not all_sessions:
            return []

        # Extract from most recent 30 sessions
        recent = all_sessions[-30:]
        hypotheses: list[str] = []
        for session in reversed(recent):
            rejected = session.get("rejected_hypotheses", [])
            if not isinstance(rejected, list):
                continue
            for rh in rejected:
                if not isinstance(rh, dict):
                    continue
                text = rh.get("text", "?")
                outcome = rh.get("outcome", "failed")
                hypotheses.append(f"  - {text} → {outcome}")
            if len(hypotheses) >= 5:
                break

        if not hypotheses:
            return []

        lines: list[str] = []
        lines.append("■ HYPOTHESIS GRAVEYARD (IMMORTAL — 반복 탐색 방지):")
        lines.extend(hypotheses[:5])
        lines.append("  ⚠ 위 접근법은 이전 세션에서 시도되어 실패함. 동일 접근 재시도 금지.")
        return lines
    except Exception:
        return []


def _surface_self_improvement_state(project_dir: str) -> list[str]:
    """Surface KBSI (Knowledge-Based Self-Improvement) state for SessionStart.

    Reads self-improvement-logs/state.json to surface a 2-3 line summary of
    the current self-improvement system state. Non-IMMORTAL — informational
    only (AGENTS.md §11 rules are always in system prompt anyway).

    P1 Compliance: JSON read + dict formatting — deterministic.
    SOT Compliance: Read-only.
    Returns: list of lines (empty if no KBSI state).
    """
    si_dir = os.path.join(project_dir, "self-improvement-logs")
    sot_path = os.path.join(si_dir, "state.json")

    if not os.path.exists(sot_path):
        return []

    try:
        with open(sot_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

    insights = state.get("insights", {})
    if not insights and not state.get("queued_changes"):
        return []

    lines: list[str] = []

    applied = sum(1 for v in insights.values() if v.get("status") == "applied")
    pending = sum(1 for v in insights.values() if v.get("status") == "pending")
    rejected = sum(1 for v in insights.values() if v.get("status") == "rejected")

    lines.append(f"■ KBSI STATE: {applied} applied, {pending} pending, {rejected} rejected")

    # Surface pending insights that need attention
    if pending > 0:
        pending_ids = [
            k for k, v in insights.items() if v.get("status") == "pending"
        ][:3]
        lines.append(f"  Pending review: {', '.join(pending_ids)}")

    # Surface queued changes
    queued = state.get("queued_changes", [])
    queued_pending = [q for q in queued if not q.get("applied")]
    if queued_pending:
        structural = sum(1 for q in queued_pending if q.get("change_type") == "STRUCTURAL")
        lines.append(
            f"  Queued changes: {len(queued_pending)} "
            f"({structural} STRUCTURAL — need user approval)"
        )

    return lines


def _surface_recent_gate_feedback(project_dir: str) -> list[str]:
    """QO-1: Surface recent gate feedback for IMMORTAL section.

    Reads gate-reports/ for the most recent gate report and extracts
    specific failure reasons. Enables agents to see WHY a gate failed,
    not just that it did. Critical for guided revision after context reset.

    IMMORTAL: Gate failure reasons must survive compression for revision.
    P1 Compliance: Deterministic file read + regex — zero LLM.
    SOT Compliance: Read-only (gate-reports/).
    Returns: list of lines (empty if no gate feedback).
    """
    if not project_dir:
        return []

    # Find thesis project directory
    sot_path, sot = _read_active_thesis_sot(project_dir)
    if not sot_path or not sot:
        return []

    project_root = os.path.dirname(sot_path)
    gate_dir = os.path.join(project_root, "gate-reports")
    if not os.path.isdir(gate_dir):
        return []

    # Find most recent gate report
    gate_files = []
    for f in os.listdir(gate_dir):
        if f.endswith(".md") or f.endswith(".json"):
            gate_files.append(os.path.join(gate_dir, f))
    if not gate_files:
        return []

    gate_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    latest_gate = gate_files[0]

    try:
        with open(latest_gate, "r", encoding="utf-8") as f:
            content = f.read(10_000)  # Cap at 10KB
    except (IOError, OSError):
        return []

    if not content.strip():
        return []

    lines: list[str] = []
    gate_name = os.path.basename(latest_gate).replace(".md", "").replace(".json", "")
    lines.append("■ RECENT GATE FEEDBACK (IMMORTAL — revision guidance):")
    lines.append(f"  Gate: {gate_name}")

    # H-1 Fix: Precise gate feedback extraction — JSON first, structured MD fallback.
    # Previous regex ("FAIL" in line) caused false positives on descriptive text.
    fail_items: list[str] = []
    warn_items: list[str] = []
    gate_status = ""

    if latest_gate.endswith(".json"):
        # JSON gate report (validate_wave_gate.py --output-json): deterministic fields
        try:
            gate_data = json.loads(content)
            gate_status = str(gate_data.get("status", "")).upper()
            for err in gate_data.get("errors", []):
                if isinstance(err, str):
                    fail_items.append(err[:150])
            for wrn in gate_data.get("warnings", []):
                if isinstance(wrn, str):
                    warn_items.append(wrn[:150])
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
    else:
        # MD gate report: state machine — only extract items within structured sections
        section = None  # None | "errors" | "warnings"
        for report_line in content.split("\n"):
            stripped = report_line.strip()
            # Detect section transitions
            if stripped.lower().startswith("errors:") or stripped == "## Errors":
                section = "errors"
                continue
            elif stripped.lower().startswith("warnings:") or stripped == "## Warnings":
                section = "warnings"
                continue
            elif stripped.lower().startswith("status:"):
                m = re.match(r"status:\s*(\w+)", stripped, re.IGNORECASE)
                if m:
                    gate_status = m.group(1).upper()
                section = None
                continue
            elif stripped.startswith("#") or stripped.startswith("Gate:") or \
                    stripped.startswith("Files:") or stripped.startswith("Total "):
                section = None
                continue
            # Extract items within active section (indented "- " bullets only)
            if section == "errors" and stripped.startswith("- "):
                fail_items.append(stripped[2:].strip()[:150])
            elif section == "warnings" and stripped.startswith("- "):
                warn_items.append(stripped[2:].strip()[:150])
            # Checklist-style "- [ ]" (unchecked = fail) is always valid
            elif stripped.startswith("- [ ] "):
                fail_items.append(stripped[6:].strip()[:150])

    if gate_status:
        lines.append(f"  Status: {gate_status}")
    if fail_items:
        lines.append(f"  Failures ({len(fail_items)}):")
        for fi in fail_items[:5]:
            lines.append(f"    - {fi}")
    if warn_items:
        lines.append(f"  Warnings ({len(warn_items)}):")
        for wi in warn_items[:3]:
            lines.append(f"    - {wi}")
    if not fail_items and not warn_items and gate_status != "FAIL":
        lines.append("  Status: All checks passed (no revision needed)")

    return lines


def _surface_previous_sections_summary(project_dir: str) -> list[str]:
    """QO-2: Surface previous section outputs for IMMORTAL section.

    Reads thesis-output/*/wave-results/ and thesis-output/*/phase-*/ for
    the most recently completed step outputs. Surfaces title, word count,
    and key headings to maintain narrative coherence across compression.

    IMMORTAL: Previous section context is critical for coherent writing.
    P1 Compliance: Deterministic file read + regex — zero LLM.
    SOT Compliance: Read-only (output files).
    Returns: list of lines (empty if no previous outputs).
    """
    if not project_dir:
        return []

    sot_path, sot = _read_active_thesis_sot(project_dir)
    if not sot_path or not sot:
        return []

    project_root = os.path.dirname(sot_path)
    current_step = sot.get("current_step", 0)
    if not isinstance(current_step, int) or current_step <= 1:
        return []

    # Collect output files from outputs/ record in SOT
    outputs = sot.get("outputs", {})
    if not isinstance(outputs, dict):
        return []

    # Get last 5 completed step outputs (most recent first)
    step_files: list[tuple[int, str]] = []
    for key, val in outputs.items():
        # key format: "step-N" or "step-N-ko"
        if not key.startswith("step-") or key.endswith("-ko"):
            continue
        try:
            step_n = int(key.replace("step-", ""))
        except (ValueError, TypeError):
            continue
        if step_n >= current_step:
            continue  # Only past steps
        file_path = val if isinstance(val, str) else ""
        if file_path:
            full_path = os.path.join(project_root, file_path)
            if os.path.exists(full_path):
                step_files.append((step_n, full_path))

    if not step_files:
        return []

    step_files.sort(key=lambda x: x[0], reverse=True)

    lines: list[str] = []
    lines.append("■ PREVIOUS SECTION OUTPUTS (IMMORTAL — narrative coherence):")

    for step_n, fpath in step_files[:5]:
        try:
            # H-2 Fix: Read full file for accurate word count.
            # Previous 5KB cap caused severe undercount (e.g., 10K-word file → "800 words").
            with open(fpath, "r", encoding="utf-8") as f:
                full_content = f.read()
            word_count = len(full_content.split())
            # Heading extraction uses first 5KB only (efficiency for very large files)
            heading_content = full_content[:5_000]
            title = ""
            headings: list[str] = []
            for line in heading_content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("## ") and not title:
                    title = stripped[3:].strip()[:80]
                elif stripped.startswith("## "):
                    headings.append(stripped[3:].strip()[:60])
            fname = os.path.basename(fpath)
            title_str = f" — {title}" if title else ""
            lines.append(f"  Step {step_n}: {fname}{title_str} ({word_count} words)")
            if headings:
                lines.append(f"    Sections: {', '.join(headings[:4])}")
        except (IOError, OSError):
            continue

    return lines


def _extract_thesis_gate_hitl_state(project_dir: str) -> list[str]:
    """CM-4: Extract Gate pass/fail and HITL decision history for IMMORTAL surface.

    Reads session.json to get Gate and HITL state. These are human-approved
    decisions that must never be lost in compression — HITL re-asking wastes
    human effort; Gate state loss causes incorrect step sequencing.

    P1 Compliance: JSON read + dict iteration — deterministic.
    SOT Compliance: Read-only.
    Returns: list of human-readable status lines (empty if no thesis project).
    """
    lines: list[str] = []
    if not project_dir:
        return lines

    # Use shared SOT reader — single read, consistent snapshot
    sot_path, sot = _read_active_thesis_sot(project_dir)
    if not sot_path or not sot:
        return lines

    # Gates
    gates = sot.get("gates", {})
    gate_parts: list[str] = []
    for gate_name, gate_data in sorted(gates.items()):
        if isinstance(gate_data, dict):
            status = gate_data.get("status", "pending")
            marker = "✅" if status == "pass" else ("❌" if status == "fail" else "⏳")
            gate_parts.append(f"{marker}{gate_name}:{status}")
        elif isinstance(gate_data, str):
            gate_parts.append(f"{gate_data} {gate_name}")
    if gate_parts:
        lines.append(f"Gates: {', '.join(gate_parts)}")

    # HITL
    hitls = sot.get("hitl_checkpoints", {})
    hitl_parts: list[str] = []
    for hitl_name, hitl_data in sorted(hitls.items()):
        if isinstance(hitl_data, dict):
            status = hitl_data.get("status", "pending")
            if status != "pending":
                marker = "✅" if status == "completed" else "⏳"
                hitl_parts.append(f"{marker}{hitl_name}")
        elif isinstance(hitl_data, str) and hitl_data != "pending":
            hitl_parts.append(f"✅{hitl_name}")
    if hitl_parts:
        lines.append(f"HITL completed: {', '.join(hitl_parts)}")

    # execution_substep (from 결함 C)
    substep = sot.get("execution_substep")
    if substep:
        step_n = sot.get("current_step", "?")
        lines.append(f"Last substep: step-{step_n} @ {substep} (resume here after reset)")

    return lines


def _build_recovery_output(source, latest_path, summary, sot_warning, snapshot_age, fallback_note="", project_dir=None, snapshot_content="", risk_data=None, compression_note=""):
    """Build the RLM-style recovery output for SessionStart injection."""
    age_str = _format_age(snapshot_age)

    # CM-2: Detect active Adversarial Dialogue BEFORE building output
    # Inject PROMINENTLY at top of recovery — dialogue mid-round is highest priority context
    active_dialogue = _detect_active_dialogue(project_dir) if project_dir else None

    # CM-4: Extract Gate/HITL state for IMMORTAL surface
    gate_hitl_lines = _extract_thesis_gate_hitl_state(project_dir) if project_dir else []

    # Build header
    output_lines = [
        "[CONTEXT RECOVERY]",
        f"이전 세션이 {'clear' if source == 'clear' else 'compact' if source == 'compact' else source}되었습니다.",
        f"전체 복원 파일: {latest_path}",
        "",
    ]

    # CM-2: ACTIVE DIALOGUE WARNING — top of output, before all other context
    if active_dialogue:
        step_n = active_dialogue.get("step", "?")
        round_k = active_dialogue.get("round", "?")
        domain = active_dialogue.get("domain", "?")
        last_verdict = active_dialogue.get("last_verdict", "unknown")
        max_rounds = active_dialogue.get("max_rounds", "?")
        rounds_used = active_dialogue.get("rounds_used", "?")
        substep = active_dialogue.get("execution_substep")
        output_lines.append(
            f"⚠️ ACTIVE ADVERSARIAL DIALOGUE DETECTED (Step {step_n}, Round {round_k}, Domain: {domain})"
        )
        output_lines.append(
            f"   Last verdict: {last_verdict} | Rounds: {rounds_used}/{max_rounds}"
        )
        output_lines.append(
            f"   → Resume from Round {int(round_k) + 1 if str(round_k).isdigit() else '?'}."
            f" DO NOT restart from Round 1."
        )
        if substep:
            output_lines.append(f"   → Last substep recorded: {substep}")
        output_lines.append(
            f"   → Dialogue summary: dialogue-logs/step-{step_n}-summary.md (does NOT exist yet — dialogue in progress)"
        )
        output_lines.append("")

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

    # Compression audit trail — alert if snapshot was heavily compressed
    if compression_note:
        output_lines.append("")
        output_lines.append(compression_note)

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

            # P0-RLM: Active Knowledge Retrieval — relevance-scored
            # Surface past sessions most relevant to CURRENT work context
            file_paths_for_retrieval = [c for l, c in summary if l == "수정_파일_경로"]
            _current_thesis_step = _get_current_thesis_step(project_dir)
            relevant = _retrieve_relevant_sessions(
                ki_path, task_info or "", file_paths_for_retrieval,
                current_step=_current_thesis_step,
                error_info_for_scoring=bool(error_info),
            )
            if relevant:
                output_lines.append("")
                output_lines.append("■ ACTIVE RETRIEVAL — 현재 작업과 관련된 과거 세션:")
                for score, sess in relevant:
                    ts = sess.get("timestamp", "")[:10]
                    past_task = (sess.get("user_task", "") or "(기록 없음)")[:80]
                    session_id_short = sess.get("session_id", "?")[:8]
                    output_lines.append(
                        f"  - [{ts}] {past_task} (relevance:{score:.1f}, id:{session_id_short})"
                    )
                    # Surface actionable Grep for the most relevant session
                    if score >= 5.0:
                        sid = sess.get("session_id", "")
                        if sid:
                            output_lines.append(
                                f'    → Grep "{sid[:12]}" {ki_path} → 이 세션의 상세 정보'
                            )

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

            # P1-2b: Hypothesis Graveyard — tried-and-failed approaches
            # Prevents repeating dead-end approaches after context reset
            rejected_hints = _extract_recent_rejected_hypotheses(recent)
            if rejected_hints:
                output_lines.append("")
                output_lines.append("■ 실패한 접근법 (반복 방지 — 자동 표면화):")
                for rh in rejected_hints[:5]:
                    output_lines.append(f"  - {rh}")

            # P1-3: Proactive Team Summary surfacing
            # Surface recent team coordination history for quality continuity
            team_hints = _extract_recent_team_summaries(recent)
            if team_hints:
                output_lines.append("")
                output_lines.append("■ 최근 팀 실행 이력 (자동 표면화):")
                for th in team_hints[:3]:
                    output_lines.append(f"  - {th}")

            # P1-4: Proactive Success Pattern surfacing
            # Surface proven work patterns for cross-session quality improvement
            success_hints = _extract_recent_success_patterns(recent)
            if success_hints:
                output_lines.append("")
                output_lines.append("■ 검증된 성공 패턴 (자동 표면화):")
                for sh in success_hints[:3]:
                    output_lines.append(f"  - {sh}")

            # P3-RLM: Active Quarterly Archive consumption (long-term patterns)
            qa_path = os.path.join(ka_snapshot_dir, "knowledge-archive-quarterly.jsonl")
            qa_insights = _extract_quarterly_insights(qa_path)
            if qa_insights:
                output_lines.append("")
                output_lines.append("■ 장기 패턴 (Quarterly Archive — 자동 표면화):")
                for insight in qa_insights[:5]:
                    output_lines.append(f"  - {insight}")
                output_lines.append(f"  (원본: {qa_path})")
            elif os.path.exists(qa_path):
                output_lines.append(f"■ 분기별 아카이브: {qa_path}")
                output_lines.append(f'  - Grep "error_patterns_aggregated" {qa_path} → 장기 에러 추세')

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

    # Proactive Failure Predictions (from /predict-failures — cross-domain scan)
    # Distinct from PREDICTIVE DEBUGGING above (which is historical error-based)
    failure_pred_lines = _surface_failure_predictions(project_dir) if project_dir else []
    if failure_pred_lines:
        output_lines.append("")
        for fpl in failure_pred_lines:
            output_lines.append(fpl)

    # Active Agent Team (IMMORTAL — resume, do NOT recreate)
    team_lines = _surface_active_team(project_dir) if project_dir else []
    if team_lines:
        output_lines.append("")
        for tl in team_lines:
            output_lines.append(tl)

    # pCCS State (IMMORTAL — per-claim confidence scoring)
    pccs_lines = _surface_pccs_state(project_dir) if project_dir else []
    if pccs_lines:
        output_lines.append("")
        for pl in pccs_lines:
            output_lines.append(pl)

    # CM-OPT-2: Hypothesis Graveyard (IMMORTAL — prevents circular exploration)
    # Surfaces recent rejected hypotheses so Orchestrator avoids re-trying
    # failed approaches after context reset. Extracted from knowledge-index.
    hyp_lines = _surface_hypothesis_graveyard(project_dir) if project_dir else []
    if hyp_lines:
        output_lines.append("")
        for hl in hyp_lines:
            output_lines.append(hl)

    # KBSI State (non-IMMORTAL — informational, rules always in AGENTS.md)
    kbsi_lines = _surface_self_improvement_state(project_dir) if project_dir else []
    if kbsi_lines:
        output_lines.append("")
        for kl in kbsi_lines:
            output_lines.append(kl)

    # Phase 1-A: Thesis continuity markers (pending gates + blocked steps)
    thesis_continuity = _extract_thesis_continuity(project_dir)
    if thesis_continuity:
        output_lines.append("")
        output_lines.append("■ THESIS CONTINUITY:")
        pg = thesis_continuity.get("pending_gates", [])
        if pg:
            output_lines.append(f"  Pending gates: {', '.join(pg)}")
        bs = thesis_continuity.get("blocked_steps", [])
        if bs:
            output_lines.append(f"  Blocked steps: {', '.join(bs)}")

    # CM-4: IMMORTAL Gate/HITL state — human decisions must never be lost to compression
    if gate_hitl_lines:
        output_lines.append("")
        output_lines.append("■ THESIS GATE & HITL STATE (IMMORTAL — human decisions):")
        for ghl in gate_hitl_lines:
            output_lines.append(f"  {ghl}")

    # CM-1: IMMORTAL Active Thesis Execution Context block
    # Most critical information for Orchestrator context recovery: current step
    # and what it requires. This block is injected at top priority so it survives
    # even heavy compression. Extracted from session.json (live SOT, not snapshot).
    active_step_block = _build_active_thesis_step_block(project_dir)
    if active_step_block:
        output_lines.append("")
        output_lines.append("■ ACTIVE THESIS EXECUTION CONTEXT (IMMORTAL):")
        for line in active_step_block:
            output_lines.append(f"  {line}")

    # QO-1: Recent Gate Feedback (IMMORTAL — revision guidance)
    # Surfaces WHY a gate failed, not just that it did. Enables targeted revision.
    gate_feedback_lines = _surface_recent_gate_feedback(project_dir) if project_dir else []
    if gate_feedback_lines:
        output_lines.append("")
        for gfl in gate_feedback_lines:
            output_lines.append(gfl)

    # QO-2: Previous Section Outputs (IMMORTAL — narrative coherence)
    # Surfaces titles, word counts, and headings of completed step outputs.
    # Enables agents to maintain narrative continuity after compression.
    prev_sections_lines = _surface_previous_sections_summary(project_dir) if project_dir else []
    if prev_sections_lines:
        output_lines.append("")
        for psl in prev_sections_lines:
            output_lines.append(psl)

    # Phase 1-C: Quality gate trend (pass/fail history from knowledge-index)
    if os.path.exists(ki_path) if has_archive else False:
        gate_trend = _get_quality_gate_trend(ki_path)
        if gate_trend:
            output_lines.append("")
            output_lines.append(f"■ Quality Gate Trend: {gate_trend}")

    # MEMORY.md Health Check (deterministic — P1 compliant)
    memory_warnings = _check_memory_health(project_dir)
    if memory_warnings:
        output_lines.append("")
        output_lines.append("■ MEMORY.md 건강 검진:")
        for mw in memory_warnings:
            output_lines.append(f"  ⚠ {mw}")

    # Today/Yesterday Session Summary (deterministic — P1 compliant)
    if os.path.exists(ki_path) if has_archive else False:
        day_summary = _get_today_yesterday_summary(ki_path)
        if day_summary:
            output_lines.append("")
            for ds in day_summary:
                output_lines.append(f"■ {ds}")

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


def _extract_recent_rejected_hypotheses(recent_sessions):
    """P1-2b: Extract tried-and-failed approaches from recent Knowledge Archive sessions.

    Prevents repeating dead-end approaches after context reset by surfacing
    the hypothesis graveyard (extracted by _context_lib._extract_hypothesis_graveyard
    and stored as 'rejected_hypotheses' in knowledge-index entries).

    P1 Compliance: Deterministic extraction from structured JSON data.
    Returns: list of human-readable strings (max 5).
    """
    results = []
    for session in reversed(recent_sessions):
        rejected = session.get("rejected_hypotheses", [])
        if not isinstance(rejected, list):
            continue
        for rh in rejected:
            if not isinstance(rh, dict):
                continue
            text = rh.get("text", "?")
            status = rh.get("status", "tried")
            outcome = rh.get("outcome", "failed")
            results.append(f"[{status}] {text} → {outcome}")
        if len(results) >= 5:
            break
    return results[:5]


def _extract_recent_team_summaries(recent_sessions):
    """P1-3: Extract team coordination history from recent Knowledge Archive sessions.

    Proactively surfaces past team execution patterns at SessionStart,
    enabling continuity of team coordination across context resets.
    Symmetric with _extract_recent_error_resolutions (P1-1).

    P1 Compliance: Deterministic extraction from structured JSON data.
    Returns: list of human-readable strings (max 3).
    """
    results = []
    for session in reversed(recent_sessions):
        team_summaries = session.get("team_summaries", [])
        if not isinstance(team_summaries, list):
            continue
        for ts in team_summaries:
            if isinstance(ts, dict):
                team = ts.get("team", "?")
                status = ts.get("status", "?")
                agents = ts.get("agents", [])
                agent_str = ", ".join(agents[:3]) if isinstance(agents, list) else str(agents)
                results.append(f"{team} ({status}) — {agent_str}")
            elif isinstance(ts, str):
                results.append(ts[:80])
        if len(results) >= 3:
            break
    return results[:3]


def _extract_recent_success_patterns(recent_sessions):
    """P1-4: Extract success patterns from recent Knowledge Archive sessions.

    Proactively surfaces proven work patterns (Edit→Bash→success sequences)
    at SessionStart, enabling cross-session learning for quality improvement.
    Symmetric with _extract_recent_error_resolutions (P1-1).

    P1 Compliance: Deterministic extraction from structured JSON data.
    Returns: list of human-readable strings (max 3).
    """
    results = []
    for session in reversed(recent_sessions):
        success_patterns = session.get("success_patterns", [])
        if not isinstance(success_patterns, list):
            continue
        for sp in success_patterns:
            if isinstance(sp, dict):
                pattern = sp.get("pattern", "")
                count = sp.get("count", 1)
                files = sp.get("files", [])
                file_str = ", ".join(files[:2]) if isinstance(files, list) and files else ""
                loc = f" ({file_str})" if file_str else ""
                results.append(f"{pattern} ×{count}{loc}")
            elif isinstance(sp, str):
                results.append(sp[:80])
        if len(results) >= 3:
            break
    return results[:3]


def parse_snapshot_sections(md_text):
    """P1-RLM: Parse snapshot into sections using SECTION markers.

    Splits a snapshot markdown string at <!-- SECTION:name --> boundaries,
    returning a dict mapping section names to their content.

    If no markers are found (pre-P1 snapshot), returns {"_full": md_text}.
    Non-blocking: returns partial results on any parse error.

    P1 Compliance: Deterministic string splitting.
    """
    marker_pattern = _SECTION_MARKER_RE

    sections = {}
    current_name = "_preamble"
    current_lines = []

    for line in md_text.split("\n"):
        match = marker_pattern.match(line.strip())
        if match:
            # Save previous section (even if empty)
            sections[current_name] = "\n".join(current_lines)
            current_name = match.group(1)
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    sections[current_name] = "\n".join(current_lines)

    # If no markers found, return full text
    if len(sections) <= 1 and "_preamble" in sections:
        return {"_full": md_text}

    return sections


# IMMORTAL sections that should always be loaded during selective peek
IMMORTAL_SECTIONS = {
    "header", "task", "next_step", "sot", "autopilot",
    "quality_gate", "team", "ulw", "diagnosis", "decisions",
    "resume", "completion", "git",
}


def _get_current_thesis_step(project_dir):
    """CM-3: Extract current_step from active (non-completed) thesis for proximity scoring.

    Uses _read_active_thesis_sot() — no additional disk read.
    Returns None for completed/paused projects (no active step to boost).
    Returns: int or None
    """
    _, sot = _read_active_thesis_sot(project_dir)
    if not sot:
        return None
    if sot.get("status") in ("completed", "paused"):
        return None
    step = sot.get("current_step")
    return step if isinstance(step, int) else None


def _retrieve_relevant_sessions(ki_path, task_info, file_paths, max_results=3,
                                current_step=None, error_info_for_scoring=False):
    """P0-RLM: Active Knowledge Retrieval — relevance-scored session matching.

    Instead of showing only the N most recent sessions, this function scores
    ALL knowledge-index entries by relevance to the current session context
    (task description + modified files) and returns the top matches.

    Scoring heuristic (deterministic, P1 compliant):
      - Keyword overlap between current task and past user_task/last_instruction
      - File path overlap between current modified files and past modified_files
      - Tag overlap between current path_tags and past tags
      - CM-3: thesis_step proximity boost (within ±2: +8, within ±5: +3)
      - Temporal decay: sessions within 30 days get recency bonus (max +3.0)
      - Error resolution rate: past sessions with resolved errors get bonus (+2.0 max)

    Returns: list of (score, session_dict) tuples, sorted by score desc.
    Non-blocking: returns empty list on any error.
    """
    if not os.path.exists(ki_path):
        return []

    try:
        all_sessions = []
        with open(ki_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        all_sessions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if not all_sessions:
            return []

        # Build current context keywords
        current_keywords = _tokenize(task_info)
        current_files = set(file_paths) if file_paths else set()
        current_file_basenames = {os.path.basename(f) for f in current_files if f}

        # H-3: Pre-compute current invocation number OUTSIDE the loop.
        # get_invocation_plan() is deterministic — same result for same current_step.
        # Computing inside the loop would be O(N) redundant calls.
        cur_invocation_number: int | None = None
        if current_step is not None:
            try:
                from query_step import get_invocation_plan
                _plan = get_invocation_plan(current_step)
                _in_progress = [p for p in _plan if p["status"] == "in_progress"]
                if _in_progress:
                    cur_invocation_number = _in_progress[0]["invocation"]
            except Exception:
                pass  # Non-blocking

        scored = []
        for session in all_sessions:
            score = 0.0

            # 1. Task keyword overlap (weight: 2.0 per match)
            past_task = session.get("user_task", "") or ""
            past_last = session.get("last_instruction", "") or ""
            past_keywords = _tokenize(past_task) | _tokenize(past_last)
            keyword_overlap = current_keywords & past_keywords
            score += len(keyword_overlap) * 2.0

            # 2. File path exact match (weight: 5.0 per match)
            past_files = session.get("modified_files", [])
            if isinstance(past_files, list):
                past_file_set = set(past_files)
                file_overlap = current_files & past_file_set
                score += len(file_overlap) * 5.0

                # 2b. Basename overlap (weight: 2.0) — catches path variations
                past_basenames = {os.path.basename(f) for f in past_files if f}
                basename_overlap = current_file_basenames & past_basenames
                score += len(basename_overlap - {os.path.basename(f) for f in file_overlap}) * 2.0

            # 3. Tag overlap (weight: 3.0 per match)
            past_tags = session.get("tags", [])
            if isinstance(past_tags, list) and current_files:
                current_tags = set(extract_path_tags(list(current_files)))
                tag_overlap = current_tags & set(past_tags)
                score += len(tag_overlap) * 3.0

            # 4. Error pattern type match (weight: 1.5) — same error types recur
            past_errors = session.get("error_patterns", [])
            if isinstance(past_errors, list) and past_errors:
                # M8: Proportional error pattern scoring (count-based + resolution bonus)
                resolved = sum(1 for e in past_errors if isinstance(e, dict) and e.get("resolution"))
                score += min(len(past_errors) * 0.3, 3.0)  # Count-based, capped at 3.0
                score += min(resolved * 0.5, 2.5)  # Resolution bonus, capped at 2.5

            # CM-3: Step proximity boost — sessions from nearby thesis steps are more relevant.
            # Reads "thesis_step" (scalar int, not a range — renamed from step_range).
            # Kept deliberately moderate so step proximity is a tie-breaker, not a dominator.
            # Max boost (15.0 at dist=0) is below file-match ceiling (~25.0) and keyword (~20.0).
            if current_step is not None:
                past_step = session.get("thesis_step")
                if isinstance(past_step, int):
                    dist = abs(past_step - current_step)
                    if dist == 0:
                        score += 15.0   # Exact same step — strongest signal
                    elif dist <= 2:
                        score += 8.0    # Adjacent steps — same chapter context
                    elif dist <= 5:
                        score += 3.0    # Same wave area — weak proximity

            # 5b. Invocation block proximity — sessions from same orchestrator invocation
            # share domain context (same wave/phase). Boost same-invocation sessions.
            # B-3: invocation_number stored in KI; A-2: used here for scoring.
            # H-3: cur_invocation_number is pre-computed OUTSIDE the loop (see below loop setup).
            if cur_invocation_number is not None:
                past_inv = session.get("invocation_number")
                if isinstance(past_inv, int):
                    inv_dist = abs(past_inv - cur_invocation_number)
                    if inv_dist == 0:
                        score += 12.0  # Same invocation block — strong relevance
                    elif inv_dist == 1:
                        score += 5.0   # Adjacent invocation — shared phase context

            # QO-3a: Design decision type match (weight: 3.5 per match)
            # Past sessions with similar design decisions are more relevant.
            # A-2 Fix: Filter common verbs/prepositions that inflate false matches.
            # _tokenize() only filters 2-char stops; decision text contains
            # "switched", "added", "used" etc. that match unrelated tasks.
            past_decisions = session.get("design_decisions", [])
            if isinstance(past_decisions, list) and past_decisions and current_keywords:
                decision_tokens = set()
                for d in past_decisions:
                    if isinstance(d, str):
                        raw = _tokenize(d)
                        decision_tokens |= {
                            t for t in raw
                            if t not in _DECISION_EXTRA_STOP_WORDS
                        }
                decision_overlap = current_keywords & decision_tokens
                score += min(len(decision_overlap) * 3.5, 14.0)  # Capped at 14.0

            # QO-3b: Tool sequence pattern match (weight: 2.5 per pattern hit)
            # Sessions with similar tool sequences represent similar work patterns.
            # A-1 Fix: Use regex to extract tool names cleanly from RLE format
            # (e.g., "Edit(3)→Bash(2)" → {"Edit", "Bash"}).
            past_tool_seq = session.get("tool_sequence", "")
            if isinstance(past_tool_seq, str) and past_tool_seq:
                past_tools = set(re.findall(r"([A-Z][a-zA-Z]+)", past_tool_seq))
                has_edit_bash = "Edit" in past_tools and "Bash" in past_tools
                has_agent = "Agent" in past_tools
                if has_edit_bash:
                    score += 2.5  # Code modification + validation pattern
                if has_agent:
                    score += 1.5  # Agent delegation pattern

            # QO-3c: Phase alignment (weight: 2.0 for exact match, 1.0 for related)
            # Sessions in the same workflow phase share context constraints.
            past_phase = session.get("phase", "")
            past_session_type = session.get("session_type", "")
            if past_phase or past_session_type:
                # Phase flow alignment — same phase means similar work context
                past_phase_flow = session.get("phase_flow", past_phase)
                if isinstance(past_phase_flow, str) and past_phase_flow:
                    past_phase_tokens = set(past_phase_flow.lower().replace("→", " ").split())
                    # Use current task keywords as proxy for current phase
                    phase_keywords = {"implementation", "research", "writing", "debugging",
                                      "audit", "refactoring", "translation", "exploration"}
                    cur_phase_kw = current_keywords & phase_keywords
                    past_phase_kw = past_phase_tokens & phase_keywords
                    if cur_phase_kw and cur_phase_kw & past_phase_kw:
                        score += 2.0  # Same phase type

            # QO-3d: Success pattern applicability (weight: 3.0 per applicable pattern)
            # Past sessions with proven success patterns for similar file types.
            past_success = session.get("success_patterns", [])
            if isinstance(past_success, list) and past_success and current_file_basenames:
                for sp in past_success:
                    if not isinstance(sp, dict):
                        continue
                    sp_files = sp.get("files", [])
                    if isinstance(sp_files, list):
                        sp_basenames = {os.path.basename(f) for f in sp_files if f}
                        if sp_basenames & current_file_basenames:
                            score += 3.0  # Same files → pattern directly applicable
                            break  # One match is enough

            # 6. Temporal decay — recent sessions are more likely relevant
            # Max boost: +3.0 at age=0, linear decay to 0 at 30 days
            session_ts = session.get("timestamp")
            if session_ts:
                try:
                    session_time = datetime.fromisoformat(session_ts.replace("Z", "+00:00"))
                    age_days = (datetime.now(session_time.tzinfo) - session_time).total_seconds() / 86400
                    if 0 <= age_days <= 30:
                        score += max(0.0, (30 - age_days) * 0.1)  # 3.0 at day 0, 0 at day 30
                except (ValueError, TypeError, AttributeError):
                    pass

            # 7. Error resolution rate — sessions with resolved errors boost
            # CM-OPT-1: Always score (not conditional on current-session errors).
            # Past error solutions are valuable preemptively — surface them BEFORE
            # the current session hits the same error, not only after.
            past_err_for_res = session.get("error_patterns", [])
            if isinstance(past_err_for_res, list) and past_err_for_res:
                resolved = sum(1 for e in past_err_for_res if isinstance(e, dict) and e.get("resolution"))
                total = len(past_err_for_res)
                if total > 0 and resolved > 0:
                    resolution_rate = resolved / total
                    score += min(resolution_rate * 2.0, 2.0)  # Up to +2.0

            if score > 0:
                scored.append((score, session))

        # Sort by score descending, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:max_results]
    except Exception:
        return []


def _extract_quarterly_insights(qa_path):
    """P3-RLM: Extract actionable insights from quarterly archive.

    Reads knowledge-archive-quarterly.jsonl and surfaces:
    - Top recurring error types across quarters
    - Persistent high-touch files (frequently modified)
    - Design decision continuity

    P1 Compliance: Deterministic aggregation from structured JSON data.
    Non-blocking: returns empty list on any error.
    Returns: list of human-readable insight strings.
    """
    if not os.path.exists(qa_path):
        return []

    try:
        quarters = []
        with open(qa_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        quarters.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if not quarters:
            return []

        insights = []

        # 1. Aggregate error patterns across all quarters
        error_totals = {}
        total_sessions = 0
        for q in quarters:
            total_sessions += q.get("session_count", 0)
            for etype, count in q.get("error_patterns_aggregated", {}).items():
                error_totals[etype] = error_totals.get(etype, 0) + count

        if error_totals:
            top_errors = sorted(error_totals.items(), key=lambda x: x[1], reverse=True)[:3]
            error_str = ", ".join(f"{t}({c})" for t, c in top_errors)
            insights.append(f"반복 에러: {error_str} (총 {total_sessions} 세션)")

        # 2. Top modified files across quarters
        file_totals = {}
        for q in quarters:
            for fpath, count in q.get("top_modified_files", {}).items():
                file_totals[fpath] = file_totals.get(fpath, 0) + count
        if file_totals:
            top_files = sorted(file_totals.items(), key=lambda x: x[1], reverse=True)[:3]
            for fpath, count in top_files:
                basename = os.path.basename(fpath)
                insights.append(f"고빈도 수정: {basename} ({count}회)")

        # 3. Design decision count
        total_decisions = sum(
            len(q.get("design_decisions", [])) for q in quarters
        )
        if total_decisions > 0:
            insights.append(f"누적 설계 결정: {total_decisions}개 ({len(quarters)}분기)")

        return insights
    except Exception:
        return []


def _extract_compression_audit(snapshot_content):
    """Extract compression-audit HTML comment from snapshot.

    Format: <!-- compression-audit: P1-dedup:-500ch P3-wlog:-200ch P5-diff:-800ch | final:8500ch/12000ch -->
    Only surfaces a warning if compression reached P5+ (significant data loss).
    Returns: warning string or empty string.
    """
    match = re.search(
        r'<!-- compression-audit:\s*(.*?)\s*\|\s*final:(\d+)ch/(\d+)ch\s*-->',
        snapshot_content,
    )
    if len(snapshot_content) > 1000000:  # 1MB limit for regex/processing
        return "⚠️  COMPRESSION: Snapshot too large for detailed audit."

    phases_str = match.group(1).strip()
    final_size = int(match.group(2))
    max_size = int(match.group(3))

    # Extract highest phase number from P1-xxx, P5-xxx, P7-xxx format
    phase_nums = re.findall(r'P(\d+)-', phases_str)
    max_phase = max((int(p) for p in phase_nums), default=0)

    if max_phase >= 5:
        ratio = round(final_size / max_size * 100) if max_size > 0 else 0
        return (
            f"⚠️ COMPRESSION: Snapshot was compressed to P{max_phase} "
            f"({ratio}% of max). Some context may have been lost. "
            f"Read the full snapshot file for complete details."
        )
    return ""


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
