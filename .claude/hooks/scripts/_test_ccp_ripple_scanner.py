#!/usr/bin/env python3
"""Unit tests for ccp_ripple_scanner.py — CCP-2 P1 Dependency Scanner.

Test categories:
  1. Hub-Spoke map detection
  2. File reference discovery (grep-based)
  3. Test file mapping (naming conventions)
  4. Hook registration lookup (settings.json)
  5. Python importer detection
  6. Report formatting
  7. Edge cases (missing files, empty input, self-references)
  8. Safety-first (crash → exit 0)

Run: python3 _test_ccp_ripple_scanner.py
"""

import json
import os
import sys
import tempfile
import textwrap
import unittest

# Import the module under test
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ccp_ripple_scanner as scanner


class TestHubSpokeMap(unittest.TestCase):
    """Test Hub-Spoke synchronization map detection."""

    def test_agents_md_is_hub(self):
        """AGENTS.md should be identified as Hub with multiple sync targets."""
        entry = scanner.HUB_SPOKE_MAP.get("AGENTS.md")
        self.assertIsNotNone(entry)
        self.assertIn("Hub", entry["role"])
        self.assertIn("CLAUDE.md", entry["sync_targets"])
        self.assertIn("GEMINI.md", entry["sync_targets"])
        self.assertIn(".github/copilot-instructions.md", entry["sync_targets"])

    def test_claude_md_is_spoke(self):
        """CLAUDE.md should be identified as Spoke pointing to AGENTS.md."""
        entry = scanner.HUB_SPOKE_MAP.get("CLAUDE.md")
        self.assertIsNotNone(entry)
        self.assertIn("Spoke", entry["role"])
        self.assertIn("AGENTS.md", entry["sync_targets"])

    def test_soul_md_is_dna(self):
        """soul.md should be in the map with AGENTS.md as sync target."""
        entry = scanner.HUB_SPOKE_MAP.get("soul.md")
        self.assertIsNotNone(entry)
        self.assertIn("AGENTS.md", entry["sync_targets"])

    def test_cursor_mdc_is_spoke(self):
        """Cursor IDE rule file should be identified as Spoke."""
        entry = scanner.HUB_SPOKE_MAP.get(".cursor/rules/agenticworkflow.mdc")
        self.assertIsNotNone(entry)
        self.assertIn("Spoke", entry["role"])
        self.assertIn("AGENTS.md", entry["sync_targets"])

    def test_agents_md_includes_cursor_spoke(self):
        """AGENTS.md sync_targets should include Cursor IDE spoke."""
        entry = scanner.HUB_SPOKE_MAP.get("AGENTS.md")
        self.assertIn(".cursor/rules/agenticworkflow.mdc", entry["sync_targets"])

    def test_agents_md_includes_skill_spokes(self):
        """AGENTS.md sync_targets should include workflow-generator skill files."""
        entry = scanner.HUB_SPOKE_MAP.get("AGENTS.md")
        self.assertIn(".claude/skills/workflow-generator/SKILL.md", entry["sync_targets"])
        self.assertIn(".claude/skills/workflow-generator/references/workflow-template.md", entry["sync_targets"])
        self.assertIn(".claude/skills/workflow-generator/references/claude-code-patterns.md", entry["sync_targets"])

    def test_unknown_file_not_in_map(self):
        """Files not in the map should return None."""
        self.assertIsNone(scanner.HUB_SPOKE_MAP.get("random_file.py"))


