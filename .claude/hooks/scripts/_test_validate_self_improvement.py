#!/usr/bin/env python3
"""Tests for validate_self_improvement.py — KBSI insight validation (SI-1~SI-6).

Run: python3 -m pytest _test_validate_self_improvement.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import validate_self_improvement as vsi


def _make_insight(**overrides):
    """Create a valid insight dict with optional overrides."""
    base = {
        "id": "SI-001",
        "title": "Test Insight",
        "condition": "When something happens",
        "rule": "Do this instead",
        "rationale": "Because quality matters",
        "type": "SAFE",
        "status": "pending",
    }
    base.update(overrides)
    return base


class TestSI1Format(unittest.TestCase):
    """SI-1: Rule format validation."""

    def test_valid_insight(self):
        results = vsi._check_si1_format(_make_insight())
        statuses = [r["status"] for r in results]
        self.assertNotIn("FAIL", statuses)

    def test_missing_field(self):
        insight = _make_insight()
        del insight["title"]
        results = vsi._check_si1_format(insight)
        self.assertTrue(any(r["status"] == "FAIL" for r in results))
        self.assertTrue(any("title" in r["detail"] for r in results))

    def test_empty_field(self):
        insight = _make_insight(rule="")
        results = vsi._check_si1_format(insight)
        self.assertTrue(any(r["status"] == "FAIL" for r in results))

    def test_none_field(self):
        insight = _make_insight(condition=None)
        results = vsi._check_si1_format(insight)
        self.assertTrue(any(r["status"] == "FAIL" for r in results))

    def test_invalid_type(self):
        insight = _make_insight(type="INVALID")
        results = vsi._check_si1_format(insight)
        self.assertTrue(any(r["status"] == "FAIL" and "type" in r["detail"] for r in results))

    def test_invalid_status(self):
        insight = _make_insight(status="INVALID")
        results = vsi._check_si1_format(insight)
        self.assertTrue(any(r["status"] == "FAIL" and "status" in r["detail"] for r in results))

    def test_invalid_id_format(self):
        insight = _make_insight(id="BAD-001")
        results = vsi._check_si1_format(insight)
        self.assertTrue(any(r["status"] == "FAIL" and "ID format" in r["detail"] for r in results))

    def test_valid_id_format(self):
        insight = _make_insight(id="SI-042")
        results = vsi._check_si1_format(insight)
        fail_results = [r for r in results if r["status"] == "FAIL"]
        self.assertEqual(len(fail_results), 0)


class TestSI2Immutable(unittest.TestCase):
    """SI-2: Immutable boundary keyword detection."""

    def test_detects_absolute_standard(self):
        insight = _make_insight(condition="Modify Absolute Standard 1 threshold")
        results = vsi._check_si2_immutable(insight)
        self.assertTrue(any(r["status"] == "WARN" for r in results))

    def test_detects_in_rule(self):
        insight = _make_insight(rule="Change P1 Sandwich validation order")
        results = vsi._check_si2_immutable(insight)
        self.assertTrue(any(r["status"] == "WARN" for r in results))

    def test_detects_in_rationale(self):
        insight = _make_insight(rationale="DNA inheritance requires this")
        results = vsi._check_si2_immutable(insight)
        self.assertTrue(any(r["status"] == "WARN" for r in results))

    def test_structural_no_warn(self):
        """If already STRUCTURAL, should PASS (not WARN)."""
        insight = _make_insight(
            type="STRUCTURAL",
            condition="Modify Absolute Standard",
        )
        results = vsi._check_si2_immutable(insight)
        self.assertTrue(any(r["status"] == "PASS" for r in results))

    def test_no_keywords(self):
        insight = _make_insight(condition="Fix typo in output")
        results = vsi._check_si2_immutable(insight)
        self.assertTrue(any(r["status"] == "PASS" for r in results))

    def test_korean_keyword(self):
        insight = _make_insight(condition="절대 기준을 변경합니다")
        results = vsi._check_si2_immutable(insight)
        self.assertTrue(any(r["status"] == "WARN" for r in results))


class TestSI3HubFiles(unittest.TestCase):
    """SI-3: Hub file change detection."""

    def test_detects_agents_md(self):
        insight = _make_insight(condition="Update AGENTS.md section 5")
        results = vsi._check_si3_hub_files(insight)
        self.assertTrue(any(r["status"] == "WARN" for r in results))

    def test_detects_context_lib(self):
        insight = _make_insight(rule="Add function to _context_lib.py")
        results = vsi._check_si3_hub_files(insight)
        self.assertTrue(any(r["status"] == "WARN" for r in results))

    def test_structural_no_warn(self):
        insight = _make_insight(
            type="STRUCTURAL",
            condition="Changes AGENTS.md",
        )
        results = vsi._check_si3_hub_files(insight)
        self.assertTrue(any(r["status"] == "PASS" for r in results))

    def test_no_hub_files(self):
        insight = _make_insight(condition="Update validate_pacs.py output")
        results = vsi._check_si3_hub_files(insight)
        statuses = [r["status"] for r in results]
        self.assertIn("PASS", statuses)


class TestSI4Markers(unittest.TestCase):
    """SI-4: §11 marker boundary verification."""

    def test_valid_markers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = os.path.join(tmpdir, "AGENTS.md")
            with open(agents_md, "w") as f:
                f.write(
                    "# Content\n\n"
                    f"{vsi.AGENTS_MD_START_MARKER}\n"
                    "Some insights here\n"
                    f"{vsi.AGENTS_MD_END_MARKER}\n"
                )

            results = vsi._check_si4_markers(agents_md)
            self.assertTrue(any(r["status"] == "PASS" for r in results))

    def test_missing_start_marker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = os.path.join(tmpdir, "AGENTS.md")
            with open(agents_md, "w") as f:
                f.write(
                    "# Content\n\n"
                    f"{vsi.AGENTS_MD_END_MARKER}\n"
                )

            results = vsi._check_si4_markers(agents_md)
            self.assertTrue(any(r["status"] == "FAIL" for r in results))

    def test_missing_end_marker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = os.path.join(tmpdir, "AGENTS.md")
            with open(agents_md, "w") as f:
                f.write(
                    "# Content\n\n"
                    f"{vsi.AGENTS_MD_START_MARKER}\n"
                )

            results = vsi._check_si4_markers(agents_md)
            self.assertTrue(any(r["status"] == "FAIL" for r in results))

    def test_reversed_markers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = os.path.join(tmpdir, "AGENTS.md")
            with open(agents_md, "w") as f:
                f.write(
                    f"{vsi.AGENTS_MD_END_MARKER}\n"
                    f"{vsi.AGENTS_MD_START_MARKER}\n"
                )

            results = vsi._check_si4_markers(agents_md)
            self.assertTrue(any(r["status"] == "FAIL" for r in results))

    def test_file_not_found(self):
        results = vsi._check_si4_markers("/nonexistent/AGENTS.md")
        self.assertTrue(any(r["status"] == "SKIP" for r in results))

    def test_counts_existing_insights(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = os.path.join(tmpdir, "AGENTS.md")
            with open(agents_md, "w") as f:
                f.write(
                    "# Content\n\n"
                    f"{vsi.AGENTS_MD_START_MARKER}\n"
                    "#### SI-001: First Rule\n"
                    "#### SI-002: Second Rule\n"
                    f"{vsi.AGENTS_MD_END_MARKER}\n"
                )

            results = vsi._check_si4_markers(agents_md)
            info_results = [r for r in results if r["status"] == "INFO"]
            self.assertTrue(any("2 insights" in r["detail"] for r in info_results))


class TestSI5Duplicates(unittest.TestCase):
    """SI-5: Bigram duplicate detection."""

    def _setup_with_applied(self, tmpdir, applied_insights):
        si_dir = os.path.join(tmpdir, "si")
        os.makedirs(si_dir)
        state = {
            "version": "1.0",
            "insights": applied_insights,
            "total_applied": len(applied_insights),
            "total_rejected": 0,
        }
        with open(os.path.join(si_dir, "state.json"), "w") as f:
            json.dump(state, f)
        return si_dir

    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = self._setup_with_applied(tmpdir, {
                "SI-001": {
                    "id": "SI-001", "title": "t", "condition": "alpha beta gamma delta",
                    "rule": "epsilon zeta eta theta", "rationale": "r",
                    "type": "SAFE", "status": "applied",
                }
            })

            new_insight = _make_insight(
                condition="completely different words here now",
                rule="nothing overlapping whatsoever found",
            )
            results = vsi._check_si5_duplicates(new_insight, si_dir)
            self.assertTrue(any(r["status"] == "PASS" for r in results))

    def test_detects_duplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = self._setup_with_applied(tmpdir, {
                "SI-001": {
                    "id": "SI-001", "title": "t",
                    "condition": "validate claim inheritance correctly structured format",
                    "rule": "check claim prefix match against registry validation deterministic",
                    "rationale": "r", "type": "SAFE", "status": "applied",
                }
            })

            # New insight with substantial overlap
            new_insight = _make_insight(
                id="SI-002",
                condition="validate claim inheritance correctly structured format",
                rule="check claim prefix match against registry validation deterministic",
            )
            results = vsi._check_si5_duplicates(new_insight, si_dir)
            self.assertTrue(any(r["status"] == "WARN" for r in results))

    def test_no_applied_insights(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = self._setup_with_applied(tmpdir, {})
            new_insight = _make_insight()
            results = vsi._check_si5_duplicates(new_insight, si_dir)
            self.assertTrue(any(r["status"] == "PASS" for r in results))

    def test_no_si_dir(self):
        results = vsi._check_si5_duplicates(_make_insight())
        self.assertTrue(any(r["status"] == "SKIP" for r in results))

    def test_skip_self(self):
        """Should not flag itself as duplicate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = self._setup_with_applied(tmpdir, {
                "SI-001": {
                    "id": "SI-001", "title": "t",
                    "condition": "validate claim inheritance correctly structured format",
                    "rule": "check claim prefix match against registry validation deterministic",
                    "rationale": "r", "type": "SAFE", "status": "applied",
                }
            })

            # Same ID = self
            new_insight = _make_insight(
                id="SI-001",
                condition="validate claim inheritance correctly structured format",
                rule="check claim prefix match against registry validation deterministic",
            )
            results = vsi._check_si5_duplicates(new_insight, si_dir)
            # Should PASS because it skips itself
            self.assertTrue(any(r["status"] == "PASS" for r in results))


