# Output Path Conventions for Generated Agents

Standard output path patterns for agents in the thesis workflow.

## Directory Structure

```
thesis-output/{project-name}/
├── session.json                    ← SOT (Orchestrator only)
├── todo-checklist.md               ← Progress tracker
├── research-synthesis.md           ← Cross-wave synthesis
├── wave-results/
│   ├── wave-1/                     ← Steps 39-54
│   │   ├── step-039-{agent-output}.md
│   │   ├── step-040-{agent-output}.md
│   │   └── ...
│   ├── wave-2/                     ← Steps 59-74
│   ├── wave-3/                     ← Steps 79-94
│   ├── wave-4/                     ← Steps 99-106
│   └── wave-5/                     ← Steps 111-114
├── gate-results/
│   ├── gate-1-report.md            ← Steps 55-58
│   ├── gate-2-report.md            ← Steps 75-78
│   └── gate-3-report.md            ← Steps 95-98
├── phase-2/                        ← Steps 123-140
│   ├── step-123-{design-output}.md
│   └── ...
├── phase-3/                        ← Steps 141-164
│   ├── step-143-chapter-1.md
│   └── ...
├── submission-package/             ← Steps 165-172
│   ├── step-165-journal-analysis.md
│   └── ...
├── verification-logs/              ← L1 verification (per step)
│   ├── step-039-verify.md
│   └── ...
├── pacs-logs/                      ← L1.5 pACS ratings (per step)
│   ├── step-039-pacs.md
│   └── ...
├── review-logs/                    ← L2 review results (per step)
│   ├── step-039-review.md
│   └── ...
├── dialogue-logs/                  ← Adversarial Dialogue rounds
│   ├── step-039-r1-fc.md           ← Round 1 fact-checker
│   ├── step-039-r1-rv.md           ← Round 1 reviewer
│   └── step-039-summary.md         ← Dialogue conclusion
└── translations/                   ← Phase 6 Korean translations
    ├── step-181-chapter-1.ko.md
    └── ...
```

## Naming Convention

Output files follow this pattern:

```
step-{NNN}-{description}.md
```

Where:
- `{NNN}`: 3-digit zero-padded step number (e.g., 039, 143)
- `{description}`: Agent-specific output description in kebab-case

## Output Path in query_step.py

Each step in `query_step.py` returns an `output_path` field with the expected
output location. Agents should write to this path.

```python
# Example from query_step.py
{
    "agent": "literature-searcher",
    "output_path": "wave-results/wave-1/step-039-literature-search.md",
    ...
}
```

## Rules for New Agents

1. **Always use the output_path from query_step.py** — do not invent paths
2. **One output file per step** — additional artifacts go in the same directory
3. **Markdown format** — all output is `.md` (for verification hooks)
4. **Korean translations** use `.ko.md` suffix in `translations/` directory
5. **Verification logs** are separate from output (different directory)
6. **Never write to SOT** — only Orchestrator writes to session.json
