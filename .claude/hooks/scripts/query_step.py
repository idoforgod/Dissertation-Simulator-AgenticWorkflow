#!/usr/bin/env python3
"""Step Execution Registry — deterministic step→execution parameters mapping.

Eliminates Orchestrator hallucination at 8 critical decision points:
  H-1: Step→Agent mapping (which agent executes this step?)
  H-2: pCCS mode selection (FULL or DEGRADED?)
  H-3: Critic agent routing (which critic reviews this step?)
  H-4: Tier selection (Tier 1/2/3?)
  H-5: Step consolidation (which steps execute together as one call?)
  H-6: Output size enforcement (minimum output bytes per step type)
  H-7: Invocation planning (how many Orchestrator calls needed?)
  H-8: Writing standard injection (doctoral-level academic writing in ALL prompts)

The Orchestrator calls this script INSTEAD of interpreting prose rules.
All outputs are deterministic — no LLM interpretation needed.

Usage:
  python3 query_step.py --step 47 [--project-dir <dir>]
  python3 query_step.py --step 47 --json
  python3 query_step.py --step 47 --field agent
  python3 query_step.py --list-agents
  python3 query_step.py --list-steps --agent literature-searcher
  python3 query_step.py --invocation-plan [--project-dir <dir>] [--json]
  python3 query_step.py --single-prompt --step 143 --topic "AI safety" --json
  python3 query_step.py --single-prompt --step 143 --topic "AI safety" --context "Reference wave-results/" --json

P1 Compliance: Pure stdlib, no LLM, deterministic, exit 0 always.
"""

import argparse
import json
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Step Registry — THE single source of truth for step execution parameters
# ---------------------------------------------------------------------------

# Agent assignment by step range.
# Format: (start, end, agent_name, description_prefix)
# Within a range, each step maps to the same agent.
# For mixed-agent sections, individual step overrides are in _STEP_OVERRIDES.

_RANGE_AGENTS: list[tuple[int, int, str, str]] = [
    # Phase 0: Initialization (steps 1-8) — Orchestrator direct
    (1, 8, "_orchestrator", "Phase 0 setup"),
    # Phase 0-A: Topic Exploration (steps 9-14)
    (9, 11, "topic-explorer", "Topic exploration"),
    (12, 14, "literature-analyzer", "Literature feasibility"),
    # Phase 0-D: Learning Mode (steps 15-34)
    (15, 16, "methodology-tutor", "Learning setup"),
    (17, 22, "methodology-tutor", "Learning module"),
    (23, 28, "methodology-tutor", "Learning module"),
    (29, 32, "methodology-tutor", "Learning module"),
    (33, 34, "assessment-agent", "Assessment"),
    # HITL-1 (steps 35-38) — Orchestrator direct (human interaction)
    (35, 38, "_orchestrator", "HITL-1 interaction"),
    # Wave 1 (steps 39-54)
    (39, 42, "literature-searcher", "Wave 1 literature search"),
    (43, 46, "seminal-works-analyst", "Wave 1 seminal works"),
    (47, 50, "trend-analyst", "Wave 1 trend analysis"),
    (51, 54, "methodology-scanner", "Wave 1 methodology scan"),
    # Gate 1 (steps 55-58)
    (55, 55, "_orchestrator", "Gate 1 cross-validation"),
    (56, 56, "translator", "Gate 1 translation"),
    (57, 57, "_orchestrator", "Gate 1 translation validation"),
    (58, 58, "_orchestrator", "Gate 1 SOT record"),
    # Wave 2 (steps 59-74)
    (59, 62, "theoretical-framework-analyst", "Wave 2 theory analysis"),
    (63, 66, "empirical-evidence-analyst", "Wave 2 empirical analysis"),
    (67, 70, "gap-identifier", "Wave 2 gap identification"),
    (71, 74, "variable-relationship-analyst", "Wave 2 variable analysis"),
    # Gate 2 (steps 75-78)
    (75, 75, "_orchestrator", "Gate 2 cross-validation"),
    (76, 76, "translator", "Gate 2 translation"),
    (77, 77, "_orchestrator", "Gate 2 translation validation"),
    (78, 78, "_orchestrator", "Gate 2 SOT record"),
    # Wave 3 (steps 79-94)
    (79, 82, "critical-reviewer", "Wave 3 critical review"),
    (83, 86, "methodology-critic", "Wave 3 methodology critique"),
    (87, 90, "limitation-analyst", "Wave 3 limitation analysis"),
    (91, 94, "future-direction-analyst", "Wave 3 future directions"),
    # Gate 3 (steps 95-98)
    (95, 95, "_orchestrator", "Gate 3 cross-validation"),
    (96, 96, "translator", "Gate 3 translation"),
    (97, 97, "_orchestrator", "Gate 3 translation validation"),
    (98, 98, "_orchestrator", "Gate 3 SOT record"),
    # Wave 4 (steps 99-106)
    (99, 102, "synthesis-agent", "Wave 4 synthesis"),
    (103, 106, "conceptual-model-builder", "Wave 4 conceptual model"),
    # SRCS Full (steps 107-110)
    (107, 107, "unified-srcs-evaluator", "SRCS full evaluation"),
    (108, 108, "translator", "SRCS translation"),
    (109, 109, "_orchestrator", "SRCS translation validation"),
    (110, 110, "_orchestrator", "SRCS SOT record"),
    # Wave 5 (steps 111-114)
    (111, 112, "plagiarism-checker", "Wave 5 plagiarism check"),
    (113, 113, "translator", "Wave 5 translation"),
    (114, 114, "_orchestrator", "Wave 5 SOT record"),
    # HITL-2 (steps 115-120) — Orchestrator direct
    (115, 120, "_orchestrator", "HITL-2 literature review approval"),
    # Phase 2 (steps 121-140)
    (121, 121, "_orchestrator", "Phase 2 design approach"),
    (122, 122, "_orchestrator", "Phase 2 agent configuration"),
]

# Phase 2 has research-type-dependent agents — handled by _STEP_OVERRIDES_BY_RESEARCH_TYPE
_PHASE2_QUANT_AGENTS: list[tuple[int, int, str, str]] = [
    (123, 123, "quantitative-designer", "Research methodology"),
    (124, 124, "hypothesis-developer", "Variable definition"),
    (125, 125, "sampling-designer", "Sampling strategy"),
    (126, 126, "instrument-developer", "Research instruments"),
    (127, 127, "statistical-planner", "Statistical analysis plan"),
    (128, 128, "data-collection-planner", "Data collection procedure"),
    (129, 129, "ethics-reviewer", "Ethical considerations"),
]

