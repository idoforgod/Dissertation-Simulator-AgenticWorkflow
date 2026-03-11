# Dissertation Simulator: Architecture and Philosophy

이 문서는 **Dissertation Simulator** — AgenticWorkflow 코드베이스에서 태어난 박사 논문 연구 시뮬레이션 시스템의 **도메인 고유 아키텍처와 설계 철학**을 기술한다.

> **부모-자식 문서 분리**: 이 프로젝트는 "만능줄기세포" (AgenticWorkflow)와 그로부터 태어난 "자식 시스템" (Dissertation Simulator)을 구분한다. 부모 문서(`AGENTICWORKFLOW-*.md`)는 방법론/프레임워크를, 이 문서(`DISSERTATION-SIMULATOR-*.md`)는 도메인 고유 아키텍처를 기술한다. 이 분리는 자식 시스템이 독립적으로 이해·운영될 수 있게 한다.

---

## 1. 설계 철학

### 1.1 존재 이유: DNA 유전의 실증

Dissertation Simulator는 AgenticWorkflow의 "만능줄기세포 → 분화된 세포" 철학을 **최초로 실증**하는 대규모 자식 시스템이다. 부모의 전체 게놈(절대 기준, SOT 패턴, 5계층 QA, Safety Hook, Context Preservation, P1 Sandwich)이 박사 논문 도메인에 맞게 발현된다.

| 부모 게놈 (DNA) | 자식에서의 발현 |
|---------------|--------------|
| 절대 기준 1 (품질) | 학술적 엄밀성 절대주의 — 토큰 비용보다 논문 품질 |
| 절대 기준 2 (SOT) | `session.json` — 논문 전용 단일 상태 파일 |
| 5계층 QA | L0(Anti-Skip) → L1(Verification) → L1.5(pACS) → L1.7(pCCS per-claim) → L2(Adversarial Review) |
| P2 (전문성 기반 위임) | 58개 전문 에이전트 (기반 11 + 논문 46 + 통합 1) — 역할별 극도의 전문화 |
| Context Preservation | 4개 HITL 리셋 포인트 + 3-File Memory + IMMORTAL 섹션 + Hypothesis Graveyard |
| Safety Hook | GroundedClaim 검증 + Hallucination Firewall + query_step.py 결정론적 라우팅 + Step Consolidation (17 invocations / 211 steps) |
| P1 Sandwich | pCCS + Predictive Debugging — Python(A) → LLM(B) → Python(C) → LLM(B2) → Python(D) |

### 1.2 핵심 신념: 연구의 엄밀성은 자동화할 수 있다

박사 논문 연구는 인간 전문가만의 영역으로 여겨지지만, 이 시스템은 핵심 전제를 세운다:

> **엄밀한 프로세스를 설계하면, AI 에이전트가 인간 연구자를 보조하여 박사급 품질의 연구 산출물을 생산할 수 있다.**

단, "보조"가 핵심이다. 9개 HITL 체크포인트에서 인간 연구자가 방향을 승인하고, AI는 실행·검증·합성을 담당한다.

### 1.3 5계층 품질 보장 체계

Dissertation Simulator의 품질 보장 체계. 부모의 4계층(L0-L2)에 **L1.7 pCCS**를 추가한 5계층:

```
L0: Anti-Skip Guard + Step Output Verification (verify_step_output.py)
  └── VO-1: 파일 존재 + size ≥ min_output_bytes (query_step.py 기준)
  └── VO-2: UTF-8 유효성
  └── VO-3: Placeholder 미검출 (Lorem ipsum, TODO, FIXME, [insert], [TBD] 등 11개 패턴)
  └── VO-4: Tier A step → GroundedClaim ≥ 1개 존재
  └── VO-5: Claim prefix가 expected agent prefix와 일치 (AGENT_CLAIM_PREFIXES 기반)
  └── V-1 제거: LLM 기반 파일 경로 해석을 glob 결정론적 매칭으로 대체
  └── GAP-3 제거: Claim prefix 불일치 원천봉쇄 (잘못된 에이전트 claim 통과 방지)
  └── GAP-4 제거: Placeholder 콘텐츠 통과 방지

L1: Verification Gate (Python P1 — 결정론적)
  └── GroundedClaim 스키마 검증 (id, sources[], confidence, uncertainty)
  └── Hallucination Firewall (blocked: "all studies agree", "100%", "universally accepted")
  └── VE1-VE5 교차 증거 검증 (validate_criteria_evidence.py)
  └── MIN_CONFIDENCE 임계값 (FACTUAL:95, EMPIRICAL:85, THEORETICAL:75)

L1.5: pACS (predicted Agent Confidence Score)
  └── F/C/L 3차원 자기 평가 — 최저점 원칙 (min-score)

L1.7: pCCS (predicted Claim Confidence Score) ← P1 Sandwich 아키텍처
  └── Phase A: compute_pccs_signals.py — P1 ground truth signal 추출 (A1-A6)
  └── Phase B-1: @claim-quality-evaluator — LLM 시맨틱 품질 평가 (sonnet)
  └── Phase C-1: validate_pccs_assessment.py — P1 LLM 평가 검증 (CA1-CA5)
  └── Phase B-2: @claim-quality-critic — LLM 적대적 교차 검증 (sonnet)
  └── Phase C-2: validate_pccs_assessment.py — P1 재검증
  └── Phase D: generate_pccs_report.py — P1 최종 점수 합성 + 결정 (proceed/rewrite)
  └── Claim 유형별 적응 가중치: FACTUAL(0.50/0.50) → SPECULATIVE(0.15/0.85)
  └── SPECULATIVE 예외: pCCS<40에서만 rewrite (일반: <50)

L2: Adversarial Review (Enhanced)
  └── Research domain: @fact-checker + @reviewer 병렬 적대적 검증
  └── Development domain: @code-reviewer 단독 검증
  └── Review FAIL → Adversarial Dialogue (Generator-Critic 반복 루프, max_rounds 설정)
  └── P1 검증: DA1-DA5 (대화 상태), CI1-CI4 (claim 상속)
  └── P1 Dialogue Decision (determine_dialogue_outcome.py):
      All PASS → consensus | Any FAIL + round<max → continue | Any FAIL + round≥max → escalate
      V-2 제거: LLM 기반 대화 루프 종료 판단을 결정론적 규칙으로 대체

Cross-Validation Gates (5개)
  └── Gate 1-4: Wave 간 claim 품질 교차 검증
  └── Gate 5: 연구 설계 최종 검증

SRCS Unified Evaluation
  └── 4축: Source · Rigor · Confidence · Specificity
  └── Claim 유형별 차등 가중치 · 75점 임계값
```

