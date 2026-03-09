# GroundedClaim (GRA) Schema Reference

Complete schema reference for agents producing research claims.

## GroundedClaim YAML Format

Research agents output claims in this YAML structure within markdown files:

```yaml
- id: "{PREFIX}-{NNN}"
  claim_type: FACTUAL | EMPIRICAL | THEORETICAL | METHODOLOGICAL | INTERPRETIVE | SPECULATIVE
  statement: "The claim text — one complete assertion."
  sources:
    - reference: "Author (Year). Title. Journal, Vol(Issue), pp-pp."
      doi: "10.xxxx/xxxxx"
      type: PRIMARY | SECONDARY | TERTIARY
  confidence: 85
  effect_size: "d = 0.45 (medium)"     # Optional — for statistical findings
  uncertainty: "Limited to Western academic contexts; may not generalize."
```

## Field Specifications

### id (Required)

Two formats coexist:
- Simple: `{PREFIX}-{NNN}` (e.g., `LS-001`, `GI-007`)
- Sub-prefixed: `{PREFIX}-{SUB}{NNN}` (e.g., `VRA-H001`, `MS-IS001`)

Where:
- `PREFIX`: 2-4 uppercase letters identifying the **domain family**
- `SUB`: 1-4 uppercase letters identifying the **agent within the family** (optional)
- `NNN`: 2-4 digit number (001, 002, ...)

**Prefix Sharing Convention:**

GRA research agents define **domain-level prefixes**. Phase 2+ agents in the same
domain **share** the parent prefix and add a sub-prefix for disambiguation.
This is intentional — it groups claims by research domain for cross-wave traceability.

**GRA Domain Prefixes** (from `agent-template-guide.md`):

| Prefix | Owner Agent | Shared By | Sub-prefix Examples |
|--------|------------|-----------|-------------------|
| LS | literature-searcher | literature-analyzer, topic-explorer | LS-A001, LS-T001 |
| SWA | seminal-works-analyst | — | SWA-001 |
| TRA | trend-analyst | — | TRA-001 |
| MS | methodology-scanner | integration-strategist, participant-selector, qualitative-analysis-planner | MS-IS001, MS-PS001, MS-QA001 |
| TFA | theoretical-framework-analyst | paradigm-consultant | TFA-P001 |
| EEA | empirical-evidence-analyst | — | EEA-001 |
| GI | gap-identifier | — | GI-001 |
| VRA | variable-relationship-analyst | hypothesis-developer | VRA-H001 |
| CR | critical-reviewer | — | CR-001 |
| MC | methodology-critic | — | MC-001 |
| LA | limitation-analyst | — | LA-001 |
| FDA | future-direction-analyst | publication-strategist | FDA-PB001 |
| SA | synthesis-agent | thesis-architect, research-synthesizer | SA-TA001, SA-RS001 |
| CMB | conceptual-model-builder | research-model-developer | CMB-M001 |
| PC | plagiarism-checker | unified-srcs-evaluator | PC-SRCS-001 |

**Utility/Phase 2-4 Agent Prefixes** (independent — not shared):

| Prefix | Agent |
|--------|-------|
| AB | abstract-writer |
| AS | assessment-agent |
| CL | cover-letter-writer |
| CM | citation-manager |
| DC | data-collection-planner |
| ER | ethics-reviewer |
| ID | instrument-developer |
| JM | journal-matcher |
| MF | manuscript-formatter |
| MM | mixed-methods-designer |
| MT | methodology-tutor |
| PC | practice-coach ⚠️ |
| PL | thesis-plagiarism-checker |
| QD | quantitative-designer |
| QLD | qualitative-data-designer |
| SD | sampling-designer |
| SP | submission-preparer |
| STP | statistical-planner |
| TR | thesis-reviewer |
| TW | thesis-writer |

