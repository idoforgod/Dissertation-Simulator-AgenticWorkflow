#!/usr/bin/env python3
"""Unit tests for query_step.py — Step Execution Registry."""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from query_step import (
    _WRITING_STANDARD_SUFFIX,
    _compact_ranges,
    _get_critic_config,
    _get_gate_context,
    _get_pccs_config,
    _get_phase,
    _get_wave,
    generate_consolidated_prompt,
    generate_single_step_prompt,
    get_invocation_plan,
    get_next_execution_step,
    list_agents,
    list_steps_for_agent,
    query_step,
)


class TestQueryStepBasic(unittest.TestCase):
    """Test basic query_step functionality."""

    def test_valid_step_returns_dict(self):
        result = query_step(1)
        self.assertIsInstance(result, dict)
        self.assertNotIn("error", result)

    def test_invalid_step_zero(self):
        result = query_step(0)
        self.assertIn("error", result)

    def test_invalid_step_212(self):
        result = query_step(212)
        self.assertIn("error", result)

    def test_all_steps_have_agent(self):
        """Every step 1-211 must return a non-empty agent.

        Phase 2 steps (121-140) need explicit research_type (GAP-6 fix).
        """
        for step in range(1, 212):
            rt = "quantitative" if 121 <= step <= 140 else "undecided"
            result = query_step(step, rt)
            self.assertNotIn("error", result, f"Step {step} returned error")
            self.assertIn("agent", result, f"Step {step} missing 'agent' key")
            self.assertTrue(result["agent"], f"Step {step} has empty agent")

    def test_all_steps_have_required_fields(self):
        """Every step must have all required output fields.

        Phase 2 steps (121-140) need explicit research_type (GAP-6 fix).
        """
        required = {
            "step", "agent", "description", "tier", "phase",
            "wave", "critic", "dialogue_domain", "dialogue",
            "l2_enhanced", "pccs_required", "pccs_mode",
            "has_grounded_claims", "output_path",
            "gate_before", "gate_after", "hitl",
            "hitl_required", "translation_required",
            "execution_command",
        }
        for step in range(1, 212):
            rt = "quantitative" if 121 <= step <= 140 else "undecided"
            result = query_step(step, rt)
            missing = required - set(result.keys())
            self.assertEqual(missing, set(), f"Step {step} missing fields: {missing}")


class TestAgentMapping(unittest.TestCase):
    """Test H-1: Step→Agent mapping correctness."""

    def test_wave1_literature_searcher(self):
        for step in range(39, 43):
            result = query_step(step)
            self.assertEqual(result["agent"], "literature-searcher", f"Step {step}")

    def test_wave1_seminal_works(self):
        for step in range(43, 47):
            result = query_step(step)
            self.assertEqual(result["agent"], "seminal-works-analyst", f"Step {step}")

    def test_wave1_trend_analyst(self):
        for step in range(47, 51):
            result = query_step(step)
            self.assertEqual(result["agent"], "trend-analyst", f"Step {step}")

    def test_wave1_methodology_scanner(self):
        for step in range(51, 55):
            result = query_step(step)
            self.assertEqual(result["agent"], "methodology-scanner", f"Step {step}")

    def test_wave2_agents(self):
        expected = [
            (59, 62, "theoretical-framework-analyst"),
            (63, 66, "empirical-evidence-analyst"),
            (67, 70, "gap-identifier"),
            (71, 74, "variable-relationship-analyst"),
        ]
        for start, end, agent in expected:
            for step in range(start, end + 1):
                result = query_step(step)
                self.assertEqual(result["agent"], agent, f"Step {step}")

    def test_wave3_agents(self):
        expected = [
            (79, 82, "critical-reviewer"),
            (83, 86, "methodology-critic"),
            (87, 90, "limitation-analyst"),
            (91, 94, "future-direction-analyst"),
        ]
        for start, end, agent in expected:
            for step in range(start, end + 1):
                result = query_step(step)
                self.assertEqual(result["agent"], agent, f"Step {step}")

    def test_wave4_agents(self):
        for step in range(99, 103):
            self.assertEqual(query_step(step)["agent"], "synthesis-agent")
        for step in range(103, 107):
            self.assertEqual(query_step(step)["agent"], "conceptual-model-builder")

    def test_gate_steps_orchestrator(self):
        for step in [55, 57, 58, 75, 77, 78, 95, 97, 98]:
            result = query_step(step)
            self.assertEqual(result["agent"], "_orchestrator", f"Gate step {step}")

    def test_translation_gate_steps(self):
        for step in [56, 76, 96, 108, 113]:
            result = query_step(step)
            self.assertEqual(result["agent"], "translator", f"Translation step {step}")

    def test_phase3_thesis_writer(self):
        for step in [143, 144, 145, 146, 147, 148, 151, 153, 155, 158]:
            result = query_step(step)
            self.assertEqual(result["agent"], "thesis-writer", f"Step {step}")

    def test_phase4_agents(self):
        self.assertEqual(query_step(165)["agent"], "publication-strategist")
        self.assertEqual(query_step(166)["agent"], "journal-matcher")
        self.assertEqual(query_step(167)["agent"], "submission-preparer")
        self.assertEqual(query_step(168)["agent"], "cover-letter-writer")

    def test_phase6_all_translator(self):
        for step in range(181, 211):
            result = query_step(step)
            self.assertEqual(result["agent"], "translator", f"Step {step}")


