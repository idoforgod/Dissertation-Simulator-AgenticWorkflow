#!/usr/bin/env python3
"""
PreToolUse Hook — CCP-2 Ripple Effect Scanner (P1 Dependency Discovery)

Automatically discovers and reports dependencies of the file being edited,
providing deterministic data for CCP Step 2 (Ripple Effect Analysis).

The LLM MUST use this data when performing CCP-2. This eliminates the
"forgetting to check dependencies" failure mode.

Triggered by: PreToolUse with matcher "Edit|Write"
Location: .claude/settings.json (Project)
Path: Direct execution (standalone, NOT through context_guard.py)

P1 Hallucination Prevention:
  - File reference discovery is deterministic (subprocess grep).
  - Hub-Spoke sync map is hardcoded (known architecture).
  - Test file mapping uses naming conventions (deterministic regex).
  - Hook registration lookup is deterministic (JSON parse).
  - No _context_lib.py import — self-contained for fast startup.

SOT Compliance: NO ACCESS to SOT (state.yaml or session.json).
  Reads only stdin JSON (hook payload) and project files (grep-based).

Exit code: Always 0 — this is an INFORMATIONAL hook, never blocks.

Design decisions:
  - Self-contained: No imports from _context_lib.py (same rationale as
    predictive_debug_guard.py — each PreToolUse spawns a new process).
  - Grep-based: Uses subprocess grep for file reference discovery.
    For ~200 files, completes in <1 second.
  - Hub-Spoke map is hardcoded: Architecture changes are rare. The map
    has clear comments for maintenance. This is more P1-pure than heuristic
    discovery.
  - Stderr for Claude: Claude receives stderr as context for CCP-2.
  - Silent on no dependencies: If no external references found, exits
    without output (no noise for isolated files).

ADR: ADR-042 in DECISION-LOG.md
"""

import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Hub-Spoke Synchronization Map (Hardcoded — Deterministic)
#
# MAINTENANCE: When adding/removing Spoke files, update this map.
# This map defines which files MUST be checked for consistency when
# a Hub or Spoke file is modified.
# ---------------------------------------------------------------------------
HUB_SPOKE_MAP: Dict[str, Dict] = {
    "AGENTS.md": {
        "role": "Hub (complete definition)",
        "sync_targets": [
            "CLAUDE.md",
            "GEMINI.md",
            ".github/copilot-instructions.md",
            "docs/protocols/code-change-protocol.md",
            "AGENTICWORKFLOW-USER-MANUAL.md",
            "AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md",
            "README.md",
            ".cursor/rules/agenticworkflow.mdc",
            ".claude/skills/workflow-generator/SKILL.md",
            ".claude/skills/workflow-generator/references/workflow-template.md",
            ".claude/skills/workflow-generator/references/claude-code-patterns.md",
        ],
    },
    "CLAUDE.md": {
        "role": "Spoke (Claude Code — loaded every turn)",
        "sync_targets": ["AGENTS.md"],
    },
    "GEMINI.md": {
        "role": "Spoke (Gemini CLI)",
        "sync_targets": ["AGENTS.md"],
    },
    ".github/copilot-instructions.md": {
        "role": "Spoke (GitHub Copilot)",
        "sync_targets": ["AGENTS.md"],
    },
    "docs/protocols/code-change-protocol.md": {
        "role": "Detail (CCP protocol)",
        "sync_targets": ["AGENTS.md"],
    },
    "soul.md": {
        "role": "DNA definition (genome)",
        "sync_targets": ["AGENTS.md"],
    },
    "AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md": {
        "role": "Architecture document",
        "sync_targets": ["AGENTS.md", "CLAUDE.md"],
    },
    "AGENTICWORKFLOW-USER-MANUAL.md": {
        "role": "User manual",
        "sync_targets": ["AGENTS.md", "CLAUDE.md"],
    },
    ".cursor/rules/agenticworkflow.mdc": {
        "role": "Spoke (Cursor IDE)",
        "sync_targets": ["AGENTS.md"],
    },
    ".claude/skills/workflow-generator/SKILL.md": {
        "role": "Skill definition (workflow-generator)",
        "sync_targets": ["AGENTS.md"],
    },
    ".claude/skills/workflow-generator/references/workflow-template.md": {
        "role": "Skill reference (workflow template)",
        "sync_targets": ["AGENTS.md"],
    },
    ".claude/skills/workflow-generator/references/claude-code-patterns.md": {
        "role": "Skill reference (Claude Code patterns)",
        "sync_targets": ["AGENTS.md"],
    },
}