_PHASE2_QUAL_AGENTS: list[tuple[int, int, str, str]] = [
    (123, 123, "paradigm-consultant", "Research methodology"),
    (124, 124, "qualitative-data-designer", "Variable definition"),
    (125, 125, "participant-selector", "Sampling strategy"),
    (126, 126, "instrument-developer", "Research instruments"),
    (127, 127, "qualitative-analysis-planner", "Analysis plan"),
    (128, 128, "data-collection-planner", "Data collection procedure"),
    (129, 129, "ethics-reviewer", "Ethical considerations"),
]

_PHASE2_MIXED_AGENTS: list[tuple[int, int, str, str]] = [
    (123, 123, "mixed-methods-designer", "Research methodology"),
    (124, 124, "integration-strategist", "Variable definition"),
    (125, 125, "sampling-designer", "Sampling strategy"),
    (126, 126, "instrument-developer", "Research instruments"),
    (127, 127, "statistical-planner", "Analysis plan"),
    (128, 128, "data-collection-planner", "Data collection procedure"),
    (129, 129, "ethics-reviewer", "Ethical considerations"),
]

# Phase 2 common tail (steps 130-140)
_PHASE2_COMMON_TAIL: list[tuple[int, int, str, str]] = [
    (130, 130, "research-model-developer", "Research timeline"),
    (131, 131, "thesis-writer", "Draft research design"),
    (132, 132, "_orchestrator", "Internal review"),
    (133, 133, "translator", "Phase 2 translation"),
    (134, 134, "_orchestrator", "Phase 2 translation validation"),
    (135, 135, "_orchestrator", "Phase 2 SOT record"),
    (136, 136, "_orchestrator", "HITL-3 research type"),
    (137, 137, "_orchestrator", "HITL-4 design approval"),
    (138, 138, "_orchestrator", "HITL-3/4 checkpoint"),
    (139, 139, "_orchestrator", "Finalize design package"),
    (140, 140, "_orchestrator", "Archive design artifacts"),
]

# Phase 3: Thesis Writing (steps 141-164)
_PHASE3_AGENTS: list[tuple[int, int, str, str]] = [
    (141, 141, "thesis-architect", "Create thesis outline"),
    (142, 142, "_orchestrator", "HITL-5 outline approval"),
    (143, 143, "thesis-writer", "Chapter 1 Introduction"),
    (144, 144, "thesis-writer", "Chapter 2 Literature Review"),
    (145, 145, "thesis-writer", "Chapter 3 Research Methodology"),
    (146, 146, "thesis-writer", "Chapter 4 Results"),
    (147, 147, "thesis-writer", "Chapter 5 Discussion"),
    (148, 148, "thesis-writer", "Chapter 6 Conclusion"),
    (149, 149, "abstract-writer", "Abstract"),
    (150, 150, "citation-manager", "References"),
    (151, 151, "thesis-writer", "Appendices"),
    (152, 152, "thesis-reviewer", "Internal review cycle 1"),
    (153, 153, "thesis-writer", "Revision 1"),
    (154, 154, "thesis-reviewer", "Internal review cycle 2"),
    (155, 155, "thesis-writer", "Revision 2"),
    (156, 156, "thesis-plagiarism-checker", "Full thesis plagiarism"),
    (157, 157, "_orchestrator", "HITL-6 draft review"),
    (158, 158, "thesis-writer", "Final revision"),
    (159, 159, "manuscript-formatter", "Format check"),
    (160, 160, "_orchestrator", "HITL-7 final approval"),
    (161, 161, "translator", "Translate chapters"),
    (162, 162, "_orchestrator", "Validate translations"),
    (163, 163, "_orchestrator", "Bilingual package"),
    (164, 164, "_orchestrator", "Archive writing artifacts"),
]

# Phase 4: Publication (steps 165-172)
_PHASE4_AGENTS: list[tuple[int, int, str, str]] = [
    (165, 165, "publication-strategist", "Identify journals"),
    (166, 166, "journal-matcher", "Journal requirements"),
    (167, 167, "submission-preparer", "Submission package"),
    (168, 168, "cover-letter-writer", "Cover letter"),
    (169, 169, "manuscript-formatter", "Journal formatting"),
    (170, 170, "_orchestrator", "Final quality check"),
    (171, 171, "_orchestrator", "HITL-8 submission approval"),
    (172, 172, "_orchestrator", "Final submission package"),
]

# Phase 5: Finalization (steps 173-180)
_PHASE5_AGENTS: list[tuple[int, int, str, str]] = [
    (173, 173, "_orchestrator", "Consolidate artifacts"),
    (174, 174, "_orchestrator", "Cross-reference validation"),
    (175, 175, "citation-manager", "Citation report"),
    (176, 176, "_orchestrator", "Supplementary materials"),
    (177, 177, "_orchestrator", "Data availability"),
    (178, 178, "thesis-plagiarism-checker", "Final plagiarism check"),
    (179, 179, "_orchestrator", "Author contribution"),
    (180, 180, "_orchestrator", "Archive project"),
]

# Phase 6: Translation (steps 181-210) + Export (step 211)
_PHASE6_AGENTS: list[tuple[int, int, str, str]] = [
    (181, 210, "translator", "Translation step"),
    (211, 211, "_orchestrator", "Generate consolidated Korean thesis DOCX"),
]


# ---------------------------------------------------------------------------
# Output path overrides — steps with non-standard output locations
# ---------------------------------------------------------------------------

# Steps whose output_path and output_dir don't follow phase-based conventions.
# Checked BEFORE the phase-based if/else chain in _get_output_pattern/_get_output_dir.
_OUTPUT_OVERRIDES: dict[int, dict[str, str]] = {
    211: {
        "pattern": "deliverables/consolidated-thesis-ko.docx",
        "dir": "deliverables",
    },
}


# ---------------------------------------------------------------------------
# Execution commands — P1 deterministic bash commands for automated steps
# ---------------------------------------------------------------------------

# Steps with a pre-defined execution command. The orchestrator runs this
# command verbatim via Bash instead of dispatching to a sub-agent.
# Template variable {project_dir} is resolved at CLI output time.
_EXECUTION_COMMANDS: dict[int, tuple[str, str]] = {
    # (script_filename, arguments_template)
    211: ("merge_ko_to_docx.py", "--project-dir {project_dir} --json"),
}


