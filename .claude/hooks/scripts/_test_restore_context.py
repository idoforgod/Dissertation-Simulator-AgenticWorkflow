#!/usr/bin/env python3
"""Tests for restore_context.py — SessionStart recovery + Active Knowledge Retrieval.

Run: python3 -m pytest _test_restore_context.py -v
  or: python3 _test_restore_context.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import restore_context as rc


class TestRetrieveRelevantSessions(unittest.TestCase):
    """Test P0-RLM: Active Knowledge Retrieval scoring."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.ki_path = str(self.tmpdir / "knowledge-index.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_ki(self, entries):
        with open(self.ki_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def test_empty_ki_returns_empty(self):
        result = rc._retrieve_relevant_sessions(self.ki_path, "test task", [])
        self.assertEqual(result, [])

    def test_nonexistent_ki_returns_empty(self):
        result = rc._retrieve_relevant_sessions("/nonexistent/path.jsonl", "task", [])
        self.assertEqual(result, [])

    def test_keyword_matching(self):
        """Sessions with overlapping task keywords should score higher."""
        self._write_ki([
            {"session_id": "aaa", "user_task": "implement hook scripts validation", "modified_files": [], "tags": []},
            {"session_id": "bbb", "user_task": "write documentation for API", "modified_files": [], "tags": []},
            {"session_id": "ccc", "user_task": "fix hook scripts error handling", "modified_files": [], "tags": []},
        ])
        result = rc._retrieve_relevant_sessions(self.ki_path, "hook scripts testing", [])
        self.assertTrue(len(result) > 0)
        # Sessions with "hook" and "scripts" should rank higher
        top_session_id = result[0][1]["session_id"]
        self.assertIn(top_session_id, ["aaa", "ccc"])

    def test_file_path_matching(self):
        """Sessions with matching modified files should score high."""
        self._write_ki([
            {"session_id": "aaa", "user_task": "unrelated task", "modified_files": ["/path/to/restore_context.py"], "tags": []},
            {"session_id": "bbb", "user_task": "another task", "modified_files": ["/path/to/other.py"], "tags": []},
        ])
        result = rc._retrieve_relevant_sessions(
            self.ki_path, "some task", ["/path/to/restore_context.py"]
        )
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0][1]["session_id"], "aaa")

    def test_tag_matching(self):
        """Sessions with matching tags should get bonus score."""
        self._write_ki([
            {"session_id": "aaa", "user_task": "work on hooks", "modified_files": [], "tags": ["hooks", "context"]},
            {"session_id": "bbb", "user_task": "work on docs", "modified_files": [], "tags": ["docs", "readme"]},
        ])
        result = rc._retrieve_relevant_sessions(
            self.ki_path, "context preservation hooks",
            ["/project/.claude/hooks/scripts/save_context.py"]
        )
        self.assertTrue(len(result) > 0)
        # "aaa" has tag "hooks" which should match path tag extraction
        top_id = result[0][1]["session_id"]
        self.assertEqual(top_id, "aaa")

    def test_max_results_limit(self):
        """Should return at most max_results entries."""
        entries = [
            {"session_id": f"s{i}", "user_task": "hook script work", "modified_files": [], "tags": []}
            for i in range(20)
        ]
        self._write_ki(entries)
        result = rc._retrieve_relevant_sessions(self.ki_path, "hook script", [], max_results=3)
        self.assertLessEqual(len(result), 3)

    def test_zero_score_sessions_excluded(self):
        """Sessions with no relevance should not appear."""
        self._write_ki([
            {"session_id": "aaa", "user_task": "xyz abc def", "modified_files": ["/foo/bar.py"], "tags": ["unrelated"]},
        ])
        result = rc._retrieve_relevant_sessions(self.ki_path, "hook scripts", ["/other/path.py"])
        self.assertEqual(len(result), 0)

    def test_error_patterns_bonus(self):
        """Sessions with error patterns get a small bonus."""
        self._write_ki([
            {"session_id": "aaa", "user_task": "hook work", "modified_files": [], "tags": [],
             "error_patterns": [{"type": "syntax", "tool": "Edit"}]},
            {"session_id": "bbb", "user_task": "hook work", "modified_files": [], "tags": [],
             "error_patterns": []},
        ])
        result = rc._retrieve_relevant_sessions(self.ki_path, "hook work", [])
        self.assertTrue(len(result) >= 2)
        # "aaa" should score higher due to error_patterns bonus
        self.assertEqual(result[0][1]["session_id"], "aaa")


