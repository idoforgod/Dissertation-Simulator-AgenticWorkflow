#!/usr/bin/env python3
"""
Skill Output P1 Validation — validate_skill_output.py

Deterministic structural check for newly created skill SKILL.md files.
Verifies that all required AgenticWorkflow DNA sections are present
and the skill package is complete.

Required structural rules (from SKILL.md template + skill-template-guide.md):
  - SK-1: YAML frontmatter with `name` and `description` fields
  - SK-2: `## Inherited DNA` section present
  - SK-3: `## Protocol` section with at least one numbered step
  - SK-4: Quality section present (`## Quality Gates` or `## Quality Checklist`
          or `## P1 Enforcement`)
  - SK-5: References directory exists with at least one .md file

Usage:
    # Validate a single skill:
    python3 validate_skill_output.py --skill-dir .claude/skills/my-skill/

    # Batch check all skills:
    python3 validate_skill_output.py --skills-root .claude/skills/

Output: JSON to stdout
    {
      "skill_dir": ".claude/skills/my-skill",
      "checks": [
        {"check": "SK-1", "status": "PASS", "detail": "name: my-skill, description present"},
        {"check": "SK-2", "status": "PASS", "detail": "Inherited DNA section found"},
        ...
      ],
      "passed": true,
      "warnings": []
    }

Exit codes:
    0 — always (non-blocking, P1 compliant)

Architecture:
    - Pure Python, stdlib only (no external dependencies)
    - Deterministic: same input → same output, every time
    - P1 Compliance: zero heuristic inference, zero LLM — pure regex + string checks
    - SOT Compliance: read-only
"""

import argparse
import json
import os
import re
import sys

# =============================================================================
# Regex Patterns
# =============================================================================

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_FIELD_RE = re.compile(r"^(\w[\w\-]*)\s*:\s*(.+)$", re.MULTILINE)
_INHERITED_DNA_RE = re.compile(r"^##\s+Inherited DNA", re.MULTILINE | re.IGNORECASE)
_PROTOCOL_SECTION_RE = re.compile(
    r"^##\s+(?:Generation\s+)?(?:Protocol|Workflow)", re.MULTILINE | re.IGNORECASE
)
_NUMBERED_STEP_RE = re.compile(
    r"^###\s+Step\s+\d+", re.MULTILINE | re.IGNORECASE
)
_QUALITY_SECTION_RE = re.compile(
    r"^##\s+(?:Quality\s+(?:Gates?|Checklist|Criteria)|P1\s+Enforcement|검토\s+체크리스트|pACS)",
    re.MULTILINE | re.IGNORECASE,
)


# =============================================================================
# Individual SK Checks
# =============================================================================

def check_sk1_frontmatter(content: str) -> dict:
    """SK-1: YAML frontmatter with `name` and `description` fields."""
    match = _FRONTMATTER_RE.search(content)
    if not match:
        return {
            "check": "SK-1",
            "status": "FAIL",
            "detail": "No YAML frontmatter block (--- ... ---) found",
        }

    fm_text = match.group(1)
    fields: dict[str, str] = {}
    for field_match in _FIELD_RE.finditer(fm_text):
        fields[field_match.group(1).lower()] = field_match.group(2).strip()

    missing: list[str] = []
    if "name" not in fields:
        missing.append("name")
    if "description" not in fields:
        missing.append("description")

    if missing:
        return {
            "check": "SK-1",
            "status": "FAIL",
            "detail": f"Frontmatter missing required fields: {', '.join(missing)}",
        }

    name_val = fields["name"]
    desc_val = fields["description"][:80] + ("..." if len(fields["description"]) > 80 else "")
    return {
        "check": "SK-1",
        "status": "PASS",
        "detail": f"name: {name_val}, description: {desc_val}",
    }


def check_sk2_inherited_dna(content: str) -> dict:
    """SK-2: `## Inherited DNA` section must be present."""
    if _INHERITED_DNA_RE.search(content):
        return {
            "check": "SK-2",
            "status": "PASS",
            "detail": "Inherited DNA section found",
        }
    return {
        "check": "SK-2",
        "status": "FAIL",
        "detail": "No '## Inherited DNA' section found",
    }


