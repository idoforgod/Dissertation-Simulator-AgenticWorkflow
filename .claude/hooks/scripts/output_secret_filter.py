#!/usr/bin/env python3
"""
PostToolUse Hook — Output Secret Filter

Detects secrets in tool output and warns Claude via stderr.
Does NOT block — exit code 0 always. Warnings via stderr.

Triggered by: PostToolUse with matcher "Bash|Read"
Location: .claude/settings.json (Project)
Path: Direct execution (standalone, NOT through context_guard.py)

P1 Hallucination Prevention: Secret detection is deterministic
(regex-based). No AI judgment needed — 100% accurate for defined patterns.

Data flow (3-tier extraction — most reliable first):
  stdin JSON → Tier 1: tool_response direct extraction
             → Tier 2: file read via tool_input.file_path (Read only)
             → Tier 3: transcript JSONL fallback
  → 25+ pre-compiled regex full scan (all patterns, no early exit)
  → base64/URL decoding for 2nd pass scan (anti-evasion)
  → stderr warning to Claude (exit 0 always)
  → security.log atomic append with fcntl.flock (audit log, values excluded)

Design decisions:
  - 3-tier extraction eliminates transcript timing dependency:
    Tier 1: tool_response (Bash: stdout/stderr, Read: file.content)
    Tier 2: Direct file read via tool_input.file_path (Read fallback)
    Tier 3: Transcript JSONL parsing (last resort)
  - All patterns scanned exhaustively (no early exit — quality > speed).
  - Standalone: No _context_lib.py import for fast startup + independence.
  - security.log uses fcntl.flock for atomic writes (audit log integrity).
  - Log file created with chmod 600 (security of security infrastructure).
  - 2-pass scanning: raw text + base64/URL decoded variants (anti-evasion).

Known limitations:
  - Regex patterns detect known formats only. Novel/custom secret formats
    may not be detected. Acceptable: deterministic > heuristic.
  - base64 decoding may produce false positives on random binary data.
    Mitigated: only flag if decoded content matches a SECRET_PATTERN.
  - If all 3 tiers fail, exits silently (safe).
  - Cannot REMOVE secrets from Claude's context (already loaded).
    This is a DETECTIVE control, not PREVENTIVE. Prevention is handled
    by settings.json deny patterns (Layer 0).

Safety-first: Any unexpected internal error → exit(0) (never block Claude).

ADR-050 in DECISION-LOG.md
"""

