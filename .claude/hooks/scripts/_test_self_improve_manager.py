#!/usr/bin/env python3
"""Tests for self_improve_manager.py — KBSI SOT Manager.

Run: python3 -m pytest _test_self_improve_manager.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import self_improve_manager as sim


class TestValidateSot(unittest.TestCase):
    """Test SOT schema validation (SS1-SS8)."""

    def test_ss1_root_must_be_dict(self):
        errors = sim._validate_sot([])
        self.assertEqual(len(errors), 1)
        self.assertIn("SS1", errors[0])

    def test_ss2_missing_required_keys(self):
        errors = sim._validate_sot({})
        self.assertTrue(any("SS2" in e for e in errors))

    def test_ss3_version_must_be_string(self):
        data = {
            "version": 123,
            "insights": {},
            "total_applied": 0,
            "total_rejected": 0,
        }
        errors = sim._validate_sot(data)
        self.assertTrue(any("SS3" in e for e in errors))

    def test_ss4_insights_must_be_dict(self):
        data = {
            "version": "1.0",
            "insights": [],
            "total_applied": 0,
            "total_rejected": 0,
        }
        errors = sim._validate_sot(data)
        self.assertTrue(any("SS4" in e for e in errors))

    def test_ss5_insight_missing_fields(self):
        data = {
            "version": "1.0",
            "insights": {"SI-001": {"id": "SI-001"}},
            "total_applied": 0,
            "total_rejected": 0,
        }
        errors = sim._validate_sot(data)
        self.assertTrue(any("SS5" in e for e in errors))

    def test_ss6_invalid_type(self):
        data = {
            "version": "1.0",
            "insights": {
                "SI-001": {
                    "id": "SI-001", "title": "t", "condition": "c",
                    "rule": "r", "rationale": "ra", "type": "INVALID",
                    "status": "pending",
                }
            },
            "total_applied": 0,
            "total_rejected": 0,
        }
        errors = sim._validate_sot(data)
        self.assertTrue(any("SS6" in e for e in errors))

    def test_ss7_invalid_status(self):
        data = {
            "version": "1.0",
            "insights": {
                "SI-001": {
                    "id": "SI-001", "title": "t", "condition": "c",
                    "rule": "r", "rationale": "ra", "type": "SAFE",
                    "status": "INVALID",
                }
            },
            "total_applied": 0,
            "total_rejected": 0,
        }
        errors = sim._validate_sot(data)
        self.assertTrue(any("SS7" in e for e in errors))

    def test_ss8_negative_counter(self):
        data = {
            "version": "1.0",
            "insights": {},
            "total_applied": -1,
            "total_rejected": 0,
        }
        errors = sim._validate_sot(data)
        self.assertTrue(any("SS8" in e for e in errors))

    def test_valid_sot(self):
        data = {
            "version": "1.0",
            "insights": {
                "SI-001": {
                    "id": "SI-001", "title": "t", "condition": "c",
                    "rule": "r", "rationale": "ra", "type": "SAFE",
                    "status": "pending",
                }
            },
            "total_applied": 0,
            "total_rejected": 0,
        }
        errors = sim._validate_sot(data)
        self.assertEqual(len(errors), 0)


class TestNextId(unittest.TestCase):
    """Test ID generation."""

    def test_first_id(self):
        self.assertEqual(sim._next_id({"insights": {}}), "SI-001")

    def test_increment(self):
        state = {"insights": {"SI-001": {}, "SI-002": {}, "SI-003": {}}}
        self.assertEqual(sim._next_id(state), "SI-004")

    def test_gap_handling(self):
        """ID generation uses max, not count — gaps don't matter."""
        state = {"insights": {"SI-001": {}, "SI-005": {}}}
        self.assertEqual(sim._next_id(state), "SI-006")

    def test_empty_insights(self):
        self.assertEqual(sim._next_id({}), "SI-001")


