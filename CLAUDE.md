# AgenticWorkflow

Claude Code 기반의 에이전트 워크플로우 자동화 프로젝트.

## 최종 목표

1. **워크플로우 설계**: 복잡한 작업을 Research → Planning → Implementation 3단계 구조의 `workflow.md`로 설계
2. **워크플로우 실행**: `workflow.md`에 정의된 에이전트·스크립트·자동화 구성을 **실제로 구현**

> 워크플로우를 만드는 것은 중간 산출물이다. **워크플로우에 기술된 내용이 실제로 동작하는 것**이 최종 목표다.

### 존재 이유 — DNA 유전

AgenticWorkflow는 **또 다른 agentic workflow system을 낳는 부모 유기체**다. `workflow-generator` 스킬이 생산 라인이며, 자식 시스템은 부모의 전체 게놈(헌법·구조·검증·안전·기억·비판·투명)을 **내장**한다. 상세: `soul.md §0`.

## 절대 기준

> 모든 설계·구현·수정 의사결정에 적용되는 최상위 규칙. 아래 모든 원칙보다 상위.

### 절대 기준 1: 최종 결과물의 품질
> **속도, 토큰 비용, 작업량, 분량 제한은 완전히 무시한다.** 유일한 기준은 **최종 결과물의 품질**이다.

### 절대 기준 2: 단일 파일 SOT + 계층적 메모리 구조
> 모든 공유 상태는 단일 파일(SOT)에 집중. SOT 쓰기는 Orchestrator/Team Lead만. 병렬 에이전트의 동일 파일 동시 수정 금지.

### 절대 기준 3: 코드 변경 프로토콜 (CCP) — MANDATORY

> **이 규칙은 절대 기준과 동급의 강제 사항이다. 예외 없이 반드시 준수한다.**
> 코드를 작성·수정·추가·삭제하기 전에 반드시 3단계를 내부적으로 수행한다.
> 이 프로토콜을 건너뛴 코드 변경은 무효다.

**[CCP-1] 의도 파악**: 변경 목적·제약을 1-2문장으로 정의.

**[CCP-2] 영향 범위 분석** (표준 이상 변경 시 반드시 수행):
- 직접 의존 + 호출 관계 (caller/callee)
- 구조적 관계 (상속, 합성, 참조)
- 데이터 모델/스키마/타입 연쇄
- 테스트, 설정, 문서, API 스펙
- P1 자동 지원: `ccp_ripple_scanner.py`가 Edit/Write 시 의존성을 자동 발견하여 제공
- ⚠ 강결합·샷건 서저리 위험 → **사전 고지 후 사용자 협의 필수**

**[CCP-3] 변경 설계**: 코드 터치 전에 단계별 변경 계획 제안:
- Phase 1: 어떤 파일/함수부터 수정
- Phase 2: 의존성/호출자 전파
- Phase 3: 테스트/문서/설정 정합
- 결합도↓ 응집도↑ 기회 발견 시 함께 제안 (실행은 사용자 승인 후)

| 변경 규모 | 적용 깊이 |
|----------|---------|
| 경미 (오타, 주석) | CCP-1만 — "파급 없음" 확인 후 즉시 실행 |
| 표준 (함수/로직) | 전체 3단계 |
| 대규모 (아키텍처, API) | 전체 3단계 + **사전 사용자 승인 필수** |

**Coding Anchor Points (CAP)**: CAP-1 (Think before coding), CAP-2 (Simplicity first), CAP-3 (Goal-driven execution), CAP-4 (Surgical changes). When conflicting with Absolute Standard 1, quality wins.

**상세 프로토콜**: `AGENTS.md §2 절대 기준 3` (완전 정의) / `docs/protocols/code-change-protocol.md` (상세 명세)

### 절대 기준 간 우선순위
> **절대 기준 1(품질)이 최상위**. 절대 기준 2(SOT)와 3(CCP)은 품질을 보장하기 위한 동위 수단.

---

## 프로젝트 구조