def _get_execution_command(step: int) -> str | None:
    """Return fully resolved execution command for a step, or None.

    Resolves the script path relative to this file's directory.
    The {project_dir} template variable remains for CLI-level resolution.
    """
    entry = _EXECUTION_COMMANDS.get(step)
    if entry is None:
        return None
    script_name, args_template = entry
    import os
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(scripts_dir, script_name)
    return f"{sys.executable} {script_path} {args_template}"


# ---------------------------------------------------------------------------
# Step Consolidation (H-5) — deterministic grouping for multi-step execution
# ---------------------------------------------------------------------------

# Agents that must NOT be consolidated (each step needs individual execution).
# translator: each translation targets a different source chapter, needs sequential
#   glossary consistency. _orchestrator: administrative steps (HITL, gates, SOT records).
_NO_CONSOLIDATE_AGENTS: set[str] = {"translator", "_orchestrator"}

# Maximum steps in one consolidation group (safety cap).
_MAX_CONSOLIDATION_SIZE: int = 6


# ---------------------------------------------------------------------------
# Critic routing — which critic reviews which step
# ---------------------------------------------------------------------------

# Steps that use Adversarial Dialogue with research domain
# (parallel @fact-checker + @reviewer)
_DIALOGUE_RESEARCH_STEPS: set[int] = set()
# Wave 1-3 content steps (agent work, not gate/translation/SOT steps)
for _s, _e in [(39, 54), (59, 74), (79, 94)]:
    _DIALOGUE_RESEARCH_STEPS.update(range(_s, _e + 1))
# Wave 4 synthesis steps
_DIALOGUE_RESEARCH_STEPS.update(range(99, 106 + 1))

# Steps that use Adversarial Dialogue with development domain (@code-reviewer)
_DIALOGUE_DEVELOPMENT_STEPS: set[int] = set()
# Phase 2 design steps (123-131) — methodology design is development-type review
_DIALOGUE_DEVELOPMENT_STEPS.update(range(123, 131 + 1))

# Steps that use single-review (@reviewer only, no dialogue)
_SINGLE_REVIEW_STEPS: set[int] = set()
# Phase 3 review cycles
_SINGLE_REVIEW_STEPS.update({152, 154})
# Phase 4 quality check
_SINGLE_REVIEW_STEPS.add(170)

# Gate steps that need L2 Enhanced review
_GATE_STEPS: set[int] = {55, 75, 95, 107}


def _get_critic_config(step: int) -> dict[str, Any]:
    """Return critic configuration for a step.

    Returns:
        dict with keys:
        - critic: primary critic agent name (or None)
        - dialogue_domain: "research" | "development" | None
        - dialogue: bool — whether Adversarial Dialogue is used
        - l2_enhanced: bool — whether L2 Enhanced review applies
    """
    if step in _DIALOGUE_RESEARCH_STEPS:
        return {
            "critic": "fact-checker",
            "critic_secondary": "reviewer",
            "dialogue_domain": "research",
            "dialogue": True,
            "l2_enhanced": True,
        }
    if step in _DIALOGUE_DEVELOPMENT_STEPS:
        return {
            "critic": "code-reviewer",
            "critic_secondary": None,
            "dialogue_domain": "development",
            "dialogue": True,
            "l2_enhanced": True,
        }
    if step in _SINGLE_REVIEW_STEPS or step in _GATE_STEPS:
        return {
            "critic": "reviewer",
            "critic_secondary": None,
            "dialogue_domain": None,
            "dialogue": False,
            "l2_enhanced": True,
        }
    return {
        "critic": None,
        "critic_secondary": None,
        "dialogue_domain": None,
        "dialogue": False,
        "l2_enhanced": False,
    }


# ---------------------------------------------------------------------------
# pCCS mode selection — deterministic FULL vs DEGRADED
# ---------------------------------------------------------------------------

# Steps where pCCS FULL mode is required (high-importance Tier A content steps)
_PCCS_FULL_STEPS: set[int] = set()
# NOTE: Gate steps (55, 75, 95, 107) are cross-validation, not content — no pCCS
# Wave 4 synthesis (high importance — final synthesis before HITL-2)
_PCCS_FULL_STEPS.update(range(99, 106 + 1))
# Phase 3 thesis chapters (high importance — final thesis content)
_PCCS_FULL_STEPS.update(range(143, 151 + 1))

# Steps that produce GroundedClaim output (Tier A) — pCCS applicable
_GROUNDED_CLAIM_STEPS: set[int] = set()
# Wave 1-3 content steps
for _s, _e in [(39, 54), (59, 74), (79, 94)]:
    _GROUNDED_CLAIM_STEPS.update(range(_s, _e + 1))
# Wave 4 synthesis
_GROUNDED_CLAIM_STEPS.update(range(99, 106 + 1))
# Phase 2 design content (123-131)
_GROUNDED_CLAIM_STEPS.update(range(123, 131 + 1))
# Phase 3 thesis chapters (143-151)
_GROUNDED_CLAIM_STEPS.update(range(143, 151 + 1))


def _get_pccs_config(step: int) -> dict[str, Any]:
    """Return pCCS configuration for a step.

    Returns:
        dict with keys:
        - pccs_required: bool — whether pCCS scoring applies
        - pccs_mode: "FULL" | "DEGRADED" | None
        - has_grounded_claims: bool — whether step produces GroundedClaim output
    """
    if step not in _GROUNDED_CLAIM_STEPS:
        return {
            "pccs_required": False,
            "pccs_mode": None,
            "has_grounded_claims": False,
        }
    mode = "FULL" if step in _PCCS_FULL_STEPS else "DEGRADED"
    return {
        "pccs_required": True,
        "pccs_mode": mode,
        "has_grounded_claims": True,
    }


# ---------------------------------------------------------------------------
# Wave/Phase/Gate mapping
# ---------------------------------------------------------------------------

def _get_wave(step: int) -> int | None:
    """Return wave number (1-5) for a step, or None if not in a wave."""
    if 39 <= step <= 54:
        return 1
    if 59 <= step <= 74:
        return 2
    if 79 <= step <= 94:
        return 3
    if 99 <= step <= 106:
        return 4
    if 111 <= step <= 114:
        return 5
    return None


