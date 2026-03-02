# AgenticWorkflow — Gemini CLI 지시서

> 이 프로젝트에서 작업하는 모든 AI는 AgenticWorkflow 방법론을 따라야 한다.

## 필수 참조

@AGENTS.md

위 파일은 이 프로젝트의 모든 절대 기준, 설계 원칙, 워크플로우 구조를 정의한다.
상세 아키텍처는 `AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md`를 참조한다.
설계 결정 이력은 `DECISION-LOG.md`를 참조한다.

## 유전 설계 (DNA Inheritance)

이 프로젝트는 자식 agentic workflow system을 생성하는 부모 유기체이다.
모든 자식 시스템은 부모의 전체 게놈(절대 기준, SOT, 4계층 검증, Safety Hook 등)을 구조적으로 내장한다.
상세: `soul.md`, `AGENTS.md §1`.

## 절대 기준 (핵심 요약)

### 절대 기준 1: 최종 결과물의 품질

> 속도, 토큰 비용, 작업량, 분량 제한은 완전히 무시한다.
> 모든 의사결정의 유일한 기준은 **최종 결과물의 품질**이다.

### 절대 기준 2: 단일 파일 SOT

> 모든 공유 상태는 단일 파일에 집중한다. 쓰기 권한은 Orchestrator만 보유한다.
> 병렬 에이전트가 동일 파일을 동시 수정하는 구조는 금지한다.

### 절대 기준 3: 코드 변경 프로토콜 (CCP)

> 코드를 작성·수정·추가·삭제하기 전에 반드시 3단계를 수행한다:
> Step 1 의도 파악 → Step 2 영향 범위 분석 → Step 3 변경 설계.
> 분석 깊이는 변경 규모에 비례한다 (경미: Step 1만, 표준: 전체, 대규모: 전체 + 사용자 승인).
> **코딩 기준점(CAP-1~4)**: 코딩 전 사고, 단순성 우선, 목표 기반 실행, 외과적 변경. 상세: AGENTS.md §2.

> **상세 내용**: AGENTS.md §2 참조.

## 워크플로우 구조

모든 워크플로우는 3단계로 구성된다:

1. **Research** — 정보 수집 및 분석
2. **Planning** — 계획 수립, 구조화, 사람의 검토/승인
3. **Implementation** — 실제 실행 및 산출물 생성

## Gemini CLI 구현 매핑

| AgenticWorkflow 개념 | Gemini CLI 대응 |
|---------------------|----------------|
| 전문 에이전트 (Sub-agent) | Gemini CLI는 단일 세션 모델. 프롬프트 내에서 역할을 전환하여 전문성 시뮬레이션 |
| 에이전트 그룹 (Agent Team) | 별도 Gemini 세션을 병렬로 실행하여 구현 |
| 자동 검증 (Hooks) | 외부 셸 스크립트로 검증 파이프라인 구성 |
| 재사용 모듈 (Skills) | `@file.md` import로 도메인 지식 주입 |
| 외부 연동 (MCP) | Gemini extensions 또는 외부 API 스크립트 |
| SOT 상태관리 | `state.yaml` 파일 — 단일 쓰기 지점 원칙 동일 적용 |
| Autopilot Mode | SOT의 `autopilot.enabled` 필드로 제어. `(human)` 단계 자동 승인. Anti-Skip Guard(산출물 검증), Decision Log(`autopilot-logs/`) 포함. `AGENTS.md §5.1` 참조 |
| ULW (Ultrawork) Mode | 프롬프트에 `ulw` 포함 시 활성화. Autopilot과 직교하는 철저함 강도 오버레이. 3가지 강화 규칙(Intensifiers): Sisyphus Persistence(3회 재시도) + Mandatory Task Decomposition + Bounded Retry Escalation. Claude Code Hook 기반 결정론적 Compliance Guard 포함. `AGENTS.md §5.1.1` 참조 |
| Verification Protocol | 각 단계 산출물의 기능적 목표 100% 달성 검증. Anti-Skip Guard(물리적) 위에 의미론적 Verification Gate 계층. 검증 기준은 Task 앞에 선언, 실패 시 최대 10회 재시도(ULW 활성 시 15회). `AGENTS.md §5.3` 참조 |
| pACS (자체 신뢰 평가) | Verification Gate 통과 후 에이전트가 F/C/L 3차원 자기 평가. Pre-mortem Protocol 필수. min-score 원칙. GREEN(≥70): 자동 진행, YELLOW(50-69): 플래그 후 진행, RED(<50): 재작업. `AGENTS.md §5.4` 참조 |
| Adversarial Review (Enhanced L2) | 기존 L2 Calibration을 대체하는 강화된 품질 검증. `@reviewer`(코드/산출물 비판적 분석, 읽기 전용) + `@fact-checker`(외부 사실 검증, 웹 접근). P1 검증(`validate_review.py`)으로 리뷰 품질 보장. `AGENTS.md §5.5` 참조 |
| Translation Protocol | 영어 산출물 → 한국어 번역. `@translator` 서브에이전트가 `glossary.yaml` 기반 용어 일관성 유지. P1 검증(`validate_translation.py` T1-T9 + `validate_verification.py` V1a-V1c)으로 번역·검증 품질 보장. Review PASS가 Translation의 전제. `AGENTS.md §5.2` 참조 |
| Predictive Debugging (L-1) | 에러 이력 기반 위험 파일 사전 경고. `predictive_debug_guard.py`(PreToolUse 경고 전용) + `aggregate_risk_scores()`(SessionStart P1 집계) + `validate_risk_scores()`(RS1-RS6 검증). `risk-scores.json` 캐시. `_context_lib.py` + `docs/protocols/context-preservation-detail.md` 참조 |
| Abductive Diagnosis | 품질 게이트(Verification/pACS/Review) FAIL → 재시도 사이에 3단계 구조화된 진단 수행. Step A: P1 사전 증거 수집(`diagnose_context.py`), Step B: LLM 원인 분석(가설 ≥ 2개), Step C: P1 사후 검증(`validate_diagnosis.py` AD1-AD10). Fast-Path(FP1-FP3)로 결정론적 단축 가능. `diagnosis-logs/`에 기록. `AGENTS.md §5.6` 참조 |