```
AgenticWorkflow/
├── CLAUDE.md                        ← 이 파일 (Claude Code 지시서 — 경량 TOC)
├── AGENTS.md                        ← 모든 AI 에이전트 공통 지시서 (Hub — 방법론 SOT)
├── GEMINI.md                        ← Gemini CLI 전용 (Spoke)
├── soul.md                          ← DNA 유전 정의
├── DECISION-LOG.md                  ← 설계 결정 로그 (ADR)
├── DISSERTATION-SIMULATOR-ARCHITECTURE-AND-PHILOSOPHY.md  ← 자식 시스템 아키텍처
├── DISSERTATION-SIMULATOR-USER-MANUAL.md                  ← 자식 시스템 사용자 매뉴얼
├── AGENTICWORKFLOW-USER-MANUAL.md                         ← 부모 프레임워크 사용법
├── AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md         ← 부모 프레임워크 설계 철학
├── docs/protocols/                  ← 상세 프로토콜 (on-demand 참조)
│   ├── autopilot-execution.md       (워크플로우 실행 체크리스트 + NEVER DO)
│   ├── quality-gates.md             (L0-L2 5계층 + L1.7 pCCS + P1 검증 24항목 상세)
│   ├── ulw-mode.md                  (ULW 강화 규칙 3개 + 런타임 메커니즘)
│   ├── context-preservation-detail.md (Hook 내부 메커니즘 + D-7 인스턴스)
│   └── code-change-protocol.md      (CCP 3단계 + CAP + 비례성 규칙)
├── .claude/
│   ├── settings.json                ← Hook 설정
│   ├── agents/                      ← Sub-agent 정의 (58개: 기반 11 + 논문 46 + 통합 1)
│   │   ├── translator.md            (영→한 번역, glossary 기반)
│   │   ├── translation-verifier.md  (번역 품질 검증, 독립 Layer 2 pACS)
│   │   ├── reviewer.md              (적대적 리뷰어, Enhanced L2)
│   │   ├── fact-checker.md          (사실 검증, claim-by-claim, Incremental Mode)
│   │   ├── code-reviewer.md         (개발 도메인 코드 리뷰어, Adversarial Dialogue)
│   │   ├── micro-verifier.md        (경량 스팟체크, haiku 모델 — RLM micro-verification)
│   │   ├── failure-predictor.md     (Predictive Debugging Phase B-1 — cross-domain 실패 예측)
│   │   ├── failure-critic.md        (Predictive Debugging Phase B-2 — 예측 교차 검증, adversarial)
│   │   ├── claim-quality-evaluator.md (pCCS Phase B-1 — claim 시맨틱 품질 평가, sonnet)
│   │   ├── claim-quality-critic.md  (pCCS Phase B-2 — claim 품질 적대적 교차 검증, sonnet)
│   │   ├── thesis-orchestrator.md   (논문 워크플로우 총괄 — Wave/Gate/HITL 관리)
│   │   └── ... (48개 논문 전문 에이전트 — 문헌 검색·분석·연구 설계·작성·출판)
│   ├── commands/                    ← Slash Commands (31개: 시스템 4 + 라우터 1 + 논문 26)
│   │   ├── start.md                 (/start — 자연어 시작 트리거 → 스마트 라우터)
│   │   ├── install.md               (/install — Setup Init 검증)
│   │   ├── maintenance.md           (/maintenance — 건강 검진)
│   │   ├── predict-failures.md      (/predict-failures — Predictive Debugging 전체 스캔)
│   │   ├── self-improve.md          (/self-improve — KBSI 자기 개선 분석)
│   │   └── thesis-*.md (26개)       (/thesis-init, /thesis-start, /thesis-status, /thesis-translate 등 — 논문 워크플로우)
│   ├── hooks/scripts/               ← Hook + 검증 스크립트 (66개 프로덕션 + 2개 모듈 + 45개 테스트)
│   │   ├── context_guard.py         (통합 디스패처)
│   │   ├── _context_lib.py          (공유 라이브러리 — 파싱·생성·검증·압축)
│   │   ├── _claim_patterns.py       (Claim ID 정규식 SOT — 모든 스크립트 공유 모듈)
│   │   ├── save_context.py          (SessionEnd/PreCompact 저장)
│   │   ├── restore_context.py       (SessionStart 복원 + RLM + QO-1~4 품질 최적화)
│   │   ├── update_work_log.py       (PostToolUse 9개 도구 추적)
│   │   ├── generate_context_summary.py (Stop 증분 스냅샷 + 안전망)
│   │   ├── diagnose_context.py      (Abductive Diagnosis 사전 분석)
│   │   ├── validate_diagnosis.py    (AD1-AD10 사후 검증)
│   │   ├── validate_pacs.py         (PA1-PA7 + L0 검증)
│   │   ├── validate_review.py       (R1-R5 리뷰 검증)
│   │   ├── validate_traceability.py (CT1-CT5 추적성 검증)
│   │   ├── validate_domain_knowledge.py (DK1-DK7 도메인 지식)
│   │   ├── validate_translation.py  (T1-T9 번역 구조 검증)
│   │   ├── verify_translation_terms.py (T10-T12 번역 용어·숫자·인용 검증 — P1 결정론적)
│   │   ├── validate_verification.py (V1a-V1e 검증 로그 — V1d 증거 품질, V1e 복합 기준 탐지)
│   │   ├── validate_workflow.py     (W1-W9 DNA 유전 검증)
│   │   ├── validate_retry_budget.py (RB1-RB3 재시도 예산)
│   │   ├── setup_init.py            (인프라 건강 검증 + SOT 쓰기 안전)
│   │   ├── setup_maintenance.py     (주기적 건강 검진)
│   │   ├── block_destructive_commands.py (위험 명령+네트워크+시스템 차단, exit 2)
│   │   ├── block_test_file_edit.py  (TDD Guard, .tdd-guard 토글)
│   │   ├── predictive_debug_guard.py (위험 파일 경고, exit 0)
│   │   ├── ccp_ripple_scanner.py    (CCP-2 P1 의존성 자동 발견, exit 0)
│   │   ├── output_secret_filter.py  (시크릿 탐지, 3-tier 추출, 25+ 패턴, 2-패스 스캔)
│   │   ├── run_mypy_check.py        (mypy 타입 검증 훅 — Phase 1 strict, 비엄격 warn-only, exit 0)
│   │   ├── security_sensitive_file_guard.py (보안 민감 파일 경고, 12 패턴)
│   │   ├── query_workflow.py        (워크플로우 관측성 — dashboard/weakest/retry/blocked/error-trends/pccs)
│   │   ├── checklist_manager.py     (논문 SOT 관리 — init/advance/advance-group/gate/HITL/checkpoint/set-substep)
│   │   ├── validate_grounded_claim.py (GroundedClaim 스키마 검증 — 47개 prefix)
│   │   ├── guard_sot_write.py       (SOT 쓰기 보호 — 병렬 에이전트 충돌 방지)
│   │   ├── validate_thesis_output.py (논문 산출물 품질 검증)
│   │   ├── validate_wave_gate.py    (Wave/Gate 교차 검증)
│   │   ├── validate_step_sequence.py (스텝 순서 검증 — 의존성 적용)
│   │   ├── validate_task_completion.py (태스크 완료 검증 — CLI-only, Orchestrator 호출)
│   │   ├── validate_srcs_threshold.py (SRCS 임계값 검증)
│   │   ├── compute_srcs_scores.py   (SRCS 4축 점수 계산)
│   │   ├── fallback_controller.py   (3-tier Fallback — CLI-only, Orchestrator 호출)
│   │   ├── teammate_health_check.py (팀메이트 건강 점검 — CLI-only, Orchestrator 호출)
│   │   ├── build_bilingual_manifest.py (EN/KO 쌍 검증 — P1 결정론적)
│   │   ├── check_format_consistency.py (챕터 간 서식 일관성 검증 — P1 결정론적)
│   │   ├── detect_self_plagiarism.py (n-gram 자기표절 탐지 — P1 결정론적)
│   │   ├── extract_references.py    (인용 추출·정렬 — P1 결정론적)
│   │   ├── format_grounded_claims.py (GroundedClaim YAML 포맷팅 — P1 결정론적)
│   │   ├── generate_thesis_outline.py (마크다운 기반 목차 추출 — P1 결정론적)
│   │   ├── validate_fork_safety.py  (Fork 안전성 P1 검증 — FS-1~FS-5 결정론적, CLI 도구)
│   │   ├── validate_criteria_evidence.py (VE1-VE5 할루시네이션 교차 검증 — P1 결정론적, CLI 도구)
│   │   ├── validate_dialogue_state.py (DA1-DA5 Adversarial Dialogue 상태 검증 — P1 결정론적)
│   │   ├── validate_claim_inheritance.py (CI1-CI4 Claim 상속 검증 — P1 결정론적, Research 도메인)
│   │   ├── validate_team_synthesis.py (TS1-TS5 Agent Team 합성 완전성 검증 — P1 결정론적, CLI 도구)
│   │   ├── validate_agent_dna.py    (DA1-DA7 에이전트 DNA 구조 검증 — P1 결정론적, CLI 도구)
│   │   ├── scan_code_structure.py   (Predictive Debugging Phase A — F1-F7 코드 구조 스캔, P1 결정론적)
│   │   ├── extract_json_block.py    (Predictive Debugging Phase B→C 핸드오프 — LLM 응답에서 JSON 결정론적 추출, P1)
│   │   ├── validate_failure_predictions.py (Predictive Debugging Phase C — FP1-FP7 예측 검증, P1 결정론적)
│   │   ├── generate_failure_report.py (Predictive Debugging Phase D — 보고서+SOT 생성+H-3 파일 검증, P1 결정론적)
│   │   ├── compute_pccs_signals.py  (pCCS Phase A — P1 signal 추출, claim-map 생성)
│   │   ├── validate_pccs_assessment.py (pCCS Phase C — CA1-CA5 LLM 평가 검증, P1 결정론적)
│   │   ├── generate_pccs_report.py  (pCCS Phase D — P1 합성, 최종 pCCS 점수 계산)
│   │   ├── validate_pccs_output.py  (pCCS PC1-PC7 구조 검증, P1 결정론적)
│   │   ├── pccs_calibration.py      (pCCS 교정 delta 계산 — fact-checker/L1 기반, P1 결정론적)
│   │   ├── run_pccs_pipeline.py     (pCCS P1 Pipeline Runner — DEGRADED/FULL 모드 단일 진입점, 할루시네이션 방지)
│   │   ├── query_step.py           (Step Execution Registry — H-1~H-8 결정론적 step→agent/tier/critic/pCCS/consolidation/invocation/writing-standard 매핑, P1)
│   │   ├── self_improve_manager.py  (KBSI SOT 관리 — register/apply/reject/status/apply-to-agents-md/sync-claude-md/queue-change)
│   │   ├── validate_self_improvement.py (SI-1~SI-6 insight 검증 — P1 결정론적)
│   │   ├── validate_skill_output.py (SK-1~SK-5 스킬 산출물 구조 검증 — P1 결정론적, CLI 도구)
│   │   ├── verify_step_output.py   (VO-1~VO-7 Step 산출물 검증 — P1 결정론적, 할루시네이션 방지 + DW 품질)
│   │   ├── determine_dialogue_outcome.py (대화 루프 탈출 결정 — P1 결정론적, 할루시네이션 방지)
│   │   └── _test_*.py (45개)        (유닛 테스트 — 각 프로덕션 스크립트 대응)
│   ├── context-snapshots/           ← 런타임 (gitignored)
│   └── skills/
│       ├── workflow-generator/      (워크플로우 설계·생성)
│       ├── doctoral-writing/        (박사급 학술 글쓰기)
│       ├── skill-creator/           (스킬 메타 생성기)
│       └── subagent-creator/        (에이전트 메타 생성기)
├── tests/e2e/                       ← E2E 통합 테스트 (5 Track, 108+ 테스트)
│   ├── conftest.py                  (공유 Fixture — run_cm, run_qw, read_sot)
│   ├── test_e2e_lifecycle.py        (Track 1: 전체 라이프사이클)
│   ├── test_e2e_sot_integrity.py    (Track 2: SOT 무결성)
│   ├── test_e2e_cross_component.py  (Track 3: 컴포넌트 간 통합)
│   ├── test_e2e_cli_flags.py        (Track 4: CLI 플래그 완전성)
│   └── test_e2e_error_recovery.py   (Track 5: 에러 복구)
├── translations/glossary.yaml       ← 번역 용어 사전
├── prompt/                          ← 프롬프트 자료
└── coding-resource/                 ← 이론적 기반 자료
```