def _get_phase(step: int) -> str:
    """Return phase name for a step."""
    if step <= 8:
        return "phase_0_init"
    if step <= 14:
        return "phase_0a_topic"
    if step <= 34:
        return "phase_0d_learning"
    if step <= 38:
        return "hitl_1"
    if step <= 54:
        return "wave_1"
    if step <= 58:
        return "gate_1"
    if step <= 74:
        return "wave_2"
    if step <= 78:
        return "gate_2"
    if step <= 94:
        return "wave_3"
    if step <= 98:
        return "gate_3"
    if step <= 106:
        return "wave_4"
    if step <= 110:
        return "srcs_full"
    if step <= 114:
        return "wave_5"
    if step <= 120:
        return "hitl_2"
    if step <= 140:
        return "phase_2_design"
    if step <= 164:
        return "phase_3_writing"
    if step <= 172:
        return "phase_4_publication"
    if step <= 180:
        return "phase_5_finalization"
    if step <= 211:
        return "phase_6_translation"
    return "unknown"


def _get_gate_context(step: int) -> dict[str, Any]:
    """Return gate context — which gate comes before/after this step."""
    gate_before = None
    gate_after = None

    if 55 <= step <= 58:
        gate_before = None
        gate_after = "gate-1"
    elif 59 <= step <= 78:
        gate_before = "gate-1"
        gate_after = "gate-2"
    elif 79 <= step <= 98:
        gate_before = "gate-2"
        gate_after = "gate-3"
    elif 99 <= step <= 110:
        gate_before = "gate-3"
        gate_after = "srcs-full"
    elif 111 <= step <= 114:
        gate_before = "srcs-full"
        gate_after = "final-quality"

    return {"gate_before": gate_before, "gate_after": gate_after}


# ---------------------------------------------------------------------------
# HITL mapping
# ---------------------------------------------------------------------------

_HITL_STEPS: dict[int, str] = {
    35: "hitl-1", 36: "hitl-1", 37: "hitl-1", 38: "hitl-1",
    115: "hitl-2", 116: "hitl-2", 117: "hitl-2", 118: "hitl-2",
    119: "hitl-2", 120: "hitl-2",
    136: "hitl-3", 137: "hitl-4",
    142: "hitl-5",
    157: "hitl-6",
    160: "hitl-7",
    171: "hitl-8",
}


# ---------------------------------------------------------------------------
# Translation step detection
# ---------------------------------------------------------------------------

_TRANSLATION_STEPS: set[int] = set()
# Gate translation steps
_TRANSLATION_STEPS.update({56, 76, 96, 108, 113})
# Phase 2 translation
_TRANSLATION_STEPS.add(133)
# Phase 3 translation
_TRANSLATION_STEPS.add(161)
# Phase 6 all translation
_TRANSLATION_STEPS.update(range(181, 210 + 1))


# ---------------------------------------------------------------------------
# Output path pattern
# ---------------------------------------------------------------------------

def _get_output_pattern(step: int, phase: str) -> str:
    """Return expected output file path pattern for a step."""
    override = _OUTPUT_OVERRIDES.get(step)
    if override:
        return override["pattern"]
    wave = _get_wave(step)
    if wave is not None:
        return f"wave-results/wave-{wave}/step-{step:03d}-*.md"
    if phase.startswith("phase_2"):
        return f"phase-2/step-{step:03d}-*.md"
    if phase.startswith("phase_3"):
        return f"phase-3/step-{step:03d}-*.md"
    if phase.startswith("phase_4"):
        return f"submission-package/step-{step:03d}-*.md"
    if phase.startswith("phase_6"):
        return f"translations/step-{step:03d}-*.ko.md"
    return f"step-{step:03d}-*.md"


# ---------------------------------------------------------------------------
# Consolidation helpers (H-5, H-6)
# ---------------------------------------------------------------------------

def _get_output_dir(step: int, phase: str) -> str:
    """Return output directory for a step (without filename).

    Used by consolidation to construct consolidated output file paths.
    """
    override = _OUTPUT_OVERRIDES.get(step)
    if override:
        return override.get("dir", "")
    wave = _get_wave(step)
    if wave is not None:
        return f"wave-results/wave-{wave}"
    if phase.startswith("phase_2"):
        return "phase-2"
    if phase.startswith("phase_3"):
        return "phase-3"
    if phase.startswith("phase_4"):
        return "submission-package"
    if phase.startswith("phase_6"):
        return "translations"
    return ""


def _get_min_output_bytes(step: int, group_size: int) -> int:
    """Return minimum expected output bytes for a step.

    Conservative thresholds for _warn_if_output_too_small() P1 guard.
    Returns 0 for steps without meaningful output requirements.
    Non-blocking: advance guards use these as WARNING thresholds only.
    """
    # Wave 1-3 consolidated groups: comprehensive multi-task analysis
    if 39 <= step <= 94 and group_size > 1:
        return 30000
    # Wave 4 consolidated groups: synthesis
    if 99 <= step <= 106 and group_size > 1:
        return 30000
    # Phase 3 individual chapters (major content)
    if 143 <= step <= 148:
        return 15000
    # Phase 3 abstract, references, appendices
    if step in (149, 150, 151):
        return 5000
    # Phase 2 design steps (methodology/instruments)
    if 123 <= step <= 131:
        return 5000
    # Phase 3 reviews and revisions
    if step in (152, 153, 154, 155, 158):
        return 3000
    # Phase 4 publication steps
    if 165 <= step <= 169:
        return 3000
    return 0


def _get_consolidation_config(
    step: int,
    range_start: int,
    range_end: int,
    agent: str,
    phase: str,
) -> dict[str, Any]:
    """Return consolidation configuration for a step.

    Derives group from the matched _RANGE_AGENTS entry. Multi-step ranges
    sharing the same agent form a consolidation group (executed as one call).

    Returns:
        dict with:
        - consolidate_with: list of step numbers in the group
        - consolidated_output_filename: full relative path (or None for single-step)
        - min_output_bytes: minimum expected output size (0 = no minimum)
    """
    if agent in _NO_CONSOLIDATE_AGENTS:
        return {
            "consolidate_with": [step],
            "consolidated_output_filename": None,
            "min_output_bytes": 0,
        }

    # Cap group size at safety limit
    actual_end = min(range_end, range_start + _MAX_CONSOLIDATION_SIZE - 1)
    group = list(range(range_start, actual_end + 1))
    group_size = len(group)

    if group_size > 1:
        output_dir = _get_output_dir(range_start, phase)
        filename = f"step-{range_start:03d}-to-{actual_end:03d}-{agent}.md"
        full_path = f"{output_dir}/{filename}" if output_dir else filename
    else:
        full_path = None

    min_bytes = _get_min_output_bytes(step, group_size)

    return {
        "consolidate_with": group,
        "consolidated_output_filename": full_path,
        "min_output_bytes": min_bytes,
    }


