# Dissertation Simulator

**AI 에이전트 58개가 협업하는 211-step 박사 논문 연구 시뮬레이션 시스템.**

주제 탐색에서 학술지 투고까지, 박사 논문 연구의 전 과정을 AI 에이전트가 지원합니다.
문헌 검토(5 Wave) → 연구 설계(양적/질적/혼합) → 논문 집필 → 출판 전략의 4단계로 구성되며,
5계층 품질 보장(L0→L1→L1.5→L1.7→L2), 5개 Cross-Validation Gate, 9개 HITL(Human-In-The-Loop) 체크포인트가 학술적 엄밀성을 보장합니다.

> 이 시스템은 [AgenticWorkflow](AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md) — 만능줄기세포 프레임워크에서 태어난 자식 시스템입니다.
> 부모의 전체 DNA(절대 기준, 품질 보장, 안전장치, 기억 체계)를 상속하면서, 박사 논문 도메인에 특화된 아키텍처를 갖습니다.

## Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (v1.0+)
- Claude Pro/Max/Team/Enterprise 구독 (API 호출에 필요)

## 빠른 시작

```bash
# 1. 프로젝트 클론
git clone https://github.com/cysinsight/Dissertation-Simulator-AgenticWorkflow.git
cd Dissertation-Simulator-AgenticWorkflow

# 2. Claude Code 실행
claude

# 3. 시작 (스마트 라우터가 자동으로 적절한 진입점을 선택합니다)
/start
```

## 워크플로우 구조

```
Phase 0: 초기화 + 주제 탐색         (Step 1-38)    ── HITL-0/1 ──▶
Phase 1: 문헌 검토                  (Step 39-120)
  ├── Wave 1: 기초 검색 (4 agents)  ── Gate-1 ──▶
  ├── Wave 2: 심층 분석 (4 agents)  ── Gate-2 ──▶
  ├── Wave 3: 비판적 분석 (4 agents) ── Gate-3 ──▶
  ├── Wave 4: 통합 합성 (2 agents)
  ├── SRCS Full Evaluation
  └── Wave 5: 품질 보증             ── HITL-2 ──▶ (Context Reset 1)
Phase 2: 연구 설계                  (Step 121-140)  ── HITL-3/4 ──▶ (Context Reset 2)
  ├── Quantitative Path (5 agents)
  ├── Qualitative Path (4 agents)
  └── Mixed Methods Path (2 agents)
Phase 3: 논문 집필                  (Step 141-164)  ── HITL-5/6/7 ──▶ (Context Reset 3)
Phase 4: 출판 전략                  (Step 165-172)  ── HITL-8 ──▶ (Context Reset 4)
Phase 5: 최종화                     (Step 173-180)
Phase 6: 한국어 번역 + 내보내기      (Step 181-211)
```

## 핵심 특징

| 특징 | 설명 |
|------|------|
| **58개 전문 에이전트** | 문헌 검색·분석·연구 설계·작성·출판 각 과정에 전문화된 AI 에이전트 (기반 11 + 논문 46 + 통합 1) |
| **5계층 품질 보장** | L0(Anti-Skip) → L1(Verification) → L1.5(pACS) → L1.7(pCCS per-claim) → L2(Adversarial Review) |
| **9개 HITL 체크포인트** | 연구 방향·방법론·최종 산출물에 대한 인간 연구자의 승인 |
| **7가지 Input Mode** | 주제(A), 연구질문(B), 기존문헌(C), 학습(D), 선행논문(E), 제안서(F), 커스텀(G) |
| **GroundedClaim 스키마** | 15개 GRA domain prefix + 20개 utility prefix, 7가지 canonical claim 유형, Hallucination Firewall |
| **pCCS per-claim 신뢰도** | P1 Sandwich 아키텍처 — claim별 예측 신뢰도 점수. rewrite/proceed 자동 결정 |
| **Predictive Debugging** | 코드 구조 스캔 → 실패 예측 → 적대적 검증 → 사전 조치 |
| **Step Execution Registry** | `query_step.py` — 211-step 결정론적 agent/tier/critic/pCCS 매핑. Orchestrator 할루시네이션 원천봉쇄 |
| **Step Consolidation** | 동일 에이전트의 연속 step을 하나의 호출로 통합. 211 step → 17 Orchestrator invocations. P1 결정론적 프롬프트 생성 + 원자적 SOT 전진 |
| **Adversarial Dialogue** | @fact-checker + @reviewer 병렬 적대적 리뷰. Generator-Critic 반복 루프 |
| **Hallucination Containment** | V-1~V-4 취약점 + GAP-1~GAP-6+GAP-DW 커버리지 갭 봉쇄 + QO H-1~H-3 컨텍스트 메모리 할루시네이션 원천봉쇄. `verify_step_output.py`(VO-1~VO-7), `determine_dialogue_outcome.py`, `split_consolidated_group()` — 모두 P1 결정론적 |
| **3-tier Fallback** | Team → Sub-agent → Direct 실행으로 복원력 보장 |
| **Context Reset Model** | 4개 HITL 지점에서 안전한 컨텍스트 리셋 + 3-File Memory + IMMORTAL 섹션으로 복원. QO-1~5 품질 최적화: Gate 피드백·이전 섹션 요약·11개 scoring signal ACTIVE RETRIEVAL |
| **31개 Slash Commands** | `/thesis-init`, `/thesis-start`, `/self-improve`, `/predict-failures` 등 전체 워크플로우 제어 |
| **3-Layer 번역 품질** | Layer 0 (자기 검토) → Layer 1a/1b (Python T1-T12) → Layer 2 (@translation-verifier 의미론적 검증) |
| **KBSI 자기 개선** | 에러 분석 → 개선안 추출 → AGENTS.md 영구 반영. 시스템이 스스로 학습 |