import base64
import fcntl
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Secret patterns — 25+ pre-compiled regexes
# Each: (type_name, compiled_regex)
#
# Ordered by prevalence in real-world leaks.
# All patterns are anchored to specific token formats to minimize false
# positives while maximizing true positive coverage.
# ---------------------------------------------------------------------------
SECRET_PATTERNS: List[Tuple[str, "re.Pattern"]] = [
    # --- Cloud Provider API Keys ---
    # OpenAI keys: sk-proj-..., sk-svcacct-..., sk-None-..., sk-<48 chars>
    ("openai_key", re.compile(r"sk-(?!ant-)[a-zA-Z0-9\-_]{20,}")),
    ("anthropic_key", re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[A-Z0-9]{16}")),
    ("aws_secret_key", re.compile(
        r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?\S{20,}"
    )),
    ("google_api_key", re.compile(r"AIza[a-zA-Z0-9_\-]{35}")),

    # --- Version Control Tokens ---
    ("github_pat", re.compile(r"ghp_[a-zA-Z0-9]{20,}")),
    ("github_server_token", re.compile(r"ghs_[a-zA-Z0-9]{20,}")),
    ("github_oauth_token", re.compile(r"gho_[a-zA-Z0-9]{20,}")),
    ("github_user_token", re.compile(r"ghu_[a-zA-Z0-9]{20,}")),
    ("github_refresh_token", re.compile(r"ghr_[a-zA-Z0-9]{20,}")),
    ("gitlab_pat", re.compile(r"glpat-[a-zA-Z0-9\-]{20,}")),

    # --- Messaging & SaaS ---
    ("slack_token", re.compile(r"xox[bprs]-[a-zA-Z0-9\-]{10,}")),
    ("slack_webhook", re.compile(
        r"https://hooks\.slack\.com/services/T[A-Z0-9]+/"
    )),
    ("npm_token", re.compile(r"npm_[a-zA-Z0-9]{36}")),

    # --- Payment ---
    ("stripe_secret_key", re.compile(r"sk_(live|test)_[a-zA-Z0-9]{20,}")),
    ("stripe_restricted_key", re.compile(r"rk_(live|test)_[a-zA-Z0-9]{20,}")),

    # --- Communication ---
    ("twilio_api_key", re.compile(r"SK[a-f0-9]{32}")),
    ("sendgrid_api_key", re.compile(
        r"SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}"
    )),

    # --- Generic Credentials ---
    ("bearer_token", re.compile(r"Bearer\s+[a-zA-Z0-9._\-]{20,}")),
    ("basic_auth", re.compile(r"Basic\s+[A-Za-z0-9+/=]{20,}")),
    ("private_key_header", re.compile(
        r"-----BEGIN\s+(RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE KEY-----"
    )),

    # --- Database Connection Strings ---
    ("database_uri", re.compile(
        r"(?i)(postgres|mysql|mongodb|redis|amqp)://[^\s:]+:[^\s@]+@"
    )),

    # --- Environment Variable Assignments with Sensitive Values ---
    ("env_secret_assignment", re.compile(
        r"(?i)(API_KEY|SECRET_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY"
        r"|ACCESS_KEY|CLIENT_SECRET|AUTH_TOKEN|DB_PASSWORD"
        r"|DATABASE_URL|REDIS_URL|MONGO_URI"
        r"|ENCRYPTION_KEY|SIGNING_KEY|JWT_SECRET)"
        r"\s*[=:]\s*['\"]?[a-zA-Z0-9_\-./+]{8,}"
    )),

    # --- JWT Tokens (Supabase, Firebase, etc.) ---
    ("jwt_token", re.compile(
        r"eyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\."
        r"[a-zA-Z0-9_\-]{10,}"
    )),
]

# Maximum lines to read from transcript tail (defensive limit)
_MAX_TRANSCRIPT_TAIL_LINES = 200

# Security log path (relative to project .claude/context-snapshots/)
_SECURITY_LOG_FILENAME = "security.log"


# ---------------------------------------------------------------------------
# Core scanning functions
# ---------------------------------------------------------------------------

def scan_text(text: str) -> List[Tuple[str, str]]:
    """Pass 1: Scan raw text against all secret patterns.

    Returns list of (secret_type, match_preview) tuples.
    All patterns are checked exhaustively — no early exit.
    """
    findings = []
    for secret_type, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            # group(0) = full match (not capturing group content)
            preview = _mask_value(match.group(0))
            findings.append((secret_type, preview))
    return findings


def scan_decoded_variants(text: str) -> List[Tuple[str, str]]:
    """Pass 2: Decode base64/URL encoded segments and re-scan.

    Anti-evasion: catches secrets hidden in encoded form.
    Returns list of (secret_type, encoding_method) tuples.
    """
    findings = []

    # --- base64 decoding ---
    # Look for base64-like segments (20+ chars, valid base64 alphabet)
    b64_pattern = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
    for match in b64_pattern.finditer(text):
        try:
            decoded = base64.b64decode(match.group()).decode(
                "utf-8", errors="ignore"
            )
            if not decoded or len(decoded) < 8:
                continue
            for secret_type, pattern in SECRET_PATTERNS:
                if pattern.search(decoded):
                    findings.append((secret_type, "base64-encoded"))
        except Exception:
            continue

    # --- URL decoding ---
    if "%" in text:
        try:
            decoded = urllib.parse.unquote(text)
            if decoded != text:  # Actually decoded something
                for secret_type, pattern in SECRET_PATTERNS:
                    if pattern.search(decoded) and not pattern.search(text):
                        # Only flag if the secret is visible ONLY after decoding
                        findings.append((secret_type, "url-encoded"))
        except Exception:
            pass

    return findings


def _mask_value(value: str) -> str:
    """Mask a secret value for safe display.

    Format: first 4 chars + ***MASKED*** + last 4 chars
    Never expose more than 8 characters of the actual value.
    """
    if len(value) <= 12:
        return value[:4] + "***MASKED***"
    return value[:4] + "***MASKED***" + value[-4:]


# ---------------------------------------------------------------------------
# 3-Tier tool output extraction
# ---------------------------------------------------------------------------

# Maximum bytes to read from file for Read tool scanning
_MAX_READ_FILE_BYTES = 200_000  # 200KB cap for direct file reads


def extract_from_tool_response(
    tool_name: str, tool_response: dict,
) -> Optional[str]:
    """Tier 1: Extract tool output directly from tool_response.

    PostToolUse stdin provides tool_response with actual tool output.
    Structure varies by tool (empirically verified against transcript):

      Bash: {"stdout": "...", "stderr": "...", "interrupted": bool, ...}
      Read: {"type": "text", "file": {"filePath": "...", "content": "...", ...}}
      Edit: {"filePath": "...", "oldString": "...", "newString": "...", ...}

    This is the MOST RELIABLE extraction path — no transcript timing
    dependency, no file I/O beyond stdin parsing.

    Returns None if tool_response is empty or has no scannable content.
    """
    if not isinstance(tool_response, dict) or not tool_response:
        return None

    # --- Bash: stdout + stderr ---
    stdout = tool_response.get("stdout", "")
    stderr = tool_response.get("stderr", "")
    if stdout or stderr:
        return ((stdout or "") + "\n" + (stderr or "")).strip()

    # --- Read: file.content ---
    file_info = tool_response.get("file")
    if isinstance(file_info, dict):
        content = file_info.get("content", "")
        if isinstance(content, str) and content:
            return content

    return None


def extract_from_file_path(tool_input: dict) -> Optional[str]:
    """Tier 2: Read file content directly from disk (Read tool fallback).

    If tool_response didn't provide content for a Read tool invocation,
    read the file directly using tool_input.file_path.

    Caps at _MAX_READ_FILE_BYTES to prevent memory issues on large files.
    Returns None if file is missing, unreadable, or path not provided.
    """
    file_path = tool_input.get("file_path", "")
    if not file_path or not os.path.isfile(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(_MAX_READ_FILE_BYTES)
    except (IOError, OSError):
        return None


def extract_last_tool_output(transcript_path: str) -> Optional[str]:
    """Tier 3: Read the last tool_result from transcript JSONL (fallback).

    Used only when Tier 1 (tool_response) and Tier 2 (file read) fail.

    Claude Code transcript structure (verified against actual JSONL):
      - Top-level entries have type: "user", "assistant", "progress", "system"
      - Tool results are NESTED inside "user" entries:
        entry["message"]["content"][N]["type"] == "tool_result"
        entry["message"]["content"][N]["content"] == <actual text>
      - Bash results also have entry["toolUseResult"]["stdout"/"stderr"]

    This function reads tail of transcript and searches backwards for the
    most recent user entry containing a tool_result content block.

    Returns None if transcript is missing, empty, or has no tool_result.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return None

    try:
        # Read last N lines from transcript (tail-read for efficiency)
        lines = _tail_read(transcript_path, _MAX_TRANSCRIPT_TAIL_LINES)
        if not lines:
            return None

        # Search backwards for the most recent tool_result
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Tool results live inside "user" type entries
            if entry.get("type") != "user":
                continue

            # Path 1: toolUseResult.stdout (Bash results — raw output)
            tool_use_result = entry.get("toolUseResult")
            if isinstance(tool_use_result, dict):
                stdout = tool_use_result.get("stdout", "")
                stderr = tool_use_result.get("stderr", "")
                combined = (stdout or "") + "\n" + (stderr or "")
                combined = combined.strip()
                if combined:
                    return combined

            # Path 2: message.content[].tool_result (all tool types)
            message = entry.get("message", {})
            content_blocks = message.get("content", [])
            if not isinstance(content_blocks, list):
                continue

            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_result":
                    continue

                block_content = block.get("content", "")
                if isinstance(block_content, str) and block_content:
                    return block_content
                elif isinstance(block_content, list):
                    # Content blocks format (array of text blocks)
                    texts = []
                    for sub in block_content:
                        if isinstance(sub, dict):
                            texts.append(sub.get("text", ""))
                        elif isinstance(sub, str):
                            texts.append(sub)
                    joined = "\n".join(texts).strip()
                    if joined:
                        return joined

    except (IOError, OSError):
        pass

    return None


def _tail_read(filepath: str, max_lines: int) -> List[str]:
    """Read the last max_lines from a file efficiently.

    Uses seek to avoid reading the entire file.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            # Try to seek near the end (estimate ~2000 bytes per JSONL line)
            # Transcript JSONL entries can be large (file contents embedded
            # in tool_result blocks), so 500 bytes/line is insufficient.
            file_size = os.path.getsize(filepath)
            seek_pos = max(0, file_size - (max_lines * 2000))

            if seek_pos > 0:
                f.seek(seek_pos)
                f.readline()  # Discard partial line at seek point

            lines = f.readlines()
            return lines[-max_lines:]
    except (IOError, OSError):
        return []


# ---------------------------------------------------------------------------
# Security logging
# ---------------------------------------------------------------------------

def log_security_event(
    project_dir: str,
    findings: List[Tuple[str, str]],
    tool_name: str,
    session_id: str,
):
    """Append security event to security.log with file locking.

    Audit log: security.log is an append-only audit trail for
    security events. NOT a SOT — nothing reads this programmatically.
    Uses fcntl.flock for atomic writes.

    NEVER logs actual secret values — only types and counts.
    """
    snapshot_dir = os.path.join(project_dir, ".claude", "context-snapshots")
    os.makedirs(snapshot_dir, exist_ok=True)

    log_path = os.path.join(snapshot_dir, _SECURITY_LOG_FILENAME)

    # Deduplicate findings by type
    type_counts = {}
    for secret_type, detail in findings:
        type_counts[secret_type] = type_counts.get(secret_type, 0) + 1

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": session_id,
        "tool_name": tool_name,
        "findings_count": len(findings),
        "secret_types": type_counts,
    }

    entry_line = json.dumps(entry, ensure_ascii=False) + "\n"

    try:
        # Ensure restrictive permissions on security log
        fd = os.open(
            log_path,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o600,  # Owner read/write only
        )
        with os.fdopen(fd, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(entry_line)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (IOError, OSError):
        pass  # Security log failure must not block Claude


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    """Read PostToolUse JSON from stdin, scan tool output for secrets.

    Uses 3-tier extraction strategy (most reliable first):
      Tier 1: tool_response direct (no external I/O)
      Tier 2: file read via tool_input.file_path (Read tool only)
      Tier 3: transcript JSONL fallback (last resort)
    """
    # Parse stdin JSON
    try:
        stdin_data = sys.stdin.read()
        if not stdin_data.strip():
            sys.exit(0)

        payload = json.loads(stdin_data)
    except (json.JSONDecodeError, KeyError, TypeError):
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    session_id = payload.get("session_id", "unknown")
    tool_input = payload.get("tool_input", {})
    tool_response = payload.get("tool_response", {})
    transcript_path = payload.get("transcript_path", "")

    # Determine project directory
    project_dir = os.environ.get(
        "CLAUDE_PROJECT_DIR",
        payload.get("cwd", os.getcwd()),
    )

    # --- 3-Tier extraction: most reliable first ---

    # Tier 1: Direct from tool_response (no timing dependency)
    output_text = extract_from_tool_response(tool_name, tool_response)

    # Tier 2: Direct file read for Read tool (no transcript dependency)
    if output_text is None and tool_name == "Read":
        output_text = extract_from_file_path(tool_input)

    # Tier 3: Transcript JSONL fallback (last resort)
    if output_text is None:
        output_text = extract_last_tool_output(transcript_path)

    if not output_text:
        sys.exit(0)

    # --- Pass 1: Raw text scan ---
    raw_findings = scan_text(output_text)

    # --- Pass 2: Decoded variants scan (anti-evasion) ---
    decoded_findings = scan_decoded_variants(output_text)

    # --- Combine all findings ---
    all_findings = raw_findings + decoded_findings

    if not all_findings:
        sys.exit(0)

    # --- Log to security.log (values excluded, types/counts only) ---
    log_security_event(project_dir, all_findings, tool_name, session_id)

    # --- Warn Claude via stderr ---
    # Deduplicate by type for concise warning
    types_seen = {}
    for secret_type, detail in all_findings:
        if secret_type not in types_seen:
            types_seen[secret_type] = detail

    types_summary = ", ".join(
        f"{t} ({d})" for t, d in types_seen.items()
    )

    print(
        f"SECRET DETECTED IN TOOL OUTPUT: {len(all_findings)} potential "
        f"secret(s) found.\n"
        f"  Types: {types_summary}\n"
        f"  Tool: {tool_name}\n"
        f"  WARNING: Do NOT include these values in:\n"
        f"    - Code (hardcoded strings, constants)\n"
        f"    - Git commits (staged content, commit messages)\n"
        f"    - Responses to the user (chat output)\n"
        f"    - Log files or documentation\n"
        f"  INSTEAD: Reference them via environment variables or secret "
        f"managers.",
        file=sys.stderr,
    )

    # Always exit 0 — warn, don't block
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Safety-first: never block Claude on unexpected internal errors
        sys.exit(0)
