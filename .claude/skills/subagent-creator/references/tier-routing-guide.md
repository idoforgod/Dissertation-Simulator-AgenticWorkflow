# Tier Routing Guide for Generated Agents

How agents are routed to execution tiers by the Orchestrator via query_step.py.

## Tier System Overview

| Tier | Execution Model | When Used | Context |
|------|----------------|-----------|---------|
| Tier 1 | Agent Team (parallel) | EXPERIMENTAL — multiple agents work simultaneously | Shared team context, TaskCreate/SendMessage |
| Tier 2 | Sub-agent (sequential) | DEFAULT — single agent gets full context dedication | `Agent(subagent_type="{name}")` |
| Tier 3 | Orchestrator direct | SOT updates, validation, HITL, translation validation | No delegation — orchestrator executes directly |

## Default: Tier 2

**All new agents should target Tier 2 unless explicitly designed otherwise.**

Tier 2 gives each agent full context window dedication, ensuring maximum quality output.
This aligns with Absolute Criteria 1 (quality over efficiency).

## Tier Assignment Rules

### Tier 2 (Sub-agent) — Most Agents

Assign Tier 2 when:
- Agent produces content (research, writing, analysis)
- Agent needs to read multiple files for context
- Agent produces GroundedClaim output
- Agent requires deep reasoning (opus model)

### Tier 3 (Orchestrator Direct) — Orchestrator Tasks

Assign Tier 3 when:
- Step is SOT update (`--advance`, `--set-substep`)
- Step is validation-only (`validate_*.py` execution)
- Step is HITL checkpoint (user approval)
- Step is translation validation (T1-T12 P1 checks)
- Step is archiving/cleanup

### Tier 1 (Agent Team) — Experimental

Assign Tier 1 only when:
- Multiple agents can work truly in parallel on independent sub-tasks
- Each agent's output is self-contained (no dependency on other team members' output)
- All agents write to different files (no conflicts)

**Known Limitations:**
- TaskCreate IDs are session-scoped (lost on context reset)
- blocks/blockedBy dependencies are not implemented
- Fallback to Tier 2 on any team coordination failure

## Integration with query_step.py

Generated agents are registered in `query_step.py` (Step Execution Registry):

```python
# Example: assigning a new agent to steps 45-48
STEP_REGISTRY = {
    45: {"agent": "my-new-agent", "tier": 2, "critic": "fact-checker", ...},
    46: {"agent": "my-new-agent", "tier": 2, "critic": "fact-checker", ...},
    ...
}
```

**Fields returned by query_step.py for each step:**
- `agent`: Agent name (must match `.claude/agents/{name}.md`)
- `tier`: 2 or 3 (Tier 1 is dynamic, not pre-assigned)
- `critic`: Which critic reviews this agent's output (null = none)
- `critic_secondary`: Second critic for Adversarial Dialogue (null = single-review)
- `dialogue_domain`: "research" | "development" | null
- `pccs_mode`: "FULL" | "DEGRADED" | null
- `pccs_required`: true | false
- `hitl`: HITL checkpoint name or null
- `output_path`: Expected output file path pattern
- `l2_enhanced`: Whether L2 Enhanced Review is required

## maxTurns Guidelines

| Agent Complexity | Recommended maxTurns | Examples |
|-----------------|---------------------|---------|
| Simple utility | 5-10 | Format checker, file validator |
| Standard analysis | 15-25 | Literature searcher, data processor |
| Complex synthesis | 25-40 | Thesis writer, critical reviewer |
| Orchestrator | 100-150 | thesis-orchestrator (150) |

**Rule**: Set maxTurns to 1.5x the expected turns needed. Too low = premature termination.
Too high = wasted context if agent loops.

## Critic Assignment

| Agent Domain | Primary Critic | Dialogue? |
|-------------|---------------|-----------|
| Research content (literature, theory) | @fact-checker | Yes — @fact-checker + @reviewer parallel |
| Development (code, design, methodology) | @code-reviewer | Yes — single critic dialogue |
| Review/validation (gates, quality checks) | @reviewer | Single-review (no dialogue) |
| Translation | @translation-verifier | Layer 2 only (high-importance steps) |
| Utility (formatting, archiving) | None | No critic needed |