class TestParseSnapshotSections(unittest.TestCase):
    """Test P1-RLM: Selective Peek — section boundary parsing."""

    def test_parses_marked_snapshot(self):
        md = (
            "<!-- SECTION:header -->\n"
            "# Context Recovery — Session abc123\n"
            "> Saved: 2026-03-06\n"
            "\n"
            "<!-- SECTION:task -->\n"
            "## Current Task\n"
            "Implement RLM features\n"
            "\n"
            "<!-- SECTION:sot -->\n"
            "## SOT State\n"
            "state.yaml content\n"
        )
        sections = rc.parse_snapshot_sections(md)
        self.assertIn("header", sections)
        self.assertIn("task", sections)
        self.assertIn("sot", sections)
        self.assertIn("Context Recovery", sections["header"])
        self.assertIn("Implement RLM", sections["task"])

    def test_unmarked_snapshot_returns_full(self):
        """Pre-P1 snapshots without markers return _full key."""
        md = "# Context Recovery\nSome content\n"
        sections = rc.parse_snapshot_sections(md)
        self.assertIn("_full", sections)
        self.assertEqual(sections["_full"], md)

    def test_empty_sections_handled(self):
        md = (
            "<!-- SECTION:header -->\n"
            "<!-- SECTION:task -->\n"
            "## Task content\n"
        )
        sections = rc.parse_snapshot_sections(md)
        self.assertIn("header", sections)
        self.assertEqual(sections["header"].strip(), "")
        self.assertIn("task", sections)

    def test_immortal_sections_constant(self):
        """IMMORTAL_SECTIONS should contain all critical section keys."""
        from _context_lib import SNAPSHOT_SECTION_MARKERS
        # All immortal sections must exist in the marker dict
        for key in rc.IMMORTAL_SECTIONS:
            self.assertIn(key, SNAPSHOT_SECTION_MARKERS,
                          f"IMMORTAL section '{key}' missing from SNAPSHOT_SECTION_MARKERS")

    def test_marker_constant_sync(self):
        """SNAPSHOT_SECTION_MARKERS values must match the format used in parsing."""
        from _context_lib import SNAPSHOT_SECTION_MARKERS
        import re
        pattern = re.compile(r'<!-- SECTION:(\w+) -->')
        for key, marker in SNAPSHOT_SECTION_MARKERS.items():
            match = pattern.match(marker)
            self.assertIsNotNone(match, f"Marker '{marker}' doesn't match expected format")
            self.assertEqual(match.group(1), key,
                             f"Marker key mismatch: dict key='{key}', marker name='{match.group(1)}'")


class TestSelectivePeekIntegration(unittest.TestCase):
    """Test P1-RLM: Selective Peek integration in _extract_brief_summary."""

    def test_section_based_extraction(self):
        """P1 snapshots with markers should use section-based extraction."""
        md = (
            "<!-- SECTION:header -->\n"
            "# Context Recovery — Session test123\n"
            "> Saved: 2026-03-06 | Trigger: stop\n"
            "\n"
            "<!-- SECTION:task -->\n"
            "## 현재 작업 (Current Task)\n"
            "<!-- IMMORTAL: 사용자 작업 지시 -->\n"
            "Implement RLM features for memory system\n"
            "\n"
            "**최근 지시 (Latest Instruction):** Fix the consolidation bug\n"
            "\n"
            "<!-- SECTION:completion -->\n"
            "## 결정론적 완료 상태 (Deterministic Completion State)\n"
            "### 도구 호출 결과\n"
            "- Edit: 5회 호출 → 5 성공, 0 실패\n"
            "\n"
            "<!-- SECTION:modified_files -->\n"
            "## 수정된 파일 (Modified Files)\n"
            "### `/path/to/restore_context.py` (Edit, 3회 수정)\n"
            "\n"
            "<!-- SECTION:statistics -->\n"
            "## 대화 통계\n"
            "- 총 메시지: 10개\n"
            "- 도구 사용: 15회\n"
        )
        summary = rc._extract_brief_summary(md)
        labels = [l for l, _ in summary]

        # Should extract task
        self.assertIn("현재 작업", labels)
        task_content = next(c for l, c in summary if l == "현재 작업")
        self.assertIn("Implement RLM", task_content)

        # Should extract latest instruction
        self.assertIn("최근 지시", labels)

        # Should extract completion state
        self.assertIn("완료상태", labels)

        # Should extract file paths
        self.assertIn("수정_파일_경로", labels)

        # Should extract statistics
        self.assertIn("통계", labels)

    def test_legacy_fallback(self):
        """Pre-P1 snapshots without markers should use legacy extraction."""
        md = (
            "# Context Recovery — Session test123\n"
            "\n"
            "## 현재 작업 (Current Task)\n"
            "Legacy task description\n"
            "\n"
            "## 대화 통계\n"
            "- 총 메시지: 5개\n"
        )
        summary = rc._extract_brief_summary(md)
        labels = [l for l, _ in summary]
        self.assertIn("현재 작업", labels)
        self.assertIn("통계", labels)


