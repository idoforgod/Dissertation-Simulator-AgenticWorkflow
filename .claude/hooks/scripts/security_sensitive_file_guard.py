#!/usr/bin/env python3
"""
PostToolUse Hook — Security-Sensitive File Guard

Warns Claude when Edit|Write targets security-sensitive files.
Does NOT block — exit code 0 always. Warnings via stderr.

Triggered by: PostToolUse with matcher "Edit|Write"
Location: .claude/settings.json (Project)
Path: Direct execution (standalone, NOT through context_guard.py)

P1 Hallucination Prevention: File path matching is deterministic
(regex-based). No AI judgment needed — 100% accurate for defined patterns.

Layer context:
  - Layer 0 (settings.json deny): Already blocks ~/.ssh/*, ~/.zshrc, etc.
  - Layer 1 (PreToolUse): block_destructive_commands.py blocks dangerous ops.
  - Layer 2 (THIS HOOK): Catches project-level security files that Layer 0
    cannot block (e.g., .env in project root, credentials.json, *.pem).

Data flow:
  stdin JSON → extract file_path from tool_input
  → 12 pre-compiled regex patterns check
  → session deduplication (warn once per file per session)
  → stderr warning to Claude (exit 0 always)

Design decisions:
  - PostToolUse (not PreToolUse): The edit has already happened. This is a
    detective control that warns Claude to review what was written. Blocking
    would be too aggressive for legitimate project config edits.
  - Session deduplication: Uses /tmp/{session_id}_sensitivefiles.json to
    track warned files. Avoids alert fatigue on repeated edits.
  - Standalone: No _context_lib.py import for fast startup + independence.
  - Exit 0 always: This is a WARNING hook, not a BLOCKING hook.

Known limitations:
  - Cannot PREVENT writes to sensitive files (already happened in PostToolUse).
    Prevention for critical paths is handled by settings.json deny (Layer 0).
  - Session dedup file in /tmp is cleaned on OS reboot, not session end.
    Acceptable: /tmp is ephemeral by design, and stale entries are harmless.
  - Patterns check normalized file paths. Symlink targets are NOT resolved.

ADR-050 in DECISION-LOG.md (Security Hardening)
"""

import json
import os
import re
import sys
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Security-sensitive file patterns — 12 pre-compiled regexes
# Each: (compiled_regex, description_for_warning)
#
# These patterns catch files that settings.json deny CANNOT block because
# they are project-internal (not system-level paths like ~/.ssh/).
# ---------------------------------------------------------------------------
SENSITIVE_PATTERNS: List[Tuple["re.Pattern", str]] = [
    # --- Environment variable files ---
    # .env, .env.local, .env.production, .env.development, etc.
    (
        re.compile(r"(^|[/\\])\.env(\.\w+)?$"),
        "environment variable file (may contain API keys/secrets)",
    ),

    # --- Private keys and certificates ---
    (
        re.compile(r"\.(pem|key|p12|pfx|jks|keystore)$", re.IGNORECASE),
        "private key or certificate file",
    ),
    (
        re.compile(r"(^|[/\\])id_(rsa|dsa|ecdsa|ed25519)$"),
        "SSH private key",
    ),

    # --- Credential configuration files ---
    (
        re.compile(
            r"(^|[/\\])(credentials|secrets|passwords?)"
            r"\.(json|yaml|yml|toml|xml|ini|cfg)$",
            re.IGNORECASE,
        ),
        "credentials/secrets configuration file",
    ),

    # --- Cloud provider credentials ---
    (
        re.compile(r"(^|[/\\])\.aws[/\\](credentials|config)$"),
        "AWS credentials file",
    ),
    (
        re.compile(r"(^|[/\\])\.gcloud[/\\]"),
        "GCP credentials directory",
    ),
    (
        re.compile(r"(^|[/\\])\.azure[/\\]"),
        "Azure credentials directory",
    ),

    # --- Auth token files ---
    (
        re.compile(r"(^|[/\\])\.(npmrc|pypirc|netrc|htpasswd)$"),
        "authentication token file",
    ),

    # --- Kubernetes secrets ---
    (
        re.compile(
            r"(^|[/\\]).*secret.*\.(yaml|yml)$",
            re.IGNORECASE,
        ),
        "potential Kubernetes secret manifest",
    ),

    # --- Token/key store files ---
    (
        re.compile(
            r"(^|[/\\])(token|api[_-]?key|auth[_-]?token)"
            r"\.(json|yaml|yml|txt)$",
            re.IGNORECASE,
        ),
        "token/API key store file",
    ),

    # --- Firebase/Supabase service account ---
    (
        re.compile(
            r"(^|[/\\]).*service[_-]?account.*\.json$",
            re.IGNORECASE,
        ),
        "service account key file",
    ),

    # --- Terraform state (contains secrets in plaintext) ---
    (
        re.compile(r"\.(tfstate|tfvars)$"),
        "Terraform state/vars file (may contain secrets in plaintext)",
    ),
]