# ---------------------------------------------------------------------------
# D-7 Sync Pairs — files with intentionally duplicated data structures
# that MUST be updated together. When one file in a pair is edited,
# the scanner warns about the other.
#
# MAINTENANCE: When adding new D-7 pairs, add entries here.
# ---------------------------------------------------------------------------
D7_SYNC_PAIRS: Dict[str, List[str]] = {
    # REQUIRED_SCRIPTS list is duplicated in both setup scripts (D-7 design)
    ".claude/hooks/scripts/setup_init.py": [
        ".claude/hooks/scripts/setup_maintenance.py",
    ],
    ".claude/hooks/scripts/setup_maintenance.py": [
        ".claude/hooks/scripts/setup_init.py",
    ],
}

# ---------------------------------------------------------------------------
# Settings file path (relative to project root)
# ---------------------------------------------------------------------------
SETTINGS_REL_PATH = os.path.join(".claude", "settings.json")

# ---------------------------------------------------------------------------
# Test file naming conventions — deterministic mapping
# Pattern: production_file.py → _test_production_file.py
# ---------------------------------------------------------------------------
TEST_PREFIX = "_test_"
HOOKS_SCRIPTS_DIR = os.path.join(".claude", "hooks", "scripts")

# ---------------------------------------------------------------------------
# Files/directories to skip during grep (performance + noise reduction)
# ---------------------------------------------------------------------------
GREP_EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".claude/context-snapshots",
    "thesis-output", ".venv", "venv",
}

# Minimum number of dependency items to trigger output.
# If total dependencies found is 0, exit silently (no noise).
MIN_DEPS_FOR_OUTPUT = 1

# Maximum grep results per category to prevent output explosion
MAX_GREP_RESULTS = 20


def main():
    """Read PreToolUse JSON from stdin, scan dependencies, report via stderr."""
    try:
        stdin_data = sys.stdin.read()
        if not stdin_data.strip():
            sys.exit(0)

        payload = json.loads(stdin_data)
        file_path = payload.get("tool_input", {}).get("file_path", "")

        if not file_path:
            sys.exit(0)
    except (json.JSONDecodeError, KeyError, TypeError):
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        sys.exit(0)

    # Normalize to project-relative path
    try:
        rel_path = os.path.relpath(file_path, project_dir)
    except ValueError:
        rel_path = file_path

    # Skip files outside project
    if rel_path.startswith(".."):
        sys.exit(0)

    # Collect all dependency categories
    deps = DependencyReport(rel_path, project_dir)
    deps.scan_hub_spoke()
    deps.scan_references()
    deps.scan_test_files()
    deps.scan_hook_registrations()
    deps.scan_importers()

    # Only output if dependencies were found
    if deps.total_count() >= MIN_DEPS_FOR_OUTPUT:
        print(deps.format_report(), file=sys.stderr)

    sys.exit(0)