class TestResearchTypeVariants(unittest.TestCase):
    """Test Phase 2 agent variation by research type."""

    def test_quantitative_step123(self):
        result = query_step(123, "quantitative")
        self.assertEqual(result["agent"], "quantitative-designer")

    def test_qualitative_step123(self):
        result = query_step(123, "qualitative")
        self.assertEqual(result["agent"], "paradigm-consultant")

    def test_mixed_step123(self):
        result = query_step(123, "mixed")
        self.assertEqual(result["agent"], "mixed-methods-designer")

    def test_undecided_phase2_returns_error(self):
        """GAP-6: Phase 2 steps with undecided research_type return error."""
        result = query_step(123, "undecided")
        self.assertIn("error", result)
        self.assertIn("HITL-3", result["error"])

    def test_quant_sampling(self):
        result = query_step(125, "quantitative")
        self.assertEqual(result["agent"], "sampling-designer")

    def test_qual_sampling(self):
        result = query_step(125, "qualitative")
        self.assertEqual(result["agent"], "participant-selector")


class TestTierSelection(unittest.TestCase):
    """Test H-4: Tier selection correctness."""

    def test_orchestrator_steps_tier3(self):
        """Orchestrator-direct steps should be Tier 3."""
        for step in [1, 5, 35, 55, 58, 115]:
            result = query_step(step)
            if result["agent"] == "_orchestrator":
                self.assertEqual(result["tier"], 3, f"Step {step}")

    def test_agent_steps_tier2(self):
        """Agent-delegated steps should be Tier 2 (quality-first default)."""
        for step in [39, 47, 59, 79, 99, 143, 165]:
            result = query_step(step)
            self.assertEqual(result["tier"], 2, f"Step {step}")