# ---------------------------------------------------------------------------
# Session deduplication
# ---------------------------------------------------------------------------

def _dedup_path(session_id: str) -> str:
    """Return path to session deduplication file in /tmp."""
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
    return os.path.join("/tmp", f"claude_sensitive_{safe_id}.json")


def _was_already_warned(dedup_file: str, file_path: str) -> bool:
    """Check if we already warned about this file in this session."""
    try:
        if not os.path.exists(dedup_file):
            return False
        with open(dedup_file, "r") as f:
            warned = json.load(f)
        return file_path in warned
    except (json.JSONDecodeError, IOError, OSError):
        return False


def _record_warning(dedup_file: str, file_path: str):
    """Record that we warned about this file (session-scoped)."""
    try:
        warned = []
        if os.path.exists(dedup_file):
            with open(dedup_file, "r") as f:
                warned = json.load(f)
        if file_path not in warned:
            warned.append(file_path)
        with open(dedup_file, "w") as f:
            json.dump(warned, f)
    except (json.JSONDecodeError, IOError, OSError):
        pass  # Dedup failure must not block Claude


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

def check_sensitive_file(file_path: str) -> Optional[str]:
    """Check if file path matches any security-sensitive pattern.

    Returns description string if sensitive, None otherwise.
    All patterns are checked (no early exit — exhaustive scan).
    Returns the FIRST match description (most patterns are mutually exclusive).
    """
    # Normalize path separators for cross-platform matching
    normalized = file_path.replace("\\", "/")

    for pattern, description in SENSITIVE_PATTERNS:
        if pattern.search(normalized):
            return description

    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    """Read PostToolUse JSON from stdin, check for security-sensitive files."""
    try:
        stdin_data = sys.stdin.read()
        if not stdin_data.strip():
            sys.exit(0)

        payload = json.loads(stdin_data)
    except (json.JSONDecodeError, KeyError, TypeError):
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    session_id = payload.get("session_id", "unknown")
    file_path = payload.get("tool_input", {}).get("file_path", "")

    if not file_path:
        sys.exit(0)

    # Check against sensitive patterns
    description = check_sensitive_file(file_path)

    if not description:
        sys.exit(0)

    # Session deduplication — don't repeat warnings for same file
    dedup_file = _dedup_path(session_id)
    if _was_already_warned(dedup_file, file_path):
        sys.exit(0)

    # Record and warn
    _record_warning(dedup_file, file_path)

    # Determine project directory for relative path display
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    display_path = file_path
    if project_dir:
        try:
            display_path = os.path.relpath(file_path, project_dir)
        except ValueError:
            pass

    print(
        f"SECURITY-SENSITIVE FILE MODIFIED: {display_path}\n"
        f"  Type: {description}\n"
        f"  Tool: {tool_name}\n"
        f"  WARNING: Ensure this file does NOT contain:\n"
        f"    - Hardcoded secrets, API keys, or passwords\n"
        f"    - Plaintext credentials or tokens\n"
        f"    - Private key material\n"
        f"  BEST PRACTICE: Use environment variables or secret managers.\n"
        f"  If secrets are present, do NOT commit this file to git.",
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