## 프로젝트 구조

```
Dissertation-Simulator-AgenticWorkflow/
│
│  ── 자식 시스템 (Dissertation Simulator) 문서 ──
├── README.md                                        ← 이 파일
├── DISSERTATION-SIMULATOR-ARCHITECTURE-AND-PHILOSOPHY.md  ← 도메인 고유 아키텍처
├── DISSERTATION-SIMULATOR-USER-MANUAL.md             ← 사용자 매뉴얼
│
│  ── 부모 프레임워크 (AgenticWorkflow) 문서 ──
├── AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md    ← 프레임워크 설계 철학
├── AGENTICWORKFLOW-USER-MANUAL.md                    ← 프레임워크 사용법
├── DECISION-LOG.md                                   ← 설계 결정 로그 (ADR-001~071)
├── soul.md                                           ← DNA 유전 철학
│
│  ── AI 에이전트 지시서 ──
├── CLAUDE.md                 # Claude Code 전용 지시서
├── AGENTS.md                 # 모든 AI 에이전트 공통 지시서 (Hub)
├── GEMINI.md                 # Gemini CLI 전용 (Spoke)
│
│  ── 논문 워크플로우 인프라 ──
├── .claude/
│   ├── settings.json         # Hook 설정
│   ├── agents/               # 58개 에이전트 (기반 11 + 논문 46 + 통합 1)
│   │   ├── thesis-orchestrator.md    (총괄 조율 — 150 maxTurns)
│   │   ├── fact-checker.md           (사실 검증, claim-by-claim)
│   │   ├── reviewer.md              (적대적 리뷰어, Enhanced L2)
│   │   ├── claim-quality-evaluator.md (pCCS Phase B-1, sonnet)
│   │   ├── failure-predictor.md      (Predictive Debugging Phase B-1)
│   │   └── ... (46개 논문 전문 에이전트 + 6개 기반 에이전트)
│   ├── commands/              # 31개 Slash Commands (시스템 4 + 라우터 1 + 논문 26)
│   ├── hooks/scripts/         # 113개 스크립트 (프로덕션 66 + 모듈 2 + 테스트 45)
│   │   ├── checklist_manager.py      (논문 SOT 관리)
│   │   ├── query_workflow.py         (워크플로우 관측성)
│   │   ├── validate_grounded_claim.py (claim 검증)
│   │   ├── fallback_controller.py    (3-tier Fallback)
│   │   ├── compute_srcs_scores.py    (SRCS 점수 계산)
│   │   └── ... (검증·안전·컨텍스트 보존 스크립트)
│   └── skills/
│       ├── workflow-generator/  # 워크플로우 설계·생성
│       ├── doctoral-writing/    # 박사급 학술 글쓰기
│       ├── skill-creator/       # 스킬 메타 생성기
│       └── subagent-creator/    # 에이전트 메타 생성기
├── tests/e2e/                 # E2E 통합 테스트 (5 Track, 108+ 테스트)
├── prompt/
│   └── workflow.md            # 211-step 워크플로우 정의
└── thesis-output/             # 논문 산출물 (런타임 생성)
    └── [project-name]/
        ├── session.json       # 논문 SOT
        ├── todo-checklist.md  # 211-step 체크리스트
        ├── research-synthesis.md  # 연구 합성
        ├── wave-results/      # Wave별 산출물
        └── checkpoints/       # 체크포인트
```

## 품질 보장 체계

5계층 품질 보장 + P1 Sandwich 아키텍처:

```
L0: Anti-Skip Guard + Step Output Verification (verify_step_output.py)
  └── VO-1~VO-7: 파일 존재/크기, UTF-8, placeholder 미검출, GroundedClaim 존재, prefix 일치, 금지표현(VO-6), 제목구조(VO-7)

L1: Verification Gate (Python P1 — 결정론적)
  └── GroundedClaim 스키마 검증 (id, text, sources[], confidence, uncertainty)
  └── Hallucination Firewall ("all studies agree" 등 차단)
  └── VE1-VE5 교차 증거 검증 (validate_criteria_evidence.py)

L1.5: pACS (predicted Agent Confidence Score)
  └── F/C/L 3차원 자기 평가 — 최저점 원칙 (min-score)

L1.7: pCCS (predicted Claim Confidence Score) ← NEW
  └── P1 Sandwich: compute_pccs_signals.py → @claim-quality-evaluator →
      validate_pccs_assessment.py → @claim-quality-critic → generate_pccs_report.py
  └── Claim별 예측 신뢰도 점수 → proceed / rewrite_claims / rewrite_step 결정
  └── Claim 유형별 적응 가중치 (FACTUAL:0.50/0.50 → SPECULATIVE:0.15/0.85)

L2: Adversarial Review (Enhanced)
  └── Research domain: @fact-checker + @reviewer 병렬 적대적 검증
  └── Development domain: @code-reviewer 단독 검증
  └── Review FAIL → Adversarial Dialogue (Generator-Critic 반복 루프)

Cross-Validation Gates (5개)
  └── Gate 1-4: Wave 간 claim 품질 교차 검증
  └── Gate 5: 연구 설계 최종 검증

SRCS Unified Evaluation
  └── 4축: Source · Rigor · Confidence · Specificity
  └── Claim 유형별 차등 가중치 · 75점 임계값
```

## 부모-자식 문서 분리 패턴

이 프로젝트는 "만능줄기세포" (AgenticWorkflow)와 그로부터 태어난 "자식 시스템"을 구분합니다.
부모 문서(`AGENTICWORKFLOW-*.md`)는 방법론/프레임워크를, 자식 문서(`DISSERTATION-SIMULATOR-*.md`)는 도메인 고유 아키텍처를 기술합니다.
이 분리는 자식 시스템이 독립적으로 이해·운영될 수 있게 합니다.

**형제 자식 시스템**: [GlobalNews Crawling & Analysis](https://github.com/cysinsight/GlobalNews-Crawling-AgenticWorkflow) — 동일한 AgenticWorkflow DNA에서 태어난 두 번째 자식 시스템 (44개 뉴스 사이트 자동 수집, 56개 NLP 분석, 93개 Python 모듈).

## 문서 읽기 순서

| 순서 | 문서 | 목적 |
|------|------|------|
| 1 | **README.md** (이 파일) | 프로젝트 개요와 빠른 시작 |
| 2 | [`DISSERTATION-SIMULATOR-USER-MANUAL.md`](DISSERTATION-SIMULATOR-USER-MANUAL.md) | 논문 워크플로우 사용법 |
| 3 | [`DISSERTATION-SIMULATOR-ARCHITECTURE-AND-PHILOSOPHY.md`](DISSERTATION-SIMULATOR-ARCHITECTURE-AND-PHILOSOPHY.md) | 도메인 고유 아키텍처와 설계 철학 |
| 4 | [`DECISION-LOG.md`](DECISION-LOG.md) | 설계 결정의 맥락과 근거 (ADR-001~071) |
| - | [`AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md`](AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md) | (참고) 부모 프레임워크 설계 철학 |
| - | [`AGENTICWORKFLOW-USER-MANUAL.md`](AGENTICWORKFLOW-USER-MANUAL.md) | (참고) 부모 프레임워크 사용법 |
| - | [`soul.md`](soul.md) | (참고) DNA 유전 철학 |

## 절대 기준

AgenticWorkflow에서 상속한 최상위 규칙:

1. **품질 최우선** — 토큰 비용, 속도보다 학술적 엄밀성이 유일한 기준
2. **단일 파일 SOT** — `session.json`에 모든 논문 상태 집중. 동시 수정 금지
3. **코드 변경 프로토콜 (CCP)** — 의도 파악 → 영향 범위 분석 → 변경 설계
4. **English-First 강제 (MANDATORY)** — 모든 에이전트 작업·산출물은 영어로 수행. 영어 완성 → `@translator`로 한국어 번역 (순서 역전 불가). 절대 기준 1(품질)의 직접적 구현 (ADR-027a)
5. **품질 > SOT, CCP** — 충돌 시 품질이 우선

## AI 도구 호환성

| AI CLI 도구 | 지시서 파일 | 자동 적용 |
|------------|-----------|----------|
| Claude Code | `CLAUDE.md` | Yes |
| Gemini CLI | `GEMINI.md` | Yes |
| Codex CLI | `AGENTS.md` | Yes |
| Copilot CLI | `.github/copilot-instructions.md` | Yes |

상세: `AGENTS.md` (Hub — 방법론 SOT)

## License

[MIT License](LICENSE) — Copyright (c) 2026 최윤식 (Yoonsik, Choi)