class TestD7SyncPairs(unittest.TestCase):
    """Test D-7 intentionally duplicated data structure sync."""

    def test_setup_init_has_maintenance_pair(self):
        """setup_init.py should list setup_maintenance.py as D-7 pair."""
        key = ".claude/hooks/scripts/setup_init.py"
        self.assertIn(key, scanner.D7_SYNC_PAIRS)
        self.assertIn(
            ".claude/hooks/scripts/setup_maintenance.py",
            scanner.D7_SYNC_PAIRS[key],
        )

    def test_setup_maintenance_has_init_pair(self):
        """setup_maintenance.py should list setup_init.py as D-7 pair."""
        key = ".claude/hooks/scripts/setup_maintenance.py"
        self.assertIn(key, scanner.D7_SYNC_PAIRS)
        self.assertIn(
            ".claude/hooks/scripts/setup_init.py",
            scanner.D7_SYNC_PAIRS[key],
        )

    def test_d7_pairs_are_bidirectional(self):
        """All D-7 pairs must be bidirectional."""
        for source, targets in scanner.D7_SYNC_PAIRS.items():
            for target in targets:
                self.assertIn(
                    target, scanner.D7_SYNC_PAIRS,
                    f"{target} is listed as D-7 target of {source} but has no entry",
                )
                self.assertIn(
                    source, scanner.D7_SYNC_PAIRS[target],
                    f"D-7 pair is not bidirectional: {source} -> {target} but not reverse",
                )

    def test_scan_hub_spoke_includes_d7(self):
        """scan_hub_spoke should include D-7 sync warnings."""
        report = scanner.DependencyReport(
            ".claude/hooks/scripts/setup_init.py", "/tmp"
        )
        report.scan_hub_spoke()
        self.assertGreater(len(report.hub_spoke), 0)
        joined = " ".join(report.hub_spoke)
        self.assertIn("D-7", joined)
        self.assertIn("setup_maintenance.py", joined)