## 컨텍스트 보존

Gemini CLI에는 Claude Code의 자동 Hook 기반 컨텍스트 보존 시스템이 없다. 대안:

- **수동 저장**: 작업 중간에 `작업 내역을 context-snapshot.md로 저장해줘` 지시
- **세션 로그**: Gemini CLI의 `/memory` 기능으로 핵심 사항 기억
- **SOT 기반 복원**: `state.yaml`에 워크플로우 진행 상태를 기록하여 새 세션에서 복원

> Claude Code의 Context Preservation System은 Knowledge Archive에 세션별 phase(단계), phase_flow(전환 흐름), primary_language(주요 언어), error_patterns(Error Taxonomy 12패턴 분류 + resolution 매칭), success_patterns(Edit/Write→Bash 성공 시퀀스), tool_sequence(RLE 압축 도구 시퀀스), final_status(success/incomplete/error/unknown), tags(경로 기반 검색 태그), session_duration_entries(세션 길이) 메타데이터를 자동 기록하고, 스냅샷의 설계 결정은 품질 태그 우선순위(`[explicit]` > `[decision]` > `[rationale]` > `[intent]`)로 정렬하여 노이즈를 제거한다. Quality Gate 상태(Verification/pACS 점수·약점)가 IMMORTAL 우선순위로 보존되어 세션 경계에서 유실되지 않는다. 스냅샷 압축 시 IMMORTAL 섹션을 우선 보존하며(압축 감사 추적 포함), 모든 파일 쓰기에 atomic write(temp → rename) 패턴을 적용한다. P1 할루시네이션 봉쇄로 KI 스키마 검증, 부분 실패 격리, SOT 쓰기 패턴 검증, SOT 스키마 검증(8항목 — S1-S6 기본 + S7 pacs 5필드 + S8 active_team 5필드), Adversarial Review P1 검증(R1-R5 구조 + pACS Delta), Translation P1 검증(T1-T9 번역 품질 + glossary 신선도), Verification Log P1 검증(V1a-V1c 구조적 무결성), pACS P1 검증(PA1-PA6 pACS 로그 구조 무결성), L0 Anti-Skip Guard(L0a-L0c 산출물 파일 검증)이 결정론적으로 수행된다. SessionStart에서 Error→Resolution 매칭 결과가 자동 표면화되어 반복 에러 방지에 활용된다. Gemini에서는 이 정보를 수동으로 기록하거나, 세션 종료 시 상태를 `state.yaml`에 요약하는 방식으로 대응한다.

## 설계 원칙

- **P1**: AI에게 전달하기 전 Python 등으로 노이즈 제거 (전처리/후처리 명시)
- **P2**: 전문 에이전트에게 위임하여 품질 극대화
- **P3**: 이미지/리소스의 정확한 경로 명시. placeholder 누락 불가
- **P4**: 사용자 질문은 최대 4개, 각 3개 선택지. 모호함 없으면 질문 없이 진행

## 언어 및 스타일

- **프레임워크 문서·사용자 대화**: 한국어
- **워크플로우 실행**: 영어 (AI 성능 극대화 — 절대 기준 1 근거). 상세: AGENTS.md §5.2
- **최종 산출물**: 영어 원본 + 한국어 번역 쌍 (`@translator` 서브에이전트)
- **기술 용어**: 영어 유지 (SOT, Agent, Orchestrator, Hooks 등)
- **시각화**: Mermaid 다이어그램 선호
- **깊이**: 간략 요약보다 포괄적·데이터 기반 서술 선호