def check_sk3_protocol_steps(content: str) -> dict:
    """SK-3: Numbered steps (### Step N) present in the skill.

    Checks for the presence of numbered steps anywhere in the file.
    The parent section heading may vary (Protocol, Workflow, Case N, etc.)
    but the step format is universal.
    """
    steps = _NUMBERED_STEP_RE.findall(content)
    if not steps:
        return {
            "check": "SK-3",
            "status": "FAIL",
            "detail": "No numbered steps (### Step N) found in skill",
        }

    has_protocol_section = bool(_PROTOCOL_SECTION_RE.search(content))

    return {
        "check": "SK-3",
        "status": "PASS",
        "detail": f"{len(steps)} numbered step(s) found"
                  + ("" if has_protocol_section else " (no explicit Protocol section)"),
    }


def check_sk4_quality_section(content: str) -> dict:
    """SK-4: Quality Gates, Quality Checklist, or P1 Enforcement section present."""
    if _QUALITY_SECTION_RE.search(content):
        return {
            "check": "SK-4",
            "status": "PASS",
            "detail": "Quality/P1 section found",
        }
    return {
        "check": "SK-4",
        "status": "FAIL",
        "detail": "No quality section found (expected '## Quality Gates', "
                  "'## Quality Checklist', or '## P1 Enforcement')",
    }


def check_sk5_references(skill_dir: str) -> dict:
    """SK-5: References directory exists with at least one .md file."""
    refs_dir = os.path.join(skill_dir, "references")
    if not os.path.isdir(refs_dir):
        return {
            "check": "SK-5",
            "status": "FAIL",
            "detail": f"No references/ directory found in {skill_dir}",
        }

    md_files = [f for f in os.listdir(refs_dir) if f.endswith(".md")]
    if not md_files:
        return {
            "check": "SK-5",
            "status": "FAIL",
            "detail": "references/ directory exists but contains no .md files",
        }

    return {
        "check": "SK-5",
        "status": "PASS",
        "detail": f"{len(md_files)} reference file(s): {', '.join(sorted(md_files))}",
    }


# =============================================================================
# Main Validation
# =============================================================================

def validate_skill(skill_dir: str) -> dict:
    """Run all SK-1~SK-5 checks on a skill directory."""
    skill_md = os.path.join(skill_dir, "SKILL.md")
    warnings: list[str] = []

    if not os.path.isfile(skill_md):
        return {
            "skill_dir": skill_dir,
            "checks": [{
                "check": "SK-0",
                "status": "FAIL",
                "detail": f"SKILL.md not found in {skill_dir}",
            }],
            "passed": False,
            "warnings": [],
        }

    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        return {
            "skill_dir": skill_dir,
            "checks": [{
                "check": "SK-0",
                "status": "FAIL",
                "detail": f"Cannot read SKILL.md: {e}",
            }],
            "passed": False,
            "warnings": [],
        }

    checks = [
        check_sk1_frontmatter(content),
        check_sk2_inherited_dna(content),
        check_sk3_protocol_steps(content),
        check_sk4_quality_section(content),
        check_sk5_references(skill_dir),
    ]

    # Check for optional fork safety fields
    fm_match = _FRONTMATTER_RE.search(content)
    if fm_match:
        fm_text = fm_match.group(1)
        if "context: fork" in fm_text or "context:fork" in fm_text:
            has_agent = bool(re.search(r"^agent\s*:", fm_text, re.MULTILINE))
            if not has_agent:
                warnings.append(
                    "SK-W1: context: fork declared but no agent field specified "
                    "(defaults to general-purpose)"
                )

    passed = all(c["status"] == "PASS" for c in checks)

    return {
        "skill_dir": skill_dir,
        "checks": checks,
        "passed": passed,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate skill output structure (SK-1~SK-5)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--skill-dir",
        help="Path to a single skill directory containing SKILL.md",
    )
    group.add_argument(
        "--skills-root",
        help="Path to skills root directory (validates all subdirectories)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Output as JSON (default)",
    )
    args = parser.parse_args()

    results: list[dict] = []

    if args.skill_dir:
        results.append(validate_skill(args.skill_dir))
    else:
        root = args.skills_root
        if not os.path.isdir(root):
            print(json.dumps({
                "error": f"Skills root not found: {root}",
                "results": [],
            }), file=sys.stdout)
            sys.exit(0)

        for entry in sorted(os.listdir(root)):
            entry_path = os.path.join(root, entry)
            if os.path.isdir(entry_path) and os.path.isfile(
                os.path.join(entry_path, "SKILL.md")
            ):
                results.append(validate_skill(entry_path))

    all_passed = all(r["passed"] for r in results) if results else False
    output = {
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "all_passed": all_passed,
        "results": results,
    }

    print(json.dumps(output, indent=2, ensure_ascii=False), file=sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
