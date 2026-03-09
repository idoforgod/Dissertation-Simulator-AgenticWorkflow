#!/usr/bin/env python3
"""Thesis Workflow Checklist Manager — Core SOT management for doctoral research.

This script manages the thesis-specific SOT (session.json) which is INDEPENDENT
from the system-level SOT. It provides:
  - Atomic read/write to session.json
  - Schema validation for thesis SOT
  - Step progression with dependency enforcement
  - Checkpoint save/restore for context reset recovery
  - Todo-checklist.md generation and synchronization

IMPORTANT: This script does NOT import from _context_lib.py and does NOT
reference system SOT filenames to avoid triggering
_check_sot_write_safety() false positives (R6 design decision).

Usage:
  python3 checklist_manager.py --init --project-dir <dir> [--research-type <type>]
  python3 checklist_manager.py --advance --project-dir <dir> --step <N>
  python3 checklist_manager.py --status --project-dir <dir>
  python3 checklist_manager.py --save-checkpoint --project-dir <dir> --checkpoint <name>
  python3 checklist_manager.py --restore-checkpoint --project-dir <dir> --checkpoint <name>
  python3 checklist_manager.py --validate --project-dir <dir>
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Thesis SOT filename — intentionally different from system SOT filenames
# to avoid _check_sot_write_safety() conflicts (R6).
THESIS_SOT_FILENAME = "session.json"
THESIS_CHECKLIST_FILENAME = "todo-checklist.md"
THESIS_INSIGHTS_FILENAME = "research-synthesis.md"
CHECKPOINTS_DIR = "checkpoints"

# Valid thesis workflow statuses (aligned with system SOT valid_statuses
# but maintained independently — no import from _context_lib).
VALID_STATUSES = {"running", "completed", "error", "paused"}

# Valid research types
VALID_RESEARCH_TYPES = {"quantitative", "qualitative", "mixed", "undecided"}

# Valid input modes
VALID_INPUT_MODES = {"A", "B", "C", "D", "E", "F", "G"}

# Valid execution modes (from start.md Step 3.5 mode selection)
VALID_EXECUTION_MODES = {"interactive", "autopilot", "ulw", "autopilot+ulw"}

# Valid dialogue domains
VALID_DIALOGUE_DOMAINS = {"research", "development"}

# Valid dialogue outcomes
VALID_DIALOGUE_OUTCOMES = {"consensus", "escalated"}

# GroundedClaim types (from workflow.md GRA spec)
VALID_CLAIM_TYPES = {
    "FACTUAL", "EMPIRICAL", "THEORETICAL",
    "METHODOLOGICAL", "INTERPRETIVE", "SPECULATIVE",
}

# Agent claim prefixes — every claim-producing agent gets a UNIQUE prefix.
# Wave 1-5 agents (15 original, from workflow.md)
AGENT_CLAIM_PREFIXES = {
    "literature-searcher": "LS",
    "seminal-works-analyst": "SWA",
    "trend-analyst": "TRA",
    "methodology-scanner": "MS",
    "theoretical-framework-analyst": "TFA",
    "empirical-evidence-analyst": "EEA",
    "gap-identifier": "GI",
    "variable-relationship-analyst": "VRA",
    "critical-reviewer": "CR",
    "methodology-critic": "MC",
    "limitation-analyst": "LA",
    "future-direction-analyst": "FDA",
    "synthesis-agent": "SA",
    "conceptual-model-builder": "CMB",
    "plagiarism-checker": "PC",
    # Phase 0 agents
    "topic-explorer": "LS-T",
    "literature-analyzer": "LS-A",
    # Phase 2 — Quantitative
    "hypothesis-developer": "VRA-H",
    "research-model-developer": "CMB-M",
    "quantitative-designer": "QND",
    "sampling-designer": "SD",
    "statistical-planner": "SP",
    # Phase 2 — Qualitative
    "paradigm-consultant": "TFA-P",
    "participant-selector": "MS-PS",
    "qualitative-data-designer": "QDD",
    "qualitative-analysis-planner": "MS-QA",
    # Phase 2 — Mixed Methods
    "mixed-methods-designer": "MMD",
    "integration-strategist": "MS-IS",
    # Phase 2 — Support
    "ethics-reviewer": "ER",
    "instrument-developer": "ID",
    "data-collection-planner": "DCP",
    # Phase 3 — Writing
    "thesis-architect": "SA-TA",
    "thesis-writer": "TW",
    "thesis-reviewer": "TR",
    "abstract-writer": "AW",
    "citation-manager": "CM",
    "manuscript-formatter": "MF",
    "thesis-plagiarism-checker": "TPC",
    # Phase 4 — Publication
    "publication-strategist": "FDA-PB",
    "journal-matcher": "JM",
    "submission-preparer": "SUB",
    "cover-letter-writer": "CLW",
    # SRCS / Synthesis
    "unified-srcs-evaluator": "PC-SRCS",
    "research-synthesizer": "SA-RS",
    # Learning Mode
    "methodology-tutor": "MT",
    "practice-coach": "PCH",
    "assessment-agent": "AA",
}

# SRCS weights by claim type (from workflow.md)
SRCS_WEIGHTS = {
    "EMPIRICAL": {"CS": 0.35, "GS": 0.35, "US": 0.10, "VS": 0.20},
    "THEORETICAL": {"CS": 0.30, "GS": 0.30, "US": 0.15, "VS": 0.25},
    "FACTUAL": {"CS": 0.40, "GS": 0.25, "US": 0.05, "VS": 0.30},
    "METHODOLOGICAL": {"CS": 0.30, "GS": 0.35, "US": 0.10, "VS": 0.25},
    "INTERPRETIVE": {"CS": 0.25, "GS": 0.30, "US": 0.20, "VS": 0.25},
    "SPECULATIVE": {"CS": 0.20, "GS": 0.25, "US": 0.25, "VS": 0.30},
}

# SRCS threshold (from workflow.md gra_settings)
SRCS_THRESHOLD = 75

# Dependency groups for step validation.
# NOTE: These are dependency enforcement groups, NOT 1:1 checklist sections.
# Each group bundles steps that share the same prerequisite gate/hitl/phase.
# Example: "wave-2" = (55,70) includes Gate 1 validation steps (55-58) + Wave 2 work (59-70),
# because both require gate-1 to pass before entry.
# For user-facing section names, use get_checklist_section_for_step().
DEPENDENCY_GROUPS = {
    "phase-0": (1, 8),
    "phase-0-A": (9, 14),
    "phase-0-D": (15, 34),
    "hitl-1": (35, 38),
    "wave-1": (39, 54),
    "wave-2": (55, 70),
    "wave-3": (71, 86),
    "wave-4": (87, 94),
    "wave-5": (95, 98),
    "hitl-2": (99, 104),
    "phase-2": (105, 124),
    "hitl-3-4": (125, 132),
    "phase-3": (133, 156),
    "hitl-5-6-7": (157, 168),
    "phase-4": (169, 176),
    "hitl-8": (177, 180),
    "translation": (181, 210),
}

# Backward-compat alias (consumed by validate_step_sequence.py, tests)
PHASE_RANGES = DEPENDENCY_GROUPS

# Step dependencies — which phases/gates must be complete before starting
STEP_DEPENDENCIES = {
    "wave-2": {"gate": "gate-1", "phase": "wave-1"},
    "wave-3": {"gate": "gate-2", "phase": "wave-2"},
    "wave-4": {"gate": "gate-3", "phase": "wave-3"},
    "wave-5": {"gate": "srcs-full", "phase": "wave-4"},
    "phase-2": {"hitl": "hitl-2"},
    "phase-3": {"hitl": "hitl-3-4"},
    "phase-4": {"hitl": "hitl-5-6-7"},
    "translation": {"hitl": "hitl-8"},
}

# Translation step offset — each original step can have a -ko companion
TRANSLATION_STEP_OFFSET = 180  # steps 181-210 are translation steps


# ---------------------------------------------------------------------------
# Schema Validation
# ---------------------------------------------------------------------------

def validate_thesis_sot(data: dict) -> list[str]:
    """Validate thesis session.json schema. Returns list of errors (empty = valid).

    Validation rules (TS1-TS11):
      TS1: Root must be a dict
      TS2: Required keys present
      TS3: status must be in VALID_STATUSES
      TS4: current_step must be non-negative integer
      TS5: total_steps must be positive integer >= current_step
      TS6: research_type must be in VALID_RESEARCH_TYPES
      TS7: input_mode must be in VALID_INPUT_MODES
      TS8: outputs must be a dict with string values
      TS9: gates must be a dict with valid gate entries
      TS10: created_at and updated_at must be ISO format strings
      TS11: execution_mode must be in VALID_EXECUTION_MODES (if present)
    """
    errors = []

    # TS1
    if not isinstance(data, dict):
        return ["TS1: Root must be a dict"]

    # TS2
    required_keys = {
        "project_name", "status", "current_step", "total_steps",
        "research_type", "input_mode", "execution_mode", "outputs",
        "gates", "created_at", "updated_at",
    }
    missing = required_keys - set(data.keys())
    if missing:
        errors.append(f"TS2: Missing required keys: {sorted(missing)}")

    # TS3
    status = data.get("status")
    if status is not None and status not in VALID_STATUSES:
        errors.append(f"TS3: Invalid status '{status}', must be one of {sorted(VALID_STATUSES)}")

    # TS4
    current_step = data.get("current_step")
    if current_step is not None:
        if not isinstance(current_step, int) or current_step < 0:
            errors.append(f"TS4: current_step must be non-negative integer, got {current_step}")

    # TS5
    total_steps = data.get("total_steps")
    if total_steps is not None:
        if not isinstance(total_steps, int) or total_steps < 1:
            errors.append(f"TS5: total_steps must be positive integer, got {total_steps}")
        elif current_step is not None and isinstance(current_step, int) and current_step > total_steps:
            errors.append(f"TS5: current_step ({current_step}) > total_steps ({total_steps})")

    # TS6
    research_type = data.get("research_type")
    if research_type is not None and research_type not in VALID_RESEARCH_TYPES:
        errors.append(f"TS6: Invalid research_type '{research_type}'")

    # TS7
    input_mode = data.get("input_mode")
    if input_mode is not None and input_mode not in VALID_INPUT_MODES:
        errors.append(f"TS7: Invalid input_mode '{input_mode}'")

    # TS8
    outputs = data.get("outputs")
    if outputs is not None:
        if not isinstance(outputs, dict):
            errors.append("TS8: outputs must be a dict")
        else:
            for k, v in outputs.items():
                if not isinstance(v, str):
                    errors.append(f"TS8: outputs['{k}'] must be string, got {type(v).__name__}")

    # TS9
    gates = data.get("gates")
    if gates is not None:
        if not isinstance(gates, dict):
            errors.append("TS9: gates must be a dict")
        else:
            for gate_name, gate_data in gates.items():
                if isinstance(gate_data, dict):
                    gate_status = gate_data.get("status")
                    if gate_status not in {"pass", "fail", "pending", None}:
                        errors.append(f"TS9: gates['{gate_name}'].status invalid: '{gate_status}'")

    # TS11 — execution_mode (already handled above as TS11 in some versions)

    # TS12: Optional dialogue_state validation (S9-equivalent)
    dialogue_state = data.get("dialogue_state")
    if dialogue_state is not None:
        if not isinstance(dialogue_state, dict):
            errors.append("TS12: dialogue_state must be a dict")
        else:
            ds_step = dialogue_state.get("step")
            if ds_step is not None and (not isinstance(ds_step, int) or ds_step < 0):
                errors.append(f"TS12a: dialogue_state.step must be non-negative int, got {ds_step}")
            ds_rounds = dialogue_state.get("rounds_used")
            if ds_rounds is not None and (not isinstance(ds_rounds, int) or ds_rounds < 0):
                errors.append(f"TS12b: dialogue_state.rounds_used must be non-negative int, got {ds_rounds}")
            ds_max = dialogue_state.get("max_rounds")
            if ds_max is not None and (not isinstance(ds_max, int) or ds_max < 1):
                errors.append(f"TS12c: dialogue_state.max_rounds must be positive int, got {ds_max}")
            ds_status = dialogue_state.get("status")
            valid_statuses = {"in_progress", "consensus", "escalated", "not_started"}
            if ds_status is not None and ds_status not in valid_statuses:
                errors.append(f"TS12d: dialogue_state.status invalid: '{ds_status}', must be {valid_statuses}")
            ds_domain = dialogue_state.get("domain")
            if ds_domain is not None and ds_domain not in VALID_DIALOGUE_DOMAINS:
                errors.append(f"TS12e: dialogue_state.domain invalid: '{ds_domain}', must be {VALID_DIALOGUE_DOMAINS}")
            ds_outcome = dialogue_state.get("outcome")
            if ds_outcome is not None and ds_outcome not in VALID_DIALOGUE_OUTCOMES:
                errors.append(f"TS12f: dialogue_state.outcome invalid: '{ds_outcome}', must be {VALID_DIALOGUE_OUTCOMES}")

    # TS10
    for ts_field in ("created_at", "updated_at"):
        ts_val = data.get(ts_field)
        if ts_val is not None and isinstance(ts_val, str):
            try:
                datetime.fromisoformat(ts_val)
            except ValueError:
                errors.append(f"TS10: {ts_field} is not valid ISO format: '{ts_val}'")

    # TS11
    exec_mode = data.get("execution_mode")
    if exec_mode is not None and exec_mode not in VALID_EXECUTION_MODES:
        errors.append(f"TS11: Invalid execution_mode '{exec_mode}', must be one of {sorted(VALID_EXECUTION_MODES)}")

    # TS12: active_team must be None or a dict with required sub-fields
    active_team = data.get("active_team")
    if active_team is not None:
        if not isinstance(active_team, dict):
            errors.append("TS12: active_team must be None or a dict")
        else:
            for key in ("name", "status", "tasks_pending", "tasks_completed"):
                if key not in active_team:
                    errors.append(f"TS12: active_team missing required key '{key}'")
            # tasks_pending: accept list[str] (legacy) or list[dict] (new schema)
            tp = active_team.get("tasks_pending", [])
            if not isinstance(tp, list):
                errors.append("TS12: active_team.tasks_pending must be a list")
            else:
                for i, item in enumerate(tp):
                    if not isinstance(item, (str, dict)):
                        errors.append(
                            f"TS12: active_team.tasks_pending[{i}] must be str or dict"
                        )
            # tasks_completed: accept list[str] (legacy) or list[dict] (new schema)
            tc = active_team.get("tasks_completed", [])
            if not isinstance(tc, list):
                errors.append("TS12: active_team.tasks_completed must be a list")
            else:
                for i, item in enumerate(tc):
                    if not isinstance(item, (str, dict)):
                        errors.append(
                            f"TS12: active_team.tasks_completed[{i}] must be str or dict"
                        )

    # TS13: completed_teams must be a list of dicts (if present)
    completed_teams = data.get("completed_teams")
    if completed_teams is not None:
        if not isinstance(completed_teams, list):
            errors.append("TS13: completed_teams must be a list")
        else:
            for i, team in enumerate(completed_teams):
                if not isinstance(team, dict):
                    errors.append(f"TS13: completed_teams[{i}] must be a dict")

    # TS14: execution_substep must be None or a non-empty string (if present)
    exec_substep = data.get("execution_substep")
    if exec_substep is not None:
        if not isinstance(exec_substep, str) or not exec_substep.strip():
            errors.append(
                f"TS14: execution_substep must be None or a non-empty string, got {exec_substep!r}"
            )

    return errors


# ---------------------------------------------------------------------------
# Atomic File Operations
# ---------------------------------------------------------------------------

def atomic_write_json(filepath: Path, data: dict) -> None:
    """Write JSON atomically using temp file + rename pattern."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory (same filesystem for atomic rename)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(filepath.parent),
        prefix=f".{filepath.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(filepath))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_thesis_sot(project_dir: Path) -> dict:
    """Read and validate thesis SOT. Returns parsed dict."""
    sot_path = project_dir / THESIS_SOT_FILENAME
    if not sot_path.exists():
        raise FileNotFoundError(f"Thesis SOT not found: {sot_path}")

    with open(sot_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = validate_thesis_sot(data)
    if errors:
        raise ValueError(f"Thesis SOT validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    return data


def write_thesis_sot(project_dir: Path, data: dict) -> None:
    """Validate and atomically write thesis SOT.

    Authorization: Only Orchestrator (main session) may write.
    Teammates are blocked to prevent SOT corruption (Absolute Standard 2).
    """
    # Internal auth check — defense-in-depth beyond guard_sot_write.py
    is_teammate = os.environ.get("CLAUDE_AGENT_TEAMS_TEAMMATE", "") != ""
    if is_teammate:
        raise PermissionError(
            "SOT write denied: teammates cannot write thesis SOT directly. "
            "Report results to Team Lead via SendMessage."
        )

    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    errors = validate_thesis_sot(data)
    if errors:
        raise ValueError(f"Cannot write invalid SOT:\n" + "\n".join(f"  - {e}" for e in errors))

    atomic_write_json(project_dir / THESIS_SOT_FILENAME, data)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def create_initial_sot(
    project_name: str,
    research_type: str = "undecided",
    input_mode: str = "A",
    execution_mode: str = "interactive",
    total_steps: int = 210,
) -> dict:
    """Create initial thesis SOT structure."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "project_name": project_name,
        "status": "running",
        "current_step": 0,
        "total_steps": total_steps,
        "research_type": research_type,
        "input_mode": input_mode,
        "execution_mode": execution_mode,
        "research_question": "",
        "academic_field": "",
        "outputs": {},
        "gates": {
            "gate-1": {"status": "pending", "timestamp": None},
            "gate-2": {"status": "pending", "timestamp": None},
            "gate-3": {"status": "pending", "timestamp": None},
            "srcs-full": {"status": "pending", "timestamp": None},
            "final-quality": {"status": "pending", "timestamp": None},
        },
        "hitl_checkpoints": {
            "hitl-0": {"status": "pending", "timestamp": None},
            "hitl-1": {"status": "pending", "timestamp": None},
            "hitl-2": {"status": "pending", "timestamp": None},
            "hitl-3": {"status": "pending", "timestamp": None},
            "hitl-4": {"status": "pending", "timestamp": None},
            "hitl-5": {"status": "pending", "timestamp": None},
            "hitl-6": {"status": "pending", "timestamp": None},
            "hitl-7": {"status": "pending", "timestamp": None},
            "hitl-8": {"status": "pending", "timestamp": None},
        },
        "active_team": None,
        "completed_teams": [],
        "fallback_history": [],
        "context_snapshots": [],
        "execution_substep": None,  # Current sub-step within active step (e.g. "L1_verification")
        "created_at": now,
        "updated_at": now,
    }


def generate_checklist(total_steps: int = 210) -> str:
    """Generate todo-checklist.md content with all workflow steps."""
    lines = [
        "# Doctoral Research Workflow Checklist",
        "",
        f"Total steps: {total_steps}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    sections = [
        ("Phase 0: Initialization", [
            "Create thesis-output directory structure",
            "Initialize session.json (SOT)",
            "Generate todo-checklist.md",
            "Check user-resource/ directory",
            "Set research type selection",
            "Set academic field",
            "Configure GRA settings",
            "Initialize external memory files",
        ]),
        ("Phase 0-A: Topic Exploration (Mode A)", [
            "Analyze research topic context",
            "Identify major research streams",
            "Generate 5-7 candidate research questions",
            "Evaluate academic contribution potential",
            "Create topic-analysis.md",
            "Create research-questions-candidates.md",
        ]),
        ("Phase 0-D: Learning Mode (Mode D)", [
            "Select learning track",
            "Initialize learning session",
            "Concept learning module 1",
            "Example analysis 1",
            "Practice exercise 1",
            "Feedback session 1",
            "Concept learning module 2",
            "Example analysis 2",
            "Practice exercise 2",
            "Feedback session 2",
            "Concept learning module 3",
            "Example analysis 3",
            "Practice exercise 3",
            "Feedback session 3",
            "Review and assessment",
            "Generate learning portfolio",
            "Knowledge check quiz",
            "Learning progress report",
            "Recommendations for next track",
            "Save learning progress to SOT",
        ]),
        ("HITL-1: Research Question Confirmation", [
            "Display research question candidates",
            "User selects/modifies research question",
            "Configure literature review depth",
            "Set theoretical framework preference",
        ]),
        ("Wave 1: Foundation Literature Search", [
            "@literature-searcher: Develop search strategy",
            "@literature-searcher: Execute multi-database search",
            "@literature-searcher: Screen results (title/abstract)",
            "@literature-searcher: Apply inclusion/exclusion criteria",
            "@seminal-works-analyst: Identify seminal works",
            "@seminal-works-analyst: Analyze citation network",
            "@seminal-works-analyst: Map key authors and groups",
            "@seminal-works-analyst: Trace theoretical lineage",
            "@trend-analyst: Analyze temporal research trends",
            "@trend-analyst: Identify emerging topics",
            "@trend-analyst: Map research hotspots and frontiers",
            "@trend-analyst: Analyze publication trends by journal",
            "@methodology-scanner: Classify methodology types",
            "@methodology-scanner: Analyze sample sizes and designs",
            "@methodology-scanner: Review data collection methods",
            "@methodology-scanner: Summarize methodological strengths/weaknesses",
        ]),
        ("Gate 1: Foundation Validation", [
            "Cross-validate Wave 1 results",
            "Translate Wave 1 outputs to Korean",
            "Validate translations (T1-T9)",
            "Record gate-1 result in SOT",
        ]),
        ("Wave 2: Deep Analysis", [
            "@theoretical-framework-analyst: Identify relevant theories",
            "@theoretical-framework-analyst: Analyze inter-theory relationships",
            "@theoretical-framework-analyst: Propose theoretical lens",
            "@theoretical-framework-analyst: Draft theoretical framework",
            "@empirical-evidence-analyst: Compile empirical findings",
            "@empirical-evidence-analyst: Compare effect sizes",
            "@empirical-evidence-analyst: Identify consistency/inconsistency",
            "@empirical-evidence-analyst: Meta-analytic synthesis",
            "@gap-identifier: Identify theoretical gaps",
            "@gap-identifier: Identify methodological gaps",
            "@gap-identifier: Identify contextual gaps",
            "@gap-identifier: Evaluate gap significance",
            "@variable-relationship-analyst: Identify key variables",
            "@variable-relationship-analyst: Analyze relationship types",
            "@variable-relationship-analyst: Review operationalization",
            "@variable-relationship-analyst: Derive model components",
        ]),
        ("Gate 2: Deep Analysis Validation", [
            "Cross-validate Wave 2 results",
            "Translate Wave 2 outputs to Korean",
            "Validate translations (T1-T9)",
            "Record gate-2 result in SOT",
        ]),
        ("Wave 3: Critical Analysis", [
            "@critical-reviewer: Evaluate logical consistency",
            "@critical-reviewer: Check claim-evidence alignment",
            "@critical-reviewer: Explore alternative interpretations",
            "@critical-reviewer: Critique assumptions and premises",
            "@methodology-critic: Analyze internal validity threats",
            "@methodology-critic: Evaluate external validity",
            "@methodology-critic: Review measurement reliability/validity",
            "@methodology-critic: Assess statistical conclusion validity",
            "@limitation-analyst: Compile common limitations",
            "@limitation-analyst: Classify limitation types",
            "@limitation-analyst: Identify addressable limitations",
            "@limitation-analyst: Plan mitigation strategies",
            "@future-direction-analyst: Compile suggested future research",
            "@future-direction-analyst: Identify community interests",
            "@future-direction-analyst: Propose positioning strategy",
            "@future-direction-analyst: Predict contributions",
        ]),
        ("Gate 3: Critical Analysis Validation", [
            "Cross-validate Wave 3 results",
            "Translate Wave 3 outputs to Korean",
            "Validate translations (T1-T9)",
            "Record gate-3 result in SOT",
        ]),
        ("Wave 4: Synthesis and Integration", [
            "@synthesis-agent: Thematic/chronological synthesis",
            "@synthesis-agent: Integrate key findings",
            "@synthesis-agent: Write state-of-the-art summary",
            "@synthesis-agent: Draft literature review",
            "@conceptual-model-builder: Visualize variable relationships",
            "@conceptual-model-builder: Provide logical rationale for hypotheses",
            "@conceptual-model-builder: Connect framework to research model",
            "@conceptual-model-builder: Generate research model diagram",
        ]),
        ("SRCS Full Evaluation", [
            "Run unified SRCS evaluation on all claims",
            "Translate Wave 4 outputs to Korean",
            "Validate translations (T1-T9)",
            "Record SRCS results in SOT",
        ]),
        ("Wave 5: Quality Assurance", [
            "@plagiarism-checker: Run plagiarism analysis",
            "@plagiarism-checker: Generate similarity report",
            "Translate Wave 5 outputs to Korean",
            "Record final-quality-gate result in SOT",
        ]),
        ("HITL-2: Literature Review Approval", [
            "Display 15 analysis results summary",
            "Display SRCS quality report",
            "Display plagiarism check results",
            "Display flagged claims list",
            "User reviews and approves literature review",
            "Save HITL-2 checkpoint",
        ]),
        ("Phase 2: Research Design", [
            "Determine research design approach",
            "Configure design agents based on research type",
            "Design research methodology",
            "Define variables and operationalization",
            "Design sampling strategy",
            "Develop research instruments",
            "Plan statistical analysis",
            "Design data collection procedure",
            "Address ethical considerations",
            "Create research timeline",
            "Draft research design document",
            "Internal review of research design",
            "Translate research design to Korean",
            "Validate translations (T1-T9)",
            "Record Phase 2 completion in SOT",
            "HITL-3: Research type confirmation",
            "HITL-4: Research design approval",
            "Save HITL-3/4 checkpoint",
            "Finalize research design package",
            "Archive research design artifacts",
        ]),
        ("Phase 3: Thesis Writing", [
            "Create thesis outline",
            "HITL-5: Outline approval",
            "Write Chapter 1: Introduction",
            "Write Chapter 2: Literature Review",
            "Write Chapter 3: Research Methodology",
            "Write Chapter 4: Results/Findings",
            "Write Chapter 5: Discussion",
            "Write Chapter 6: Conclusion",
            "Write Abstract",
            "Compile References",
            "Create Appendices",
            "Internal review cycle 1",
            "Revision based on review 1",
            "Internal review cycle 2",
            "Revision based on review 2",
            "Plagiarism check on full thesis",
            "HITL-6: Draft review",
            "Final revision",
            "Format check (APA/MLA/Chicago)",
            "HITL-7: Final draft approval",
            "Translate thesis chapters to Korean",
            "Validate all translations (T1-T9)",
            "Generate bilingual thesis package",
            "Archive writing artifacts",
        ]),
        ("Phase 4: Publication Strategy", [
            "Identify target journals",
            "Analyze journal requirements",
            "Prepare submission package",
            "Write cover letter",
            "Format for target journal",
            "Final quality check",
            "HITL-8: Submission approval",
            "Generate final submission package",
        ]),
        ("Phase 5: Finalization", [
            "Consolidate all artifacts",
            "Final cross-reference validation",
            "Generate citation report",
            "Compile supplementary materials",
            "Create data availability statement",
            "Final plagiarism check on complete package",
            "Generate author contribution statement",
            "Archive complete project",
        ]),
        ("Phase 6: Translation (Steps 181-210)", [
            "@translator: Translate Chapter 1 Introduction",
            "@translator: Validate Chapter 1 translation (T1-T9)",
            "@translator: Translate Chapter 2 Literature Review",
            "@translator: Validate Chapter 2 translation (T1-T9)",
            "@translator: Translate Chapter 3 Research Methodology",
            "@translator: Validate Chapter 3 translation (T1-T9)",
            "@translator: Translate Chapter 4 Results/Findings",
            "@translator: Validate Chapter 4 translation (T1-T9)",
            "@translator: Translate Chapter 5 Discussion",
            "@translator: Validate Chapter 5 translation (T1-T9)",
            "@translator: Translate Chapter 6 Conclusion",
            "@translator: Validate Chapter 6 translation (T1-T9)",
            "@translator: Translate Abstract",
            "@translator: Validate Abstract translation (T1-T9)",
            "@translator: Translate Appendices",
            "@translator: Validate Appendices translation (T1-T9)",
            "@translator: Translate Cover Letter",
            "@translator: Validate Cover Letter translation (T1-T9)",
            "@translator: Cross-validate all Korean translations for consistency",
            "@translator: Update glossary.yaml with new terms",
            "@translator: Final bilingual format check",
            "@translator: Generate Korean thesis summary",
            "@translator: Validate Korean thesis summary (T1-T9)",
            "@translator: Generate bilingual keyword index",
            "@translator: Format bilingual reference list",
            "@translator: Final Korean output quality review",
            "@translator: Create bilingual submission package",
            "@translator: Validate complete Korean package",
            "@translator: Archive translation artifacts",
            "@translator: Generate translation completion report",
        ]),
    ]

    step_num = 1
    for section_title, steps in sections:
        lines.append(f"## {section_title}")
        lines.append("")
        for step_desc in steps:
            lines.append(f"- [ ] Step {step_num}: {step_desc}")
            step_num += 1
        lines.append("")

    return "\n".join(lines)


def init_project(project_dir: Path, project_name: str, **kwargs) -> dict:
    """Initialize a new thesis project directory and SOT."""
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    subdirs = [
        "wave-results/wave-1",
        "wave-results/wave-2",
        "wave-results/wave-3",
        "wave-results/wave-4",
        "wave-results/wave-5",
        "gate-reports",
        "phase-2",
        "thesis-drafts",
        "submission-package",
        "verification-logs",
        "pacs-logs",
        "review-logs",
        "dialogue-logs",
        "fallback-logs",
        CHECKPOINTS_DIR,
        "user-resource",
        "_temp",
    ]
    for subdir in subdirs:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Create SOT
    sot = create_initial_sot(project_name, **kwargs)
    write_thesis_sot(project_dir, sot)

    # Create checklist
    checklist_content = generate_checklist(sot["total_steps"])
    checklist_path = project_dir / THESIS_CHECKLIST_FILENAME
    checklist_path.write_text(checklist_content, encoding="utf-8")

    # Create empty insights file
    insights_path = project_dir / THESIS_INSIGHTS_FILENAME
    if not insights_path.exists():
        insights_path.write_text(
            "# Research Synthesis\n\nThis file accumulates key insights across all phases.\n",
            encoding="utf-8",
        )

    return sot


# ---------------------------------------------------------------------------
# Step Advancement
# ---------------------------------------------------------------------------

def get_dependency_group(step: int) -> str | None:
    """Return the dependency group name for a given step number.

    NOTE: Dependency groups are NOT 1:1 with checklist sections.
    For user-facing section names, use get_checklist_section_for_step().
    """
    for group_name, (start, end) in DEPENDENCY_GROUPS.items():
        if start <= step <= end:
            return group_name
    if TRANSLATION_STEP_OFFSET < step <= TRANSLATION_STEP_OFFSET + 30:
        return "translation"
    return None


# Backward-compat alias
get_phase_for_step = get_dependency_group


# Checklist section boundaries — matches generate_checklist() exactly
_CHECKLIST_SECTIONS = [
    ("Phase 0: Initialization", 1, 8),
    ("Phase 0-A: Topic Exploration", 9, 14),
    ("Phase 0-D: Learning Mode", 15, 34),
    ("HITL-1: Research Question", 35, 38),
    ("Wave 1: Foundation Literature", 39, 54),
    ("Gate 1: Foundation Validation", 55, 58),
    ("Wave 2: Deep Analysis", 59, 74),
    ("Gate 2: Deep Analysis Validation", 75, 78),
    ("Wave 3: Critical Analysis", 79, 94),
    ("Gate 3: Critical Analysis Validation", 95, 98),
    ("Wave 4: Synthesis", 99, 106),
    ("SRCS Full Evaluation", 107, 110),
    ("Wave 5: Quality Assurance", 111, 114),
    ("HITL-2: Literature Review Approval", 115, 120),
    ("Phase 2: Research Design", 121, 140),
    ("Phase 3: Thesis Writing", 141, 164),
    ("Phase 4: Publication Strategy", 165, 172),
    ("Phase 5: Finalization", 173, 180),
    ("Phase 6: Translation", 181, 210),
]


def get_checklist_section_for_step(step: int) -> str | None:
    """Return the user-facing checklist section name for a given step.

    Unlike get_dependency_group(), this maps 1:1 to generate_checklist() sections.
    Use this for CLI display and status reporting.
    """
    for name, start, end in _CHECKLIST_SECTIONS:
        if start <= step <= end:
            return name
    return None


def check_step_dependencies(sot: dict, target_step: int) -> list[str]:
    """Check if dependencies are met for advancing to target_step.
    Returns list of unmet dependencies (empty = all met).
    """
    target_phase = get_phase_for_step(target_step)
    if target_phase is None:
        return [f"Step {target_step} is out of range"]

    deps = STEP_DEPENDENCIES.get(target_phase)
    if deps is None:
        return []  # No dependencies for this phase

    unmet = []

    # Check gate dependency
    if "gate" in deps:
        gate_name = deps["gate"]
        gate = sot.get("gates", {}).get(gate_name, {})
        if gate.get("status") != "pass":
            unmet.append(f"Gate '{gate_name}' must pass before entering {target_phase}")

    # Check phase dependency
    if "phase" in deps:
        req_phase = deps["phase"]
        phase_range = DEPENDENCY_GROUPS.get(req_phase)
        if phase_range:
            _, end_step = phase_range
            if sot.get("current_step", 0) < end_step:
                unmet.append(f"Phase '{req_phase}' (step {end_step}) must complete before {target_phase}")

    # Check HITL dependency
    if "hitl" in deps:
        hitl_name = deps["hitl"]
        hitl = sot.get("hitl_checkpoints", {}).get(hitl_name, {})
        if hitl.get("status") != "completed":
            unmet.append(f"HITL checkpoint '{hitl_name}' must complete before {target_phase}")

    return unmet


def advance_step(project_dir: Path, target_step: int, force: bool = False) -> dict:
    """Advance the workflow to a specific step.

    Args:
        project_dir: Path to thesis project directory
        target_step: Step number to advance to
        force: Skip dependency checks (for recovery scenarios)

    Returns:
        Updated SOT dict

    Raises:
        ValueError: If step is invalid or dependencies unmet
    """
    sot = read_thesis_sot(project_dir)

    current = sot["current_step"]
    total = sot["total_steps"]

    if target_step < 0 or target_step > total:
        raise ValueError(f"Step {target_step} out of range [0, {total}]")

    if target_step <= current and not force:
        raise ValueError(
            f"Cannot go backward from step {current} to {target_step} without force=True"
        )

    if not force:
        unmet = check_step_dependencies(sot, target_step)
        if unmet:
            raise ValueError(
                f"Unmet dependencies for step {target_step}:\n"
                + "\n".join(f"  - {u}" for u in unmet)
            )

    # VE-Gate: Run validate_criteria_evidence before advancing (non-blocking warn)
    # Detects hallucinated evidence in verification logs before step is committed.
    # Exit 0 always (P1 compliant) — warn only if hallucinations_detected >= 1.
    _warn_if_hallucinations(project_dir, current)

    # H-5: pCCS compliance guard — verify pCCS decision was honored
    # Blocks advance if pCCS decision is 'rewrite_claims'/'rewrite_step' unless --force
    _warn_if_pccs_noncompliant(sot, current, force=force)

    # H-6: Review verdict guard — verify L2 review passed (if applicable)
    _warn_if_review_failed(project_dir, current)

    sot["current_step"] = target_step
    sot["execution_substep"] = None  # Clear sub-step on step advance
    write_thesis_sot(project_dir, sot)

    # Update checklist markdown
    _sync_checklist(project_dir, sot)

    return sot


def _warn_if_hallucinations(project_dir: Path, step: int) -> None:
    """Run validate_criteria_evidence.py for the step being advanced.

    Blocking with 15-second timeout: subprocess.run() is synchronous. The
    advance_step() call waits up to 15 seconds for this check to complete.
    Always returns None regardless of outcome (advance proceeds unconditionally).
    Prints WARNING to stderr if hallucinations_detected >= 1.
    Skips silently if the script is missing or verification-logs are absent.

    Intentional design: blocking ensures the hallucination check runs BEFORE
    the SOT is updated. The 15-second timeout prevents indefinite blocking.

    P1 Compliance: subprocess call — deterministic, no LLM.
    SOT Compliance: read-only (validate_criteria_evidence never writes SOT).
    """
    if step <= 0:
        return

    script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "validate_criteria_evidence.py",
    )
    if not os.path.exists(script):
        return

    verify_log = os.path.join(
        str(project_dir), "verification-logs", f"step-{step}-verify.md"
    )
    if not os.path.exists(verify_log):
        return  # No verification log for this step — skip silently

    try:
        result = subprocess.run(
            [sys.executable, script, "--step", str(step),
             "--project-dir", str(project_dir), "--auto-detect"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            n_hall = data.get("hallucinations_detected", 0)
            if n_hall >= 1:
                print(
                    f"[VE-Gate WARNING] Step {step}: {n_hall} hallucinated evidence "
                    f"claim(s) detected by validate_criteria_evidence. "
                    f"Review before accepting this step advance.",
                    file=sys.stderr,
                )
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass  # Non-blocking — advance proceeds regardless


def _warn_if_pccs_noncompliant(sot: dict, step: int, force: bool = False) -> None:
    """Check if pCCS decision was honored before advancing (H-5 guard).

    If the most recent pCCS result for this step was 'rewrite_claims' or
    'rewrite_step', verify that a subsequent pCCS re-evaluation occurred
    and returned 'proceed'. Otherwise, block the advance unless --force.

    Blocking when force=False: raises ValueError to prevent advancing with
    unresolved pCCS rewrite decisions. Use --force to override.
    P1 Compliance: reads SOT dict only — no subprocess, no LLM.
    """
    if step <= 0:
        return

    pccs = sot.get("pccs")
    if not pccs or not isinstance(pccs, dict):
        return

    history = pccs.get("history")
    if not history or not isinstance(history, dict):
        return

    step_key = f"step-{step}"
    entry = history.get(step_key)
    if not entry or not isinstance(entry, dict):
        return  # No pCCS record for this step — skip (Tier B step or not yet run)

    action = entry.get("action", "proceed")
    if action == "proceed" or action == "unknown":
        return  # pCCS said proceed — all good

    # pCCS said rewrite_claims or rewrite_step — check if re-evaluation happened
    # The history dict uses step_key as key, so if the step was re-evaluated,
    # the entry would be overwritten with the new result. If action is still
    # not 'proceed', the rewrite was not re-evaluated or still fails.
    msg = (
        f"Step {step}: pCCS decision was '{action}' but no subsequent "
        f"'proceed' re-evaluation found. Execute the required rewrite "
        f"and re-run pCCS before advancing."
    )
    if force:
        print(f"[pCCS WARNING] {msg} (--force override active)", file=sys.stderr)
    else:
        raise ValueError(f"[pCCS BLOCKED] {msg} Use --force to override.")


def _warn_if_review_failed(project_dir: Path, step: int) -> None:
    """Check if L2 review verdict was PASS before advancing (H-6 guard).

    Reads the review log for the current step and extracts the verdict.
    If verdict is FAIL, warns the Orchestrator.

    Non-blocking: always returns None. Prints WARNING to stderr if violation.
    P1 Compliance: file read + regex — deterministic, no LLM.
    """
    import re

    if step <= 0:
        return

    review_log = project_dir / "review-logs" / f"step-{step}-review.md"
    if not review_log.exists():
        return  # No review log — skip (non-L2 step or review not yet done)

    try:
        content = review_log.read_text(encoding="utf-8")
    except IOError:
        return

    # Extract verdict — case-insensitive search for "Verdict: PASS" or "Verdict: FAIL"
    # Anchored to common patterns from validate_review.py R4 format
    verdict_match = re.search(
        r'\*\*Verdict:\s*(PASS|FAIL|CONDITIONAL_PASS)\*\*',
        content,
        re.IGNORECASE,
    )
    if not verdict_match:
        # Try unbolded variant
        verdict_match = re.search(
            r'Verdict:\s*(PASS|FAIL|CONDITIONAL_PASS)',
            content,
            re.IGNORECASE,
        )

    if not verdict_match:
        return  # Cannot parse verdict — skip (don't block on unparseable format)

    verdict = verdict_match.group(1).upper()
    if verdict == "FAIL":
        print(
            f"[Review WARNING] Step {step}: L2 review verdict is FAIL. "
            f"The step should not advance until review issues are resolved. "
            f"See: {review_log}",
            file=sys.stderr,
        )


def set_execution_substep(project_dir: Path, substep: str | None) -> dict:
    """Record the current sub-step within the active step in SOT.

    Called by Orchestrator at each sub-step boundary so context recovery
    can resume from the exact sub-step rather than restarting the full step.

    Args:
        project_dir: Thesis project directory
        substep: Sub-step identifier (e.g. "L0_antiskip", "L1_verification",
                 "L1_5_pacs", "L2_dialogue_round_2", "translation", "advance")
                 or None to clear (after step advance completes).

    Valid substep identifiers:
        None          — cleared after step advance (no active substep)
        "L0_antiskip" — running L0 file-existence check
        "L1_verification" — running L1 Verification Gate
        "L1_5_pacs"   — running L1.5 pACS self-rating
        "L2_review"   — running single-pass @reviewer
        "L2_dialogue_round_{K}" — Adversarial Dialogue Round K in progress
        "translation" — running @translator
        "advance"     — about to call --advance

    SOT Compliance: Single writer (Orchestrator only). Atomically updated.
    P1 Compliance: Pure string assignment — deterministic.
    """
    sot = read_thesis_sot(project_dir)
    sot["execution_substep"] = substep
    write_thesis_sot(project_dir, sot)
    return sot


def record_output(project_dir: Path, step: int, output_path: str) -> dict:
    """Record a step's output file path in SOT."""
    sot = read_thesis_sot(project_dir)

    key = f"step-{step}"
    sot["outputs"][key] = output_path
    write_thesis_sot(project_dir, sot)
    return sot


def record_translation(project_dir: Path, step: int, ko_path: str) -> dict:
    """Record a translation output in SOT (step-N-ko convention)."""
    sot = read_thesis_sot(project_dir)

    key = f"step-{step}-ko"
    sot["outputs"][key] = ko_path
    write_thesis_sot(project_dir, sot)
    return sot


def record_gate_result(
    project_dir: Path,
    gate_name: str,
    status: str,
    report_path: str | None = None,
) -> dict:
    """Record a gate pass/fail result in SOT."""
    if status not in ("pass", "fail"):
        raise ValueError(f"Gate status must be 'pass' or 'fail', got '{status}'")

    sot = read_thesis_sot(project_dir)

    if gate_name not in sot.get("gates", {}):
        raise ValueError(f"Unknown gate: '{gate_name}'")

    now = datetime.now(timezone.utc).isoformat()
    sot["gates"][gate_name] = {
        "status": status,
        "timestamp": now,
        "report": report_path,
    }
    write_thesis_sot(project_dir, sot)
    return sot


def record_hitl(project_dir: Path, hitl_name: str, status: str = "completed") -> dict:
    """Record a HITL checkpoint completion in SOT."""
    sot = read_thesis_sot(project_dir)

    if hitl_name not in sot.get("hitl_checkpoints", {}):
        raise ValueError(f"Unknown HITL checkpoint: '{hitl_name}'")

    now = datetime.now(timezone.utc).isoformat()
    sot["hitl_checkpoints"][hitl_name] = {
        "status": status,
        "timestamp": now,
        "requires_user_approval": True,
    }
    write_thesis_sot(project_dir, sot)
    return sot


def is_hitl_blocking(project_dir: Path, hitl_name: str) -> bool:
    """Check if a HITL checkpoint is blocking (exists but not completed).

    Returns True if the HITL exists and its status is not 'completed',
    meaning it requires user approval before the workflow can proceed.
    """
    sot = read_thesis_sot(project_dir)
    hitl = sot.get("hitl_checkpoints", {}).get(hitl_name)
    if hitl is None:
        return False
    return hitl.get("status") != "completed"


# ---------------------------------------------------------------------------
# Checkpoint Management
# ---------------------------------------------------------------------------

def save_checkpoint(project_dir: Path, checkpoint_name: str) -> str:
    """Save a checkpoint snapshot of the current SOT and key files.

    Returns the checkpoint directory path.
    """
    project_dir = Path(project_dir)
    cp_dir = project_dir / CHECKPOINTS_DIR / checkpoint_name
    cp_dir.mkdir(parents=True, exist_ok=True)

    # Copy SOT
    sot_src = project_dir / THESIS_SOT_FILENAME
    if sot_src.exists():
        shutil.copy2(str(sot_src), str(cp_dir / THESIS_SOT_FILENAME))

    # Copy checklist
    cl_src = project_dir / THESIS_CHECKLIST_FILENAME
    if cl_src.exists():
        shutil.copy2(str(cl_src), str(cp_dir / THESIS_CHECKLIST_FILENAME))

    # Copy insights
    ins_src = project_dir / THESIS_INSIGHTS_FILENAME
    if ins_src.exists():
        shutil.copy2(str(ins_src), str(cp_dir / THESIS_INSIGHTS_FILENAME))

    # Record in SOT
    sot = read_thesis_sot(project_dir)
    now = datetime.now(timezone.utc).isoformat()
    sot.setdefault("context_snapshots", []).append({
        "name": checkpoint_name,
        "timestamp": now,
        "step": sot["current_step"],
    })
    write_thesis_sot(project_dir, sot)

    # Dual-save: write thesis state summary to system context-snapshots
    try:
        # Resolve the AgenticWorkflow root (may be parent of thesis-output)
        aw_root = project_dir
        while aw_root != aw_root.parent:
            if (aw_root / ".claude" / "context-snapshots").is_dir():
                break
            aw_root = aw_root.parent
        sys_snapshot_dir = aw_root / ".claude" / "context-snapshots"
        if sys_snapshot_dir.is_dir():
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            summary_path = sys_snapshot_dir / f"{ts}_thesis-checkpoint-{checkpoint_name}.md"
            summary = (
                f"# Thesis Checkpoint: {checkpoint_name}\n\n"
                f"- Project: {sot.get('project_name', 'unknown')}\n"
                f"- Step: {sot['current_step']}/{sot.get('total_steps', '?')}\n"
                f"- Status: {sot.get('status', 'unknown')}\n"
                f"- Research Type: {sot.get('research_type', 'undecided')}\n"
                f"- Timestamp: {now}\n"
                f"- Checkpoint Dir: {cp_dir}\n"
            )
            summary_path.write_text(summary, encoding="utf-8")
    except Exception:
        pass  # Non-blocking — thesis checkpoint is primary

    return str(cp_dir)


def restore_checkpoint(project_dir: Path, checkpoint_name: str) -> dict:
    """Restore SOT and files from a checkpoint.

    Returns the restored SOT dict.
    """
    project_dir = Path(project_dir)
    cp_dir = project_dir / CHECKPOINTS_DIR / checkpoint_name

    if not cp_dir.exists():
        raise FileNotFoundError(f"Checkpoint not found: {cp_dir}")

    # Restore SOT
    cp_sot = cp_dir / THESIS_SOT_FILENAME
    if cp_sot.exists():
        shutil.copy2(str(cp_sot), str(project_dir / THESIS_SOT_FILENAME))

    # Restore checklist
    cp_cl = cp_dir / THESIS_CHECKLIST_FILENAME
    if cp_cl.exists():
        shutil.copy2(str(cp_cl), str(project_dir / THESIS_CHECKLIST_FILENAME))

    # Restore insights
    cp_ins = cp_dir / THESIS_INSIGHTS_FILENAME
    if cp_ins.exists():
        shutil.copy2(str(cp_ins), str(project_dir / THESIS_INSIGHTS_FILENAME))

    return read_thesis_sot(project_dir)


# ---------------------------------------------------------------------------
# Team Management
# ---------------------------------------------------------------------------

def _find_task_in_list(task_list: list, task_id: str) -> int | None:
    """Find a task by task_id in a list that may contain str or dict items.

    Returns the index if found, None otherwise.
    """
    for i, item in enumerate(task_list):
        if isinstance(item, str) and item == task_id:
            return i
        if isinstance(item, dict) and item.get("task_id") == task_id:
            return i
    return None


def update_active_team(
    project_dir: Path,
    name: str | None = None,
    status: str | None = None,
    tasks_pending: list | None = None,
    tasks_completed: list | None = None,
    append_task: str | None = None,
    complete_task: str | None = None,
    task_agent: str | None = None,
    task_output_path: str | None = None,
) -> dict:
    """Update active_team fields in SOT.

    Args:
        name: Team name (sets active_team.name)
        status: Team status ("active", "completed", "failed")
        tasks_pending: Replace tasks_pending list
        tasks_completed: Replace tasks_completed list
        append_task: Append a single task_id to tasks_pending (stored as dict)
        complete_task: Move a task_id from tasks_pending to tasks_completed
        task_agent: Agent name for append_task (optional)
        task_output_path: Output path for append_task (optional)

    Returns:
        Updated active_team dict.
    """
    project_dir = Path(project_dir)
    sot = read_thesis_sot(project_dir)

    team = sot.get("active_team")
    if team is None and name is not None:
        # Initialize new active_team
        team = {
            "name": name,
            "status": "active",
            "tasks_pending": [],
            "tasks_completed": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    elif team is None:
        raise ValueError("No active team and no name provided to create one")

    if name is not None:
        team["name"] = name
    if status is not None:
        team["status"] = status
    if tasks_pending is not None:
        team["tasks_pending"] = tasks_pending
    if tasks_completed is not None:
        team["tasks_completed"] = tasks_completed
    if append_task is not None:
        task_dict = {
            "task_id": append_task,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent": task_agent,
            "output_path": task_output_path,
            "status": "pending",
        }
        team.setdefault("tasks_pending", []).append(task_dict)
    if complete_task is not None:
        pending = team.get("tasks_pending", [])
        idx = _find_task_in_list(pending, complete_task)
        now = datetime.now(timezone.utc).isoformat()
        if idx is not None:
            removed = pending.pop(idx)
            # Upgrade legacy str format to dict on completion
            if isinstance(removed, str):
                removed = {
                    "task_id": removed,
                    "created_at": None,
                    "agent": None,
                    "output_path": None,
                    "status": "completed",
                    "completed_at": now,
                }
            else:
                removed["status"] = "completed"
                removed["completed_at"] = now
            team.setdefault("tasks_completed", []).append(removed)
        else:
            # Task not found in pending — still record completion
            team.setdefault("tasks_completed", []).append({
                "task_id": complete_task,
                "created_at": None,
                "agent": None,
                "output_path": None,
                "status": "completed",
                "completed_at": now,
            })

    sot["active_team"] = team
    sot["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_thesis_sot(project_dir, sot)
    return team


def complete_team(project_dir: Path) -> dict | None:
    """Move active_team to completed_teams and set active_team to None.

    Returns:
        The completed team dict, or None if no active team.
    """
    project_dir = Path(project_dir)
    sot = read_thesis_sot(project_dir)

    team = sot.get("active_team")
    if team is None:
        return None

    team["status"] = "completed"
    team["completed_at"] = datetime.now(timezone.utc).isoformat()

    completed = sot.get("completed_teams", [])
    completed.append(team)
    sot["completed_teams"] = completed
    sot["active_team"] = None
    sot["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_thesis_sot(project_dir, sot)
    return team


# ---------------------------------------------------------------------------
# Status and Sync
# ---------------------------------------------------------------------------

def _sync_checklist(project_dir: Path, sot: dict) -> None:
    """Sync checklist markdown with SOT current_step."""
    cl_path = project_dir / THESIS_CHECKLIST_FILENAME
    if not cl_path.exists():
        return

    content = cl_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    current_step = sot.get("current_step", 0)

    updated_lines = []
    for line in lines:
        # Match "- [ ] Step N:" or "- [x] Step N:" patterns
        if line.strip().startswith("- [") and "Step " in line:
            try:
                # Extract step number
                step_part = line.split("Step ")[1]
                step_num = int(step_part.split(":")[0])
                if step_num <= current_step:
                    line = line.replace("- [ ]", "- [x]", 1)
                else:
                    line = line.replace("- [x]", "- [ ]", 1)
            except (IndexError, ValueError):
                pass
        updated_lines.append(line)

    cl_path.write_text("\n".join(updated_lines), encoding="utf-8")


def get_status(project_dir: Path) -> dict:
    """Get comprehensive workflow status."""
    sot = read_thesis_sot(project_dir)

    current = sot["current_step"]
    total = sot["total_steps"]
    phase = get_checklist_section_for_step(current) if current > 0 else "not-started"

    # Count completed gates
    gates = sot.get("gates", {})
    gates_passed = sum(1 for g in gates.values() if isinstance(g, dict) and g.get("status") == "pass")
    gates_total = len(gates)

    # Count completed HITL checkpoints
    hitls = sot.get("hitl_checkpoints", {})
    hitls_completed = sum(1 for h in hitls.values() if isinstance(h, dict) and h.get("status") == "completed")
    hitls_total = len(hitls)

    # Count outputs
    outputs = sot.get("outputs", {})
    en_outputs = sum(1 for k in outputs if not k.endswith("-ko"))
    ko_outputs = sum(1 for k in outputs if k.endswith("-ko"))

    return {
        "project_name": sot.get("project_name", "unknown"),
        "status": sot.get("status", "unknown"),
        "current_step": current,
        "total_steps": total,
        "progress_pct": round(current / total * 100, 1) if total > 0 else 0,
        "current_phase": phase,
        "research_type": sot.get("research_type", "undecided"),
        "input_mode": sot.get("input_mode", "A"),
        "execution_mode": sot.get("execution_mode", "interactive"),
        "gates_passed": f"{gates_passed}/{gates_total}",
        "hitls_completed": f"{hitls_completed}/{hitls_total}",
        "outputs_en": en_outputs,
        "outputs_ko": ko_outputs,
        "active_team": sot.get("active_team"),
        "fallback_count": len(sot.get("fallback_history", [])),
        "checkpoint_count": len(sot.get("context_snapshots", [])),
    }


def get_translation_progress(project_dir: Path) -> dict:
    """Get translation coverage: which steps have EN but no KO pair.

    Returns: dict with coverage percentage, translated/total counts,
    and list of missing step numbers.
    """
    sot = read_thesis_sot(project_dir)
    outputs = sot.get("outputs", {})

    # Find all English output steps
    en_steps = set()
    ko_steps = set()
    for key in outputs:
        if key.endswith("-ko"):
            # Extract step number from "step-N-ko"
            parts = key.replace("-ko", "").split("-")
            if len(parts) >= 2 and parts[-1].isdigit():
                ko_steps.add(int(parts[-1]))
        elif key.startswith("step-") and not key.endswith("-ko"):
            parts = key.split("-")
            if len(parts) >= 2 and parts[-1].isdigit():
                en_steps.add(int(parts[-1]))

    missing = sorted(en_steps - ko_steps)
    translated = len(en_steps & ko_steps)
    total_en = len(en_steps)
    coverage_pct = round(translated / total_en * 100, 1) if total_en > 0 else 0.0

    return {
        "translated": translated,
        "total_en": total_en,
        "coverage_pct": coverage_pct,
        "missing_steps": missing,
    }


# ---------------------------------------------------------------------------
# Dialogue State Management
# ---------------------------------------------------------------------------

def start_dialogue(project_dir, step: int, domain: str, max_rounds: int = 10) -> dict:
    """Initialize dialogue_state in SOT when Adversarial Dialogue loop begins.

    P1 Compliance: Atomic write via write_thesis_sot.
    SOT Compliance: Single-writer pattern enforced (Orchestrator only).

    Args:
        project_dir: Thesis project directory
        step: Workflow step number
        domain: "research" or "development"
        max_rounds: Maximum dialogue rounds (default: 10)

    Returns:
        Updated SOT dict
    """
    if domain not in VALID_DIALOGUE_DOMAINS:
        raise ValueError(f"Invalid domain '{domain}', must be one of {VALID_DIALOGUE_DOMAINS}")

    project_dir = Path(project_dir)
    # Create dialogue-logs/ directory if needed
    (project_dir / "dialogue-logs").mkdir(parents=True, exist_ok=True)

    sot = read_thesis_sot(project_dir)
    sot["dialogue_state"] = {
        "step": step,
        "domain": domain,
        "status": "in_progress",
        "rounds_used": 0,
        "max_rounds": max_rounds,
        "round_history": [],
    }
    sot["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_thesis_sot(project_dir, sot)
    return sot


def advance_dialogue_round(project_dir, step: int, round_num: int, verdict: str) -> dict:
    """Record completion of one dialogue round in SOT.

    P1 Compliance: Atomic write via write_thesis_sot.

    Args:
        project_dir: Thesis project directory
        step: Workflow step number
        round_num: Round number (1-based)
        verdict: "PASS" or "FAIL"

    Returns:
        Updated SOT dict
    """
    verdict = verdict.upper()
    if verdict not in ("PASS", "FAIL"):
        raise ValueError(f"Invalid verdict '{verdict}', must be PASS or FAIL")

    project_dir = Path(project_dir)
    sot = read_thesis_sot(project_dir)

    ds = sot.get("dialogue_state")
    if ds is None:
        raise ValueError("No active dialogue_state found. Call --dialogue-start first.")
    if ds.get("step") != step:
        raise ValueError(f"Active dialogue is for step {ds.get('step')}, not step {step}")

    ds["rounds_used"] = round_num
    ds["round_history"].append({
        "round": round_num,
        "verdict": verdict,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    sot["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_thesis_sot(project_dir, sot)
    return sot


def end_dialogue(project_dir, step: int, outcome: str) -> dict:
    """Finalize dialogue_state in SOT after loop completes.

    P1 Compliance: Atomic write via write_thesis_sot.

    Args:
        project_dir: Thesis project directory
        step: Workflow step number
        outcome: "consensus" or "escalated"

    Returns:
        Updated SOT dict
    """
    if outcome not in VALID_DIALOGUE_OUTCOMES:
        raise ValueError(f"Invalid outcome '{outcome}', must be one of {VALID_DIALOGUE_OUTCOMES}")

    project_dir = Path(project_dir)
    sot = read_thesis_sot(project_dir)

    ds = sot.get("dialogue_state")
    if ds is None:
        raise ValueError("No active dialogue_state found. Call --dialogue-start first.")
    if ds.get("step") != step:
        raise ValueError(f"Active dialogue is for step {ds.get('step')}, not step {step}")

    ds["status"] = outcome  # "consensus" or "escalated"
    ds["outcome"] = outcome
    ds["completed_at"] = datetime.now(timezone.utc).isoformat()
    sot["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_thesis_sot(project_dir, sot)
    return sot


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_init(args):
    """Handle --init command."""
    project_dir = Path(args.project_dir)
    project_name = args.project_name or project_dir.name

    kwargs = {}
    if args.research_type:
        kwargs["research_type"] = args.research_type
    if args.input_mode:
        kwargs["input_mode"] = args.input_mode
    if args.execution_mode:
        kwargs["execution_mode"] = args.execution_mode

    sot = init_project(project_dir, project_name, **kwargs)
    print(f"Thesis project initialized: {project_dir}")
    print(f"  SOT: {project_dir / THESIS_SOT_FILENAME}")
    print(f"  Checklist: {project_dir / THESIS_CHECKLIST_FILENAME}")
    print(f"  Total steps: {sot['total_steps']}")
    return 0


def _cli_advance(args):
    """Handle --advance command."""
    project_dir = Path(args.project_dir)
    target_step = args.step
    force = getattr(args, "force", False)

    try:
        sot = advance_step(project_dir, target_step, force=force)
        section = get_checklist_section_for_step(target_step)
        print(f"Advanced to step {target_step} (section: {section})")
        print(f"  Progress: {target_step}/{sot['total_steps']}")
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def _cli_status(args):
    """Handle --status command."""
    project_dir = Path(args.project_dir)

    try:
        status = get_status(project_dir)
    except FileNotFoundError:
        print(f"No thesis project found at: {project_dir}", file=sys.stderr)
        return 1

    print(f"Project: {status['project_name']}")
    print(f"Status: {status['status']}")
    print(f"Progress: {status['current_step']}/{status['total_steps']} ({status['progress_pct']}%)")
    print(f"Phase: {status['current_phase']}")
    print(f"Research type: {status['research_type']}")
    print(f"Input mode: {status['input_mode']}")
    print(f"Execution mode: {status['execution_mode']}")
    print(f"Gates: {status['gates_passed']}")
    print(f"HITL checkpoints: {status['hitls_completed']}")
    print(f"Outputs (EN): {status['outputs_en']}")
    print(f"Outputs (KO): {status['outputs_ko']}")

    # Inline translation coverage
    try:
        progress = get_translation_progress(project_dir)
        if progress["total_en"] > 0:
            print(f"Translation coverage: {progress['coverage_pct']}% ({progress['translated']}/{progress['total_en']})")
            if progress["missing_steps"]:
                print(f"  Missing: steps {', '.join(str(s) for s in progress['missing_steps'][:10])}")
    except Exception:
        pass

    if status['active_team']:
        print(f"Active team: {status['active_team']}")
    if status['fallback_count'] > 0:
        print(f"Fallbacks: {status['fallback_count']}")
    return 0


def _cli_checkpoint(args):
    """Handle --save-checkpoint or --restore-checkpoint."""
    project_dir = Path(args.project_dir)
    checkpoint = args.checkpoint

    try:
        if args.save_checkpoint:
            cp_path = save_checkpoint(project_dir, checkpoint)
            print(f"Checkpoint saved: {cp_path}")
        elif args.restore_checkpoint:
            sot = restore_checkpoint(project_dir, checkpoint)
            print(f"Checkpoint restored: {checkpoint}")
            print(f"  Current step: {sot['current_step']}")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def _cli_validate(args):
    """Handle --validate command."""
    project_dir = Path(args.project_dir)

    try:
        sot = read_thesis_sot(project_dir)
        print(f"Thesis SOT validation: PASS")
        print(f"  Project: {sot.get('project_name', 'unknown')}")
        print(f"  Step: {sot.get('current_step', 0)}/{sot.get('total_steps', 0)}")
    except FileNotFoundError:
        print(f"Thesis SOT not found at: {project_dir}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Thesis SOT validation: FAIL\n{e}", file=sys.stderr)
        return 1
    return 0


def _cli_record_hitl(args):
    """Handle --record-hitl command."""
    project_dir = Path(args.project_dir)
    hitl_name = args.record_hitl
    hitl_status = args.hitl_status

    try:
        sot = record_hitl(project_dir, hitl_name, hitl_status)
        print(f"HITL recorded: {hitl_name} = {hitl_status}")
        print(f"  Step: {sot.get('current_step', 0)}/{sot.get('total_steps', 0)}")
    except FileNotFoundError:
        print(f"Thesis SOT not found at: {project_dir}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"HITL record failed: {e}", file=sys.stderr)
        return 1
    return 0


def _cli_update_team(args):
    """Handle --update-team command."""
    project_dir = Path(args.project_dir)
    kwargs = {}
    if args.team_name:
        kwargs["name"] = args.team_name
    if args.team_status:
        kwargs["status"] = args.team_status
    if args.append_task:
        kwargs["append_task"] = args.append_task
        if getattr(args, "agent", None):
            kwargs["task_agent"] = args.agent
        if getattr(args, "task_output_path", None):
            kwargs["task_output_path"] = args.task_output_path
    if args.complete_task:
        kwargs["complete_task"] = args.complete_task

    try:
        team = update_active_team(project_dir, **kwargs)
        print(f"Active team updated: {team.get('name', 'unknown')}")
        print(f"  Status: {team.get('status')}")
        print(f"  Pending: {len(team.get('tasks_pending', []))}")
        print(f"  Completed: {len(team.get('tasks_completed', []))}")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def _cli_complete_team(args):
    """Handle --complete-team command."""
    project_dir = Path(args.project_dir)

    try:
        team = complete_team(project_dir)
        if team:
            print(f"Team completed: {team.get('name', 'unknown')}")
        else:
            print("No active team to complete.")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description="Thesis Workflow Checklist Manager")
    parser.add_argument("--project-dir", required=True, help="Path to thesis project directory")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init", action="store_true", help="Initialize new thesis project")
    group.add_argument("--advance", action="store_true", help="Advance to a specific step")
    group.add_argument("--status", action="store_true", help="Show workflow status")
    group.add_argument("--save-checkpoint", action="store_true", help="Save checkpoint")
    group.add_argument("--restore-checkpoint", action="store_true", help="Restore checkpoint")
    group.add_argument("--validate", action="store_true", help="Validate thesis SOT")
    group.add_argument("--record-hitl", help="Record HITL checkpoint completion (e.g., hitl-1)")
    group.add_argument("--is-hitl-blocking", action="store_true", help="Check if a HITL checkpoint is blocking")
    group.add_argument("--update-team", action="store_true", help="Update active team fields")
    group.add_argument("--complete-team", action="store_true", help="Move active team to completed_teams")
    group.add_argument("--record-gate", action="store_true", help="Record gate result in SOT")
    group.add_argument("--record-output", action="store_true", help="Record step output path in SOT")
    group.add_argument("--record-translation", action="store_true", help="Record translation output in SOT")
    group.add_argument("--translation-progress", action="store_true", help="Show translation coverage")
    group.add_argument("--dialogue-start", action="store_true", help="Start Adversarial Dialogue loop for a step")
    group.add_argument("--dialogue-round", action="store_true", help="Record completion of one dialogue round")
    group.add_argument("--dialogue-end", action="store_true", help="Finalize dialogue loop with outcome")
    group.add_argument("--set-substep", metavar="SUBSTEP", help="Record current execution sub-step within active step (e.g. L1_verification, L2_dialogue_round_2); use 'clear' to reset")
    group.add_argument("--update-pccs-cal", action="store_true", help="Update pCCS calibration data in SOT")

    parser.add_argument("--project-name", help="Project name (default: directory name)")
    parser.add_argument("--research-type", choices=sorted(VALID_RESEARCH_TYPES))
    parser.add_argument("--input-mode", choices=sorted(VALID_INPUT_MODES))
    parser.add_argument("--execution-mode", choices=sorted(VALID_EXECUTION_MODES))
    parser.add_argument("--step", type=int, help="Target step number (for --advance)")
    parser.add_argument("--checkpoint", help="Checkpoint name")
    parser.add_argument("--hitl-status", default="completed", help="HITL status (default: completed)")
    parser.add_argument("--hitl-name", help="HITL name (for --is-hitl-blocking)")
    parser.add_argument("--force", action="store_true", help="Force operation (skip checks)")
    parser.add_argument("--team-name", help="Team name (for --update-team)")
    parser.add_argument("--team-status", help="Team status (for --update-team)")
    parser.add_argument("--append-task", help="Task ID to append to pending (for --update-team)")
    parser.add_argument("--complete-task", help="Task ID to mark completed (for --update-team)")
    parser.add_argument("--agent", help="Agent name for task (for --append-task)")
    parser.add_argument("--task-output-path", help="Output path for task (for --append-task)")
    parser.add_argument("--gate-name", help="Gate name (for --record-gate)")
    parser.add_argument("--gate-status", choices=["pass", "fail"], help="Gate status (for --record-gate)")
    parser.add_argument("--report-path", help="Path to gate report JSON (for --record-gate)")
    parser.add_argument("--output-path", help="Output file path (for --record-output)")
    parser.add_argument("--ko-path", help="Korean translation path (for --record-translation)")
    parser.add_argument("--domain", choices=sorted(VALID_DIALOGUE_DOMAINS), help="Dialogue domain (for --dialogue-start)")
    parser.add_argument("--max-rounds", type=int, default=10, help="Max dialogue rounds (for --dialogue-start, default: 10)")
    parser.add_argument("--round", type=int, help="Round number (for --dialogue-round)")
    parser.add_argument("--verdict", choices=["PASS", "FAIL"], help="Round verdict (for --dialogue-round)")
    parser.add_argument("--outcome", choices=sorted(VALID_DIALOGUE_OUTCOMES), help="Dialogue outcome (for --dialogue-end)")
    parser.add_argument("--pccs-report", help="Path to pccs-report.json (for --update-pccs-cal)")
    parser.add_argument("--pccs-cal", help="Path to pccs-calibration.json (for --update-pccs-cal)")

    args = parser.parse_args()

    if args.init:
        return _cli_init(args)
    elif args.advance:
        if args.step is None:
            parser.error("--advance requires --step N")
        return _cli_advance(args)
    elif args.status:
        return _cli_status(args)
    elif args.save_checkpoint or args.restore_checkpoint:
        if not args.checkpoint:
            parser.error("--save-checkpoint/--restore-checkpoint requires --checkpoint NAME")
        return _cli_checkpoint(args)
    elif args.validate:
        return _cli_validate(args)
    elif args.is_hitl_blocking:
        return _cli_is_hitl_blocking(args)
    elif args.record_hitl:
        return _cli_record_hitl(args)
    elif args.update_team:
        return _cli_update_team(args)
    elif args.complete_team:
        return _cli_complete_team(args)
    elif args.record_gate:
        return _cli_record_gate(args)
    elif args.record_output:
        return _cli_record_output(args)
    elif args.record_translation:
        return _cli_record_translation(args)
    elif args.translation_progress:
        return _cli_translation_progress(args)
    elif args.dialogue_start:
        return _cli_dialogue_start(args)
    elif args.dialogue_round:
        return _cli_dialogue_round(args)
    elif args.dialogue_end:
        return _cli_dialogue_end(args)
    elif args.set_substep is not None:
        return _cli_set_substep(args)
    elif args.update_pccs_cal:
        return _cli_update_pccs_cal(args)


def _cli_dialogue_start(args) -> int:
    """Handle --dialogue-start command."""
    project_dir = Path(args.project_dir)
    step = args.step
    domain = args.domain or "research"
    max_rounds = getattr(args, "max_rounds", 10) or 10

    if step is None:
        print("ERROR: --dialogue-start requires --step N", file=sys.stderr)
        return 1

    try:
        sot = start_dialogue(project_dir, step, domain, max_rounds)
        print(f"Dialogue started: step={step}, domain={domain}, max_rounds={max_rounds}")
        print(f"  SOT updated: dialogue_state.status=in_progress")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def _cli_dialogue_round(args) -> int:
    """Handle --dialogue-round command."""
    project_dir = Path(args.project_dir)
    step = args.step
    round_num = getattr(args, "round", None)
    verdict = getattr(args, "verdict", None)

    if step is None or round_num is None or verdict is None:
        print("ERROR: --dialogue-round requires --step N --round K --verdict PASS|FAIL", file=sys.stderr)
        return 1

    try:
        sot = advance_dialogue_round(project_dir, step, round_num, verdict)
        ds = sot.get("dialogue_state", {})
        print(f"Dialogue round recorded: step={step}, round={round_num}, verdict={verdict}")
        print(f"  Rounds used: {ds.get('rounds_used', '?')} / {ds.get('max_rounds', '?')}")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def _cli_dialogue_end(args) -> int:
    """Handle --dialogue-end command."""
    project_dir = Path(args.project_dir)
    step = args.step
    outcome = getattr(args, "outcome", None)

    if step is None or outcome is None:
        print("ERROR: --dialogue-end requires --step N --outcome consensus|escalated", file=sys.stderr)
        return 1

    try:
        sot = end_dialogue(project_dir, step, outcome)
        ds = sot.get("dialogue_state", {})
        print(f"Dialogue ended: step={step}, outcome={outcome}")
        print(f"  Rounds used: {ds.get('rounds_used', '?')} / {ds.get('max_rounds', '?')}")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def _cli_set_substep(args) -> int:
    """Handle --set-substep SUBSTEP command.

    Records the current sub-step within the active step in session.json.
    Use 'clear' as SUBSTEP value to reset (after step advance completes).
    """
    project_dir = Path(args.project_dir)
    raw = args.set_substep
    substep = None if raw == "clear" else raw

    try:
        sot = set_execution_substep(project_dir, substep)
        label = f"'{substep}'" if substep else "cleared"
        print(f"execution_substep set to {label} (step {sot.get('current_step', '?')})")
    except FileNotFoundError:
        print(f"Thesis SOT not found at: {project_dir}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def _cli_update_pccs_cal(args) -> int:
    """Handle --update-pccs-cal command.

    Updates the pCCS block in session.json with calibration data and
    the latest report summary. Safe SOT write via write_thesis_sot().
    """
    project_dir = Path(args.project_dir)
    pccs_report_path = getattr(args, "pccs_report", None)
    pccs_cal_path = getattr(args, "pccs_cal", None)

    try:
        sot = read_thesis_sot(project_dir)
    except FileNotFoundError:
        print(f"Thesis SOT not found at: {project_dir}", file=sys.stderr)
        return 1

    # Initialize pccs block if absent
    if "pccs" not in sot:
        sot["pccs"] = {
            "cal_delta": 0.0,
            "last_step": None,
            "total_cal_samples": 0,
            "history": {},
        }

    pccs = sot["pccs"]

    # Update from calibration file
    if pccs_cal_path and os.path.exists(pccs_cal_path):
        try:
            with open(pccs_cal_path, "r", encoding="utf-8") as f:
                cal = json.load(f)
            pccs["cal_delta"] = cal.get("cal_delta", 0.0)
            pccs["total_cal_samples"] = cal.get("total_samples", 0)
            print(f"  cal_delta updated: {pccs['cal_delta']}")
        except (json.JSONDecodeError, IOError) as e:
            print(f"WARNING: Cannot load calibration: {e}", file=sys.stderr)

    # Update from report file
    if pccs_report_path and os.path.exists(pccs_report_path):
        try:
            with open(pccs_report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            step = report.get("step", -1)
            summary = report.get("summary", {})
            decision = report.get("decision", {})
            pccs["last_step"] = step

            # Record in history
            step_key = f"step-{step}"
            pccs["history"][step_key] = {
                "mean_pccs": summary.get("mean_pccs", 0),
                "mode": report.get("mode", "DEGRADED"),
                "green": summary.get("green", 0),
                "yellow": summary.get("yellow", 0),
                "red": summary.get("red", 0),
                "action": decision.get("action", "unknown"),
            }
            print(
                f"  step-{step}: mean={summary.get('mean_pccs', 0)}, "
                f"action={decision.get('action', '?')}"
            )
        except (json.JSONDecodeError, IOError) as e:
            print(f"WARNING: Cannot load report: {e}", file=sys.stderr)

    try:
        write_thesis_sot(project_dir, sot)
        print(f"pCCS SOT updated successfully.")
    except Exception as e:
        print(f"ERROR writing SOT: {e}", file=sys.stderr)
        return 1

    return 0


def _cli_is_hitl_blocking(args) -> int:
    """CLI handler for --is-hitl-blocking."""
    hitl_name = getattr(args, "hitl_name", None)
    # Accept hitl_name from multiple sources
    if not hitl_name:
        # Check all known HITL names
        try:
            project_dir = Path(args.project_dir)
            sot = read_thesis_sot(project_dir)
            blocking = []
            for name in sot.get("hitl_checkpoints", {}).keys():
                if is_hitl_blocking(project_dir, name):
                    blocking.append(name)
            result = {"blocking": len(blocking) > 0, "blocking_hitls": blocking}
            print(json.dumps(result))
            return 0
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
    try:
        project_dir = Path(args.project_dir)
        blocked = is_hitl_blocking(project_dir, hitl_name)
        print(json.dumps({"hitl": hitl_name, "blocking": blocked}))
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _cli_record_gate(args) -> int:
    """CLI handler for --record-gate."""
    if not args.gate_name:
        print("ERROR: --record-gate requires --gate-name", file=sys.stderr)
        return 1
    if not args.gate_status:
        print("ERROR: --record-gate requires --gate-status", file=sys.stderr)
        return 1
    try:
        project_dir = Path(args.project_dir)
        sot = record_gate_result(
            project_dir, args.gate_name, args.gate_status, args.report_path
        )
        gate_entry = sot["gates"].get(args.gate_name, {})
        print(json.dumps({"ok": True, "gate": args.gate_name, "entry": gate_entry}))
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _cli_record_output(args) -> int:
    """CLI handler for --record-output."""
    if args.step is None:
        print("ERROR: --record-output requires --step N", file=sys.stderr)
        return 1
    if not args.output_path:
        print("ERROR: --record-output requires --output-path", file=sys.stderr)
        return 1
    try:
        project_dir = Path(args.project_dir)
        sot = record_output(project_dir, args.step, args.output_path)
        key = f"step-{args.step}"
        print(json.dumps({"ok": True, "key": key, "path": sot["outputs"].get(key)}))
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _cli_record_translation(args) -> int:
    """CLI handler for --record-translation."""
    if args.step is None:
        print("ERROR: --record-translation requires --step N", file=sys.stderr)
        return 1
    if not args.ko_path:
        print("ERROR: --record-translation requires --ko-path", file=sys.stderr)
        return 1
    try:
        project_dir = Path(args.project_dir)
        sot = record_translation(project_dir, args.step, args.ko_path)
        key = f"step-{args.step}-ko"
        print(json.dumps({"ok": True, "key": key, "path": sot["outputs"].get(key)}))
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _cli_translation_progress(args) -> int:
    """CLI handler for --translation-progress."""
    project_dir = Path(args.project_dir)
    try:
        progress = get_translation_progress(project_dir)
    except FileNotFoundError:
        print(f"No thesis project found at: {project_dir}", file=sys.stderr)
        return 1

    print(f"Translation coverage: {progress['coverage_pct']}% ({progress['translated']}/{progress['total_en']})")
    if progress["missing_steps"]:
        print(f"Missing translations: steps {', '.join(str(s) for s in progress['missing_steps'])}")
    else:
        if progress["total_en"] > 0:
            print("All English outputs have Korean translations.")
        else:
            print("No English outputs yet.")
    print(json.dumps(progress))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