class TestCriticRouting(unittest.TestCase):
    """Test H-3: Critic agent routing correctness."""

    def test_wave1_research_dialogue(self):
        for step in range(39, 55):
            cfg = _get_critic_config(step)
            self.assertEqual(cfg["critic"], "fact-checker", f"Step {step}")
            self.assertEqual(cfg["critic_secondary"], "reviewer", f"Step {step}")
            self.assertEqual(cfg["dialogue_domain"], "research", f"Step {step}")
            self.assertTrue(cfg["dialogue"], f"Step {step}")

    def test_wave2_research_dialogue(self):
        for step in range(59, 75):
            cfg = _get_critic_config(step)
            self.assertTrue(cfg["dialogue"], f"Step {step}")
            self.assertEqual(cfg["dialogue_domain"], "research", f"Step {step}")

    def test_phase2_development_dialogue(self):
        for step in range(123, 132):
            cfg = _get_critic_config(step)
            self.assertEqual(cfg["critic"], "code-reviewer", f"Step {step}")
            self.assertEqual(cfg["dialogue_domain"], "development", f"Step {step}")

    def test_phase3_review_cycles_single_review(self):
        for step in [152, 154]:
            cfg = _get_critic_config(step)
            self.assertEqual(cfg["critic"], "reviewer", f"Step {step}")
            self.assertFalse(cfg["dialogue"], f"Step {step}")
            self.assertTrue(cfg["l2_enhanced"], f"Step {step}")

    def test_gate_steps_l2_enhanced(self):
        for step in [55, 75, 95, 107]:
            cfg = _get_critic_config(step)
            self.assertTrue(cfg["l2_enhanced"], f"Gate step {step}")

    def test_orchestrator_steps_no_critic(self):
        for step in [1, 5, 58, 115]:
            cfg = _get_critic_config(step)
            self.assertIsNone(cfg["critic"], f"Step {step}")
            self.assertFalse(cfg["l2_enhanced"], f"Step {step}")


class TestPCCSMode(unittest.TestCase):
    """Test H-2: pCCS mode selection correctness."""

    def test_wave1_degraded(self):
        for step in range(39, 55):
            cfg = _get_pccs_config(step)
            self.assertTrue(cfg["pccs_required"], f"Step {step}")
            self.assertEqual(cfg["pccs_mode"], "DEGRADED", f"Step {step}")

    def test_wave4_full(self):
        for step in range(99, 107):
            cfg = _get_pccs_config(step)
            self.assertTrue(cfg["pccs_required"], f"Step {step}")
            self.assertEqual(cfg["pccs_mode"], "FULL", f"Step {step}")

    def test_gate_steps_no_pccs(self):
        """Gate steps are cross-validation, not content — no pCCS needed."""
        for step in [55, 75, 95]:
            cfg = _get_pccs_config(step)
            self.assertFalse(cfg["pccs_required"], f"Gate step {step}")

    def test_srcs_eval_step_full(self):
        """SRCS evaluation step (107) produces evaluation, not claims."""
        cfg = _get_pccs_config(107)
        self.assertFalse(cfg["pccs_required"])

    def test_phase3_chapters_full(self):
        for step in range(143, 152):
            cfg = _get_pccs_config(step)
            self.assertTrue(cfg["pccs_required"], f"Step {step}")
            self.assertEqual(cfg["pccs_mode"], "FULL", f"Step {step}")

    def test_orchestrator_steps_no_pccs(self):
        for step in [1, 5, 35, 115]:
            cfg = _get_pccs_config(step)
            self.assertFalse(cfg["pccs_required"], f"Step {step}")
            self.assertIsNone(cfg["pccs_mode"], f"Step {step}")

    def test_translation_steps_no_pccs(self):
        for step in range(181, 211):
            cfg = _get_pccs_config(step)
            self.assertFalse(cfg["pccs_required"], f"Step {step}")


class TestWavePhaseMapping(unittest.TestCase):
    """Test wave and phase mapping."""

    def test_wave_numbers(self):
        self.assertEqual(_get_wave(39), 1)
        self.assertEqual(_get_wave(54), 1)
        self.assertEqual(_get_wave(59), 2)
        self.assertEqual(_get_wave(74), 2)
        self.assertEqual(_get_wave(79), 3)
        self.assertEqual(_get_wave(94), 3)
        self.assertEqual(_get_wave(99), 4)
        self.assertEqual(_get_wave(106), 4)
        self.assertEqual(_get_wave(111), 5)
        self.assertEqual(_get_wave(114), 5)

    def test_non_wave_steps(self):
        self.assertIsNone(_get_wave(1))
        self.assertIsNone(_get_wave(55))
        self.assertIsNone(_get_wave(115))
        self.assertIsNone(_get_wave(143))

    def test_phase_names(self):
        self.assertEqual(_get_phase(1), "phase_0_init")
        self.assertEqual(_get_phase(9), "phase_0a_topic")
        self.assertEqual(_get_phase(15), "phase_0d_learning")
        self.assertEqual(_get_phase(39), "wave_1")
        self.assertEqual(_get_phase(55), "gate_1")
        self.assertEqual(_get_phase(107), "srcs_full")
        self.assertEqual(_get_phase(121), "phase_2_design")
        self.assertEqual(_get_phase(141), "phase_3_writing")
        self.assertEqual(_get_phase(165), "phase_4_publication")
        self.assertEqual(_get_phase(181), "phase_6_translation")