---

## 2. 아키텍처 전체 조감도

### 2.1 Phase/Wave/Gate/HITL 구조

```
Phase 0: Initialization & Topic (Step 1-38)
├── Step 1-8: 프로젝트 초기화 (SOT, 체크리스트, 리소스)
├── Step 9-14: Mode A — 연구 주제 탐색 (@topic-explorer)
├── Step 15-34: Mode D — 학습 모드 (8 Track, @methodology-tutor)
└── HITL-0/1: 연구 질문 확인 및 승인

Phase 1: Literature Review (Step 39-120)
├── Wave 1 (Step 39-54): 기초 문헌 검색
│   └── @literature-searcher + @seminal-works-analyst + @trend-analyst + @methodology-scanner
│   └── ── Gate-1 (Step 55-58) ──▶
├── Wave 2 (Step 59-74): 심층 분석
│   └── @theoretical-framework-analyst + @empirical-evidence-analyst + @gap-identifier + @variable-relationship-analyst
│   └── ── Gate-2 (Step 75-78) ──▶
├── Wave 3 (Step 79-94): 비판적 분석
│   └── @critical-reviewer + @methodology-critic + @limitation-analyst + @future-direction-analyst
│   └── ── Gate-3 (Step 95-98) ──▶
├── Wave 4 (Step 99-106): 통합 합성
│   └── @synthesis-agent + @conceptual-model-builder
├── SRCS Full Evaluation (Step 107-110)
│   └── @unified-srcs-evaluator
├── Wave 5 (Step 111-114): 품질 보증
│   └── @plagiarism-checker + @thesis-plagiarism-checker
└── HITL-2 (Step 115-120): 문헌 검토 결과 승인 (Context Reset Point 1)

Phase 2: Research Design (Step 121-140)
├── HITL-3: 연구 유형 확정 (quantitative/qualitative/mixed)
├── 조건부 분기:
│   ├── Quantitative Path: @hypothesis-developer → @quantitative-designer → @sampling-designer → @statistical-planner
│   ├── Qualitative Path: @paradigm-consultant → @participant-selector → @qualitative-data-designer → @qualitative-analysis-planner
│   └── Mixed Methods Path: @mixed-methods-designer → @integration-strategist
├── 공통: @ethics-reviewer + @instrument-developer + @data-collection-planner
└── HITL-4: 연구 설계 승인 (Context Reset Point 2)

Phase 3: Thesis Writing (Step 141-164)
├── @thesis-architect: 개요 설계
├── @thesis-writer: 챕터별 집필
├── @thesis-reviewer: 초고 검토
├── @citation-manager + @manuscript-formatter
├── HITL-5: 논문 형식 선택
├── HITL-6: 개요 승인 (Context Reset Point 3)
└── HITL-7: 초고 리뷰

Phase 4: Publication Strategy (Step 165-172)
├── @publication-strategist + @journal-matcher
├── @submission-preparer + @cover-letter-writer
└── HITL-8: 최종 확정 (Context Reset Point 4)

Phase 5: Finalization (Step 173-180)
└── @abstract-writer + 최종 패키징

Phase 6: Translation + Export (Step 181-211)
├── @translator: 전체 산출물 한국어 번역
└── DOCX Export: 통합 한국어 논문 생성
```

### 2.1.1 Step Consolidation Architecture

211개 step은 에이전트별로 **통합 그룹**으로 묶여, 17개 Orchestrator 호출로 실행된다:

| Invocation | Steps | Label |
|-----------|-------|-------|
| 1 | 1-14 | Phase 0: Init + Topic Exploration |
| 2 | 15-34 | Phase 0-D: Learning Mode |
| 3 | 35-38 | HITL-1: Research Question |
| 4 | 39-58 | Wave 1 + Gate 1 |
| 5 | 59-78 | Wave 2 + Gate 2 |
| 6 | 79-98 | Wave 3 + Gate 3 |
| 7 | 99-114 | Wave 4 + SRCS + Wave 5 |
| 8 | 115-120 | HITL-2: Literature Review Approval |
| 9 | 121-140 | Phase 2: Research Design + HITL-3/4 |
| 10 | 141-142 | Phase 3: Outline + HITL-5 |
| 11 | 143-156 | Phase 3: Chapters + Reviews |
| 12 | 157-160 | HITL-6 + Final Revision + HITL-7 |
| 13 | 161-164 | Phase 3: Translation + Archive |
| 14 | 165-172 | Phase 4: Publication + HITL-8 |
| 15 | 173-180 | Phase 5: Finalization |
| 16 | 181-195 | Phase 6: Translation Batch 1 |
| 17 | 196-211 | Phase 6: Translation Batch 2 + Export |

**통합 실행 메커니즘**:
- 동일 에이전트의 연속 step을 하나의 호출로 통합 (예: steps 39-42 → literature-searcher 1회 호출)
- `generate_consolidated_prompt()`: P1 결정론적 프롬프트 생성 (zero unfilled template variables)
- `get_next_execution_step()`: 컨텍스트 리셋 후 mid-consolidation restart 자동 감지
- `advance_group()`: SOT 원자적 그룹 전진 (단일 파일 쓰기)
- **Consolidation Fallback Protocol**: 통합 그룹 3회 실패 → `split_consolidated_group()` P1 결정론적 분할 → 각 sub-group 독립 재시도
  - Binary split 알고리즘: >4 step → 절반 분할, 3-4 step → 이진 분할, 2 step → 개별, 1 step → 그대로
  - V-4 제거: LLM 기반 그룹 분할 전략을 결정론적 알고리즘으로 대체
- 제외 에이전트: `translator` (순차 glossary 일관성), `_orchestrator` (관리 step)
- 안전 상한: 최대 6 step/그룹 (`_MAX_CONSOLIDATION_SIZE`)

### 2.2 Input Modes (7가지 진입 경로)

| Mode | 진입 조건 | 시작 Phase |
|------|---------|-----------|
| **A** (기본) | 연구 주제 제공 → 연구 질문 생성 | Phase 0-A |
| **B** | 연구 질문 직접 입력 | Phase 1 (Wave 1) |
| **C** | 기존 문헌 리뷰 분석 | Phase 1 (분석) |
| **D** | 학습 모드 — 방법론 튜토리얼 | Phase 0-D |
| **E** | 선행 논문 업로드 → 분석 | Phase 1 (분석) |
| **F** | 연구 제안서 업로드 → 분석 | Phase 2 |
| **G** | 커스텀 입력 | 사용자 해석 |

### 2.3 3-File External Memory 전략

컨텍스트 윈도우 한계를 극복하기 위한 외부 기억 아키텍처:

| 파일 | 역할 | 크기 제한 |
|------|------|---------|
| `session.json` | SOT — 진행 상태, Gate, HITL, 산출물 경로 | 구조화 JSON |
| `todo-checklist.md` | 체크리스트 — 211 step `[x]/[ ]` 추적 | ~15KB |
| `research-synthesis.md` | 연구 합성 — 3000-4000단어 압축 인사이트 | ~15KB |

**Context Reset Model**: HITL-2, HITL-4, HITL-6, HITL-8에서 컨텍스트를 리셋하고, 3-File에서 상태를 복원하여 세션 연속성을 보장한다.

---

## 3. 에이전트 아키텍처 (58 agents)

### 3.1 에이전트 계층 구조