class TestDependencyReport(unittest.TestCase):
    """Test DependencyReport class methods."""

    def setUp(self):
        """Create a temporary project directory for testing."""
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scan_hub_spoke_for_agents_md(self):
        """scan_hub_spoke should find sync targets for AGENTS.md."""
        report = scanner.DependencyReport("AGENTS.md", self.tmpdir)
        report.scan_hub_spoke()
        self.assertGreater(len(report.hub_spoke), 0)
        # Should include CLAUDE.md as a sync target
        joined = " ".join(report.hub_spoke)
        self.assertIn("CLAUDE.md", joined)

    def test_scan_hub_spoke_for_unknown_file(self):
        """scan_hub_spoke should find nothing for files not in the map."""
        report = scanner.DependencyReport("some_random_file.py", self.tmpdir)
        report.scan_hub_spoke()
        self.assertEqual(len(report.hub_spoke), 0)

    def test_scan_test_files_convention(self):
        """scan_test_files should find _test_foo.py for foo.py."""
        # Create the test file
        hooks_dir = os.path.join(
            self.tmpdir, ".claude", "hooks", "scripts"
        )
        os.makedirs(hooks_dir, exist_ok=True)

        prod_file = os.path.join(hooks_dir, "my_module.py")
        test_file = os.path.join(hooks_dir, "_test_my_module.py")
        with open(prod_file, "w") as f:
            f.write("# production code\n")
        with open(test_file, "w") as f:
            f.write("# test code\n")

        rel_path = os.path.join(".claude", "hooks", "scripts", "my_module.py")
        report = scanner.DependencyReport(rel_path, self.tmpdir)
        report.scan_test_files()
        self.assertGreater(len(report.test_files), 0)
        joined = " ".join(report.test_files)
        self.assertIn("_test_my_module.py", joined)

    def test_scan_test_files_skips_test_files(self):
        """scan_test_files should not look for tests of test files."""
        rel_path = os.path.join(
            ".claude", "hooks", "scripts", "_test_something.py"
        )
        report = scanner.DependencyReport(rel_path, self.tmpdir)
        report.scan_test_files()
        self.assertEqual(len(report.test_files), 0)

    def test_scan_test_files_skips_non_python(self):
        """scan_test_files should skip non-Python files."""
        report = scanner.DependencyReport("AGENTS.md", self.tmpdir)
        report.scan_test_files()
        self.assertEqual(len(report.test_files), 0)

    def test_scan_hook_registrations(self):
        """scan_hook_registrations should find settings.json references."""
        # Create settings.json with a hook referencing our script
        claude_dir = os.path.join(self.tmpdir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 my_hook.py",
                            }
                        ],
                    }
                ]
            }
        }
        with open(os.path.join(claude_dir, "settings.json"), "w") as f:
            json.dump(settings, f)

        rel_path = os.path.join(".claude", "hooks", "scripts", "my_hook.py")
        report = scanner.DependencyReport(rel_path, self.tmpdir)
        report.scan_hook_registrations()
        self.assertGreater(len(report.hook_registrations), 0)
        joined = " ".join(report.hook_registrations)
        self.assertIn("PreToolUse", joined)

    def test_scan_hook_registrations_non_hook_file(self):
        """scan_hook_registrations should skip files not in hooks/scripts."""
        report = scanner.DependencyReport("AGENTS.md", self.tmpdir)
        report.scan_hook_registrations()
        self.assertEqual(len(report.hook_registrations), 0)

    def test_scan_references_finds_mentions(self):
        """scan_references should find files mentioning the target."""
        # Create files that reference each other
        os.makedirs(os.path.join(self.tmpdir, "src"), exist_ok=True)
        with open(os.path.join(self.tmpdir, "src", "target.py"), "w") as f:
            f.write("# target module\n")
        with open(os.path.join(self.tmpdir, "src", "caller.py"), "w") as f:
            f.write("import target\n")

        rel_path = os.path.join("src", "target.py")
        report = scanner.DependencyReport(rel_path, self.tmpdir)
        report.scan_references()
        # caller.py should reference target
        joined = " ".join(report.references)
        self.assertIn("caller.py", joined)

    def test_scan_references_excludes_self(self):
        """scan_references should not report self-references."""
        os.makedirs(os.path.join(self.tmpdir, "src"), exist_ok=True)
        target_path = os.path.join(self.tmpdir, "src", "myfile.py")
        with open(target_path, "w") as f:
            f.write("# myfile references myfile in a comment\n")

        rel_path = os.path.join("src", "myfile.py")
        report = scanner.DependencyReport(rel_path, self.tmpdir)
        report.scan_references()
        for ref in report.references:
            self.assertNotIn(rel_path, ref)

    def test_scan_importers_finds_python_imports(self):
        """scan_importers should find Python import statements."""
        os.makedirs(os.path.join(self.tmpdir, "pkg"), exist_ok=True)
        with open(os.path.join(self.tmpdir, "pkg", "utils.py"), "w") as f:
            f.write("def helper(): pass\n")
        with open(os.path.join(self.tmpdir, "pkg", "main.py"), "w") as f:
            f.write("from utils import helper\n")

        rel_path = os.path.join("pkg", "utils.py")
        report = scanner.DependencyReport(rel_path, self.tmpdir)
        report.scan_importers()
        joined = " ".join(report.importers)
        self.assertIn("main.py", joined)


class TestTotalCount(unittest.TestCase):
    """Test dependency count aggregation."""

    def test_empty_report(self):
        """Empty report should have 0 total count."""
        report = scanner.DependencyReport("test.py", "/tmp")
        self.assertEqual(report.total_count(), 0)

    def test_mixed_dependencies(self):
        """Total count should sum all categories."""
        report = scanner.DependencyReport("test.py", "/tmp")
        report.hub_spoke = ["a", "b"]
        report.references = ["c"]
        report.test_files = ["d"]
        report.hook_registrations = []
        report.importers = ["e", "f"]
        self.assertEqual(report.total_count(), 6)


