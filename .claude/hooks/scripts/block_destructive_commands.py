#!/usr/bin/env python3
"""
PreToolUse Hook — Destructive Command Blocker

Blocks dangerous commands BEFORE execution via exit code 2.
Claude receives stderr feedback and self-corrects.

Triggered by: PreToolUse with matcher "Bash"
Location: .claude/settings.json (Project)
Path: Direct execution (standalone, NOT through context_guard.py)

P1 Hallucination Prevention: Destructive command detection is deterministic
(regex-based). No AI judgment needed — 100% accurate for defined patterns.

Blocked patterns (from Claude Code safety guidelines + ADR-049 security hardening):

  Network exfiltration:
  - curl ... | sh/bash (piping remote content to shell)
  - wget ... | sh/bash (piping remote content to shell)

  Destructive system commands:
  - dd if= (raw disk write, irreversible)
  - mkfs (filesystem format, destroys all data)

  Git destructive operations:
  - git push --force (NOT --force-with-lease or --force-if-includes)
  - git push -f (short flag, including combined forms like -fu)
  - git reset --hard
  - git checkout . (discards ALL unstaged changes)
  - git restore . (discards ALL changes)
  - git clean -f (removes untracked files)
  - git branch -D or --delete --force (force-deletes branch)

  Catastrophic file deletion:
  - rm -rf / or rm -rf ~ (catastrophic file deletion)

Known limitations:
  - Commands in string literals may cause false positives
    (e.g., echo "git push --force" would be blocked).
    Acceptable: false positive > false negative for safety hooks.
  - Patterns check the raw command string, not parsed shell AST.

Safety-first: Any unexpected internal error → exit(0) (never block Claude).

ADR-031 (original), ADR-050 (network/system extension) in DECISION-LOG.md
"""

import json
import re
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Destructive Git patterns
# Each: (compiled_regex, stderr message for Claude self-correction)
#
# Regex notes:
#   - \s before -- flags (not \b) because \b fails between space and dash
#   - (?![-\w]) after --force to exclude --force-with-lease, --force-if-includes
#   - \s-[a-zA-Z]*f for combined short flags (-f, -uf, -fu all match)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Network exfiltration patterns — piping remote content to shell execution
# ---------------------------------------------------------------------------
NETWORK_PATTERNS = [
    # curl piped to shell (curl ... | sh, curl ... | bash)
    (
        re.compile(r"\bcurl\b.*\|\s*(ba)?sh\b"),
        "curl piped to shell is blocked. "
        "Download the file first, inspect it, then execute manually.",
    ),
    # wget piped to shell (wget ... | sh, wget ... | bash)
    (
        re.compile(r"\bwget\b.*\|\s*(ba)?sh\b"),
        "wget piped to shell is blocked. "
        "Download the file first, inspect it, then execute manually.",
    ),
]

# ---------------------------------------------------------------------------
# Destructive system patterns — irreversible system-level operations
# ---------------------------------------------------------------------------
SYSTEM_PATTERNS = [
    # dd if= (raw disk write)
    (
        re.compile(r"\bdd\b\s+if="),
        "dd is blocked. "
        "Raw disk write can cause irreversible data loss.",
    ),
    # mkfs (filesystem format)
    (
        re.compile(r"\bmkfs\b"),
        "mkfs is blocked. "
        "Filesystem formatting destroys all data on the target device.",
    ),
]