class TestImmutableDetection(unittest.TestCase):
    """Test immutable boundary keyword detection."""

    def test_detect_absolute_standard(self):
        matches = sim._detect_immutable_keywords("This modifies Absolute Standard 1")
        self.assertIn("absolute standard", matches)

    def test_detect_korean(self):
        matches = sim._detect_immutable_keywords("절대 기준을 변경합니다")
        self.assertIn("절대 기준", matches)

    def test_detect_context_lib(self):
        matches = sim._detect_immutable_keywords("Changes _context_lib.py behavior")
        self.assertIn("_context_lib.py", matches)

    def test_no_matches(self):
        matches = sim._detect_immutable_keywords("Simple formatting fix")
        self.assertEqual(len(matches), 0)

    def test_case_insensitive(self):
        matches = sim._detect_immutable_keywords("P1 SANDWICH architecture")
        self.assertIn("p1 sandwich", matches)


class TestHubFileDetection(unittest.TestCase):
    """Test hub file reference detection."""

    def test_detect_agents_md(self):
        matches = sim._detect_hub_file_references("Update AGENTS.md section 5")
        self.assertIn("AGENTS.md", matches)

    def test_detect_soul_md(self):
        matches = sim._detect_hub_file_references("Modify soul.md genome")
        self.assertIn("soul.md", matches)

    def test_no_matches(self):
        matches = sim._detect_hub_file_references("Update some_script.py")
        self.assertEqual(len(matches), 0)


class TestEnsureState(unittest.TestCase):
    """Test lazy SOT initialization."""

    def test_creates_initial_sot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "self-improvement-logs"
            si_dir.mkdir()

            state = sim._ensure_state(si_dir)

            self.assertEqual(state["version"], "1.0")
            self.assertEqual(state["insights"], {})
            self.assertEqual(state["total_applied"], 0)
            self.assertTrue((si_dir / "state.json").exists())

    def test_reads_existing_sot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "self-improvement-logs"
            si_dir.mkdir()

            # Pre-create SOT
            existing = {
                "version": "1.0",
                "insights": {"SI-001": {
                    "id": "SI-001", "title": "t", "condition": "c",
                    "rule": "r", "rationale": "ra", "type": "SAFE",
                    "status": "pending",
                }},
                "total_applied": 0,
                "total_rejected": 0,
            }
            with open(si_dir / "state.json", "w") as f:
                json.dump(existing, f)

            state = sim._ensure_state(si_dir)
            self.assertIn("SI-001", state["insights"])

    def test_creates_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "nested" / "self-improvement-logs"
            # Parent doesn't exist yet — _ensure_state should handle this
            si_dir.mkdir(parents=True)

            state = sim._ensure_state(si_dir)
            self.assertTrue((si_dir / "state.json").exists())


class TestRegisterInsight(unittest.TestCase):
    """Test insight registration."""

    def test_register_safe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            insight_id, state = sim.register_insight(
                si_dir=si_dir,
                title="Test insight",
                condition="When X happens",
                rule="Do Y instead",
                rationale="Because Z",
                insight_type="SAFE",
            )

            self.assertEqual(insight_id, "SI-001")
            self.assertEqual(state["insights"]["SI-001"]["status"], "pending")
            self.assertEqual(state["insights"]["SI-001"]["type"], "SAFE")
            self.assertTrue((si_dir / "pending" / "SI-001.json").exists())

    def test_auto_structural_on_immutable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            insight_id, state = sim.register_insight(
                si_dir=si_dir,
                title="Modify absolute standard",
                condition="When absolute standard 1 needs change",
                rule="Change quality threshold",
                rationale="Better quality metrics",
                insight_type="SAFE",  # Will be auto-upgraded
            )

            # Should be auto-upgraded to STRUCTURAL
            self.assertEqual(state["insights"]["SI-001"]["type"], "STRUCTURAL")
            self.assertTrue(state["insights"]["SI-001"]["auto_structural"])

    def test_auto_structural_on_hub_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            insight_id, state = sim.register_insight(
                si_dir=si_dir,
                title="Fix AGENTS.md format",
                condition="When AGENTS.md section structure is inconsistent",
                rule="Enforce consistent heading levels",
                rationale="Readability",
                insight_type="SAFE",
            )

            self.assertEqual(state["insights"]["SI-001"]["type"], "STRUCTURAL")

    def test_sequential_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            id1, _ = sim.register_insight(
                si_dir, "T1", "C1", "R1", "Ra1", "SAFE",
            )
            id2, _ = sim.register_insight(
                si_dir, "T2", "C2", "R2", "Ra2", "SAFE",
            )

            self.assertEqual(id1, "SI-001")
            self.assertEqual(id2, "SI-002")

    def test_invalid_error_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            with self.assertRaises(ValueError):
                sim.register_insight(
                    si_dir, "T", "C", "R", "Ra", "SAFE",
                    error_type="INVALID_TYPE",
                )

    def test_teammate_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            with patch.dict(os.environ, {"CLAUDE_AGENT_TEAMS_TEAMMATE": "worker-1"}):
                with self.assertRaises(PermissionError):
                    sim.register_insight(
                        si_dir, "T", "C", "R", "Ra", "SAFE",
                    )