## Context Preservation System

컨텍스트 토큰 초과·`/clear`·압축 시 작업 내역 상실을 방지하는 자동 저장·복원 시스템.

| Hook 이벤트 | 스크립트 | 동작 |
|------------|---------|------|
| Setup (`--init`) | `setup_init.py` | 인프라 건강 검증 + SOT 쓰기 안전 + 런타임 디렉터리 생성 |
| Setup (`--maintenance`) | `setup_maintenance.py` | 주기적 건강 검진 + doc-code 동기화 |
| PreToolUse (Bash) | `block_destructive_commands.py` | 위험 명령 차단 — 네트워크 유출+시스템 파괴+Git 파괴+치명적 rm (exit 2) |
| PreToolUse (Edit\|Write) | `block_test_file_edit.py` | TDD 모드 시 테스트 파일 보호 (exit 2) |
| PreToolUse (Edit\|Write) | `predictive_debug_guard.py` | 에러 이력 기반 위험 파일 경고 |
| PreToolUse (Edit\|Write) | `guard_sot_write.py` | SOT 쓰기 보호 — Orchestrator/Team Lead만 허용 (exit 2) |
| PreToolUse (Edit\|Write) | `ccp_ripple_scanner.py` | CCP-2 P1 의존성 자동 발견 (Hub-Spoke, 참조, 테스트, Hook) |
| SessionStart | `restore_context.py` | RLM 포인터 + 과거 세션 인덱스 + Predictive Debugging 캐시 + QO-1~4 품질 최적화 (Gate 피드백·이전 섹션 요약·11개 scoring signal·step 메타데이터) |
| PostToolUse (9개 도구) | `update_work_log.py` | 작업 로그 누적 |
| PostToolUse (Bash\|Read) | `output_secret_filter.py` | 시크릿 탐지 (3-tier 추출, 25+ 패턴, 2-패스 스캔) |
| PostToolUse (Edit\|Write) | `security_sensitive_file_guard.py` | 보안 민감 파일 수정 경고 |
| PostToolUse (Edit\|Write) | `run_mypy_check.py` | mypy 타입 검증 — Phase 1 strict / 비엄격 warn-only (exit 0) |
| PostToolUse (Write) | `validate_grounded_claim.py` | GroundedClaim 스키마 검증 (47개 prefix) |
| Stop | `generate_context_summary.py` | 증분 스냅샷 + Knowledge Archive + 안전망 |
| PreCompact | `save_context.py` | 압축 전 스냅샷 저장 |
| SessionEnd | `save_context.py` | `/clear` 시 전체 스냅샷 저장 |

