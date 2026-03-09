#!/usr/bin/env python3
"""Unit tests for validate_skill_output.py (SK-1~SK-5)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

# Import the module under test
sys.path.insert(0, os.path.dirname(__file__))
from validate_skill_output import (
    check_sk1_frontmatter,
    check_sk2_inherited_dna,
    check_sk3_protocol_steps,
    check_sk4_quality_section,
    check_sk5_references,
    validate_skill,
)


# =============================================================================
# Fixtures
# =============================================================================

VALID_SKILL_MD = """\
---
name: test-skill
description: Test skill for validation
---

# Test Skill

A test skill.

## Inherited DNA

| DNA Component | Expression |
|--------------|-----------|
| Quality | Output quality is paramount |

## Protocol

### Step 1: Analyze

Analyze the input.

### Step 2: Generate

Generate the output.

## Quality Gates

- L0: File exists
- L1: Content valid
"""

MINIMAL_SKILL_MD = """\
---
name: minimal
description: Minimal valid skill
---

# Minimal

## Inherited DNA
Present.

## Protocol
### Step 1: Do
Do the thing.

## Quality Checklist
- [ ] Done
"""

NO_FRONTMATTER = """\
# No Frontmatter Skill

## Inherited DNA
## Protocol
### Step 1: Test
## Quality Gates
"""

MISSING_NAME = """\
---
description: Missing name field
---

# Missing Name

## Inherited DNA
## Protocol
### Step 1: Test
## Quality Gates
"""

MISSING_DESCRIPTION = """\
---
name: missing-desc
---

# Missing Desc

## Inherited DNA
## Protocol
### Step 1: Test
## Quality Gates
"""

NO_DNA = """\
---
name: no-dna
description: No DNA section
---

# No DNA

## Protocol
### Step 1: Test
## Quality Gates
"""

NO_PROTOCOL = """\
---
name: no-protocol
description: No protocol section
---

# No Protocol

## Inherited DNA
Present.

## Quality Gates
"""

PROTOCOL_NO_STEPS = """\
---
name: no-steps
description: Protocol without steps
---

# No Steps

## Inherited DNA
Present.

## Protocol
Just some text without numbered steps.

## Quality Gates
"""

NO_QUALITY = """\
---
name: no-quality
description: No quality section
---

# No Quality

## Inherited DNA
Present.

## Protocol
### Step 1: Do
Do.
"""

P1_ENFORCEMENT_VARIANT = """\
---
name: p1-skill
description: Uses P1 Enforcement instead of Quality Gates
---

# P1 Skill

## Inherited DNA
Present.

## Protocol
### Step 1: Validate
Validate.

## P1 Enforcement
- All checks deterministic
"""

GENERATION_PROTOCOL_VARIANT = """\
---
name: gen-skill
description: Uses Generation Protocol heading
---

# Gen Skill

## Inherited DNA
Present.

## Generation Protocol

### Step 1: Design
Design it.

### Step 2: Build
Build it.

## Quality Criteria
Quality is paramount.
"""

FORK_CONTEXT_WITH_AGENT = """\
---
name: forked-skill
description: A forked skill
context: fork
agent: general-purpose
---

# Forked Skill

## Inherited DNA
Present.

## Protocol
### Step 1: Run
Run.

## Quality Gates
- L0: Exists
"""

FORK_CONTEXT_NO_AGENT = """\
---
name: forked-no-agent
description: Forked without agent field
context: fork
---

# Forked No Agent

## Inherited DNA
Present.

## Protocol
### Step 1: Run
Run.