# ---------------------------------------------------------------------------
# Destructive Git patterns
# Each: (compiled_regex, stderr message for Claude self-correction)
#
# Regex notes:
#   - \s before -- flags (not \b) because \b fails between space and dash
#   - (?![-\w]) after --force to exclude --force-with-lease, --force-if-includes
#   - \s-[a-zA-Z]*f for combined short flags (-f, -uf, -fu all match)
# ---------------------------------------------------------------------------
GIT_PATTERNS = [
    # git push --force (NOT --force-with-lease or --force-if-includes)
    (
        re.compile(r"\bgit\s+push\b.*\s--force(?![-\w])"),
        "git push --force is blocked. "
        "Use --force-with-lease for safer force pushing.",
    ),
    # git push -f (short flag, including combined forms like -fu, -uf)
    (
        re.compile(r"\bgit\s+push\b.*\s-[a-zA-Z]*f"),
        "git push -f is blocked. "
        "Use --force-with-lease for safer force pushing.",
    ),
    # git reset --hard
    (
        re.compile(r"\bgit\s+reset\b.*\s--hard(?![-\w])"),
        "git reset --hard is blocked. "
        "Discards uncommitted changes irreversibly. "
        "Use git stash or git reset --soft instead.",
    ),
    # git checkout . (discard ALL unstaged changes)
    (
        re.compile(r"\bgit\s+checkout\b\s+(?:--\s+)?\.(?:\s|$)"),
        "git checkout . is blocked. "
        "Discards all unstaged changes. "
        "Use git stash to preserve changes first.",
    ),
    # git restore . (discard ALL changes, with or without --staged)
    (
        re.compile(r"\bgit\s+restore\b(?:\s+--[\w-]+)*\s+\.(?:\s|$)"),
        "git restore . is blocked. "
        "Discards all changes. "
        "Use git stash to preserve changes first.",
    ),
    # git clean -f (remove untracked files, any combined flag with f)
    (
        re.compile(r"\bgit\s+clean\b.*\s-[a-zA-Z]*f"),
        "git clean -f is blocked. "
        "Permanently removes untracked files. "
        "Use git clean -n (dry run) to preview first.",
    ),
    # git branch -D (force delete, unlike safe -d)
    (
        re.compile(r"\bgit\s+branch\b.*\s-D"),
        "git branch -D is blocked. "
        "Force-deletes branch even if not fully merged. "
        "Use git branch -d for safe deletion.",
    ),
    # git branch --delete --force (long form of -D, any order)
    (
        re.compile(r"\bgit\s+branch\b.*\s--delete\b.*\s--force\b"),
        "git branch --delete --force is blocked. "
        "Force-deletes branch even if not fully merged. "
        "Use git branch -d for safe deletion.",
    ),
    (
        re.compile(r"\bgit\s+branch\b.*\s--force\b.*\s--delete\b"),
        "git branch --force --delete is blocked. "
        "Force-deletes branch even if not fully merged. "
        "Use git branch -d for safe deletion.",
    ),
]


def _check_dangerous_rm(sub_command: str) -> Optional[str]:
    """Check if an rm sub-command targets root or home with recursive+force.

    Parses flags and targets separately to handle all flag orderings:
    rm -rf /, rm -fr /, rm -r -f /, etc.
    """
    tokens = sub_command.split()
    if not tokens or tokens[0] != "rm":
        return None

    # Collect all single-dash flag characters and targets
    flags = ""
    targets = []
    for token in tokens[1:]:
        if token.startswith("-") and not token.startswith("--"):
            flags += token[1:]  # strip leading dash
        elif not token.startswith("-"):
            targets.append(token.strip("\"'"))

    has_recursive = "r" in flags or "R" in flags
    has_force = "f" in flags

    if not (has_recursive and has_force):
        return None

    # Catastrophic targets only — specific paths, not general directories
    dangerous = {"/", "/*", "~", "~/", "$HOME", "$HOME/", "$HOME/*"}
    for target in targets:
        if target in dangerous:
            return (
                f"rm -rf targeting {target} is blocked. "
                "Catastrophic, irreversible file deletion."
            )
    return None


def check_command(command: str) -> Optional[str]:
    """Check command against all destructive patterns.

    Returns block message if pattern matches, None otherwise.

    Check order (most specific → broadest):
      1. Network exfiltration (pipe-to-shell patterns)
      2. Destructive system commands (dd, mkfs)
      3. Git destructive operations (force push, hard reset, etc.)
      4. Catastrophic file deletion (rm -rf /, rm -rf ~)
    """
    # Network patterns: check entire command string (pipe-to-shell)
    for pattern, message in NETWORK_PATTERNS:
        if pattern.search(command):
            return message

    # System patterns: check entire command string
    for pattern, message in SYSTEM_PATTERNS:
        if pattern.search(command):
            return message

    # Git patterns: check entire command string (regex handles flag positions)
    for pattern, message in GIT_PATTERNS:
        if pattern.search(command):
            return message

    # rm patterns: split by shell operators and check each sub-command
    for sub_cmd in re.split(r"\s*(?:&&|\|\||;)\s*", command):
        for segment in sub_cmd.split("|"):
            result = _check_dangerous_rm(segment.strip())
            if result:
                return result

    return None


def main():
    """Read PreToolUse JSON from stdin, check for destructive commands."""
    # Read Hook JSON payload from stdin
    # Format: {"tool_name": "Bash", "tool_input": {"command": "..."}}
    try:
        stdin_data = sys.stdin.read()
        if not stdin_data.strip():
            sys.exit(0)

        payload = json.loads(stdin_data)
        command = payload.get("tool_input", {}).get("command", "")

        if not command:
            sys.exit(0)
    except (json.JSONDecodeError, KeyError, TypeError):
        # Malformed input — don't block, exit cleanly
        sys.exit(0)

    # Check against destructive patterns
    block_message = check_command(command)

    if block_message:
        # Exit code 2 = Claude Hook blocking signal
        # stderr content is sent to Claude for self-correction
        print(
            f"DESTRUCTIVE COMMAND BLOCKED: {block_message}\n"
            f"Command was: {command[:200]}",
            file=sys.stderr,
        )
        sys.exit(2)

    # No match — allow command to proceed
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Safety-first: never block Claude on unexpected internal errors
        sys.exit(0)