**필수 행동**: 세션 시작 시 `[CONTEXT RECOVERY]` 표시되면, 안내된 파일을 **반드시 Read tool로 읽어** 이전 맥락을 복원.

**상세**: Hook 내부 메커니즘, Knowledge Archive 필드, D-7 인스턴스 → `docs/protocols/context-preservation-detail.md`

## 스킬 사용 판별

| 사용자 요청 패턴 | 스킬 | 진입점 |
|----------------|------|--------|
| "워크플로우 만들어줘", "자동화 파이프라인 설계" | `workflow-generator` | SKILL.md |
| "논문 스타일로 써줘", "학술적 글쓰기" | `doctoral-writing` | SKILL.md |
| "에이전트 만들어줘", "서브에이전트 생성" | `subagent-creator` | SKILL.md |
| "스킬 만들어줘", "새 스킬 생성" | `skill-creator` | SKILL.md |

### 자연어 시작 트리거 (Smart Router)

사용자가 다음과 같은 **시작 의도의 자연어**를 입력하면 `/start` 라우터를 실행한다:

| 패턴 (한국어) | 패턴 (영어) |
|-------------|------------|
| "시작하자", "시작", "시작해", "시작해줘", "시작합시다" | "start", "let's start", "begin" |
| "워크플로우를 시작하자", "워크플로우 시작" | "start the workflow" |
| "논문 작업을 하자", "논문을 시작하자" | "let's work on the thesis" |
| "논문 시뮬레이터를 시작하자", "시뮬레이터 시작" | "start the simulator" |
| "시뮬레이션을 시작하자", "시뮬레이션 시작" | "start the simulation" |
| "연구를 시작하자", "연구 시작" | "start the research" |