class TestSI6Uniqueness(unittest.TestCase):
    """SI-6: ID uniqueness verification."""

    def test_unique_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = os.path.join(tmpdir, "si")
            os.makedirs(si_dir)
            state = {
                "version": "1.0",
                "insights": {"SI-001": {"id": "SI-001", "title": "t", "condition": "c",
                                        "rule": "r", "rationale": "ra", "type": "SAFE",
                                        "status": "applied"}},
                "total_applied": 1,
                "total_rejected": 0,
            }
            with open(os.path.join(si_dir, "state.json"), "w") as f:
                json.dump(state, f)

            insight = _make_insight(id="SI-002")
            results = vsi._check_si6_uniqueness(insight, si_dir)
            self.assertTrue(any(r["status"] == "PASS" for r in results))

    def test_duplicate_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            si_dir = os.path.join(tmpdir, "si")
            os.makedirs(si_dir)
            state = {
                "version": "1.0",
                "insights": {"SI-001": {"id": "SI-001", "title": "t", "condition": "c",
                                        "rule": "r", "rationale": "ra", "type": "SAFE",
                                        "status": "applied"}},
                "total_applied": 1,
                "total_rejected": 0,
            }
            with open(os.path.join(si_dir, "state.json"), "w") as f:
                json.dump(state, f)

            insight = _make_insight(id="SI-001")
            results = vsi._check_si6_uniqueness(insight, si_dir)
            self.assertTrue(any(r["status"] == "FAIL" for r in results))

    def test_no_sot(self):
        insight = _make_insight()
        results = vsi._check_si6_uniqueness(insight, "/nonexistent")
        self.assertTrue(any(r["status"] == "PASS" for r in results))

    def test_no_id(self):
        insight = _make_insight()
        del insight["id"]
        results = vsi._check_si6_uniqueness(insight, "/tmp")
        self.assertTrue(any(r["status"] == "FAIL" for r in results))