class TestApplyInsight(unittest.TestCase):
    """Test insight application."""

    def _setup_with_pending(self, tmpdir):
        si_dir = Path(tmpdir) / "si"
        si_dir.mkdir()
        sim.register_insight(si_dir, "T", "C", "R", "Ra", "SAFE")
        return si_dir

    def test_apply_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = self._setup_with_pending(tmpdir)

            state = sim.apply_insight(si_dir, "SI-001")

            self.assertEqual(state["insights"]["SI-001"]["status"], "applied")
            self.assertIsNotNone(state["insights"]["SI-001"]["applied_at"])
            self.assertEqual(state["total_applied"], 1)
            # Pending file removed, applied file created
            self.assertFalse((si_dir / "pending" / "SI-001.json").exists())
            self.assertTrue((si_dir / "applied" / "SI-001.json").exists())

    def test_apply_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = self._setup_with_pending(tmpdir)

            with self.assertRaises(ValueError):
                sim.apply_insight(si_dir, "SI-999")

    def test_apply_already_applied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = self._setup_with_pending(tmpdir)
            sim.apply_insight(si_dir, "SI-001")

            with self.assertRaises(ValueError):
                sim.apply_insight(si_dir, "SI-001")


class TestRejectInsight(unittest.TestCase):
    """Test insight rejection."""

    def test_reject_with_reason(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()
            sim.register_insight(si_dir, "T", "C", "R", "Ra", "SAFE")

            state = sim.reject_insight(si_dir, "SI-001", "Too specific")

            self.assertEqual(state["insights"]["SI-001"]["status"], "rejected")
            self.assertEqual(state["insights"]["SI-001"]["rejection_reason"], "Too specific")
            self.assertEqual(state["total_rejected"], 1)

    def test_reject_already_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()
            sim.register_insight(si_dir, "T", "C", "R", "Ra", "SAFE")
            sim.reject_insight(si_dir, "SI-001", "reason")

            with self.assertRaises(ValueError):
                sim.reject_insight(si_dir, "SI-001", "again")


class TestComputeEffectiveness(unittest.TestCase):
    """Test effectiveness measurement."""

    def _create_ki(self, tmpdir, entries):
        ki_path = os.path.join(tmpdir, "ki.jsonl")
        with open(ki_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return ki_path

    def test_effectiveness_reduction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            sim.register_insight(
                si_dir, "T", "C", "R", "Ra", "SAFE",
                error_type="edit_mismatch",
            )
            sim.apply_insight(si_dir, "SI-001")

            # Set a known applied_at timestamp
            state = sim._read_state(si_dir)
            state["insights"]["SI-001"]["applied_at"] = "2026-03-01T00:00:00"
            sim._write_state(si_dir, state)

            ki_path = self._create_ki(tmpdir, [
                # Before application
                {"timestamp": "2026-02-15T00:00:00", "error_patterns": [{"type": "edit_mismatch"}]},
                {"timestamp": "2026-02-20T00:00:00", "error_patterns": [{"type": "edit_mismatch"}]},
                {"timestamp": "2026-02-25T00:00:00", "error_patterns": [{"type": "edit_mismatch"}]},
                # After application — fewer errors
                {"timestamp": "2026-03-05T00:00:00", "error_patterns": [{"type": "edit_mismatch"}]},
            ])

            result = sim.compute_effectiveness(si_dir, "SI-001", ki_path)

            self.assertEqual(result["before_count"], 3)
            self.assertEqual(result["after_count"], 1)
            self.assertAlmostEqual(result["effectiveness_pct"], 66.7, places=1)

    def test_effectiveness_no_error_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            sim.register_insight(si_dir, "T", "C", "R", "Ra", "SAFE")
            sim.apply_insight(si_dir, "SI-001")

            ki_path = self._create_ki(tmpdir, [])
            result = sim.compute_effectiveness(si_dir, "SI-001", ki_path)

            self.assertIn("error", result)

    def test_effectiveness_not_applied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            sim.register_insight(
                si_dir, "T", "C", "R", "Ra", "SAFE",
                error_type="syntax_error",
            )

            ki_path = self._create_ki(tmpdir, [])
            result = sim.compute_effectiveness(si_dir, "SI-001", ki_path)

            self.assertIn("error", result)

    def test_effectiveness_ki_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            sim.register_insight(
                si_dir, "T", "C", "R", "Ra", "SAFE",
                error_type="file_not_found",
            )
            sim.apply_insight(si_dir, "SI-001")

            result = sim.compute_effectiveness(si_dir, "SI-001", "/nonexistent/ki.jsonl")
            self.assertIn("error", result)


class TestApplyToAgentsMd(unittest.TestCase):
    """Test AGENTS.md marker-based append."""

    def _create_agents_md(self, tmpdir, section_content=""):
        agents_md = os.path.join(tmpdir, "AGENTS.md")
        content = (
            "# Section 1\n\nContent of section 1.\n\n"
            "# Section 10\n\nContent of section 10.\n\n"
            "## 11. Self-Improvement\n\n"
            f"{sim.AGENTS_MD_START_MARKER}\n"
            f"{section_content}"
            f"{sim.AGENTS_MD_END_MARKER}\n"
        )
        with open(agents_md, "w") as f:
            f.write(content)
        return agents_md

    def test_append_insight(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = self._create_agents_md(tmpdir)

            insight = {
                "id": "SI-001",
                "title": "Test Rule",
                "condition": "When X",
                "rule": "Do Y",
                "rationale": "Because Z",
                "error_type": "syntax_error",
                "applied_at": "2026-03-09T00:00:00",
            }

            result = sim.apply_to_agents_md(agents_md, insight)

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["insight_id"], "SI-001")

            # Verify content
            with open(agents_md) as f:
                content = f.read()
            self.assertIn("SI-001: Test Rule", content)
            self.assertIn("**Condition**: When X", content)
            self.assertIn("**Rule**: Do Y", content)

    def test_preserves_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = self._create_agents_md(tmpdir)

            with open(agents_md) as f:
                before_content = f.read()
            before_start_idx = before_content.find(sim.AGENTS_MD_START_MARKER)
            before_text = before_content[:before_start_idx]

            insight = {
                "id": "SI-001", "title": "T", "condition": "C",
                "rule": "R", "rationale": "Ra",
            }
            sim.apply_to_agents_md(agents_md, insight)

            with open(agents_md) as f:
                after_content = f.read()
            after_start_idx = after_content.find(sim.AGENTS_MD_START_MARKER)
            after_text = after_content[:after_start_idx]

            self.assertEqual(before_text, after_text)

    def test_missing_markers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = os.path.join(tmpdir, "AGENTS.md")
            with open(agents_md, "w") as f:
                f.write("# No markers here\n")

            result = sim.apply_to_agents_md(agents_md, {"id": "SI-001"})
            self.assertEqual(result["status"], "FAIL")

    def test_missing_file(self):
        result = sim.apply_to_agents_md("/nonexistent/AGENTS.md", {"id": "SI-001"})
        self.assertEqual(result["status"], "FAIL")

    def test_teammate_blocked(self):
        """Teammates must not modify AGENTS.md (Hub file protection)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = self._create_agents_md(tmpdir)

            with patch.dict(os.environ, {"CLAUDE_AGENT_TEAMS_TEAMMATE": "worker-1"}):
                result = sim.apply_to_agents_md(agents_md, {"id": "SI-001"})
                self.assertEqual(result["status"], "FAIL")
                self.assertIn("teammates", result["error"])

    def test_multiple_appends(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = self._create_agents_md(tmpdir)

            for i in range(3):
                insight = {
                    "id": f"SI-{i+1:03d}",
                    "title": f"Rule {i+1}",
                    "condition": f"Condition {i+1}",
                    "rule": f"Rule body {i+1}",
                    "rationale": f"Rationale {i+1}",
                }
                result = sim.apply_to_agents_md(agents_md, insight)
                self.assertEqual(result["status"], "PASS")

            with open(agents_md) as f:
                content = f.read()

            self.assertIn("SI-001", content)
            self.assertIn("SI-002", content)
            self.assertIn("SI-003", content)


class TestSyncClaudeMd(unittest.TestCase):
    """Test CLAUDE.md marker-based sync."""

    def _create_claude_md(self, tmpdir, section_content=""):
        claude_md = os.path.join(tmpdir, "CLAUDE.md")
        content = (
            "# CLAUDE.md Header\n\n"
            "Some content before.\n\n"
            f"{sim.CLAUDE_MD_START_MARKER}\n"
            f"{section_content}"
            f"{sim.CLAUDE_MD_END_MARKER}\n\n"
            "Some content after.\n"
        )
        with open(claude_md, "w") as f:
            f.write(content)
        return claude_md

    def test_sync_with_applied_insights(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            sim.register_insight(si_dir, "Test 1", "C1", "R1", "Ra1", "SAFE")
            sim.apply_insight(si_dir, "SI-001")

            claude_md = self._create_claude_md(tmpdir)
            result = sim.sync_claude_md(si_dir, claude_md)

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["applied_count"], 1)

            with open(claude_md) as f:
                content = f.read()
            self.assertIn("SI-001", content)
            self.assertIn("Test 1", content)

    def test_preserves_surrounding_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()
            sim._ensure_state(si_dir)

            claude_md = self._create_claude_md(tmpdir)
            sim.sync_claude_md(si_dir, claude_md)

            with open(claude_md) as f:
                content = f.read()
            self.assertIn("CLAUDE.md Header", content)
            self.assertIn("Some content before.", content)
            self.assertIn("Some content after.", content)

    def test_missing_markers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()
            sim._ensure_state(si_dir)

            claude_md = os.path.join(tmpdir, "CLAUDE.md")
            with open(claude_md, "w") as f:
                f.write("# No markers\n")

            result = sim.sync_claude_md(si_dir, claude_md)
            self.assertEqual(result["status"], "FAIL")

    def test_teammate_blocked(self):
        """Teammates must not modify CLAUDE.md (Hub file protection)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()
            sim._ensure_state(si_dir)

            claude_md = self._create_claude_md(tmpdir)

            with patch.dict(os.environ, {"CLAUDE_AGENT_TEAMS_TEAMMATE": "worker-1"}):
                result = sim.sync_claude_md(si_dir, claude_md)
                self.assertEqual(result["status"], "FAIL")
                self.assertIn("teammates", result["error"])


class TestQueueChange(unittest.TestCase):
    """Test queued changes for Track 2."""

    def test_queue_safe_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            state = sim.queue_change(si_dir, "some_hook.py", "SAFE", "Fix warning message")

            self.assertEqual(len(state["queued_changes"]), 1)
            self.assertEqual(state["queued_changes"][0]["change_type"], "SAFE")

    def test_auto_structural_context_lib(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            state = sim.queue_change(
                si_dir, "_context_lib.py", "SAFE", "Add helper"
            )

            # _context_lib.py always STRUCTURAL
            self.assertEqual(state["queued_changes"][0]["change_type"], "STRUCTURAL")

    def test_auto_structural_hub_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            state = sim.queue_change(
                si_dir, "AGENTS.md", "SAFE", "Add section"
            )

            self.assertEqual(state["queued_changes"][0]["change_type"], "STRUCTURAL")

    def test_queued_changes_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            sim.queue_change(si_dir, "hook.py", "SAFE", "desc")

            self.assertTrue((si_dir / "queued-changes" / "change-001.json").exists())


class TestValidateQueuedChanges(unittest.TestCase):
    """Test queued change validation."""

    def test_empty_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()
            sim._ensure_state(si_dir)

            result = sim.validate_queued_changes(si_dir)
            self.assertEqual(result["total"], 0)
            self.assertTrue(result["requires_user_approval"] is False)

    def test_structural_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            sim.queue_change(si_dir, "_context_lib.py", "SAFE", "Change")

            result = sim.validate_queued_changes(si_dir)
            self.assertTrue(result["requires_user_approval"])
            self.assertEqual(result["structural"], 1)


class TestGetStatus(unittest.TestCase):
    """Test status reporting."""

    def test_empty_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            status = sim.get_status(si_dir)

            self.assertEqual(status["total_insights"], 0)
            self.assertEqual(status["by_status"]["pending"], 0)
            self.assertEqual(status["version"], "1.0")

    def test_mixed_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            sim.register_insight(si_dir, "T1", "C1", "R1", "Ra1", "SAFE")
            sim.register_insight(si_dir, "T2", "C2", "R2", "Ra2", "STRUCTURAL")
            sim.apply_insight(si_dir, "SI-001")
            sim.reject_insight(si_dir, "SI-002", "reason")

            status = sim.get_status(si_dir)

            self.assertEqual(status["total_insights"], 2)
            self.assertEqual(status["by_status"]["applied"], 1)
            self.assertEqual(status["by_status"]["rejected"], 1)


class TestAtomicWrite(unittest.TestCase):
    """Test atomic write operations."""

    def test_atomic_json_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            data = {"key": "value", "num": 42}

            sim._atomic_write_json(path, data)

            with open(path) as f:
                loaded = json.load(f)
            self.assertEqual(loaded["key"], "value")

    def test_atomic_text_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.md"
            content = "# Hello World\n\nContent here.\n"

            sim._atomic_write_text(path, content)

            with open(path) as f:
                loaded = f.read()
            self.assertEqual(loaded, content)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a" / "b" / "test.json"

            sim._atomic_write_json(path, {"test": True})

            self.assertTrue(path.exists())


class TestCLI(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_register_missing_fields(self):
        """CLI should return 1 when required fields missing."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "self_improve_manager.py"),
             "--register", "--si-dir", "/tmp/test-si",
             "--title", "Test"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)

    def test_status_output(self):
        """CLI --status should output valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            import subprocess
            result = subprocess.run(
                [sys.executable, str(Path(__file__).parent / "self_improve_manager.py"),
                 "--status", "--si-dir", str(si_dir)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0)
            output = json.loads(result.stdout)
            self.assertIn("total_insights", output)

    def test_next_id_output(self):
        """CLI --next-id should output valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = Path(tmpdir) / "si"
            si_dir.mkdir()

            import subprocess
            result = subprocess.run(
                [sys.executable, str(Path(__file__).parent / "self_improve_manager.py"),
                 "--next-id", "--si-dir", str(si_dir)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0)
            output = json.loads(result.stdout)
            self.assertEqual(output["next_id"], "SI-001")


if __name__ == "__main__":
    unittest.main()