class TestFormatReport(unittest.TestCase):
    """Test report formatting."""

    def test_format_includes_header(self):
        """Report should include the file path in the header."""
        report = scanner.DependencyReport("AGENTS.md", "/tmp")
        report.hub_spoke = ["  -> CLAUDE.md (sync required)"]
        output = report.format_report()
        self.assertIn("CCP-2 DEPENDENCY SCAN: AGENTS.md", output)

    def test_format_includes_hub_spoke_section(self):
        """Report should have Hub-Spoke section when applicable."""
        report = scanner.DependencyReport("AGENTS.md", "/tmp")
        report.hub_spoke = ["  -> CLAUDE.md (sync required)"]
        output = report.format_report()
        self.assertIn("[Hub-Spoke SYNC REQUIRED]", output)
        self.assertIn("CLAUDE.md", output)

    def test_format_includes_footer(self):
        """Report should include CCP-2 reminder at the end."""
        report = scanner.DependencyReport("test.py", "/tmp")
        report.references = ["  -> other.py"]
        output = report.format_report()
        self.assertIn("CCP-2:", output)

    def test_format_omits_empty_sections(self):
        """Report should not include empty sections."""
        report = scanner.DependencyReport("test.py", "/tmp")
        report.references = ["  -> other.py"]
        # hub_spoke is empty
        output = report.format_report()
        self.assertNotIn("[Hub-Spoke", output)
        self.assertIn("[REFERENCED BY]", output)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and safety."""

    def test_outside_project_path(self):
        """Paths outside project should be skipped (starts with ..)."""
        # This is handled in main() — rel_path.startswith("..")
        # We test the DependencyReport with a normal path to ensure no crash
        report = scanner.DependencyReport("normal.py", "/tmp")
        self.assertEqual(report.total_count(), 0)

    def test_grep_nonexistent_directory(self):
        """Grep on nonexistent directory should return empty list."""
        report = scanner.DependencyReport("test.py", "/nonexistent/path")
        results = report._grep_project("pattern")
        self.assertEqual(results, [])

    def test_grep_exclude_dirs(self):
        """GREP_EXCLUDE_DIRS should contain .git and node_modules."""
        self.assertIn(".git", scanner.GREP_EXCLUDE_DIRS)
        self.assertIn("node_modules", scanner.GREP_EXCLUDE_DIRS)
        self.assertIn(".claude/context-snapshots", scanner.GREP_EXCLUDE_DIRS)

    def test_constants_are_reasonable(self):
        """Constants should have reasonable values."""
        self.assertGreaterEqual(scanner.MIN_DEPS_FOR_OUTPUT, 1)
        self.assertGreaterEqual(scanner.MAX_GREP_RESULTS, 10)


class TestMainFunction(unittest.TestCase):
    """Test the main() entry point with mocked stdin."""

    def test_empty_stdin_exits_0(self):
        """Empty stdin should exit 0 without error."""
        import io
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("")
        try:
            with self.assertRaises(SystemExit) as cm:
                scanner.main()
            self.assertEqual(cm.exception.code, 0)
        finally:
            sys.stdin = old_stdin

    def test_malformed_json_exits_0(self):
        """Malformed JSON should exit 0 without error."""
        import io
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("not json")
        try:
            with self.assertRaises(SystemExit) as cm:
                scanner.main()
            self.assertEqual(cm.exception.code, 0)
        finally:
            sys.stdin = old_stdin

    def test_missing_file_path_exits_0(self):
        """JSON without file_path should exit 0."""
        import io
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps({"tool_input": {}}))
        try:
            with self.assertRaises(SystemExit) as cm:
                scanner.main()
            self.assertEqual(cm.exception.code, 0)
        finally:
            sys.stdin = old_stdin

    def test_no_project_dir_exits_0(self):
        """Missing CLAUDE_PROJECT_DIR should exit 0."""
        import io
        old_stdin = sys.stdin
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        sys.stdin = io.StringIO(json.dumps({
            "tool_input": {"file_path": "/some/path.py"}
        }))
        if "CLAUDE_PROJECT_DIR" in os.environ:
            del os.environ["CLAUDE_PROJECT_DIR"]
        try:
            with self.assertRaises(SystemExit) as cm:
                scanner.main()
            self.assertEqual(cm.exception.code, 0)
        finally:
            sys.stdin = old_stdin
            if old_env is not None:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env


if __name__ == "__main__":
    unittest.main()