class TestBigramExtraction(unittest.TestCase):
    """Test bigram extraction helper."""

    def test_basic_extraction(self):
        bigrams = vsi._extract_bigrams("hello world foo bar baz")
        self.assertIn(("hello", "world"), bigrams)
        self.assertIn(("foo", "bar"), bigrams)

    def test_stopword_filtering(self):
        bigrams = vsi._extract_bigrams("the quick and brown fox")
        # "the" and "and" are stopwords
        self.assertIn(("quick", "brown"), bigrams)

    def test_case_insensitive(self):
        bigrams = vsi._extract_bigrams("Hello World")
        self.assertIn(("hello", "world"), bigrams)

    def test_short_words_filtered(self):
        """Words ≤ 2 chars should be filtered."""
        bigrams = vsi._extract_bigrams("to do it on my")
        self.assertEqual(len(bigrams), 0)

    def test_empty_text(self):
        bigrams = vsi._extract_bigrams("")
        self.assertEqual(len(bigrams), 0)


class TestValidateInsight(unittest.TestCase):
    """Test full validation pipeline."""

    def test_valid_insight_passes(self):
        result = vsi.validate_insight(_make_insight())
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["warnings"]), 0)

    def test_missing_field_fails(self):
        insight = _make_insight()
        del insight["rule"]
        result = vsi.validate_insight(insight)
        self.assertFalse(result["passed"])

    def test_with_agents_md(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_md = os.path.join(tmpdir, "AGENTS.md")
            with open(agents_md, "w") as f:
                f.write(
                    "# Content\n\n"
                    f"{vsi.AGENTS_MD_START_MARKER}\n"
                    f"{vsi.AGENTS_MD_END_MARKER}\n"
                )

            result = vsi.validate_insight(
                _make_insight(),
                agents_md_path=agents_md,
            )
            self.assertTrue(result["passed"])
            # SI-4 should be in results
            si4_results = [r for r in result["results"] if r["check"] == "SI-4"]
            self.assertTrue(len(si4_results) > 0)

    def test_immutable_keyword_warns(self):
        insight = _make_insight(condition="Modify Absolute Standard 1")
        result = vsi.validate_insight(insight)
        self.assertTrue(result["passed"])  # WARN doesn't fail
        self.assertTrue(len(result["warnings"]) > 0)


class TestValidateAllPending(unittest.TestCase):
    """Test batch validation."""

    def test_no_pending_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = vsi.validate_all_pending(tmpdir)
            self.assertEqual(result["total"], 0)
            self.assertTrue(result["all_passed"])

    def test_validates_pending_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pending_dir = Path(tmpdir) / "pending"
            pending_dir.mkdir()

            # Write valid pending insight
            insight = _make_insight()
            with open(pending_dir / "SI-001.json", "w") as f:
                json.dump(insight, f)

            result = vsi.validate_all_pending(tmpdir)
            self.assertEqual(result["total"], 1)
            self.assertTrue(result["all_passed"])

    def test_invalid_pending_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pending_dir = Path(tmpdir) / "pending"
            pending_dir.mkdir()

            # Write invalid insight (missing fields)
            with open(pending_dir / "SI-001.json", "w") as f:
                json.dump({"id": "SI-001"}, f)

            result = vsi.validate_all_pending(tmpdir)
            self.assertEqual(result["total"], 1)
            self.assertFalse(result["all_passed"])

    def test_corrupt_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pending_dir = Path(tmpdir) / "pending"
            pending_dir.mkdir()

            with open(pending_dir / "SI-001.json", "w") as f:
                f.write("not valid json{{{")

            result = vsi.validate_all_pending(tmpdir)
            self.assertEqual(result["total"], 1)
            self.assertFalse(result["all_passed"])


class TestCLI(unittest.TestCase):
    """Test CLI entry points."""

    def test_check_markers_requires_agents_md(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "validate_self_improvement.py"),
             "--check-markers"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)  # P1: always exit 0
        output = json.loads(result.stdout)
        self.assertFalse(output["passed"])

    def test_validate_all_requires_si_dir(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "validate_self_improvement.py"),
             "--validate-all"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["passed"])

    def test_validate_file_not_found(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "validate_self_improvement.py"),
             "--insight-file", "/nonexistent/SI-001.json"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)  # P1: always exit 0
        output = json.loads(result.stdout)
        self.assertFalse(output["passed"])


if __name__ == "__main__":
    unittest.main()