# ---------------------------------------------------------------------------
# Invocation Plan (H-7) — deterministic Orchestrator call boundaries
# ---------------------------------------------------------------------------

# Each entry: (start_step, end_step, label)
# Boundaries at HITL, gate, and phase transitions.
_INVOCATION_PLAN: list[tuple[int, int, str]] = [
    (1, 14, "Phase 0: Init + Topic Exploration"),
    (15, 34, "Phase 0-D: Learning Mode"),
    (35, 38, "HITL-1: Research Question"),
    (39, 58, "Wave 1 + Gate 1"),
    (59, 78, "Wave 2 + Gate 2"),
    (79, 98, "Wave 3 + Gate 3"),
    (99, 114, "Wave 4 + SRCS + Wave 5"),
    (115, 120, "HITL-2: Literature Review Approval"),
    (121, 140, "Phase 2: Research Design + HITL-3/4"),
    (141, 142, "Phase 3: Outline + HITL-5"),
    (143, 156, "Phase 3: Chapters + Reviews"),
    (157, 160, "HITL-6 + Final Revision + HITL-7"),
    (161, 164, "Phase 3: Translation + Archive"),
    (165, 172, "Phase 4: Publication + HITL-8"),
    (173, 180, "Phase 5: Finalization"),
    (181, 195, "Phase 6: Translation Batch 1"),
    (196, 211, "Phase 6: Translation Batch 2 + Export"),
]


def get_invocation_plan(current_step: int = 0) -> list[dict[str, Any]]:
    """Return the deterministic list of Orchestrator invocations.

    Each invocation defines a batch of steps for one Orchestrator call.
    Boundaries are set at HITL, gate, and phase transitions. The main agent
    (thesis-start.md) uses this plan to know exactly how many invocations
    are needed, preventing premature termination.

    Args:
        current_step: Current workflow step (from SOT). Used to mark
                      completed/current/pending status.

    Returns:
        List of dicts with: invocation, start, end, label, status, total
    """
    total = len(_INVOCATION_PLAN)
    result: list[dict[str, Any]] = []
    for idx, (start, end, label) in enumerate(_INVOCATION_PLAN, 1):
        if current_step >= end:
            status = "completed"
        elif current_step >= start:
            status = "in_progress"
        else:
            status = "pending"
        result.append({
            "invocation": idx,
            "start": start,
            "end": end,
            "label": label,
            "status": status,
            "total": total,
        })
    return result


# ---------------------------------------------------------------------------
# Core query function
# ---------------------------------------------------------------------------

def query_step(step: int, research_type: str = "undecided") -> dict[str, Any]:
    """Query execution parameters for a given step.

    Args:
        step: Step number (1-211)
        research_type: "quantitative", "qualitative", "mixed", or "undecided"

    Returns:
        dict with all deterministic execution parameters.
    """
    if step < 1 or step > 211:
        return {"error": f"Step {step} out of range [1, 211]"}

    # Build the full agent list based on research type
    all_ranges: list[tuple[int, int, str, str]] = list(_RANGE_AGENTS)

    # Add Phase 2 type-specific agents
    # Guard: Phase 2 steps (121-140) MUST have a decided research type.
    # "undecided" is only allowed for non-Phase-2 queries.
    if research_type == "quantitative":
        all_ranges.extend(_PHASE2_QUANT_AGENTS)
    elif research_type == "qualitative":
        all_ranges.extend(_PHASE2_QUAL_AGENTS)
    elif research_type == "mixed":
        all_ranges.extend(_PHASE2_MIXED_AGENTS)
    elif 121 <= step <= 140:
        # Phase 2 step with undecided type — this is an error.
        # HITL-3 must set research_type before Phase 2 execution.
        return {
            "error": f"Step {step} is in Phase 2 (121-140) but research_type "
                     f"is '{research_type}'. HITL-3 must set research_type "
                     f"before Phase 2 execution.",
            "step": step,
        }
    else:
        # Non-Phase-2 step with undecided type — safe to default
        all_ranges.extend(_PHASE2_QUANT_AGENTS)

    all_ranges.extend(_PHASE2_COMMON_TAIL)
    all_ranges.extend(_PHASE3_AGENTS)
    all_ranges.extend(_PHASE4_AGENTS)
    all_ranges.extend(_PHASE5_AGENTS)
    all_ranges.extend(_PHASE6_AGENTS)

    # Find agent for this step
    agent = "_orchestrator"
    description = "Unknown step"
    range_start = step
    range_end = step
    for start, end, agent_name, desc in all_ranges:
        if start <= step <= end:
            agent = agent_name
            description = desc
            range_start = start
            range_end = end
            break

    # Tier determination — deterministic (from thesis-orchestrator.md Step-to-Tier Mapping)
    # Default: Tier 2. Orchestrator direct = Tier 3. Translator = Tier 2.
    if agent == "_orchestrator":
        tier = 3  # Orchestrator performs directly
    else:
        tier = 2  # Default: sub-agent (quality-first)

    phase = _get_phase(step)
    gate_ctx = _get_gate_context(step)
    critic_cfg = _get_critic_config(step)
    pccs_cfg = _get_pccs_config(step)
    hitl = _HITL_STEPS.get(step)
    is_translation = step in _TRANSLATION_STEPS
    output_pattern = _get_output_pattern(step, phase)

    # Consolidation (H-5, H-6)
    consol = _get_consolidation_config(
        step, range_start, range_end, agent, phase,
    )

    return {
        "step": step,
        "agent": agent,
        "description": description,
        "tier": tier,
        "phase": phase,
        "wave": _get_wave(step),
        "research_type_used": research_type,
        # Critic routing (H-3)
        "critic": critic_cfg["critic"],
        "critic_secondary": critic_cfg.get("critic_secondary"),
        "dialogue_domain": critic_cfg["dialogue_domain"],
        "dialogue": critic_cfg["dialogue"],
        "l2_enhanced": critic_cfg["l2_enhanced"],
        # pCCS (H-2)
        "pccs_required": pccs_cfg["pccs_required"],
        "pccs_mode": pccs_cfg["pccs_mode"],
        "has_grounded_claims": pccs_cfg["has_grounded_claims"],
        # Context
        "output_path": output_pattern,
        "gate_before": gate_ctx["gate_before"],
        "gate_after": gate_ctx["gate_after"],
        "hitl": hitl,
        "hitl_required": hitl is not None,
        "translation_required": is_translation,
        # Consolidation (H-5, H-6)
        "consolidate_with": consol["consolidate_with"],
        "consolidated_output_filename": consol["consolidated_output_filename"],
        "min_output_bytes": consol["min_output_bytes"],
        # Execution command (P1 deterministic bash command for automated steps)
        "execution_command": _get_execution_command(step),
    }