class DependencyReport:
    """Collects and formats dependency information for a file."""

    def __init__(self, rel_path: str, project_dir: str):
        self.rel_path = rel_path
        self.project_dir = project_dir
        self.filename = os.path.basename(rel_path)
        self.filestem = os.path.splitext(self.filename)[0]

        # Dependency categories
        self.hub_spoke: List[str] = []
        self.references: List[str] = []
        self.test_files: List[str] = []
        self.hook_registrations: List[str] = []
        self.importers: List[str] = []

    def total_count(self) -> int:
        return (len(self.hub_spoke) + len(self.references) +
                len(self.test_files) + len(self.hook_registrations) +
                len(self.importers))

    # --- Scanners ---

    def scan_hub_spoke(self):
        """Check if this file is in the Hub-Spoke map or D-7 sync pairs."""
        # Hub-Spoke sync
        entry = HUB_SPOKE_MAP.get(self.rel_path)
        if entry:
            role = entry["role"]
            for target in entry["sync_targets"]:
                self.hub_spoke.append(
                    f"  -> {target} (sync required — this file is {role})"
                )

        # D-7 sync pairs (intentionally duplicated data structures)
        d7_entry = D7_SYNC_PAIRS.get(self.rel_path)
        if d7_entry:
            for target in d7_entry:
                self.hub_spoke.append(
                    f"  -> {target} (D-7 sync — duplicated data structure)"
                )

    def scan_references(self):
        """Find files that reference this file by name (grep-based)."""
        # Search for the filename (without extension for flexibility)
        patterns = set()
        patterns.add(self.filename)
        if self.filestem and self.filestem != self.filename:
            patterns.add(self.filestem)

        found_files: Set[str] = set()
        for pattern in patterns:
            results = self._grep_project(pattern)
            for match in results:
                # Skip self-references
                if match == self.rel_path:
                    continue
                # Skip already-reported Hub-Spoke targets
                if any(match in line for line in self.hub_spoke):
                    continue
                found_files.add(match)

        # Categorize and format
        for f in sorted(found_files)[:MAX_GREP_RESULTS]:
            self.references.append(f"  -> {f}")

    def scan_test_files(self):
        """Find corresponding test files using naming conventions."""
        if not self.filename.endswith(".py"):
            return

        # Skip if this IS a test file
        if self.filename.startswith(TEST_PREFIX):
            return

        # Convention: foo.py → _test_foo.py in same directory
        test_filename = TEST_PREFIX + self.filename
        test_path = os.path.join(os.path.dirname(self.rel_path), test_filename)
        abs_test_path = os.path.join(self.project_dir, test_path)

        if os.path.exists(abs_test_path):
            self.test_files.append(
                f"  -> {test_path} (update test after modification)"
            )

        # Also check tests/e2e/ directory for integration tests referencing this file
        e2e_refs = self._grep_project(
            self.filestem,
            search_path=os.path.join(self.project_dir, "tests"),
        )
        for ref in e2e_refs[:5]:
            entry = f"  -> {ref} (e2e test references this file)"
            if entry not in self.test_files:
                self.test_files.append(entry)

    def scan_hook_registrations(self):
        """Find Hook registrations in settings.json referencing this file."""
        settings_path = os.path.join(self.project_dir, SETTINGS_REL_PATH)
        if not os.path.exists(settings_path):
            return

        # Only relevant for Hook scripts
        if not self.rel_path.startswith(HOOKS_SCRIPTS_DIR):
            return

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        hooks = settings.get("hooks", {})
        for event_type, matchers in hooks.items():
            if not isinstance(matchers, list):
                continue
            for matcher_entry in matchers:
                hook_list = matcher_entry.get("hooks", [])
                matcher_name = matcher_entry.get("matcher", "")
                for hook in hook_list:
                    cmd = hook.get("command", "")
                    if self.filename in cmd:
                        self.hook_registrations.append(
                            f"  -> settings.json [{event_type}] "
                            f"matcher=\"{matcher_name}\""
                        )

    def scan_importers(self):
        """Find Python files that import this module."""
        if not self.filename.endswith(".py"):
            return

        # Search for import patterns
        module_name = self.filestem
        patterns = [
            f"import {module_name}",
            f"from {module_name} import",
            f"from .{module_name} import",
        ]

        found: Set[str] = set()
        for pattern in patterns:
            results = self._grep_project(pattern, glob_pattern="*.py")
            for match in results:
                if match != self.rel_path:
                    found.add(match)

        for f in sorted(found)[:MAX_GREP_RESULTS]:
            if not any(f in line for line in self.references):
                self.importers.append(f"  -> {f}")

    # --- Helpers ---

    def _grep_project(
        self,
        pattern: str,
        search_path: Optional[str] = None,
        glob_pattern: Optional[str] = None,
    ) -> List[str]:
        """Run grep on the project and return matching file paths.

        Returns project-relative paths. Excludes GREP_EXCLUDE_DIRS.
        """
        if search_path is None:
            search_path = self.project_dir

        if not os.path.isdir(search_path):
            return []

        cmd = ["grep", "-rl", "--include=*"]
        if glob_pattern:
            cmd = ["grep", "-rl", f"--include={glob_pattern}"]

        for exclude_dir in GREP_EXCLUDE_DIRS:
            cmd.extend(["--exclude-dir", exclude_dir])

        cmd.extend([pattern, search_path])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self.project_dir,
            )
            if result.returncode not in (0, 1):  # 1 = no matches (normal)
                return []

            files = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    rel = os.path.relpath(line, self.project_dir)
                    if not rel.startswith(".."):
                        files.append(rel)
                except ValueError:
                    pass
            return files
        except (subprocess.TimeoutExpired, OSError):
            return []

    # --- Formatting ---

    def format_report(self) -> str:
        """Format the dependency report for stderr output."""
        lines = [
            f"CCP-2 DEPENDENCY SCAN: {self.rel_path}",
            "-" * 50,
        ]

        if self.hub_spoke:
            lines.append("[Hub-Spoke SYNC REQUIRED]")
            lines.extend(self.hub_spoke)
            lines.append("")

        if self.importers:
            lines.append("[IMPORTERS]")
            lines.extend(self.importers)
            lines.append("")

        if self.references:
            lines.append(f"[REFERENCED BY] ({len(self.references)} files)")
            lines.extend(self.references)
            lines.append("")

        if self.test_files:
            lines.append("[TEST FILES]")
            lines.extend(self.test_files)
            lines.append("")

        if self.hook_registrations:
            lines.append("[HOOK REGISTRATIONS]")
            lines.extend(self.hook_registrations)
            lines.append("")

        lines.append("CCP-2: Include above dependencies in your ripple effect analysis.")

        return "\n".join(lines)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Safety-first: never block Claude on unexpected internal errors
        sys.exit(0)