**라우팅 규칙**: `thesis-output/` 존재 여부 → 프로젝트 상태 → 적절한 진입점 자동 선택. 상세: `.claude/commands/start.md`

### 논문 워크플로우 (Slash Commands)

`/start` (스마트 라우터) → `/thesis-init` → `/thesis-start` → `/thesis-status` 등 27개 논문 전용 명령어. 211-step 박사 논문 시뮬레이션 워크플로우를 구동하며, Wave/Gate/HITL 아키텍처를 통해 품질을 보장한다. 논문 SOT는 `session.json` (시스템 SOT `state.yaml`과 독립).

## 설계 원칙

1. **P1 — 정확도를 위한 데이터 정제**: AI 전달 전 Python 등으로 노이즈 제거
2. **P2 — 전문성 기반 위임 구조**: 전문 에이전트에게 위임, Orchestrator는 조율만
3. **P3 — 이미지/리소스 정확성**: 정확한 다운로드 경로 명시, placeholder 불가
4. **P4 — 질문 설계 규칙**: 최대 4개 질문, 각 3개 선택지. 모호함 없으면 질문 없이 진행

## Autopilot Mode

워크플로우 실행 시 `(human)` 단계와 AskUserQuestion을 자동 승인하는 모드. 상세: `AGENTS.md §5.1`