class TestGateContext(unittest.TestCase):
    """Test gate before/after context."""

    def test_pre_gate1(self):
        ctx = _get_gate_context(39)
        self.assertIsNone(ctx["gate_before"])
        self.assertIsNone(ctx["gate_after"])

    def test_gate1_steps(self):
        ctx = _get_gate_context(55)
        self.assertIsNone(ctx["gate_before"])
        self.assertEqual(ctx["gate_after"], "gate-1")

    def test_wave2_gate_context(self):
        ctx = _get_gate_context(59)
        self.assertEqual(ctx["gate_before"], "gate-1")
        self.assertEqual(ctx["gate_after"], "gate-2")

    def test_wave3_gate_context(self):
        ctx = _get_gate_context(79)
        self.assertEqual(ctx["gate_before"], "gate-2")
        self.assertEqual(ctx["gate_after"], "gate-3")


class TestHITLMapping(unittest.TestCase):
    """Test HITL checkpoint mapping."""

    def test_hitl1_steps(self):
        for step in range(35, 39):
            result = query_step(step)
            self.assertEqual(result["hitl"], "hitl-1", f"Step {step}")
            self.assertTrue(result["hitl_required"], f"Step {step}")

    def test_hitl2_steps(self):
        for step in range(115, 121):
            result = query_step(step)
            self.assertEqual(result["hitl"], "hitl-2", f"Step {step}")

    def test_non_hitl_step(self):
        result = query_step(39)
        self.assertIsNone(result["hitl"])
        self.assertFalse(result["hitl_required"])


class TestTranslation(unittest.TestCase):
    """Test translation step detection."""

    def test_gate_translation_steps(self):
        for step in [56, 76, 96, 108, 113]:
            result = query_step(step)
            self.assertTrue(result["translation_required"], f"Step {step}")

    def test_phase6_all_translation(self):
        for step in range(181, 211):
            result = query_step(step)
            self.assertTrue(result["translation_required"], f"Step {step}")

    def test_non_translation_step(self):
        result = query_step(39)
        self.assertFalse(result["translation_required"])


class TestListAgents(unittest.TestCase):
    """Test agent listing functions."""

    def test_list_agents_returns_dict(self):
        agents = list_agents()
        self.assertIsInstance(agents, dict)
        self.assertGreater(len(agents), 10)

    def test_list_agents_covers_all_steps(self):
        agents = list_agents()
        all_steps = set()
        for steps in agents.values():
            all_steps.update(steps)
        for step in range(1, 211):
            self.assertIn(step, all_steps, f"Step {step} not covered by any agent")

    def test_list_steps_for_known_agent(self):
        steps = list_steps_for_agent("literature-searcher")
        self.assertGreater(len(steps), 0)
        self.assertIn(39, steps)

    def test_list_steps_for_unknown_agent(self):
        steps = list_steps_for_agent("nonexistent-agent")
        self.assertEqual(steps, [])


class TestCompactRanges(unittest.TestCase):
    """Test _compact_ranges helper."""

    def test_single(self):
        self.assertEqual(_compact_ranges([5]), "5")

    def test_consecutive(self):
        self.assertEqual(_compact_ranges([1, 2, 3]), "1-3")

    def test_mixed(self):
        self.assertEqual(_compact_ranges([1, 2, 3, 5, 6, 8]), "1-3, 5-6, 8")

    def test_empty(self):
        self.assertEqual(_compact_ranges([]), "none")