class TestOrphanMarkerRemoval(unittest.TestCase):
    """Test Phase 2 fix: _remove_section() cleans up SECTION markers."""

    def test_remove_section_drops_preceding_marker(self):
        """When a section is removed, its preceding SECTION marker should also be removed."""
        from _context_lib import _remove_section
        sections = [
            "## Some Section",
            "content line",
            "",
            "<!-- SECTION:statistics -->",
            "## 대화 통계",
            "- 총 메시지: 10개",
            "",
            "<!-- SECTION:commands -->",
            "## 실행된 명령 (Commands Executed)",
            "- `git status`",
        ]
        result = _remove_section(sections, "## 대화 통계")
        result_text = "\n".join(result)

        # Statistics section and its marker should be gone
        self.assertNotIn("대화 통계", result_text)
        self.assertNotIn("SECTION:statistics", result_text)

        # Commands section should remain
        self.assertIn("실행된 명령", result_text)
        self.assertIn("SECTION:commands", result_text)


class TestBuildRecoveryOutput(unittest.TestCase):
    """Test _build_recovery_output includes active retrieval block."""

    def test_active_retrieval_block_present(self):
        """When relevant sessions exist, ACTIVE RETRIEVAL block should appear."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            # Place ki at the path get_snapshot_dir() expects
            snapshot_dir = tmpdir / ".claude" / "context-snapshots"
            snapshot_dir.mkdir(parents=True)
            ki_path = snapshot_dir / "knowledge-index.jsonl"
            with open(ki_path, "w") as f:
                f.write(json.dumps({
                    "session_id": "test123",
                    "user_task": "hook scripts work",
                    "modified_files": ["/path/restore_context.py"],
                    "tags": ["hooks"],
                    "timestamp": "2026-03-06T12:00:00",
                }) + "\n")

            summary = [
                ("현재 작업", "hook scripts enhancement"),
                ("수정_파일_경로", "/path/restore_context.py"),
            ]

            output = rc._build_recovery_output(
                source="compact",
                latest_path=str(snapshot_dir / "latest.md"),
                summary=summary,
                sot_warning=None,
                snapshot_age=60,
                project_dir=str(tmpdir),
            )

            self.assertIn("ACTIVE RETRIEVAL", output)
            self.assertIn("test123", output)
        finally:
            shutil.rmtree(tmpdir)


class TestExtractRecentErrorResolutions(unittest.TestCase):
    """Test P1-1: Error resolution extraction."""

    def test_extracts_resolved_errors(self):
        sessions = [{
            "error_patterns": [{
                "type": "syntax",
                "tool": "Edit",
                "file": "foo.py",
                "resolution": {"tool": "Edit", "file": "foo.py"},
            }]
        }]
        result = rc._extract_recent_error_resolutions(sessions)
        self.assertEqual(len(result), 1)
        self.assertIn("syntax", result[0])

    def test_empty_sessions(self):
        result = rc._extract_recent_error_resolutions([])
        self.assertEqual(result, [])

    def test_max_three_results(self):
        sessions = [{
            "error_patterns": [
                {"type": f"err{i}", "tool": "Bash", "file": f"f{i}.py",
                 "resolution": {"tool": "Edit", "file": f"f{i}.py"}}
                for i in range(10)
            ]
        }]
        result = rc._extract_recent_error_resolutions(sessions)
        self.assertLessEqual(len(result), 3)


class TestExtractQuarterlyInsights(unittest.TestCase):
    """Test P3-RLM: Quarterly archive active consumption."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.qa_path = str(self.tmpdir / "knowledge-archive-quarterly.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_qa(self, entries):
        with open(self.qa_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def test_empty_file_returns_empty(self):
        result = rc._extract_quarterly_insights(self.qa_path)
        self.assertEqual(result, [])

    def test_nonexistent_returns_empty(self):
        result = rc._extract_quarterly_insights("/nonexistent/path.jsonl")
        self.assertEqual(result, [])

    def test_extracts_error_patterns(self):
        self._write_qa([{
            "quarter": "2026-Q1",
            "session_count": 15,
            "error_patterns_aggregated": {"syntax": 10, "type_error": 5},
            "design_decisions": [],
            "top_modified_files": {},
        }])
        result = rc._extract_quarterly_insights(self.qa_path)
        self.assertTrue(any("syntax" in r for r in result))

    def test_extracts_top_files(self):
        self._write_qa([{
            "quarter": "2026-Q1",
            "session_count": 10,
            "error_patterns_aggregated": {},
            "design_decisions": [],
            "top_modified_files": {"/path/to/important.py": 25},
        }])
        result = rc._extract_quarterly_insights(self.qa_path)
        self.assertTrue(any("important.py" in r for r in result))

    def test_extracts_design_decision_count(self):
        self._write_qa([{
            "quarter": "2026-Q1",
            "session_count": 10,
            "error_patterns_aggregated": {},
            "design_decisions": ["Decision A", "Decision B"],
            "top_modified_files": {},
        }])
        result = rc._extract_quarterly_insights(self.qa_path)
        self.assertTrue(any("설계 결정" in r for r in result))

    def test_aggregates_across_quarters(self):
        self._write_qa([
            {
                "quarter": "2025-Q4",
                "session_count": 5,
                "error_patterns_aggregated": {"syntax": 3},
                "design_decisions": ["D1"],
                "top_modified_files": {},
            },
            {
                "quarter": "2026-Q1",
                "session_count": 10,
                "error_patterns_aggregated": {"syntax": 7},
                "design_decisions": ["D2"],
                "top_modified_files": {},
            },
        ])
        result = rc._extract_quarterly_insights(self.qa_path)
        # Should show aggregated count of 10 syntax errors
        self.assertTrue(any("syntax(10)" in r for r in result))


class TestCheckMemoryHealth(unittest.TestCase):
    """Test Improvement A: MEMORY.md health check."""

    def test_healthy_memory_returns_empty(self):
        """A well-formed MEMORY.md should produce no warnings."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            # Create a fake MEMORY.md with valid content
            memory_dir = tmpdir / "memory"
            memory_dir.mkdir()
            memory_path = memory_dir / "MEMORY.md"
            memory_path.write_text(
                "# Project Memory\n\n"
                "## Preferences\n\n"
                "- Use English for workflow\n"
                "- Korean for communication\n"
                "- Always run tests\n\n"
                "## Architecture\n\n"
                "- Hook-based context preservation\n"
                "- SOT pattern with state.yaml\n",
                encoding="utf-8",
            )
            # _check_memory_health uses _find_memory_md which scans ~/.claude-*/
            # We test the core logic directly by monkeypatching _find_memory_md
            original = rc._find_memory_md
            rc._find_memory_md = lambda _: str(memory_path)
            try:
                warnings = rc._check_memory_health(str(tmpdir))
                self.assertEqual(warnings, [])
            finally:
                rc._find_memory_md = original
        finally:
            shutil.rmtree(tmpdir)

    def test_mh1_line_count_exceeds_200(self):
        """MH-1: Files > 200 lines should trigger a warning."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            memory_path = tmpdir / "MEMORY.md"
            lines = ["# Memory\n"] + [f"Line {i}\n" for i in range(210)]
            memory_path.write_text("".join(lines), encoding="utf-8")
            original = rc._find_memory_md
            rc._find_memory_md = lambda _: str(memory_path)
            try:
                warnings = rc._check_memory_health(str(tmpdir))
                self.assertTrue(any("200줄" in w for w in warnings))
            finally:
                rc._find_memory_md = original
        finally:
            shutil.rmtree(tmpdir)

    def test_mh2_duplicate_headers(self):
        """MH-2: Duplicate ## headers should trigger a warning."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            memory_path = tmpdir / "MEMORY.md"
            memory_path.write_text(
                "# Memory\n\n"
                "## Preferences\n\nSome content\n\n"
                "## Architecture\n\nMore content\n\n"
                "## Preferences\n\nDuplicate!\n",
                encoding="utf-8",
            )
            original = rc._find_memory_md
            rc._find_memory_md = lambda _: str(memory_path)
            try:
                warnings = rc._check_memory_health(str(tmpdir))
                self.assertTrue(any("중복 섹션" in w for w in warnings))
                self.assertTrue(any("Preferences" in w for w in warnings))
            finally:
                rc._find_memory_md = original
        finally:
            shutil.rmtree(tmpdir)

    def test_mh3_empty_sections(self):
        """MH-3: Empty sections (## followed by ##) should trigger a warning."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            memory_path = tmpdir / "MEMORY.md"
            memory_path.write_text(
                "# Memory\n\n"
                "## Filled Section\n\nContent here\n\n"
                "## Empty Section\n\n"
                "## Another Section\n\nContent\n",
                encoding="utf-8",
            )
            original = rc._find_memory_md
            rc._find_memory_md = lambda _: str(memory_path)
            try:
                warnings = rc._check_memory_health(str(tmpdir))
                self.assertTrue(any("빈 섹션" in w for w in warnings))
            finally:
                rc._find_memory_md = original
        finally:
            shutil.rmtree(tmpdir)

    def test_no_memory_returns_empty(self):
        """No MEMORY.md found → no warnings (graceful)."""
        original = rc._find_memory_md
        rc._find_memory_md = lambda _: None
        try:
            warnings = rc._check_memory_health("/nonexistent")
            self.assertEqual(warnings, [])
        finally:
            rc._find_memory_md = original


class TestGetTodayYesterdaySummary(unittest.TestCase):
    """Test Improvement B: Today/Yesterday session summary."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.ki_path = str(self.tmpdir / "knowledge-index.jsonl")
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.yesterday = datetime.fromtimestamp(
            datetime.now().timestamp() - 86400
        ).strftime("%Y-%m-%d")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_ki(self, entries):
        with open(self.ki_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def test_today_sessions_counted(self):
        """Today's sessions should be aggregated correctly."""
        self._write_ki([
            {"timestamp": f"{self.today}T10:00:00", "user_task": "task A",
             "modified_files": ["/a/foo.py", "/a/bar.py"]},
            {"timestamp": f"{self.today}T14:00:00", "user_task": "task B",
             "modified_files": ["/a/foo.py", "/a/baz.py"]},
        ])
        result = rc._get_today_yesterday_summary(self.ki_path)
        self.assertTrue(any("오늘 작업" in s for s in result))
        self.assertTrue(any("2개 세션" in s for s in result))
        self.assertTrue(any("3개 파일" in s for s in result))  # foo, bar, baz

    def test_yesterday_sessions_counted(self):
        """Yesterday's sessions should be aggregated."""
        self._write_ki([
            {"timestamp": f"{self.yesterday}T10:00:00", "user_task": "old task",
             "modified_files": ["/a/old.py"]},
        ])
        result = rc._get_today_yesterday_summary(self.ki_path)
        self.assertTrue(any("어제 작업" in s for s in result))

    def test_nonexistent_returns_empty(self):
        """Non-existent ki_path should return empty list."""
        result = rc._get_today_yesterday_summary("/nonexistent/path.jsonl")
        self.assertEqual(result, [])


class TestSurfaceRecentGateFeedback(unittest.TestCase):
    """Test QO-1: Gate feedback surfacing for IMMORTAL section."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self._setup_thesis_project()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _setup_thesis_project(self, sot_data=None):
        """Create minimal thesis project structure."""
        proj_dir = self.tmpdir / "thesis-output" / "test-project"
        proj_dir.mkdir(parents=True, exist_ok=True)
        sot = sot_data or {"current_step": 10, "status": "in_progress"}
        (proj_dir / "session.json").write_text(
            json.dumps(sot), encoding="utf-8"
        )
        return proj_dir

    def test_no_project_dir_returns_empty(self):
        result = rc._surface_recent_gate_feedback("")
        self.assertEqual(result, [])

    def test_no_gate_dir_returns_empty(self):
        result = rc._surface_recent_gate_feedback(str(self.tmpdir))
        self.assertEqual(result, [])

    def test_extracts_fail_items_from_md(self):
        """MD gate report: items must be in structured Errors:/Warnings: sections."""
        proj_dir = self.tmpdir / "thesis-output" / "test-project"
        gate_dir = proj_dir / "gate-reports"
        gate_dir.mkdir(parents=True, exist_ok=True)
        (gate_dir / "gate-1.md").write_text(
            "Gate: gate-1 — Cross-Validation\n"
            "Status: FAIL\n"
            "Files: 5\n"
            "Total claims: 20\n\n"
            "Errors:\n"
            "  - Missing literature coverage in Wave 1\n"
            "  - Insufficient citations in Step 3\n\n"
            "Warnings:\n"
            "  - Low sample size in methodology\n",
            encoding="utf-8",
        )
        result = rc._surface_recent_gate_feedback(str(self.tmpdir))
        self.assertTrue(any("RECENT GATE FEEDBACK" in l for l in result))
        self.assertTrue(any("Failures (2)" in l for l in result))
        self.assertTrue(any("Warnings (1)" in l for l in result))
        self.assertTrue(any("FAIL" in l for l in result))

    def test_extracts_fail_items_from_json(self):
        """JSON gate report: parsed from structured fields directly."""
        proj_dir = self.tmpdir / "thesis-output" / "test-project"
        gate_dir = proj_dir / "gate-reports"
        gate_dir.mkdir(parents=True, exist_ok=True)
        (gate_dir / "gate-1.json").write_text(
            json.dumps({
                "gate": "gate-1",
                "status": "fail",
                "errors": ["L0 fail: step-3.md (100 bytes < 500)"],
                "warnings": ["Inconsistency: step-5 claim prefix"],
            }),
            encoding="utf-8",
        )
        result = rc._surface_recent_gate_feedback(str(self.tmpdir))
        self.assertTrue(any("RECENT GATE FEEDBACK" in l for l in result))
        self.assertTrue(any("Failures (1)" in l for l in result))
        self.assertTrue(any("L0 fail" in l for l in result))

    def test_no_false_positives_on_descriptive_text(self):
        """H-1: Descriptive text mentioning 'FAIL' should NOT be counted as failures."""
        proj_dir = self.tmpdir / "thesis-output" / "test-project"
        gate_dir = proj_dir / "gate-reports"
        gate_dir.mkdir(parents=True, exist_ok=True)
        (gate_dir / "gate-1.md").write_text(
            "Gate: gate-1 — Cross-Validation\n"
            "Status: PASS\n"
            "Files: 5\n\n"
            "No FAILURES were detected in this validation run.\n"
            "This is a FAILSAFE mechanism that ensures quality.\n"
            "The test did not FAIL under any condition.\n",
            encoding="utf-8",
        )
        result = rc._surface_recent_gate_feedback(str(self.tmpdir))
        # Should NOT report any failures — these are descriptive text, not structured items
        self.assertFalse(any("Failures" in l for l in result))
        self.assertTrue(any("All checks passed" in l for l in result))

    def test_all_passed_gate(self):
        proj_dir = self.tmpdir / "thesis-output" / "test-project"
        gate_dir = proj_dir / "gate-reports"
        gate_dir.mkdir(parents=True, exist_ok=True)
        (gate_dir / "gate-1.md").write_text(
            "Gate: gate-1 — Cross-Validation\n"
            "Status: PASS\n"
            "Files: 5\n"
            "Total claims: 20\n",
            encoding="utf-8",
        )
        result = rc._surface_recent_gate_feedback(str(self.tmpdir))
        self.assertTrue(any("All checks passed" in l for l in result))

    def test_empty_gate_file_returns_empty(self):
        proj_dir = self.tmpdir / "thesis-output" / "test-project"
        gate_dir = proj_dir / "gate-reports"
        gate_dir.mkdir(parents=True, exist_ok=True)
        (gate_dir / "gate-1.md").write_text("", encoding="utf-8")
        result = rc._surface_recent_gate_feedback(str(self.tmpdir))
        self.assertEqual(result, [])


class TestSurfacePreviousSectionsSummary(unittest.TestCase):
    """Test QO-2: Previous section output surfacing for IMMORTAL section."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _setup_project(self, current_step=10, outputs=None):
        proj_dir = self.tmpdir / "thesis-output" / "test-project"
        proj_dir.mkdir(parents=True, exist_ok=True)
        sot = {"current_step": current_step, "status": "in_progress"}
        if outputs:
            sot["outputs"] = outputs
        (proj_dir / "session.json").write_text(
            json.dumps(sot), encoding="utf-8"
        )
        return proj_dir

    def test_no_project_dir_returns_empty(self):
        result = rc._surface_previous_sections_summary("")
        self.assertEqual(result, [])

    def test_no_outputs_returns_empty(self):
        self._setup_project(current_step=5, outputs={})
        result = rc._surface_previous_sections_summary(str(self.tmpdir))
        self.assertEqual(result, [])

    def test_step_1_returns_empty(self):
        """Step 1 has no previous steps."""
        self._setup_project(current_step=1, outputs={})
        result = rc._surface_previous_sections_summary(str(self.tmpdir))
        self.assertEqual(result, [])

    def test_extracts_title_and_word_count(self):
        proj_dir = self._setup_project(
            current_step=5,
            outputs={"step-3": "wave-results/step-3.md"},
        )
        output_dir = proj_dir / "wave-results"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "step-3.md").write_text(
            "## Literature Review\n\n"
            "This is a sample section with some words.\n"
            "## Methodology\n\nMore content here.\n",
            encoding="utf-8",
        )
        result = rc._surface_previous_sections_summary(str(self.tmpdir))
        self.assertTrue(any("PREVIOUS SECTION OUTPUTS" in l for l in result))
        self.assertTrue(any("Step 3" in l for l in result))
        self.assertTrue(any("Literature Review" in l for l in result))
        self.assertTrue(any("words" in l for l in result))

    def test_word_count_accurate_for_large_files(self):
        """H-2: Word count must reflect entire file, not just first 5KB."""
        proj_dir = self._setup_project(
            current_step=5,
            outputs={"step-3": "wave-results/step-3.md"},
        )
        output_dir = proj_dir / "wave-results"
        output_dir.mkdir(parents=True, exist_ok=True)
        # Create a file larger than 5KB (~1000 words per KB for English)
        large_content = "## Introduction\n\n" + ("word " * 10_000)  # 10K words >> 5KB
        (output_dir / "step-3.md").write_text(large_content, encoding="utf-8")
        result = rc._surface_previous_sections_summary(str(self.tmpdir))
        # Extract the word count from the result line
        step_line = next((l for l in result if "Step 3" in l), "")
        # Should show ~10002 words (10000 + "Introduction" + "##"), NOT ~800
        import re as test_re
        m = test_re.search(r"\((\d+) words\)", step_line)
        self.assertIsNotNone(m, f"No word count found in: {step_line}")
        reported_count = int(m.group(1))
        self.assertGreater(reported_count, 5000,
                           f"Word count {reported_count} appears truncated (expected >5000)")

    def test_skips_ko_outputs(self):
        """Korean translation outputs should be skipped."""
        proj_dir = self._setup_project(
            current_step=5,
            outputs={
                "step-3": "wave-results/step-3.md",
                "step-3-ko": "wave-results/step-3-ko.md",
            },
        )
        output_dir = proj_dir / "wave-results"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "step-3.md").write_text(
            "## English Content\nWords here.\n", encoding="utf-8"
        )
        (output_dir / "step-3-ko.md").write_text(
            "## 한국어 콘텐츠\n여기에 단어들.\n", encoding="utf-8"
        )
        result = rc._surface_previous_sections_summary(str(self.tmpdir))
        # Only step-3 should appear, not step-3-ko
        step_lines = [l for l in result if "Step" in l]
        self.assertEqual(len(step_lines), 1)

    def test_skips_future_steps(self):
        """Steps >= current_step should be excluded."""
        proj_dir = self._setup_project(
            current_step=5,
            outputs={
                "step-3": "wave-results/step-3.md",
                "step-5": "wave-results/step-5.md",
                "step-7": "wave-results/step-7.md",
            },
        )
        output_dir = proj_dir / "wave-results"
        output_dir.mkdir(parents=True, exist_ok=True)
        for n in [3, 5, 7]:
            (output_dir / f"step-{n}.md").write_text(
                f"## Step {n} Content\nWords.\n", encoding="utf-8"
            )
        result = rc._surface_previous_sections_summary(str(self.tmpdir))
        # Only step-3 should appear (step-5 and step-7 are >= current_step=5)
        step_lines = [l for l in result if "Step" in l]
        self.assertEqual(len(step_lines), 1)
        self.assertTrue(any("Step 3" in l for l in step_lines))


