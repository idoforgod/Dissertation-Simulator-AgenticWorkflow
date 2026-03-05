# AgenticWorkflow — GitHub Copilot 지시서

> 이 프로젝트에서 작업하는 모든 AI는 AgenticWorkflow 방법론을 따라야 한다.

## 필수 참조

이 프로젝트의 모든 절대 기준, 설계 원칙, 워크플로우 구조는 `AGENTS.md`에 정의되어 있다.
Copilot CLI는 `AGENTS.md`를 자동으로 인식하므로, 해당 파일의 모든 규칙이 자동 적용된다.
상세 아키텍처는 `AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md`를 참조한다.
설계 결정 이력은 `DECISION-LOG.md`를 참조한다.

## 유전 설계 (DNA Inheritance)

이 프로젝트는 자식 agentic workflow system을 생성하는 부모 유기체이다.
모든 자식 시스템은 부모의 전체 게놈(절대 기준, SOT, 4계층 검증, Safety Hook 등)을 구조적으로 내장한다.
상세: `soul.md`, `AGENTS.md §1`.

## 절대 기준 (핵심 요약)

1. **품질 최우선** — 속도, 비용, 작업량보다 최종 결과물의 품질이 유일한 기준
2. **단일 파일 SOT** — 모든 공유 상태는 단일 파일에 집중. 쓰기 권한은 Orchestrator만
3. **코드 변경 프로토콜** — 의도 파악 → 영향 범위 분석 → 변경 설계 3단계 수행. 분석 깊이는 변경 규모에 비례. **코딩 기준점(CAP-1~4)**: 코딩 전 사고, 단순성 우선, 목표 기반 실행, 외과적 변경

> **상세 내용**: AGENTS.md §2 참조.

## 워크플로우 구조

모든 워크플로우는 3단계: **Research** → **Planning** → **Implementation**.

## Copilot 구현 매핑

| AgenticWorkflow 개념 | Copilot 대응 |
|---------------------|-------------|
| 전문 에이전트 | Copilot의 단일 세션 내 역할 지정 |
| 자동 검증 | GitHub Actions 또는 외부 스크립트로 구현 |
| SOT 상태관리 | `state.yaml` 파일 — 단일 쓰기 지점 원칙 동일 적용. SOT 파일 형식: `state.yaml`, `state.yml`, `state.json` |
| Autopilot Mode | SOT의 `autopilot.enabled` 필드로 제어. `(human)` 단계 자동 승인. Anti-Skip Guard: 산출물 파일 존재 + 최소 100 bytes 검증. `AGENTS.md §5.1` 참조 |
| ULW (Ultrawork) Mode | 프롬프트에 `ulw` 포함 시 활성화. Autopilot과 직교하는 철저함 강도 오버레이. 3가지 강화 규칙(Intensifiers): Sisyphus Persistence(3회 재시도) + Mandatory Task Decomposition + Bounded Retry Escalation. `AGENTS.md §5.1.1` 참조 |
| Verification Protocol | 각 단계 산출물의 기능적 목표 100% 달성 검증. Anti-Skip Guard(물리적) 위에 의미론적 Verification Gate 계층. 검증 기준은 Task 앞에 선언, 실패 시 최대 10회 재시도(ULW 활성 시 15회). `AGENTS.md §5.3` 참조 |
| pACS (자체 신뢰 평가) | Verification Gate 통과 후 에이전트가 F/C/L 3차원 자기 평가. Pre-mortem Protocol 필수. min-score 원칙. GREEN(≥70): 자동 진행, YELLOW(50-69): 플래그 후 진행, RED(<50): 재작업. `AGENTS.md §5.4` 참조 |
| Adversarial Review (Enhanced L2) | 기존 L2 Calibration을 대체하는 강화된 품질 검증. `@reviewer`(코드/산출물 비판적 분석) + `@fact-checker`(외부 사실 검증). P1 검증(`validate_review.py` R1-R5)으로 리뷰 품질 보장. `AGENTS.md §5.5` 참조 |
| Translation Protocol | 영어 산출물 → 한국어 번역. `@translator` 서브에이전트가 `glossary.yaml` 기반 용어 일관성 유지. P1 검증(`validate_translation.py` T1-T9, `validate_verification.py` V1a-V1c). Review PASS가 Translation의 전제. `AGENTS.md §5.2` 참조 |
| Predictive Debugging (L-1) | 에러 이력 기반 위험 파일 사전 경고. `predictive_debug_guard.py`(PreToolUse 경고 전용) + `aggregate_risk_scores()`(SessionStart P1 집계) + `validate_risk_scores()`(RS1-RS6 검증). `risk-scores.json` 캐시. `_context_lib.py` + `docs/protocols/context-preservation-detail.md` 참조 |

## 컨텍스트 보존

Copilot CLI에는 자동 Hook 기반 컨텍스트 보존이 없다. 대안:

- **수동 저장**: 작업 진행 시 `state.yaml`에 현재 상태 기록
- **세션 재개**: `/resume SESSION-ID`로 이전 세션 이어가기
- **스냅샷**: 중요 시점에 작업 내역을 MD 파일로 수동 저장

> Claude Code의 Context Preservation System은 5개 Hook으로 자동 저장·복원하며, Knowledge Archive에 세션별 phase(단계), phase_flow(전환 흐름), primary_language(주요 언어), error_patterns(Error Taxonomy 12패턴 분류), tool_sequence(RLE 압축), final_status(세션 종료 상태) 메타데이터를 자동 기록한다. 스냅샷 압축 시 IMMORTAL 섹션을 우선 보존한다. P1 할루시네이션 봉쇄로 KI 스키마 검증, SOT 스키마 검증(8항목), Adversarial Review P1(R1-R5), Translation P1(T1-T9), Verification Log P1(V1a-V1c), pACS P1(PA1-PA6), L0 Anti-Skip Guard(L0a-L0c)이 결정론적으로 수행된다. Copilot에서는 이 정보를 `state.yaml`에 수동 기록하거나, 스냅샷 MD 파일에 세션 메타데이터를 포함하는 방식으로 대응한다.

## 설계 원칙

- **P1**: AI에게 전달하기 전 Python 등으로 노이즈 제거 (전처리/후처리 명시)
- **P2**: 전문 에이전트에게 위임하여 품질 극대화
- **P3**: 리소스의 정확한 경로 명시. placeholder 누락 불가
- **P4**: 사용자 질문은 최대 4개, 각 3개 선택지

## 언어 및 스타일

### English-First 강제 (MANDATORY)

> 워크플로우 전체 진행·에이전트 작업·최종 결과물은 **영어** (강제). 영어 원본 완성 → `@translator`로 한국어 번역 (순서 역전 불가). 절대 기준 1(품질)의 직접적 구현. 상세: AGENTS.md §5.2

- **프레임워크 문서·사용자 대화**: 한국어 (허용) / **기술 용어**: 영어 유지 / **시각화**: Mermaid 선호