# ---------------------------------------------------------------------------
# Writing Standard — doctoral-level academic writing injection (H-8)
# ---------------------------------------------------------------------------

_WRITING_STANDARD_SUFFIX: str = (
    "\n\n  WRITING STANDARD (doctoral-level academic writing — MANDATORY):\n"
    "  All output must follow the doctoral-writing skill "
    "(.claude/skills/doctoral-writing/SKILL.md).\n"
    "  Apply these 4 principles rigorously:\n"
    "  (1) Clarity — precise terminology, logical paragraph structure, "
    "no ambiguous references;\n"
    "  (2) Conciseness — no filler phrases, every sentence advances the argument, "
    "eliminate redundancy;\n"
    "  (3) Academic Rigor — proper citations, evidence-based claims, "
    "appropriate hedging;\n"
    "  (4) Logical Flow — coherent transitions between paragraphs and sections, "
    "hierarchical organization.\n"
    "  Avoid banned expressions: 'it is important to note that', "
    "'it goes without saying', 'in order to', 'due to the fact that'.\n"
    "  Read .claude/skills/doctoral-writing/SKILL.md for the complete framework."
)


def generate_consolidated_prompt(
    first_step: int,
    last_step: int,
    research_topic: str,
    research_type: str = "undecided",
    checklist_path: str | None = None,
) -> dict[str, Any]:
    """P1 deterministic: generate a fully rendered consolidated prompt.

    Eliminates LLM hallucination risk by pre-computing ALL template variables:
    - Step descriptions (from _RANGE_AGENTS, not LLM memory)
    - Output filename (from _get_consolidation_config)
    - Trace marker instructions
    - Per-step section headings

    Args:
        first_step: First step in the consolidated group
        last_step: Last step in the consolidated group
        research_topic: The research question/topic string
        research_type: "quantitative"/"qualitative"/"mixed"/"undecided"
        checklist_path: Optional path to todo-checklist.md for richer descriptions

    Returns:
        dict with:
        - prompt: str (fully rendered, zero unfilled template variables)
        - agent: str (sub-agent to invoke)
        - output_file: str (consolidated output filename)
        - min_output_bytes: int

    Raises:
        ValueError: If step range is invalid or doesn't match a consolidation group boundary.
    """
    # Input validation (P1 — prevent misuse that causes semantic mismatches)
    if first_step < 1 or last_step > 211:
        raise ValueError(
            f"Step range [{first_step}, {last_step}] out of bounds [1, 211]"
        )
    if first_step > last_step:
        raise ValueError(
            f"first_step ({first_step}) > last_step ({last_step})"
        )

    # Query first step to get agent and consolidation config
    info = query_step(first_step, research_type)

    if "error" in info:
        raise ValueError(f"Invalid step {first_step}: {info['error']}")

    # Validate that [first_step, last_step] matches the actual consolidation group
    cw = info.get("consolidate_with", [first_step])
    if len(cw) <= 1:
        raise ValueError(
            f"Step {first_step} is not part of a multi-step consolidation group "
            f"(consolidate_with={cw}). Use --step {first_step} for single-step "
            f"execution instead of --consolidated-prompt."
        )
    expected_first = min(cw)
    expected_last = max(cw)
    if first_step != expected_first or last_step != expected_last:
        raise ValueError(
            f"Step range [{first_step}, {last_step}] does not match "
            f"consolidation group boundary [{expected_first}, {expected_last}]. "
            f"Use the exact group boundary from query_step()."
        )

    agent = info["agent"]
    output_file = info.get("consolidated_output_filename") or info["output_path"]
    min_bytes = info.get("min_output_bytes", 0)

    # Build per-step sections with descriptions from the registry (P1 source)
    step_sections: list[str] = []
    for step in range(first_step, last_step + 1):
        step_info = query_step(step, research_type)
        desc = step_info["description"]

        # Try richer description from checklist if available
        if checklist_path:
            try:
                import re as _re
                with open(checklist_path, "r", encoding="utf-8") as f:
                    content = f.read(50_000)
                m = _re.search(
                    rf"^-\s*\[[ xX]\]\s*Step\s+{step}\s*:\s*(.+)$",
                    content, _re.MULTILINE,
                )
                if m:
                    desc = m.group(1).strip()[:200]
            except Exception:
                pass  # Fall back to registry description

        step_sections.append(f"  ## Step {step}: {desc}")
        step_sections.append(f"  [Content for step {step}]")
        step_sections.append("")

    sections_text = "\n".join(step_sections)

    prompt = (
        f"Execute steps {first_step}-{last_step}:\n\n"
        f"{sections_text}\n"
        f"  Research topic: {research_topic}\n"
        f"  Output to: {output_file}\n\n"
        f"  STRUCTURE REQUIREMENT: Each step MUST have its own level-2 heading "
        f"(## Step N: description).\n"
        f"  Claims for step N must include trace markers: [trace:step-N].\n"
        f"  Write as a SINGLE comprehensive document with clear per-step structure.\n"
        f"  Use GroundedClaim schema for all claims.\n"
        f"  Minimum output size: {min_bytes} bytes."
        f"{_WRITING_STANDARD_SUFFIX}"
    )

    return {
        "prompt": prompt,
        "agent": agent,
        "output_file": output_file,
        "min_output_bytes": min_bytes,
        "first_step": first_step,
        "last_step": last_step,
    }