class TestQO3ScoringSignals(unittest.TestCase):
    """Test QO-3: Enhanced scoring signals in _retrieve_relevant_sessions."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.ki_path = str(self.tmpdir / "knowledge-index.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_ki(self, entries):
        with open(self.ki_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def test_design_decision_match_boosts_score(self):
        """QO-3a: Sessions with matching design decision tokens should rank higher."""
        self._write_ki([
            {"session_id": "with_decisions", "user_task": "P1 validation gate work",
             "modified_files": [], "tags": [],
             "design_decisions": ["Switched to P1 deterministic validation for gate reports"]},
            {"session_id": "no_decisions", "user_task": "P1 validation gate work",
             "modified_files": [], "tags": [],
             "design_decisions": []},
        ])
        result = rc._retrieve_relevant_sessions(self.ki_path, "P1 validation gate", [])
        self.assertTrue(len(result) >= 2)
        self.assertEqual(result[0][1]["session_id"], "with_decisions")

    def test_tool_sequence_match_boosts_score(self):
        """QO-3b: Sessions with Edit+Bash tool patterns should score higher."""
        self._write_ki([
            {"session_id": "edit_bash", "user_task": "fix hook bug",
             "modified_files": [], "tags": [],
             "tool_sequence": "Edit(3)→Bash(2)→Edit(1)"},
            {"session_id": "read_only", "user_task": "fix hook bug",
             "modified_files": [], "tags": [],
             "tool_sequence": "Read(5)"},
        ])
        result = rc._retrieve_relevant_sessions(self.ki_path, "fix hook bug", [])
        self.assertTrue(len(result) >= 2)
        self.assertEqual(result[0][1]["session_id"], "edit_bash")

    def test_phase_alignment_boosts_score(self):
        """QO-3c: Sessions with matching phase keywords should score higher."""
        self._write_ki([
            {"session_id": "impl_phase", "user_task": "hook implementation work",
             "modified_files": [], "tags": [],
             "phase": "implementation", "phase_flow": "implementation→testing"},
            {"session_id": "research_phase", "user_task": "hook implementation work",
             "modified_files": [], "tags": [],
             "phase": "research", "phase_flow": "research→exploration"},
        ])
        result = rc._retrieve_relevant_sessions(self.ki_path, "implementation of hook work", [])
        self.assertTrue(len(result) >= 2)
        self.assertEqual(result[0][1]["session_id"], "impl_phase")

    def test_success_pattern_boosts_score(self):
        """QO-3d: Sessions with matching success pattern files should rank higher."""
        self._write_ki([
            {"session_id": "with_success", "user_task": "work on context",
             "modified_files": [], "tags": [],
             "success_patterns": [{"files": ["/path/restore_context.py"]}]},
            {"session_id": "no_success", "user_task": "work on context",
             "modified_files": [], "tags": [],
             "success_patterns": []},
        ])
        result = rc._retrieve_relevant_sessions(
            self.ki_path, "work on context", ["/path/restore_context.py"]
        )
        self.assertTrue(len(result) >= 2)
        self.assertEqual(result[0][1]["session_id"], "with_success")


class TestQO4StepMetadata(unittest.TestCase):
    """Test QO-4: Step metadata surfacing in active thesis block."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_build_active_thesis_step_block_includes_metadata(self):
        """QO-4: Active thesis block should include step metadata when available."""
        # Create minimal thesis project
        proj_dir = self.tmpdir / "thesis-output" / "test-project"
        proj_dir.mkdir(parents=True, exist_ok=True)
        sot = {
            "current_step": 5,
            "status": "in_progress",
            "research_type": "quantitative",
            "consolidated_groups": {
                "group_1": {"steps": [5, 6, 7], "status": "in_progress"}
            },
        }
        (proj_dir / "session.json").write_text(
            json.dumps(sot), encoding="utf-8"
        )
        # Build active thesis step block
        lines = rc._build_active_thesis_step_block(str(self.tmpdir))
        # Should mention current step
        combined = "\n".join(lines)
        self.assertIn("5", combined)


class TestBuildRecoveryOutputCompressionNote(unittest.TestCase):
    """Test that compression_note parameter is properly handled."""

    def test_compression_note_appears_in_output(self):
        """When compression_note is provided, it should appear in the output."""
        output = rc._build_recovery_output(
            source="compact",
            latest_path="/tmp/fake/snapshot.md",
            summary=[("현재 작업", "test task")],
            sot_warning=None,
            snapshot_age=30,
            compression_note="⚠️ Snapshot was heavily compressed (80% reduction)",
        )
        self.assertIn("heavily compressed", output)

    def test_empty_compression_note_omitted(self):
        """When compression_note is empty, no extra lines should appear."""
        output = rc._build_recovery_output(
            source="compact",
            latest_path="/tmp/fake/snapshot.md",
            summary=[("현재 작업", "test task")],
            sot_warning=None,
            snapshot_age=30,
            compression_note="",
        )
        self.assertNotIn("compressed", output)


if __name__ == "__main__":
    unittest.main()