## Quality Gates
- L0: Exists
"""


# =============================================================================
# SK-1: Frontmatter
# =============================================================================

class TestSK1Frontmatter(unittest.TestCase):
    def test_valid_frontmatter(self):
        result = check_sk1_frontmatter(VALID_SKILL_MD)
        self.assertEqual(result["status"], "PASS")
        self.assertIn("test-skill", result["detail"])

    def test_no_frontmatter(self):
        result = check_sk1_frontmatter(NO_FRONTMATTER)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("frontmatter", result["detail"].lower())

    def test_missing_name(self):
        result = check_sk1_frontmatter(MISSING_NAME)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("name", result["detail"])

    def test_missing_description(self):
        result = check_sk1_frontmatter(MISSING_DESCRIPTION)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("description", result["detail"])

    def test_long_description_truncated(self):
        long_desc = "A" * 200
        content = f"---\nname: long\ndescription: {long_desc}\n---\n"
        result = check_sk1_frontmatter(content)
        self.assertEqual(result["status"], "PASS")
        self.assertIn("...", result["detail"])


# =============================================================================
# SK-2: Inherited DNA
# =============================================================================

class TestSK2InheritedDNA(unittest.TestCase):
    def test_dna_present(self):
        result = check_sk2_inherited_dna(VALID_SKILL_MD)
        self.assertEqual(result["status"], "PASS")

    def test_dna_missing(self):
        result = check_sk2_inherited_dna(NO_DNA)
        self.assertEqual(result["status"], "FAIL")

    def test_dna_case_insensitive(self):
        content = "## inherited dna\nPresent."
        result = check_sk2_inherited_dna(content)
        self.assertEqual(result["status"], "PASS")


# =============================================================================
# SK-3: Protocol Steps
# =============================================================================

class TestSK3ProtocolSteps(unittest.TestCase):
    def test_protocol_with_steps(self):
        result = check_sk3_protocol_steps(VALID_SKILL_MD)
        self.assertEqual(result["status"], "PASS")
        self.assertIn("2", result["detail"])  # 2 steps

    def test_no_steps_anywhere(self):
        result = check_sk3_protocol_steps(NO_PROTOCOL)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("No numbered steps", result["detail"])

    def test_protocol_section_no_steps(self):
        result = check_sk3_protocol_steps(PROTOCOL_NO_STEPS)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("No numbered steps", result["detail"])

    def test_generation_protocol_variant(self):
        result = check_sk3_protocol_steps(GENERATION_PROTOCOL_VARIANT)
        self.assertEqual(result["status"], "PASS")
        self.assertIn("2", result["detail"])

    def test_minimal_valid(self):
        result = check_sk3_protocol_steps(MINIMAL_SKILL_MD)
        self.assertEqual(result["status"], "PASS")


# =============================================================================
# SK-4: Quality Section
# =============================================================================

class TestSK4QualitySection(unittest.TestCase):
    def test_quality_gates(self):
        result = check_sk4_quality_section(VALID_SKILL_MD)
        self.assertEqual(result["status"], "PASS")

    def test_quality_checklist(self):
        result = check_sk4_quality_section(MINIMAL_SKILL_MD)
        self.assertEqual(result["status"], "PASS")

    def test_p1_enforcement(self):
        result = check_sk4_quality_section(P1_ENFORCEMENT_VARIANT)
        self.assertEqual(result["status"], "PASS")

    def test_no_quality(self):
        result = check_sk4_quality_section(NO_QUALITY)
        self.assertEqual(result["status"], "FAIL")

    def test_quality_criteria_accepted(self):
        # "## Quality Criteria" is accepted as a valid quality section
        content = "## Quality Criteria\n- Item\n"
        result = check_sk4_quality_section(content)
        self.assertEqual(result["status"], "PASS")

    def test_unrelated_heading_not_matched(self):
        # An unrelated heading should NOT match
        content = "## Performance Metrics\n- Item\n"
        result = check_sk4_quality_section(content)
        self.assertEqual(result["status"], "FAIL")


# =============================================================================
# SK-5: References Directory
# =============================================================================

class TestSK5References(unittest.TestCase):
    def test_references_with_md_files(self):
        with tempfile.TemporaryDirectory() as td:
            refs = os.path.join(td, "references")
            os.makedirs(refs)
            with open(os.path.join(refs, "guide.md"), "w") as f:
                f.write("# Guide\n")
            result = check_sk5_references(td)
            self.assertEqual(result["status"], "PASS")
            self.assertIn("guide.md", result["detail"])

    def test_no_references_dir(self):
        with tempfile.TemporaryDirectory() as td:
            result = check_sk5_references(td)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("references/", result["detail"])

    def test_references_empty(self):
        with tempfile.TemporaryDirectory() as td:
            refs = os.path.join(td, "references")
            os.makedirs(refs)
            result = check_sk5_references(td)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("no .md files", result["detail"])

    def test_references_non_md_only(self):
        with tempfile.TemporaryDirectory() as td:
            refs = os.path.join(td, "references")
            os.makedirs(refs)
            with open(os.path.join(refs, "data.json"), "w") as f:
                f.write("{}")
            result = check_sk5_references(td)
            self.assertEqual(result["status"], "FAIL")

    def test_multiple_reference_files(self):
        with tempfile.TemporaryDirectory() as td:
            refs = os.path.join(td, "references")
            os.makedirs(refs)
            for name in ["guide.md", "checklist.md", "examples.md"]:
                with open(os.path.join(refs, name), "w") as f:
                    f.write(f"# {name}\n")
            result = check_sk5_references(td)
            self.assertEqual(result["status"], "PASS")
            self.assertIn("3", result["detail"])


# =============================================================================
# Integration: validate_skill
# =============================================================================

class TestValidateSkill(unittest.TestCase):
    def _create_skill(self, td: str, skill_md: str, ref_files: list[str] | None = None) -> str:
        """Helper: create a skill directory with SKILL.md and optional references."""
        with open(os.path.join(td, "SKILL.md"), "w") as f:
            f.write(skill_md)
        if ref_files is not None:
            refs = os.path.join(td, "references")
            os.makedirs(refs, exist_ok=True)
            for name in ref_files:
                with open(os.path.join(refs, name), "w") as f:
                    f.write(f"# {name}\n")
        return td

    def test_valid_skill_all_pass(self):
        with tempfile.TemporaryDirectory() as td:
            self._create_skill(td, VALID_SKILL_MD, ["guide.md"])
            result = validate_skill(td)
            self.assertTrue(result["passed"])
            self.assertEqual(len(result["checks"]), 5)
            for check in result["checks"]:
                self.assertEqual(check["status"], "PASS", f"{check['check']} failed")

    def test_missing_skill_md(self):
        with tempfile.TemporaryDirectory() as td:
            result = validate_skill(td)
            self.assertFalse(result["passed"])
            self.assertEqual(result["checks"][0]["check"], "SK-0")

    def test_partial_failures(self):
        with tempfile.TemporaryDirectory() as td:
            # NO_QUALITY has no quality section, and no references dir
            self._create_skill(td, NO_QUALITY)
            result = validate_skill(td)
            self.assertFalse(result["passed"])
            statuses = {c["check"]: c["status"] for c in result["checks"]}
            self.assertEqual(statuses["SK-1"], "PASS")
            self.assertEqual(statuses["SK-2"], "PASS")
            self.assertEqual(statuses["SK-3"], "PASS")
            self.assertEqual(statuses["SK-4"], "FAIL")
            self.assertEqual(statuses["SK-5"], "FAIL")

    def test_fork_without_agent_warning(self):
        with tempfile.TemporaryDirectory() as td:
            self._create_skill(td, FORK_CONTEXT_NO_AGENT, ["guide.md"])
            result = validate_skill(td)
            self.assertTrue(result["passed"])
            self.assertTrue(len(result["warnings"]) > 0)
            self.assertIn("SK-W1", result["warnings"][0])

    def test_fork_with_agent_no_warning(self):
        with tempfile.TemporaryDirectory() as td:
            self._create_skill(td, FORK_CONTEXT_WITH_AGENT, ["guide.md"])
            result = validate_skill(td)
            self.assertTrue(result["passed"])
            self.assertEqual(len(result["warnings"]), 0)


# =============================================================================
# CLI Integration
# =============================================================================

class TestCLI(unittest.TestCase):
    def test_cli_single_skill(self):
        with tempfile.TemporaryDirectory() as td:
            # Create valid skill
            with open(os.path.join(td, "SKILL.md"), "w") as f:
                f.write(VALID_SKILL_MD)
            refs = os.path.join(td, "references")
            os.makedirs(refs)
            with open(os.path.join(refs, "guide.md"), "w") as f:
                f.write("# Guide\n")

            script = os.path.join(os.path.dirname(__file__), "validate_skill_output.py")
            proc = subprocess.run(
                [sys.executable, script, "--skill-dir", td],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertEqual(data["total"], 1)
            self.assertTrue(data["all_passed"])

    def test_cli_skills_root(self):
        with tempfile.TemporaryDirectory() as root:
            # Create two skills
            for name in ["skill-a", "skill-b"]:
                skill_dir = os.path.join(root, name)
                os.makedirs(os.path.join(skill_dir, "references"))
                with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
                    f.write(VALID_SKILL_MD)
                with open(os.path.join(skill_dir, "references", "guide.md"), "w") as f:
                    f.write("# Guide\n")

            script = os.path.join(os.path.dirname(__file__), "validate_skill_output.py")
            proc = subprocess.run(
                [sys.executable, script, "--skills-root", root],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertEqual(data["total"], 2)
            self.assertTrue(data["all_passed"])

    def test_cli_exit_0_on_failure(self):
        """P1 compliance: always exit 0 even on validation failures."""
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "SKILL.md"), "w") as f:
                f.write(NO_FRONTMATTER)

            script = os.path.join(os.path.dirname(__file__), "validate_skill_output.py")
            proc = subprocess.run(
                [sys.executable, script, "--skill-dir", td],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertFalse(data["all_passed"])

    def test_validate_real_skills(self):
        """Validate existing project skills pass all checks."""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        skills_root = os.path.join(project_root, "skills")
        if not os.path.isdir(skills_root):
            self.skipTest("Skills root not found")

        script = os.path.join(os.path.dirname(__file__), "validate_skill_output.py")
        proc = subprocess.run(
            [sys.executable, script, "--skills-root", skills_root],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        # All existing skills should pass
        for result in data["results"]:
            for check in result["checks"]:
                self.assertEqual(
                    check["status"], "PASS",
                    f"{result['skill_dir']}: {check['check']} — {check['detail']}",
                )


if __name__ == "__main__":
    unittest.main()