def generate_single_step_prompt(
    step: int,
    research_topic: str,
    research_type: str = "undecided",
    context: str = "",
) -> dict[str, Any]:
    """P1 deterministic: generate a fully rendered single-step prompt.

    Eliminates LLM hallucination risk for single-step execution (H-8)
    by pre-computing ALL template variables, identical to how
    generate_consolidated_prompt() handles multi-step groups.

    Args:
        step: Step number (1-211)
        research_topic: The research question/topic string
        research_type: "quantitative"/"qualitative"/"mixed"/"undecided"
        context: Optional additional context (e.g., chapter-specific instructions)

    Returns:
        dict with:
        - prompt: str (fully rendered, zero unfilled template variables)
        - agent: str (sub-agent to invoke)
        - output_file: str (output filename pattern)
        - min_output_bytes: int

    Raises:
        ValueError: If step is invalid or is part of a multi-step consolidation group.
    """
    if step < 1 or step > 211:
        raise ValueError(f"Step {step} out of bounds [1, 211]")

    info = query_step(step, research_type)

    if "error" in info:
        raise ValueError(f"Invalid step {step}: {info['error']}")

    # Reject multi-step consolidation groups — use generate_consolidated_prompt() instead
    cw = info.get("consolidate_with", [step])
    if len(cw) > 1:
        raise ValueError(
            f"Step {step} is part of a multi-step consolidation group "
            f"({min(cw)}-{max(cw)}). Use generate_consolidated_prompt() instead."
        )

    agent = info["agent"]
    description = info["description"]
    output_path = info["output_path"]
    min_bytes = info.get("min_output_bytes", 0)
    has_claims = info.get("has_grounded_claims", False)

    # Build the prompt deterministically
    parts: list[str] = [
        f"Execute step {step}: {description}.\n",
        f"  Research topic: {research_topic}\n",
        f"  Output to: {output_path}\n",
    ]

    if context:
        parts.append(f"\n  Context: {context}\n")

    if has_claims:
        parts.append(f"  Use GroundedClaim schema for all claims.\n")
        parts.append(f"  Claims must include trace markers: [trace:step-{step}].\n")

    if min_bytes > 0:
        parts.append(f"  Minimum output size: {min_bytes} bytes.\n")

    # Append doctoral-level writing standard (H-8)
    parts.append(_WRITING_STANDARD_SUFFIX)

    prompt = "".join(parts)

    return {
        "prompt": prompt,
        "agent": agent,
        "output_file": output_path,
        "min_output_bytes": min_bytes,
        "step": step,
    }


def get_next_execution_step(
    current_step: int,
    research_type: str = "undecided",
) -> dict[str, Any]:
    """P1 deterministic: compute the next step to execute, handling consolidation restart.

    After a context reset, current_step may be mid-consolidation-group.
    This function deterministically computes whether to restart the group
    or proceed to the next step.

    Args:
        current_step: Current step from SOT (steps 1-N completed)
        research_type: Research type for Phase 2 agent resolution

    Returns:
        dict with:
        - next_step: int (the step to execute next)
        - reason: "normal" | "restart_consolidated_group"
        - consolidated_group: list[int] | None (if restarting a group)
        - agent: str
        - description: str
    """
    if current_step < 0:
        current_step = 0  # Treat negative as "nothing completed"

    if current_step >= 211:
        return {
            "next_step": None,
            "reason": "workflow_completed",
            "consolidated_group": None,
            "agent": None,
            "description": "All 211 steps completed",
        }

    candidate = current_step + 1
    info = query_step(candidate, research_type)

    # Guard: query_step returns error dict for out-of-range steps
    if "error" in info:
        return {
            "next_step": candidate,
            "reason": "normal",
            "consolidated_group": None,
            "agent": "_orchestrator",
            "description": info.get("error", "Unknown step"),
        }

    consolidate_with = info.get("consolidate_with", [candidate])
    group_start = min(consolidate_with) if consolidate_with else candidate

    if len(consolidate_with) > 1 and group_start < candidate:
        # Mid-consolidation: current_step is inside a group that wasn't fully completed.
        # Restart from the beginning of the group.
        return {
            "next_step": group_start,
            "reason": "restart_consolidated_group",
            "consolidated_group": consolidate_with,
            "agent": info["agent"],
            "description": info["description"],
        }

    return {
        "next_step": candidate,
        "reason": "normal",
        "consolidated_group": consolidate_with if len(consolidate_with) > 1 else None,
        "agent": info["agent"],
        "description": info["description"],
    }


def list_agents() -> dict[str, list[int]]:
    """Return a mapping of agent_name → list of steps they handle.

    Uses 'quantitative' for Phase 2 steps (121-140) to enumerate all agents.
    Non-Phase-2 steps use 'undecided' (which safely defaults to quantitative).
    """
    result: dict[str, list[int]] = {}
    for step in range(1, 212):
        # Phase 2 steps need explicit research_type to avoid GAP-6 error
        rt = "quantitative" if 121 <= step <= 140 else "undecided"
        info = query_step(step, rt)
        agent = info.get("agent")
        if not agent:
            continue  # skip error entries
        if agent not in result:
            result[agent] = []
        result[agent].append(step)
    return result