> ⚠️ **PC 충돌**: `practice-coach` (utility)와 `plagiarism-checker` (GRA domain)가
> 동일 prefix PC를 사용한다. 이는 설계 시 의도된 공유가 아닌 **실제 충돌**이다.
> 새 에이전트에서 PC를 사용하지 말 것.

**New prefix allocation rules:**
1. 같은 연구 도메인의 Phase 2+ 에이전트 → 부모 GRA prefix 공유 + sub-prefix 추가
2. 독립 유틸리티 에이전트 → 새 prefix 할당 (위 테이블과 중복 불가)
3. 유일성 확인: `grep -r "Claim Prefix" .claude/agents/`

### claim_type (Required)

7 canonical types (raw types are mapped automatically by `_claim_patterns.py`):

| Canonical Type | Accepts Also | Description |
|---------------|-------------|-------------|
| FACTUAL | DEFINITIONAL, HISTORICAL | Verifiable facts with citations |
| EMPIRICAL | — | Research findings with data |
| THEORETICAL | THEOLOGICAL | Theory-based assertions |
| METHODOLOGICAL | METHODOLOGICAL_CRITIQUE, AUDIT, STRUCTURAL | Research method claims |
| INTERPRETIVE | ANALYTICAL, COUNTERARGUMENT, ASSUMPTION_CRITIQUE, SYNTHESIS, ARGUMENTATIVE | Analytical interpretations |
| SPECULATIVE | — | Forward-looking propositions |
| UNKNOWN | (unmapped types default here) | Unrecognized claim types |

### sources (Required — at least 1)

```yaml
sources:
  - reference: "Full APA-style reference string"
    doi: "10.xxxx/xxxxx"          # Optional but strongly preferred
    type: PRIMARY                  # PRIMARY | SECONDARY | TERTIARY
```

- PRIMARY: Original research / first-hand data
- SECONDARY: Reviews, meta-analyses, textbooks
- TERTIARY: Encyclopedias, handbooks

### confidence (Required)

Integer 0-100 representing claim confidence:

| Range | Meaning | Typical claim_type |
|-------|---------|-------------------|
| 90-100 | Very high — well-established facts | FACTUAL |
| 70-89 | High — strong evidence, minor caveats | EMPIRICAL |
| 50-69 | Moderate — mixed evidence | INTERPRETIVE |
| 30-49 | Low — limited evidence | SPECULATIVE |
| 0-29 | Very low — highly uncertain | SPECULATIVE |

Also accepted as string: `"high"` (→90), `"medium"` (→70), `"low"` (→50), `"speculative"` (→40)

### uncertainty (Required)

Explicit limitation statement. NEVER omit:
- Geographic/cultural scope limits
- Temporal validity bounds
- Methodological constraints
- Sample size limitations

## Hallucination Firewall

Research agents MUST include these rules in their instructions:

```markdown
### Hallucination Firewall
- BLOCK: "all studies agree", "100%", "no exceptions", "it is universally accepted"
- REQUIRE_SOURCE: Any statistical claim (p-values, effect sizes, percentages)
- SOFTEN: "certainly" → "evidence suggests", "obviously" → "notably"
- VERIFY: "it is known that" → must have citation, else rephrase
- NEVER fabricate DOIs, author names, journal titles, or publication years
```

## Validation

Generated claims are validated by:
1. `validate_grounded_claim.py` (PostToolUse hook) — checks prefix, structure
2. `validate_criteria_evidence.py` (VE1-VE5) — cross-checks evidence quality
3. `compute_pccs_signals.py` (pCCS Phase A) — extracts confidence signals

## Common Mistakes

1. **Missing uncertainty field** → validator rejects
2. **Duplicate prefix across agents** → claim ID collisions
3. **confidence as string "high)" with typo** → known parsing issue, use integer
4. **No sources for FACTUAL claims** → defeats the purpose of grounding
5. **DOI fabrication** → fact-checker will flag; use "unavailable" if unknown