class TestCLI(unittest.TestCase):
    """Test CLI invocation."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "query_step.py")
        return subprocess.run(
            [sys.executable, script, *args],
            capture_output=True, text=True, timeout=10,
        )

    def test_cli_step_json(self):
        result = self._run("--step", "47", "--json")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["step"], 47)
        self.assertEqual(data["agent"], "trend-analyst")

    def test_cli_step_field(self):
        result = self._run("--step", "47", "--field", "agent")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "trend-analyst")

    def test_cli_invalid_step(self):
        result = self._run("--step", "0", "--json")
        self.assertNotEqual(result.returncode, 0)

    def test_cli_list_agents(self):
        result = self._run("--list-agents")
        self.assertEqual(result.returncode, 0)
        self.assertIn("literature-searcher", result.stdout)

    def test_cli_list_agents_json(self):
        result = self._run("--list-agents", "--json")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("literature-searcher", data)

    def test_cli_list_steps(self):
        result = self._run("--list-steps", "--agent", "trend-analyst")
        self.assertEqual(result.returncode, 0)
        self.assertIn("trend-analyst", result.stdout)

    def test_cli_research_type(self):
        result = self._run("--step", "123", "--research-type", "qualitative", "--json")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["agent"], "paradigm-consultant")

    def test_cli_human_readable(self):
        result = self._run("--step", "47")
        self.assertEqual(result.returncode, 0)
        self.assertIn("trend-analyst", result.stdout)
        self.assertIn("Tier: 2", result.stdout)


# =============================================================================
# F-1: Tests for get_invocation_plan()
# =============================================================================

class TestGetInvocationPlan(unittest.TestCase):
    """Tests for get_invocation_plan() — P1 invocation plan computation."""

    def test_returns_list(self):
        plan = get_invocation_plan(0)
        self.assertIsInstance(plan, list)
        self.assertGreater(len(plan), 0)

    def test_total_field_consistent(self):
        plan = get_invocation_plan(0)
        total = plan[0]["total"]
        for entry in plan:
            self.assertEqual(entry["total"], total)

    def test_all_entries_have_required_keys(self):
        plan = get_invocation_plan(0)
        for entry in plan:
            self.assertIn("invocation", entry)
            self.assertIn("start", entry)
            self.assertIn("end", entry)
            self.assertIn("label", entry)
            self.assertIn("status", entry)
            self.assertIn("total", entry)

    def test_covers_all_211_steps(self):
        """Invocation plan must cover steps 1-211 with no gaps."""
        plan = get_invocation_plan(0)
        # First entry starts at 1
        self.assertEqual(plan[0]["start"], 1)
        # Last entry ends at 211
        self.assertEqual(plan[-1]["end"], 211)
        # No gaps between entries
        for i in range(1, len(plan)):
            self.assertEqual(plan[i]["start"], plan[i - 1]["end"] + 1)

    def test_step_0_all_pending(self):
        plan = get_invocation_plan(0)
        for entry in plan:
            self.assertEqual(entry["status"], "pending")

    def test_step_211_all_completed(self):
        plan = get_invocation_plan(211)
        for entry in plan:
            self.assertEqual(entry["status"], "completed")

    def test_mid_workflow_mixed_status(self):
        plan = get_invocation_plan(50)
        statuses = [e["status"] for e in plan]
        self.assertIn("completed", statuses)
        self.assertIn("in_progress", statuses)
        self.assertIn("pending", statuses)

    def test_exactly_one_in_progress(self):
        """At any valid step, there should be exactly one in_progress invocation."""
        for step in [1, 50, 100, 150, 200]:
            plan = get_invocation_plan(step)
            in_progress = [e for e in plan if e["status"] == "in_progress"]
            self.assertEqual(len(in_progress), 1, f"step={step}")

    def test_invocation_numbers_sequential(self):
        plan = get_invocation_plan(0)
        for i, entry in enumerate(plan, 1):
            self.assertEqual(entry["invocation"], i)


# =============================================================================
# F-1: Tests for get_next_execution_step()
# =============================================================================

class TestGetNextExecutionStep(unittest.TestCase):
    """Tests for get_next_execution_step() — P1 next step computation."""

    def test_step_0_returns_step_1(self):
        result = get_next_execution_step(0)
        self.assertEqual(result["next_step"], 1)
        self.assertEqual(result["reason"], "normal")

    def test_step_211_completed(self):
        result = get_next_execution_step(211)
        self.assertIsNone(result["next_step"])
        self.assertEqual(result["reason"], "workflow_completed")
        self.assertIsNone(result["agent"])

    def test_step_212_completed(self):
        result = get_next_execution_step(212)
        self.assertIsNone(result["next_step"])
        self.assertEqual(result["reason"], "workflow_completed")

    def test_negative_step_no_crash(self):
        """F-3: Negative step should not crash (treated as 0)."""
        result = get_next_execution_step(-1)
        self.assertEqual(result["next_step"], 1)
        self.assertEqual(result["reason"], "normal")

    def test_negative_large_no_crash(self):
        result = get_next_execution_step(-100)
        self.assertEqual(result["next_step"], 1)

    def test_mid_consolidation_restarts_group(self):
        """current_step=40 means steps 1-40 done; step 41 is next but 39-42 is a group."""
        result = get_next_execution_step(40)
        self.assertEqual(result["next_step"], 39)
        self.assertEqual(result["reason"], "restart_consolidated_group")
        self.assertIsNotNone(result["consolidated_group"])
        self.assertEqual(min(result["consolidated_group"]), 39)
        self.assertEqual(max(result["consolidated_group"]), 42)

    def test_group_start_returns_normal(self):
        """current_step=38 means start fresh with group 39-42."""
        result = get_next_execution_step(38)
        self.assertEqual(result["next_step"], 39)
        self.assertEqual(result["reason"], "normal")
        self.assertIsNotNone(result["consolidated_group"])
        self.assertEqual(result["consolidated_group"], [39, 40, 41, 42])

    def test_group_end_returns_next_group(self):
        """current_step=42 means group 39-42 done; next is 43-46."""
        result = get_next_execution_step(42)
        self.assertEqual(result["next_step"], 43)
        self.assertEqual(result["reason"], "normal")
        self.assertIsNotNone(result["consolidated_group"])
        self.assertEqual(min(result["consolidated_group"]), 43)

    def test_single_step_no_group(self):
        """_orchestrator steps return no consolidated_group."""
        result = get_next_execution_step(0)  # next is step 1 (_orchestrator)
        self.assertIsNone(result["consolidated_group"])

    def test_has_agent_field(self):
        result = get_next_execution_step(38)
        self.assertIn("agent", result)
        self.assertIsNotNone(result["agent"])

    def test_has_description_field(self):
        result = get_next_execution_step(38)
        self.assertIn("description", result)
        self.assertIsNotNone(result["description"])

    def test_all_wave1_mid_group_restarts(self):
        """Every mid-group step in wave 1 should trigger restart."""
        for step in [39, 40, 41]:  # mid-group for [39,40,41,42]
            result = get_next_execution_step(step)
            self.assertEqual(result["reason"], "restart_consolidated_group",
                             f"step={step} should restart")
            self.assertEqual(result["next_step"], 39, f"step={step}")


# =============================================================================
# F-1: Tests for generate_consolidated_prompt()
# =============================================================================

class TestGenerateConsolidatedPrompt(unittest.TestCase):
    """Tests for generate_consolidated_prompt() — P1 prompt generation."""

    def test_normal_group_returns_dict(self):
        result = generate_consolidated_prompt(39, 42, "Impact of AI on education")
        self.assertIsInstance(result, dict)
        self.assertIn("prompt", result)
        self.assertIn("agent", result)
        self.assertIn("output_file", result)
        self.assertIn("min_output_bytes", result)

    def test_prompt_contains_all_steps(self):
        result = generate_consolidated_prompt(39, 42, "AI in education")
        prompt = result["prompt"]
        for step in range(39, 43):
            self.assertIn(f"Step {step}", prompt)

    def test_prompt_contains_research_topic(self):
        topic = "Machine learning in healthcare"
        result = generate_consolidated_prompt(39, 42, topic)
        self.assertIn(topic, result["prompt"])

    def test_output_file_matches_group(self):
        result = generate_consolidated_prompt(39, 42, "test topic")
        self.assertIn("step-039-to-042", result["output_file"])
        self.assertIn("literature-searcher", result["output_file"])

    def test_agent_is_correct(self):
        result = generate_consolidated_prompt(39, 42, "test topic")
        self.assertEqual(result["agent"], "literature-searcher")

    def test_min_output_bytes_positive(self):
        result = generate_consolidated_prompt(39, 42, "test topic")
        self.assertGreater(result["min_output_bytes"], 0)

    def test_zero_unfilled_template_variables(self):
        """The core hallucination prevention: no {placeholder} in output."""
        result = generate_consolidated_prompt(39, 42, "test topic")
        prompt = result["prompt"]
        import re
        placeholders = re.findall(r'\{[a-z_]+\}', prompt)
        self.assertEqual(placeholders, [], f"Found unfilled templates: {placeholders}")

    def test_prompt_has_structure_requirement(self):
        result = generate_consolidated_prompt(39, 42, "test topic")
        self.assertIn("## Step", result["prompt"])
        self.assertIn("GroundedClaim", result["prompt"])

    # --- Input validation tests (F-2) ---

    def test_first_step_greater_than_last_raises(self):
        with self.assertRaises(ValueError):
            generate_consolidated_prompt(42, 39, "test")

    def test_step_out_of_range_low_raises(self):
        with self.assertRaises(ValueError):
            generate_consolidated_prompt(0, 3, "test")

    def test_step_out_of_range_high_raises(self):
        with self.assertRaises(ValueError):
            generate_consolidated_prompt(209, 212, "test")

    def test_subset_of_group_raises(self):
        """F-2: Calling with subset (40,42) when group is (39,42) must raise."""
        with self.assertRaises(ValueError):
            generate_consolidated_prompt(40, 42, "test")

    def test_partial_group_raises(self):
        """F-2: Calling with (39,41) when group is (39,42) must raise."""
        with self.assertRaises(ValueError):
            generate_consolidated_prompt(39, 41, "test")

    def test_single_step_raises(self):
        """F-2: Single-step groups (e.g. step 211) must not use consolidated prompt."""
        with self.assertRaises(ValueError) as ctx:
            generate_consolidated_prompt(211, 211, "test")
        self.assertIn("not part of a multi-step consolidation group", str(ctx.exception))

    def test_non_consolidatable_step_raises(self):
        """F-2: Steps in _NO_CONSOLIDATE_AGENTS (translator) must reject."""
        with self.assertRaises(ValueError):
            generate_consolidated_prompt(181, 181, "test")

    def test_wave2_group(self):
        result = generate_consolidated_prompt(59, 62, "test topic")
        self.assertEqual(result["agent"], "theoretical-framework-analyst")
        self.assertIn("step-059-to-062", result["output_file"])

    def test_wave3_group(self):
        result = generate_consolidated_prompt(79, 82, "test topic")
        self.assertEqual(result["agent"], "critical-reviewer")

    def test_wave4_group(self):
        result = generate_consolidated_prompt(99, 102, "test topic")
        self.assertEqual(result["agent"], "synthesis-agent")

    def test_prompt_contains_writing_standard(self):
        """H-8: Consolidated prompt must include doctoral writing standard."""
        result = generate_consolidated_prompt(39, 42, "test topic")
        prompt = result["prompt"]
        self.assertIn("WRITING STANDARD", prompt)
        self.assertIn("Clarity", prompt)
        self.assertIn("Conciseness", prompt)
        self.assertIn("Academic Rigor", prompt)
        self.assertIn("Logical Flow", prompt)


# =============================================================================
# F-3: Tests for generate_single_step_prompt()
# =============================================================================

class TestGenerateSingleStepPrompt(unittest.TestCase):
    """Tests for generate_single_step_prompt() — P1 single-step prompt (H-8)."""

    def test_returns_dict_with_required_keys(self):
        result = generate_single_step_prompt(143, "AI safety in LLMs")
        self.assertIsInstance(result, dict)
        self.assertIn("prompt", result)
        self.assertIn("agent", result)
        self.assertIn("output_file", result)
        self.assertIn("min_output_bytes", result)
        self.assertIn("step", result)

    def test_prompt_contains_step_and_topic(self):
        topic = "Impact of AI on education"
        result = generate_single_step_prompt(143, topic)
        self.assertIn("step 143", result["prompt"].lower())
        self.assertIn(topic, result["prompt"])

    def test_prompt_contains_writing_standard(self):
        """H-8: Single-step prompt MUST include doctoral writing standard."""
        result = generate_single_step_prompt(143, "test topic")
        prompt = result["prompt"]
        self.assertIn("WRITING STANDARD", prompt)
        self.assertIn("Clarity", prompt)
        self.assertIn("Conciseness", prompt)
        self.assertIn("Academic Rigor", prompt)
        self.assertIn("Logical Flow", prompt)

    def test_prompt_contains_output_path(self):
        result = generate_single_step_prompt(143, "test topic")
        self.assertIn("Output to:", result["prompt"])

    def test_agent_matches_registry(self):
        result = generate_single_step_prompt(143, "test topic")
        self.assertEqual(result["agent"], "thesis-writer")

    def test_context_included_when_provided(self):
        ctx = "Reference wave-results/ for this chapter"
        result = generate_single_step_prompt(143, "test topic", context=ctx)
        self.assertIn(ctx, result["prompt"])

    def test_context_absent_when_empty(self):
        result = generate_single_step_prompt(143, "test topic", context="")
        self.assertNotIn("Context:", result["prompt"])

    def test_zero_unfilled_template_variables(self):
        """H-8: No {placeholder} in output — same guarantee as consolidated."""
        result = generate_single_step_prompt(143, "test topic")
        prompt = result["prompt"]
        import re
        placeholders = re.findall(r'\{[a-z_]+\}', prompt)
        self.assertEqual(placeholders, [], f"Found unfilled templates: {placeholders}")

    def test_step_out_of_range_low_raises(self):
        with self.assertRaises(ValueError):
            generate_single_step_prompt(0, "test")

    def test_step_out_of_range_high_raises(self):
        with self.assertRaises(ValueError):
            generate_single_step_prompt(212, "test")

    def test_consolidated_group_step_raises(self):
        """Must reject steps that are part of a multi-step group."""
        with self.assertRaises(ValueError) as ctx:
            generate_single_step_prompt(39, "test")  # Part of [39,40,41,42]
        self.assertIn("consolidation group", str(ctx.exception))

    def test_grounded_claims_for_tier_a(self):
        """Tier A steps should include GroundedClaim instruction."""
        # Step 143 (thesis-writer) has has_grounded_claims=True
        result = generate_single_step_prompt(143, "test topic")
        self.assertIn("GroundedClaim", result["prompt"])

    def test_min_output_bytes_for_phase3(self):
        """Phase 3 chapter steps should have min_output_bytes > 0."""
        result = generate_single_step_prompt(143, "test topic")
        self.assertGreater(result["min_output_bytes"], 0)

    def test_writing_standard_suffix_is_constant(self):
        """Verify _WRITING_STANDARD_SUFFIX is non-empty and contains key phrases."""
        self.assertGreater(len(_WRITING_STANDARD_SUFFIX), 100)
        self.assertIn("WRITING STANDARD", _WRITING_STANDARD_SUFFIX)
        self.assertIn("doctoral-writing", _WRITING_STANDARD_SUFFIX)


if __name__ == "__main__":
    unittest.main()