def list_steps_for_agent(agent_name: str) -> list[int]:
    """Return all steps handled by a specific agent."""
    agents = list_agents()
    return agents.get(agent_name, [])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step Execution Registry — deterministic step→execution mapping"
    )
    parser.add_argument("--step", type=int, help="Step number to query (1-211)")
    parser.add_argument("--project-dir", help="Project directory (reads research_type from SOT)")
    parser.add_argument("--research-type",
                        choices=["quantitative", "qualitative", "mixed", "undecided"],
                        help="Research type override (default: read from SOT or 'undecided')")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--field", help="Output only a specific field value")
    parser.add_argument("--list-agents", action="store_true", help="List all agents and their step ranges")
    parser.add_argument("--list-steps", action="store_true", help="List steps for a specific agent (use with --agent)")
    parser.add_argument("--agent", help="Agent name (for --list-steps)")
    parser.add_argument("--invocation-plan", action="store_true",
                        help="Show invocation plan with completion status")
    parser.add_argument("--next-step", action="store_true",
                        help="Compute next execution step (handles consolidation restart)")
    parser.add_argument("--consolidated-prompt", action="store_true",
                        help="Generate fully rendered consolidated prompt (requires --step)")
    parser.add_argument("--single-prompt", action="store_true",
                        help="Generate fully rendered single-step prompt (requires --step)")
    parser.add_argument("--topic", help="Research topic for prompt generation")
    parser.add_argument("--context", help="Additional context for --single-prompt (e.g., chapter instructions)")
    parser.add_argument("--checklist", help="Path to todo-checklist.md for richer descriptions")

    args = parser.parse_args()

    # Determine research type
    research_type = "undecided"
    if args.research_type:
        research_type = args.research_type
    elif args.project_dir:
        try:
            import os
            sot_path = os.path.join(args.project_dir, "session.json")
            if os.path.exists(sot_path):
                with open(sot_path, "r", encoding="utf-8") as f:
                    sot = json.load(f)
                research_type = sot.get("research_type", "undecided")
        except (json.JSONDecodeError, IOError):
            pass  # Fall back to undecided

    if args.list_agents:
        agents = list_agents()
        if args.json:
            print(json.dumps(agents, indent=2))
        else:
            for agent_name in sorted(agents.keys()):
                steps = agents[agent_name]
                ranges = _compact_ranges(steps)
                print(f"{agent_name}: {ranges} ({len(steps)} steps)")
        return 0

    if args.list_steps:
        if not args.agent:
            print("ERROR: --list-steps requires --agent NAME", file=sys.stderr)
            return 1
        steps = list_steps_for_agent(args.agent)
        if args.json:
            print(json.dumps(steps))
        else:
            if steps:
                print(f"{args.agent}: steps {_compact_ranges(steps)}")
            else:
                print(f"{args.agent}: no steps assigned")
        return 0

    if args.invocation_plan:
        current_step = 0
        if args.project_dir:
            try:
                import os
                sot_path = os.path.join(args.project_dir, "session.json")
                if os.path.exists(sot_path):
                    with open(sot_path, "r", encoding="utf-8") as f:
                        sot = json.load(f)
                    current_step = sot.get("current_step", 0)
            except (json.JSONDecodeError, IOError):
                pass
        plan = get_invocation_plan(current_step)
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            for entry in plan:
                marker = {"completed": "x", "in_progress": ">", "pending": " "}
                m = marker.get(entry["status"], " ")
                print(f"  [{m}] {entry['invocation']:2d}/{entry['total']} "
                      f"Steps {entry['start']:3d}-{entry['end']:3d}: "
                      f"{entry['label']}")
        return 0

    if args.next_step:
        current_step = 0
        if args.project_dir:
            try:
                sot_path = os.path.join(args.project_dir, "session.json")
                if os.path.exists(sot_path):
                    with open(sot_path, "r", encoding="utf-8") as f:
                        sot = json.load(f)
                    current_step = sot.get("current_step", 0)
            except (json.JSONDecodeError, IOError):
                pass
        result = get_next_execution_step(current_step, research_type)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            ns = result["next_step"]
            if ns is None:
                print("Workflow completed (all 211 steps done)")
            else:
                print(f"Next step: {ns} ({result['description']})")
                print(f"  Agent: {result['agent']}")
                print(f"  Reason: {result['reason']}")
                if result["consolidated_group"]:
                    cg = result["consolidated_group"]
                    print(f"  Consolidated group: steps {cg[0]}-{cg[-1]}")
        return 0

    if args.consolidated_prompt:
        if args.step is None:
            parser.error("--consolidated-prompt requires --step")
            return 1
        info = query_step(args.step, research_type)
        cw = info.get("consolidate_with", [args.step])
        if len(cw) <= 1:
            print(f"ERROR: Step {args.step} is not part of a consolidated group",
                  file=sys.stderr)
            return 1
        topic = args.topic or "(research topic not provided)"
        result = generate_consolidated_prompt(
            first_step=min(cw),
            last_step=max(cw),
            research_topic=topic,
            research_type=research_type,
            checklist_path=args.checklist,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(result["prompt"])
        return 0

    if args.single_prompt:
        if args.step is None:
            parser.error("--single-prompt requires --step")
            return 1
        info = query_step(args.step, research_type)
        cw = info.get("consolidate_with", [args.step])
        if len(cw) > 1:
            print(f"ERROR: Step {args.step} is part of a consolidated group "
                  f"({min(cw)}-{max(cw)}). Use --consolidated-prompt instead.",
                  file=sys.stderr)
            return 1
        topic = args.topic or "(research topic not provided)"
        result = generate_single_step_prompt(
            step=args.step,
            research_topic=topic,
            research_type=research_type,
            context=args.context or "",
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(result["prompt"])
        return 0

    if args.step is None:
        parser.error("--step is required (or use --list-agents / --invocation-plan / --next-step)")
        return 1

    result = query_step(args.step, research_type)

    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        return 1

    # Resolve {project_dir} in execution_command when --project-dir is available
    if result.get("execution_command") and args.project_dir:
        result["execution_command"] = result["execution_command"].replace(
            "{project_dir}", args.project_dir,
        )

    if args.field:
        val = result.get(args.field)
        if val is None and args.field not in result:
            print(f"ERROR: Unknown field '{args.field}'", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(val))
        else:
            print(val if val is not None else "null")
        return 0

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Step {result['step']}: {result['description']}")
        print(f"  Agent: {result['agent']}")
        print(f"  Tier: {result['tier']}")
        print(f"  Phase: {result['phase']}")
        if result['wave']:
            print(f"  Wave: {result['wave']}")
        if result['critic']:
            critic_str = result['critic']
            if result.get('critic_secondary'):
                critic_str += f" + {result['critic_secondary']}"
            print(f"  Critic: {critic_str}")
            if result['dialogue']:
                print(f"  Dialogue: {result['dialogue_domain']}")
        if result['pccs_required']:
            print(f"  pCCS: {result['pccs_mode']}")
        if result['hitl']:
            print(f"  HITL: {result['hitl']}")
        if result['gate_before']:
            print(f"  Gate before: {result['gate_before']}")
        if result['gate_after']:
            print(f"  Gate after: {result['gate_after']}")
        print(f"  Output: {result['output_path']}")
        if len(result.get('consolidate_with', [])) > 1:
            cw = result['consolidate_with']
            print(f"  Consolidate: steps {cw[0]}-{cw[-1]} ({len(cw)} steps)")
            print(f"  Consolidated file: {result['consolidated_output_filename']}")
        if result.get('min_output_bytes', 0) > 0:
            print(f"  Min output: {result['min_output_bytes']} bytes")

    return 0


def _compact_ranges(steps: list[int]) -> str:
    """Convert [1,2,3,5,6,8] to '1-3, 5-6, 8'."""
    if not steps:
        return "none"
    sorted_steps = sorted(steps)
    ranges: list[str] = []
    start = sorted_steps[0]
    end = start
    for s in sorted_steps[1:]:
        if s == end + 1:
            end = s
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = end = s
    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ", ".join(ranges)


if __name__ == "__main__":
    sys.exit(main())