```
thesis-orchestrator (총괄)
├── Phase 0 에이전트 (5)
│   ├── topic-explorer (LS-T)
│   ├── literature-analyzer (LS-A)
│   ├── methodology-tutor (MT)
│   ├── practice-coach (PCH)
│   └── assessment-agent (AA)
├── Phase 1 에이전트 — Wave별 (19)
│   ├── Wave 1: literature-searcher, seminal-works-analyst, trend-analyst, methodology-scanner
│   ├── Wave 2: theoretical-framework-analyst, empirical-evidence-analyst, gap-identifier, variable-relationship-analyst
│   ├── Wave 3: critical-reviewer, methodology-critic, limitation-analyst, future-direction-analyst
│   ├── Wave 4: synthesis-agent, conceptual-model-builder
│   └── Wave 5: plagiarism-checker
├── Phase 2 에이전트 — 경로별 (14)
│   ├── Quantitative: hypothesis-developer, research-model-developer, quantitative-designer, sampling-designer, statistical-planner
│   ├── Qualitative: paradigm-consultant, participant-selector, qualitative-data-designer, qualitative-analysis-planner
│   ├── Mixed: mixed-methods-designer, integration-strategist
│   └── 공통: ethics-reviewer, instrument-developer, data-collection-planner
├── Phase 3 에이전트 (7)
│   ├── thesis-architect, thesis-writer, thesis-reviewer
│   ├── abstract-writer, citation-manager, manuscript-formatter
│   └── thesis-plagiarism-checker
├── Phase 4 에이전트 (4)
│   ├── publication-strategist, journal-matcher
│   └── submission-preparer, cover-letter-writer
├── 품질·검증 에이전트 (7)
│   ├── reviewer (적대적 리뷰어, Enhanced L2)
│   ├── fact-checker (사실 검증, claim-by-claim, Incremental Mode)
│   ├── code-reviewer (개발 도메인 코드 리뷰어)
│   ├── micro-verifier (경량 스팟체크, haiku)
│   ├── unified-srcs-evaluator (PC-SRCS)
│   └── research-synthesizer (SA-RS)
├── pCCS 에이전트 (2)
│   ├── claim-quality-evaluator (Phase B-1, sonnet — 시맨틱 품질 평가)
│   └── claim-quality-critic (Phase B-2, sonnet — 적대적 교차 검증)
├── Predictive Debugging 에이전트 (2)
│   ├── failure-predictor (Phase B-1 — cross-domain 실패 예측)
│   └── failure-critic (Phase B-2 — 예측 교차 검증, adversarial)
└── 번역 에이전트 (2)
    ├── translator (영→한 번역, glossary 기반)
    └── translation-verifier (번역 품질 검증, 독립 Layer 2 pACS)
```

### 3.2 GroundedClaim 스키마

모든 에이전트는 통합 GroundedClaim 형식으로 claim을 생산한다:

```json
{
  "id": "LS-001",
  "text": "Recent meta-analyses show...",
  "claim_type": "EMPIRICAL",
  "sources": ["Smith et al. (2024)", "DOI:10.1234/..."],
  "confidence": 85,
  "verification": "verified"
}
```

**Claim Prefix 체계** (15 GRA domain prefix + 20 utility prefix):

GRA 도메인 prefix는 Phase 2+ 에이전트와 **의도적으로 공유**된다. 하위 prefix로 에이전트를 식별:

| Phase | Owner Agent | Prefix | 공유 에이전트 (하위 prefix) |
|-------|------------|--------|--------------------------|
| Wave 1 | literature-searcher | LS | literature-analyzer (LS-A), topic-explorer (LS-T) |
| Wave 1 | seminal-works-analyst | SWA | — |
| Wave 1 | trend-analyst | TRA | — |
| Wave 1 | methodology-scanner | MS | integration-strategist (MS-IS), participant-selector (MS-PS), qualitative-analysis-planner (MS-QA) |
| Wave 2 | theoretical-framework-analyst | TFA | paradigm-consultant (TFA-P) |
| Wave 2 | empirical-evidence-analyst | EEA | — |
| Wave 2 | gap-identifier | GI | — |
| Wave 2 | variable-relationship-analyst | VRA | hypothesis-developer (VRA-H) |
| Wave 3 | critical-reviewer | CR | — |
| Wave 3 | methodology-critic | MC | — |
| Wave 3 | limitation-analyst | LA | — |
| Wave 3 | future-direction-analyst | FDA | publication-strategist (FDA-PB) |
| Wave 4 | synthesis-agent | SA | thesis-architect (SA-TA), research-synthesizer (SA-RS) |
| Wave 4 | conceptual-model-builder | CMB | research-model-developer (CMB-M) |
| Quality | plagiarism-checker | PC | unified-srcs-evaluator (PC-SRCS) |

### 3.3 SRCS 가중치 체계

| Claim 유형 | Source (CS) | Rigor (GS) | Confidence (US) | Specificity (VS) |
|-----------|------------|------------|-----------------|------------------|
| EMPIRICAL | 0.35 | 0.35 | 0.10 | 0.20 |
| THEORETICAL | 0.30 | 0.30 | 0.15 | 0.25 |
| FACTUAL | 0.40 | 0.25 | 0.05 | 0.30 |
| METHODOLOGICAL | 0.30 | 0.35 | 0.10 | 0.25 |
| INTERPRETIVE | 0.25 | 0.30 | 0.20 | 0.25 |
| SPECULATIVE | 0.20 | 0.25 | 0.25 | 0.30 |

### 3.4 번역 3-Layer 품질 아키텍처

English-First 강제 원칙에 따라 영어 산출물 완성 후 한국어 번역을 수행하며, 3계층 품질 보장 체계를 적용한다:

```
Layer 0: @translator Self-Review
  └── 영→한 번역 후 자기 검토 (glossary 기반 용어 일관성)

Layer 1a: Structural Validation (T1-T9)
  └── validate_translation.py — 파일 존재, 크기, 헤딩 수 ±20%, 코드 블록 일치 등

Layer 1b: Content Preservation (T10-T12)
  └── verify_translation_terms.py — 용어집 준수(T10), 숫자/통계 보존(T11), 인용 보존(T12)
  └── P1 Compliant: 순수 Python regex — LLM 추론 0%

Layer 2: Semantic Verification (선택적)
  └── @translation-verifier — 독립 pACS 평가
  └── 3축: Fidelity(Ft), Naturalness(Nt), Completeness(Ct)
  └── pACS >= 0.85: PASS, 0.70-0.84: CONDITIONAL, < 0.70: FAIL
  └── Layer 1 결과와 교차 검증 (Agreement / Layer 1 only / Semantic only)
```

---

## 4. 핵심 인프라

### 4.1 SOT 관리 (`session.json`)

시스템 SOT(`state.yaml`)와 완전히 독립된 논문 전용 상태 파일:

```json
{
  "project_name": "my-thesis",
  "status": "running",
  "current_step": 0,
  "total_steps": 211,
  "research_type": "undecided",
  "input_mode": "A",
  "research_question": "",
  "academic_field": "",
  "outputs": {},
  "gates": {
    "gate-1": { "status": "pending", "timestamp": null },
    "gate-2": { "status": "pending", "timestamp": null },
    "gate-3": { "status": "pending", "timestamp": null },
    "srcs-full": { "status": "pending", "timestamp": null },
    "final-quality": { "status": "pending", "timestamp": null }
  },
  "hitl_checkpoints": {
    "hitl-0": { "status": "pending", "timestamp": null },
    "hitl-1": { "status": "pending", "timestamp": null },
    "...": "..."
  },
  "fallback_history": [],
  "context_snapshots": [],
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

**검증 규칙 (TS1-TS10)**: 스키마 타입, 필수 키, 상태 열거형, 범위 검증, 타임스탬프 형식 등 10개 결정론적 규칙.

### 4.2 인프라 스크립트 (66개 프로덕션 + 2개 공유 모듈)

**Core & Observability** (4):

| 스크립트 | 역할 |
|---------|------|
| `checklist_manager.py` | SOT CRUD, 체크리스트, Gate/HITL, Checkpoint, advance guards (H-5/H-6) |
| `query_workflow.py` | 관측성 — dashboard, weakest-step, blocked, retry, error-trends, pccs |
| `query_step.py` | **Step Execution Registry** — 211-step 결정론적 agent/tier/critic/pCCS 매핑 + Step Consolidation/Execution P1 함수 4개 (`generate_consolidated_prompt`, `generate_single_step_prompt`, `get_next_execution_step`, `get_invocation_plan`) |
| `fallback_controller.py` | 3-tier Fallback 제어 (Team→Sub-agent→Direct) + `split_consolidated_group()` P1 결정론적 그룹 분할 |

**Hallucination Containment** (2):

| 스크립트 | 역할 |
|---------|------|
| `verify_step_output.py` | **Step Output Verification** — VO-1~VO-7 결정론적 산출물 검증. V-1(파일 경로), GAP-3(prefix 불일치), GAP-4(placeholder), GAP-DW(비박사급 글쓰기) 제거. VO-6(금지 표현 WARNING), VO-7(제목 구조 FAIL) |
| `determine_dialogue_outcome.py` | **Dialogue Outcome Decision** — All PASS→consensus, Any FAIL→continue/escalate. V-2(대화 루프 종료) 제거 |

**pCCS System** (7):

| 스크립트 | 역할 |
|---------|------|
| `compute_pccs_signals.py` | Phase A — P1 ground truth signal 추출 (A1-A6), claim-map 생성 |
| `validate_pccs_assessment.py` | Phase C — CA1-CA5 LLM 평가 검증 |
| `generate_pccs_report.py` | Phase D — P1 합성, 최종 pCCS 점수 계산, 결정 매트릭스 |
| `validate_pccs_output.py` | PC1-PC7 구조 검증 |
| `pccs_calibration.py` | 교정 delta 계산 (fact-checker/L1 기반) |
| `run_pccs_pipeline.py` | Pipeline Runner — DEGRADED/FULL 모드 단일 진입점 |
| `_claim_patterns.py` | 공유 모듈 — Claim ID regex, 17→7 canonical type 매핑, confidence 파싱 |

**Predictive Debugging** (4):

| 스크립트 | 역할 |
|---------|------|
| `scan_code_structure.py` | Phase A — F1-F7 코드 구조 스캔 |
| `extract_json_block.py` | Phase B→C 핸드오프 — LLM 응답에서 JSON 추출 |
| `validate_failure_predictions.py` | Phase C — FP1-FP7 예측 검증 |
| `generate_failure_report.py` | Phase D — 보고서+SOT 생성+H-3 파일 검증 |

**Quality & Validation** (22):

| 스크립트 | 역할 |
|---------|------|
| `validate_grounded_claim.py` | GroundedClaim ID·스키마 검증, Hallucination Firewall |
| `validate_criteria_evidence.py` | VE1-VE5 할루시네이션 교차 검증 |
| `compute_srcs_scores.py` | SRCS 4축 결정론적 점수 계산 |
| `validate_wave_gate.py` | Wave/Gate 교차 검증 — 통합파일 모드 인식 + 혼합 상태 경고 |
| `validate_step_sequence.py` | 스텝 순서·의존성 검증 |
| `validate_thesis_output.py` | 산출물 파일 존재·크기 검증 — TO5 per-step heading 검증 + TO6 prefix 균일성 검증 (통합 모드) |
| `validate_srcs_threshold.py` | SRCS 75점 임계값 검증 |
| `validate_agent_dna.py` | DA1-DA7 에이전트 DNA 구조 검증 |
| `validate_claim_inheritance.py` | CI1-CI4 Claim 상속 검증 |
| `validate_dialogue_state.py` | DA1-DA5 Adversarial Dialogue 상태 검증 |
| `validate_team_synthesis.py` | TS1-TS5 Agent Team 합성 완전성 검증 |
| `validate_fork_safety.py` | FS-1~FS-5 Fork 안전성 검증 |
| `validate_skill_output.py` | SK-1~SK-5 스킬 산출물 구조 검증 |
| `validate_self_improvement.py` | SI-1~SI-6 KBSI insight 검증 |
| `verify_translation_terms.py` | T10-T12 번역 콘텐츠 보존 검증 |
| `build_bilingual_manifest.py` | EN/KO 쌍 완전성 검증 |
| `check_format_consistency.py` | 챕터 간 서식 일관성 검증 |
| `detect_self_plagiarism.py` | n-gram 기반 자기표절 탐지 |
| `extract_references.py` | 인용 추출·정렬 |
| `format_grounded_claims.py` | GroundedClaim YAML 포맷팅 |
| `generate_thesis_outline.py` | 마크다운 목차 추출 |
| `run_mypy_check.py` | mypy 타입 검증 (Phase 1 strict) |

**Quality & Validation** 추가 (기타에서 이관 없음, 상기 22개에 포함):

| 스크립트 | 역할 |
|---------|------|
| `validate_task_completion.py` | 태스크 완료 검증 — CLI-only, Orchestrator 호출 |
| `teammate_health_check.py` | 팀메이트 건강 점검 — CLI-only, Orchestrator 호출 |

**Safety & Guards** (6): `guard_sot_write.py`, `block_destructive_commands.py`, `block_test_file_edit.py`, `predictive_debug_guard.py`, `ccp_ripple_scanner.py`, `security_sensitive_file_guard.py`

**Context Preservation** (7): `context_guard.py`, `save_context.py`, `restore_context.py`, `generate_context_summary.py`, `update_work_log.py`, `diagnose_context.py`, `validate_diagnosis.py`

**기타** (13): `setup_init.py`, `setup_maintenance.py`, `teammate_health_check.py`, `validate_task_completion.py`, `output_secret_filter.py`, `self_improve_manager.py`, `validate_pacs.py`, `validate_review.py`, `validate_traceability.py`, `validate_verification.py`, `validate_domain_knowledge.py`, `validate_translation.py`, `validate_workflow.py`, `validate_retry_budget.py`

### 4.3 Context Memory 품질 최적화

컨텍스트 보존 시스템이 thesis 워크플로우에 특화된 품질 최적화를 수행한다:

| 기능 | 역할 | 위치 |
|------|------|------|
| **Thesis Continuity Markers** | pending gates + blocked steps를 SessionStart 시 표면화, knowledge-index에 아카이브 | `_context_lib.py` → `restore_context.py` |
| **Session Type Classification** | 세션을 7개 카테고리(debugging/feature/refactoring/audit/research/writing/translation)로 자동 분류 → KI 검색 정밀도 향상 | `_context_lib.py` |
| **Quality Gate Trend** | knowledge-index에서 gate pending 이력을 집계, 반복 실패 패턴 감지 시 root cause analysis 권고 | `restore_context.py` |
| **Thesis Step Proximity** | knowledge-index의 `thesis_step` 필드로 현재 step ±5 이내 세션에 +20 부스트, ±10 이내 +10 부스트 → 관련 세션 우선 복원 | `restore_context.py` |
| **Hypothesis Graveyard** | knowledge-index에서 `rejected_hypotheses`를 집계, SessionStart 시 표면화 → 동일 가설 반복 방지 | `restore_context.py` |
| **pCCS Trend Detection** | pCCS 이력에서 mean_pccs 방향 (↑/↓/→) 탐지, 연속 rewrite 경고 → Orchestrator 조기 개입 | `restore_context.py` |
| **Active Team Surfacing** | `_surface_active_team()`으로 Agent Team 상태를 IMMORTAL 섹션에 표면화 → 컨텍스트 리셋 후 팀 재개 보장 | `restore_context.py` |
| **Active Dialogue Detection** | `_detect_active_dialogue()`로 dialogue-logs/에서 미완 적대적 대화를 탐지 → Round 1부터 재시작 방지 | `restore_context.py` |
| **IMMORTAL Sections** | Gate/HITL 상태, 실행 컨텍스트, pCCS 상태, 활성 팀, 실패 예측, Gate 피드백, 이전 섹션 요약이 컨텍스트 압축에서도 생존 | `restore_context.py` |
| **Failure Predictions** | Predictive Debugging 결과를 IMMORTAL 섹션으로 표면화, 결과 없으면 UNAVAILABLE 경고 (unknown ≠ safe) | `restore_context.py` |
| **Invocation Plan Progress** | `get_invocation_plan()`으로 17개 invocation 중 완료/진행/대기 상태를 IMMORTAL 섹션에 표면화 | `restore_context.py` |
| **Consolidated Group State** | `get_next_execution_step()`으로 mid-consolidation restart 상태를 IMMORTAL 섹션에 표면화. QO-4: `query_step()`으로 output_path, min_bytes, tier, claims, pCCS 모드 메타데이터 표면화 | `restore_context.py` |
| **Gate Feedback (QO-1)** | `_surface_recent_gate_feedback()`로 최근 Gate의 FAIL/WARN 사유를 IMMORTAL 섹션에 표면화. JSON 파싱 우선 + MD state machine fallback으로 오탐 원천봉쇄 (ADR-074 H-1) | `restore_context.py` |
| **Previous Sections (QO-2)** | `_surface_previous_sections_summary()`로 지난 5개 step 산출물의 제목·정확한 워드카운트·섹션 구조를 IMMORTAL 섹션에 표면화 → 서사적 일관성 유지 | `restore_context.py` |
| **Enhanced Session Scoring (QO-3)** | ACTIVE RETRIEVAL에 4개 scoring signal 추가 (7→11): 설계 결정 매칭(3.5), 도구 시퀀스 패턴(2.5), 단계 정렬(2.0), 성공 패턴(3.0). 일반 동사/전치사 stopword 필터로 오탐 방지 (ADR-074 A-1/A-2) | `restore_context.py` |
| **KI Quality Fields (QO-5)** | knowledge-index에 3개 필드 추가: previous_section_outputs(제목+워드카운트), review_feedback_summary(`parse_review_verdict()` 기반 정확한 추출), word_count_trend(단계별 분량 추세) | `_context_lib.py` |

모든 기능은 P1 compliant (결정론적 Python 추출, LLM 추론 0%), read-only (SOT 수정 없음), additive-only (기존 동작 변경 없음). ADR-074에 의해 모든 추출 로직의 할루시네이션이 원천봉쇄됨.

### 4.4 E2E 테스트 (108 tests, 5 Track)

| Track | 파일 | 테스트 수 | 검증 대상 |
|-------|------|---------|---------|
| 1 | `test_e2e_lifecycle.py` | 30 | init → advance → gate → HITL → checkpoint → restore |
| 2 | `test_e2e_sot_integrity.py` | 17 | 스키마 검증, 필드 일관성, 원자적 쓰기, 타임스탬프 |
| 3 | `test_e2e_cross_component.py` | 17 | checklist_manager ↔ query_workflow ↔ context_summary |
| 4 | `test_e2e_cli_flags.py` | 26 | 모든 argparse 플래그 성공/에러 시나리오 |
| 5 | `test_e2e_error_recovery.py` | 18 | 손상 SOT, 누락 파일, 의존성 차단, 체크포인트 복구 |

---

## 5. 부모에서 상속된 DNA

Dissertation Simulator가 AgenticWorkflow로부터 상속한 게놈 구성요소:

| 부모 구성요소 | 자식에서의 발현 | 상세 참조 |
|------------|--------------|---------|
| 절대 기준 3개 | 논문 도메인에 맞게 맥락화 (품질=학술적 엄밀성, SOT=session.json, CCP=동일) | `AGENTS.md §2` |
| 5계층 QA | L0(Anti-Skip) → L1(Verification) → L1.5(pACS) → L1.7(pCCS) → L2(Adversarial Review) | §1.3 |
| P1 Sandwich | pCCS (7 scripts + 2 agents) + Predictive Debugging (4 scripts + 2 agents) | §1.3, §4.2 |
| Context Preservation | HITL 리셋 포인트 + 3-File Memory + IMMORTAL 섹션 + Hypothesis Graveyard | `docs/protocols/context-preservation-detail.md` |
| Safety Hook 체계 | GroundedClaim 검증 + Hallucination Firewall + `query_step.py` 결정론적 라우팅 | `.claude/hooks/scripts/` |
| Autopilot Mode | Wave 내 자동 진행 (Gate/HITL에서만 정지) | `AGENTS.md §5.1` |
| ULW Mode | 학술 연구의 철저함 보장 | `docs/protocols/ulw-mode.md` |
| Adversarial Dialogue | @fact-checker + @reviewer 병렬 적대적 리뷰 → Generator-Critic 반복 루프 | `AGENTS.md §5.5` |
| KBSI (자기 개선) | 에러 분석 → 개선안 추출 → AGENTS.md 영구 반영 | `/self-improve` |
| Hub-and-Spoke 문서 | 부모(`AGENTICWORKFLOW-*.md`) vs 자식(`DISSERTATION-SIMULATOR-*.md`) 분리 | 이 문서 자체 |
| `soul.md` | DNA 유전 철학 | `soul.md` |

---

## 부록: 용어 정리

| 용어 | 정의 |
|------|------|
| **5계층 QA** | L0(Anti-Skip) → L1(Verification Gate) → L1.5(pACS) → L1.7(pCCS) → L2(Adversarial Review) 품질 보장 체계 |
| **P1 Sandwich** | Python(Phase A) → LLM(Phase B) → Python(Phase C) → LLM(Phase B-2) → Python(Phase D) 할루시네이션 봉쇄 아키텍처 |
| **pCCS** | predicted Claim Confidence Score — claim별 예측 신뢰도 점수. 7개 P1 스크립트 + 2개 LLM 에이전트 |
| **pACS** | predicted Agent Confidence Score — F/C/L 3차원 자기 평가, min-score 원칙 |
| **SRCS** | Source-Rigor-Confidence-Specificity — 4축 claim 품질 평가, 75점 임계값 |
| **GroundedClaim** | 출처(sources)·신뢰도(confidence)·불확실성(uncertainty)이 명시된 연구 주장 단위. 7가지 canonical type |
| **Claim Prefix** | 에이전트별 2-4자리 대문자 도메인 식별자. 15개 GRA domain prefix + 20개 utility prefix. 동일 도메인 에이전트는 prefix를 공유하고 sub-prefix로 구별 |
| **Wave** | Phase 1 내의 병렬 작업 단위. Wave 1-4: 각 4개 에이전트 병렬 실행, Wave 5: 품질 보증 |
| **Gate** | Wave 간 교차 검증 관문 (3개: Gate 1-3). 이전 Wave의 claim 품질 미달 시 진행 차단 |
| **HITL** | Human-In-The-Loop — 인간 연구자의 승인이 필수인 체크포인트 (9개) |
| **Context Reset Point** | HITL-2/4/6/8에서 컨텍스트를 리셋하고 3-File Memory + IMMORTAL에서 복원하는 지점 |
| **IMMORTAL Section** | 컨텍스트 압축에서도 생존하는 우선순위 블록 — Gate/HITL 상태, 활성 팀, pCCS 상태, 실패 예측 |
| **Adversarial Dialogue** | @fact-checker + @reviewer 병렬 적대적 검증. Review FAIL 시 Generator-Critic 반복 루프 |
| **3-tier Fallback** | Team → Sub-agent → Direct 실행 강등 체계. `fallback_controller.py`가 제어 |
| **Predictive Debugging** | 코드 구조 스캔(F1-F7) → 실패 예측 → 적대적 검증(FP1-FP7) → 사전 조치 |
| **query_step.py** | Step Execution Registry — 211-step 결정론적 agent/tier/critic/pCCS 매핑. Orchestrator 할루시네이션 원천봉쇄 |
| **KBSI** | Knowledge-Based Self-Improvement — 에러 분석 → 개선안 추출 → AGENTS.md 영구 반영. 시스템 자기 학습 |
| **Hypothesis Graveyard** | 과거 세션에서 rejected된 가설을 SessionStart 시 표면화 → 동일 가설 반복 방지 |
| **Step Consolidation** | 동일 에이전트의 연속 step을 하나의 호출로 통합. 211 step → 17 Orchestrator invocations. `_MAX_CONSOLIDATION_SIZE=6` |
| **Invocation Plan** | `get_invocation_plan()` — 17개 Orchestrator 호출의 P1 결정론적 매핑. 각 호출의 step 범위·라벨·완료 상태 포함 |
| **Consolidation Fallback** | 통합 그룹 3회 실패 시 개별 step으로 분할 → 각 step 독립 재시도. 교착 방지 |
| **advance_group()** | 통합 그룹의 SOT 원자적 전진. 모든 step에 동일 output_path 기록 + guard 1회 실행 + current_step 갱신 |
| **Hallucination Containment** | V-1~V-4 취약점과 GAP-1~GAP-6+GAP-DW 커버리지 갭을 P1 결정론적 스크립트로 봉쇄하는 체계. verify_step_output.py(VO-1~VO-7) + determine_dialogue_outcome.py + split_consolidated_group() + H-8 단일 Step 프롬프트 P1 생성 |
| **verify_step_output.py** | P1 결정론적 Step 산출물 검증. VO-1(파일 존재/크기) → VO-2(UTF-8) → VO-3(placeholder 미검출) → VO-4(GroundedClaim 존재) → VO-5(prefix 일치) → VO-6(금지 학술 표현 WARNING) → VO-7(제목 구조 FAIL). V-1, GAP-3, GAP-4, GAP-DW 제거 |
| **determine_dialogue_outcome.py** | P1 결정론적 Dialogue Loop 종료 판단. All PASS→consensus, Any FAIL+round<max→continue, Any FAIL+round≥max→escalate. V-2 제거 |
| **split_consolidated_group()** | P1 결정론적 통합 그룹 분할. Binary split 알고리즘 (>4→절반, 3-4→이진, 2→개별, 1→그대로). V-4 제거 |