**5계층 품질 보장**: L0(Anti-Skip Guard) → L1(Verification Gate) → L1.5(pACS Self-Rating) → L1.7(pCCS per-claim confidence) → L2(Calibration). 상세: `docs/protocols/quality-gates.md`

**워크플로우 실행 전 반드시 읽기**: `docs/protocols/autopilot-execution.md` — 단계별 체크리스트 + NEVER DO

## ULW (Ultrawork) Mode

프롬프트에 `ulw` 포함 시 활성화되는 **철저함 강도 오버레이**. Autopilot(자동화 축)과 직교. 3가지 강화 규칙: I-1(Sisyphus Persistence), I-2(Mandatory Task Decomposition), I-3(Bounded Retry Escalation).

**상세**: `docs/protocols/ulw-mode.md`

## 언어 및 스타일 규칙

### 핵심 지침: English-First 강제 (MANDATORY)

> **이 규칙은 절대 기준과 동급의 강제 사항이다. 예외 없이 반드시 준수한다.**

| 구분 | 언어 | 강제 여부 |
|------|------|----------|
| **워크플로우 전체 진행 단계** | **영어** | **강제** |
| **에이전트 작업·산출물** | **영어** | **강제** |
| **최종 결과물 (논문 등)** | **영어 원본 먼저** → 한국어 번역 | **강제** |
| 프레임워크 문서·사용자 대화 | 한국어 | 허용 |
| 기술 용어 | 영어 유지 (SOT, Agent Team, Hooks 등) | 강제 |

**근거 (절대 기준 1 — 품질의 직접적 구현)**:
1. **토큰 효율성** — 한국어는 토큰 소비가 2-3배 높음
2. **정확도 향상** — LLM의 주 학습 언어로 더 정밀한 이해·생성
3. **할루시네이션 감소** — 영어가 한국어보다 할루시네이션 발생률이 낮음
4. **일관성 보장** — 영어 프롬프트는 해석의 모호함이 적음

**강제 순서**: 영어로 최종 결과물 완성 → `@translator` 스킬로 한국어 번역 생성. **이 순서는 역전 불가.**

- **시각화**: Mermaid 다이어그램 선호
- **깊이**: 간략 요약보다 포괄적·데이터 기반 서술 선호

### 번역 프로토콜

워크플로우에 `Translation: @translator`로 표기된 단계에 한해 `@translator` 서브에이전트 호출. 번역 대상은 텍스트 콘텐츠(`.md`, `.txt`)만. SOT `outputs.step-N-ko`에 기록. 용어 사전 `translations/glossary.yaml` 자동 유지.

## 스킬 개발 규칙

1. **모든 절대 기준을 반드시 포함** — 해당 도메인에 맞게 맥락화
2. **파일 간 역할 분담** 명확히 — SKILL.md(WHY), references/(WHAT/HOW/VERIFY)
3. **절대 기준 간 충돌 시나리오** 구체적으로 명시
4. 수정 후 반드시 **절대 기준 관점에서 성찰**

## Knowledge-Based Self-Improvement (KBSI)

워크플로우 실행 과정에서 발견된 오류·개선을 일반화하여 영구 저장하는 자기 개선 시스템. 상세: `AGENTS.md §11`

- **Track 1 (Reactive)**: 오류 → insight → `AGENTS.md §11.4` 영구 저장
- **Track 2 (Proactive)**: 개선 기회 → 컴포넌트 자동 업데이트 (SAFE=자동, STRUCTURAL=사용자 승인)
- **SOT**: `self-improvement-logs/state.json` (thesis/system SOT와 독립)
- **P1 Sandwich**: `validate_self_improvement.py` (SI-1~SI-6) → LLM → `self_improve_manager.py`
- **Safety**: Immutable boundary + Hub file 탐지 시 자동 STRUCTURAL 분류

<!-- KBSI-START -->
<!-- KBSI-END -->
