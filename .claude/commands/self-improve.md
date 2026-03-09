---
description: "Knowledge-Based Self-Improvement — analyze errors and improvements, generate permanent insights for AGENTS.md"
---

# /self-improve — Knowledge-Based Self-Improvement (KBSI)

Analyzes recent workflow execution for errors and improvements, extracts
generalizable insights, and permanently stores them in AGENTS.md §11.

Uses a P1-sandwich architecture to prevent hallucinations:

```
P1 Validation (SI-1~SI-6) → LLM Analysis → P1 Application (marker-based append)
```

SOT: `self-improvement-logs/state.json`
Insights: `AGENTS.md §11.4` (within SELF-IMPROVEMENT-START/END markers)
Track 2 queued changes: `self-improvement-logs/queued-changes/`

---

## Orchestration (main context executes — do NOT delegate to sub-agent)

Announce to user: "Starting KBSI self-improvement analysis."

### Step 1: Gather Context (P1)

Check KBSI system status:
```bash
python3 .claude/hooks/scripts/self_improve_manager.py \
  --status --si-dir self-improvement-logs
```

Report current state to user (applied/pending/rejected counts).

### Step 2: Analyze Knowledge Index

Read the knowledge-index.jsonl to identify recurring error patterns:
```
.claude/context-snapshots/knowledge-index.jsonl
```

Look for:
- **Error patterns** that appear ≥ 2 times across sessions (`error_patterns` field)
- **Rejected hypotheses** that recur (`rejected_hypotheses` field)
- **Success patterns** that could be generalized (`success_patterns` field)

### Step 3: Generate Insights (LLM)

For each candidate pattern, formulate an insight with:
- **Title**: Short descriptive name
- **Condition**: When does this rule apply? (specific, testable)
- **Rule**: What should be done? (actionable, unambiguous)
- **Rationale**: Why? (with evidence from KI data)
- **Type**: SAFE (additive) or STRUCTURAL (changes core behavior)
- **Error Type**: Associated error category (if Track 1)

Quality criteria — ALL 4 must pass:
1. **Recurrence**: Pattern appeared ≥ 2 times
2. **Generalizability**: Applies beyond the specific instance
3. **Actionability**: Produces a concrete, testable rule
4. **Non-redundancy**: Not already covered by existing §11 insights

### Step 4: Register Insights (P1)

For each insight, register via CLI:
```bash
python3 .claude/hooks/scripts/self_improve_manager.py \
  --register --si-dir self-improvement-logs \
  --title "..." \
  --condition "..." \
  --rule "..." \
  --rationale "..." \
  --type SAFE \
  --error-type "..."
```

Note: The P1 script auto-upgrades SAFE → STRUCTURAL if immutable boundary
keywords or hub file references are detected.

### Step 5: Validate (P1)

Validate all pending insights:
```bash
python3 .claude/hooks/scripts/validate_self_improvement.py \
  --validate-all --si-dir self-improvement-logs
```

Report SI-1~SI-6 results to user.

Also verify AGENTS.md markers:
```bash
python3 .claude/hooks/scripts/validate_self_improvement.py \
  --check-markers --agents-md AGENTS.md
```

### Step 6: User Approval

Present insights to user for review:
- **SAFE** insights: recommend auto-apply (user can override)
- **STRUCTURAL** insights: **require explicit user approval** (mandatory)

Wait for user decision before proceeding.

### Step 7: Apply Approved Insights

For each approved insight:

1. Mark as applied in SOT:
```bash
python3 .claude/hooks/scripts/self_improve_manager.py \
  --apply --si-dir self-improvement-logs --id SI-NNN
```

2. Append to AGENTS.md §11 (P1 marker-based):
```bash
python3 .claude/hooks/scripts/self_improve_manager.py \
  --apply-to-agents-md --si-dir self-improvement-logs \
  --agents-md AGENTS.md --id SI-NNN
```

3. Sync CLAUDE.md summary:
```bash
python3 .claude/hooks/scripts/self_improve_manager.py \
  --sync-claude-md --si-dir self-improvement-logs \
  --claude-md CLAUDE.md
```

### Step 8: Track 2 — Component Improvements (if applicable)

If workflow improvements were identified:

1. Queue changes:
```bash
python3 .claude/hooks/scripts/self_improve_manager.py \
  --queue-change --si-dir self-improvement-logs \
  --target "path/to/file" \
  --change-type SAFE \
  --description "..."
```

2. Validate queue:
```bash
python3 .claude/hooks/scripts/self_improve_manager.py \
  --validate-queued-changes --si-dir self-improvement-logs
```

3. STRUCTURAL changes: present to user for approval
4. Hook .py changes: queued for end-of-run (not immediate)
5. Agent .md changes: can be applied immediately after test

### Step 9: Report

Report to user:
- How many insights registered
- How many applied / rejected
- Any STRUCTURAL changes pending approval
- Any Track 2 queued changes

---

## Safety Rules

1. **LLM never directly edits AGENTS.md** — all writes go through `self_improve_manager.py --apply-to-agents-md` (P1 marker-based)
2. **LLM never directly edits CLAUDE.md** — all syncs go through `self_improve_manager.py --sync-claude-md` (P1 marker-based)
3. **STRUCTURAL insights always need user approval** — no exceptions
4. **`_context_lib.py` changes are always STRUCTURAL** — 57 dependents
5. **Hook .py changes queued** — not applied mid-run
6. **§1-§10 byte preservation verified** by P1 script before every AGENTS.md write
