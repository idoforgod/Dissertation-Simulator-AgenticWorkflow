# AgenticWorkflow Decision Log (ADR)

이 문서는 AgenticWorkflow 프로젝트의 **모든 주요 설계 결정**을 시간순으로 기록한다.
각 결정은 ADR(Architecture Decision Record) 형식을 따르며, 맥락·결정·근거·대안·상태를 포함한다.

> **목적**: 프로젝트의 "왜?"를 추적하여, 미래의 의사결정자(사람 또는 AI)가 기존 결정의 맥락을 이해하고 일관된 판단을 내릴 수 있게 한다.

---

## ADR 형식

```
### ADR-NNN: 제목
- **날짜**: YYYY-MM-DD (커밋 기준)
- **상태**: Accepted / Superseded / Deprecated
- **맥락**: 결정이 필요했던 상황
- **결정**: 선택한 방향
- **근거**: 선택의 이유
- **대안**: 검토했으나 선택하지 않은 방향
- **관련 커밋**: 해시 + 메시지
```

---

## 1. Foundation (프로젝트 기반)

### ADR-001: 워크플로우는 중간물, 동작하는 시스템이 최종 산출물

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: 많은 자동화 프로젝트가 "계획을 세우는 것"에서 멈춘다. workflow.md를 만드는 것 자체가 목표가 되는 함정을 방지해야 했다.
- **결정**: 프로젝트를 2단계로 구분한다 — Phase 1(workflow.md 설계 = 중간 산출물), Phase 2(에이전트·스크립트·자동화가 실제 동작 = 최종 산출물).
- **근거**: 설계도가 아무리 정교해도 실행되지 않으면 미완성이다. Phase 2가 없는 Phase 1은 가치의 절반만 달성한다.
- **대안**: workflow.md 자체를 최종 산출물로 취급 → 기각 (실행 가능성 검증 불가)
- **관련 커밋**: `348601e` Initial commit: AgenticWorkflow project

### ADR-002: 절대 기준 체계 — 3개 기준의 계층적 우선순위

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: 프로젝트에 여러 설계 원칙이 존재하는데, 원칙 간 충돌 시 판단 기준이 필요했다. "빠르게 할지 vs 품질을 높일지", "SOT 단순성 vs 기능 확장" 등의 트레이드오프가 반복되었다.
- **결정**: 3개 절대 기준을 정의하고, 명시적 우선순위를 설정한다:
  1. **절대 기준 1 (품질)** — 최상위. 모든 기준의 존재 이유.
  2. **절대 기준 2 (SOT)** — 데이터 무결성 보장 수단. 품질에 종속.
  3. **절대 기준 3 (CCP)** — 코드 변경 품질 보장 수단. 품질에 종속.
- **근거**: 추상적인 "모든 원칙이 중요하다"는 실전에서 작동하지 않는다. 명시적 우선순위가 있어야 충돌 시 결정론적으로 해소할 수 있다.
- **대안**:
  - 모든 원칙을 동위 → 기각 (충돌 해소 기준 부재)
  - SOT를 최상위 → 기각 (데이터 무결성이 목적이 아닌 수단)
- **관련 커밋**: `348601e` Initial commit

### ADR-003: 품질 절대주의 — 속도·비용·분량 완전 무시

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: AI 기반 자동화에서 토큰 비용, 실행 시간, 에이전트 수를 최소화하려는 경향이 있다. 이로 인해 단계를 생략하거나, 산출물을 축약하거나, 검증을 건너뛰는 안티패턴이 발생한다.
- **결정**: "속도, 토큰 비용, 작업량, 분량 제한은 **완전히 무시**한다. 유일한 의사결정 기준은 최종 결과물의 품질이다."
- **근거**: 비용 절감으로 품질이 떨어지면, 결국 재작업 비용이 더 크다. 처음부터 최고 품질을 목표로 하는 것이 장기적으로 효율적이다.
- **대안**: 비용-품질 트레이드오프 매트릭스 → 기각 (판단 복잡도 증가, 항상 비용 쪽으로 기울어지는 인센티브 구조)
- **관련 커밋**: `348601e` Initial commit

### ADR-004: Research → Planning → Implementation 3단계 구조적 제약

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: 워크플로우의 단계 수와 구조를 자유롭게 정할 수 있으면, 에이전트가 Research를 건너뛰거나 Planning 없이 구현에 들어가는 문제가 발생한다.
- **결정**: 모든 워크플로우는 반드시 3단계(Research → Planning → Implementation)를 따른다. 이것은 관례가 아닌 구조적 제약이다.
- **근거**:
  - Research 생략 → 불충분한 정보로 작업 → 품질 하락 (절대 기준 1 위반)
  - Planning 생략 → 사람 검토 없이 구현 → 방향 오류 누적
  - Implementation 생략 → 설계도만 존재하는 미완성 시스템 (ADR-001 위반)
- **대안**: 유연한 N단계 → 기각 (구조적 보장 없음)
- **관련 커밋**: `348601e` Initial commit

### ADR-005: 설계 원칙 P1-P4 — 절대 기준의 하위 원칙

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: 절대 기준은 "무엇을 최적화하는가"를 정의하지만, "어떻게"에 대한 구체적 지침이 필요했다.
- **결정**: 4개 설계 원칙을 정의한다:
  - **P1**: 정확도를 위한 데이터 정제 (Code가 정제, AI가 판단)
  - **P2**: 전문성 기반 위임 구조 (Orchestrator는 조율만)
  - **P3**: 리소스 정확성 (placeholder 누락 불가)
  - **P4**: 질문 설계 규칙 (최대 4개, 각 3개 선택지)
- **근거**: P1은 RLM 논문의 Code-based Filtering, P2는 재귀적 Sub-call과 대응. P3은 실행 가능성 보장, P4는 사용자 피로 최소화.
- **대안**: 원칙 없이 절대 기준만으로 운영 → 기각 (너무 추상적)
- **관련 커밋**: `348601e` Initial commit

### ADR-006: 단일 파일 SOT 패턴

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: 수십 개의 에이전트가 동시에 작동하는 환경에서, 상태를 여러 파일에 분산하면 데이터 불일치가 불가피하다.
- **결정**: 모든 공유 상태는 단일 파일(`state.yaml`)에 집중한다. 쓰기 권한은 Orchestrator/Team Lead만 보유하고, 나머지 에이전트는 읽기 전용 + 산출물 파일 생성만 한다.
- **근거**: 단일 쓰기 지점 패턴은 분산 시스템의 데이터 일관성을 보장하는 검증된 패턴이다. 복수 에이전트의 동시 수정으로 인한 충돌을 원천 차단한다.
- **대안**:
  - 분산 상태 + 병합 전략 → 기각 (복잡도 폭발, 충돌 해소 오버헤드)
  - 데이터베이스 기반 → 기각 (외부 의존성, 오버엔지니어링)
- **관련 커밋**: `348601e` Initial commit

### ADR-007: 코드 변경 프로토콜 (CCP) + 비례성 규칙

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: 코드 변경 시 파급 효과를 분석하지 않으면, 한 곳의 수정이 예상치 못한 곳에서 에러를 발생시킨다 (샷건 서저리).
- **결정**: 코드 변경 전 반드시 3단계(의도 파악 → 영향 범위 분석 → 변경 설계)를 수행한다. 단, 비례성 규칙으로 변경 규모에 따라 분석 깊이를 조절한다:
  - 경미(오타, 주석) → Step 1만
  - 표준(함수/로직 변경) → 전체 3단계
  - 대규모(아키텍처, API) → 전체 3단계 + 사전 사용자 승인
- **근거**: 프로토콜 자체를 건너뛰지는 않되, 사소한 변경에 과도한 분석은 절대 기준 1(품질) 위반이다. 비례성 규칙으로 프로토콜의 존재와 실용성을 동시에 보장한다.
- **대안**: 모든 변경에 동일한 깊이 적용 → 기각 (오타 수정에 풀 분석은 비생산적)
- **관련 커밋**: `348601e` Initial commit

---

## 2. Documentation Architecture (문서 아키텍처)

### ADR-008: Hub-and-Spoke 문서 구조 — AGENTS.md를 Hub으로

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: 여러 AI 도구(Claude Code, Cursor, Copilot, Gemini)가 각자의 설정 파일을 갖는데, 공통 규칙을 각 파일에 중복 작성하면 동기화 문제가 발생한다.
- **결정**: Hub-and-Spoke 패턴을 채택한다:
  - **Hub**: `AGENTS.md` — 모든 AI 에이전트 공통 규칙 (방법론 SOT)
  - **Spoke**: `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.cursor/rules/agenticworkflow.mdc` — 각 도구별 구현 상세
- **근거**: 공통 규칙의 단일 정의 지점(AGENTS.md)을 유지하면서, 도구별 특수 사항(Hook 설정, Slash Command 등)은 각 Spoke에서 다룬다. 이는 절대 기준 2(SOT)의 문서 차원 적용이다.
- **대안**:
  - 단일 통합 문서 → 기각 (도구별 특수 사항 포함 시 비대해짐)
  - 완전 독립 문서 → 기각 (공통 규칙 중복, 동기화 불가)
- **관련 커밋**: `5b649cb` feat: Hub-and-Spoke universal system prompt for all AI CLI tools

### ADR-009: RLM 논문을 이론적 기반으로 채택

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: 에이전트 아키텍처의 설계 배경이 필요했다. "왜 SOT를 외부 파일로 관리하는가", "왜 Python으로 전처리하는가"에 대한 이론적 근거가 필요했다.
- **결정**: MIT CSAIL의 Recursive Language Models (RLM) 논문을 이론적 기반으로 채택한다. RLM의 핵심 패러다임 — "프롬프트를 신경망에 직접 넣지 말고, 외부 환경의 객체로 취급하라" — 이 AgenticWorkflow의 설계 전반에 적용된다.
- **근거**: RLM의 Python REPL ↔ SOT, 재귀적 Sub-call ↔ Sub-agent 위임, Code-based Filtering ↔ P1 원칙 등 구조적 대응이 정확하다. 이론적 뿌리가 있으면 설계 일관성을 유지하기 쉽다.
- **대안**: 독자적 프레임워크 → 기각 (이론적 검증 부재)
- **관련 커밋**: `e051837` docs: Add coding-resource PDF

### ADR-010: 독립 아키텍처 문서 분리

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: CLAUDE.md(무엇이 있는가), AGENTS.md(어떤 규칙인가), USER-MANUAL(어떻게 쓰는가)은 있지만, "왜 이렇게 설계했는가"를 체계적으로 서술하는 문서가 없었다.
- **결정**: `AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md`를 별도 문서로 생성한다. 설계 철학, 아키텍처 조감도, 구성 요소 관계, 설계 원칙의 이론적 배경을 서술한다.
- **근거**: "WHY" 문서가 없으면, 시간이 지남에 따라 설계 결정의 맥락이 유실되고, 상충하는 수정이 발생한다.
- **대안**: CLAUDE.md에 통합 → 기각 (프롬프트 크기 증가, 도구별 지시서와 철학 문서의 성격 차이)
- **관련 커밋**: `feba502` docs: Add architecture and philosophy document

### ADR-011: Spoke 파일 정리 — 사용하지 않는 도구 제거

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: 초기에 Amazon Q, Windsurf, Aider 등 다양한 AI 도구용 Spoke 파일을 만들었지만, 실제로 사용하지 않는 도구의 설정 파일이 유지보수 부담이 되었다.
- **결정**:
  - `.amazonq/`, `.windsurf/` 삭제 및 모든 문서에서 참조 제거
  - `.aider.conf.yml` 삭제 및 참조 제거
  - `.github/copilot-instructions.md`는 삭제 후 복원 (실제 사용 중)
- **근거**: 사용하지 않는 파일은 동기화 대상만 늘리고 품질에 기여하지 않는다. 필요할 때 다시 만들면 된다.
- **대안**: 모든 Spoke 유지 → 기각 (문서 동기화 시 불필요한 작업량 증가)
- **관련 커밋**: `162a322`, `a4afb26`, `708cb57` (복원), `5634b0e`

---

## 3. Context Preservation System (컨텍스트 보존)

### ADR-012: Hook 기반 컨텍스트 자동 보존 시스템

- **날짜**: 2026-02-16
- **상태**: Accepted
- **맥락**: Claude Code의 컨텍스트 윈도우가 소진되면(`/clear`, 압축), 진행 중이던 작업 맥락이 완전히 상실된다. 수동 저장은 까먹기 쉽고, 일관성이 없다.
- **결정**: 5개 Hook 이벤트(SessionStart, PostToolUse, Stop, PreCompact, SessionEnd)에 Python 스크립트를 연결하여 자동 저장·복원 시스템을 구축한다. RLM 패턴(외부 메모리 객체 + 포인터 기반 복원)을 적용한다.
- **근거**: 자동화된 보존은 사용자 개입 없이 100% 작동한다. RLM 패턴을 적용하면 전체 내역을 주입하는 대신, 포인터+요약으로 필요한 부분만 로드할 수 있다.
- **대안**:
  - 수동 저장 (`/save` 커맨드) → 기각 (까먹기 쉬움)
  - 전체 트랜스크립트 백업 → 기각 (크기 문제, 컨텍스트 윈도우에 못 넣음)
- **관련 커밋**: `bb7b9a1` feat: Add Context Preservation Hook System

### ADR-013: Knowledge Archive — 세션 간 축적 인덱스

- **날짜**: 2026-02-17
- **상태**: Accepted
- **맥락**: 단일 세션의 스냅샷만으로는 프로젝트의 장기적 이력을 추적할 수 없다. "이전에 비슷한 에러를 어떻게 해결했는가?" 같은 cross-session 질문에 답할 수 없었다.
- **결정**: `knowledge-index.jsonl`에 세션별 메타데이터를 구조화하여 축적한다. Grep으로 프로그래밍적 탐색이 가능한 형태로 설계한다 (RLM sub-call 대응).
- **근거**: JSONL 형식은 append-only로 동시성 문제가 적고, Grep/jq로 프로그래밍적 탐색이 가능하다. 이는 RLM의 "외부 환경 탐색" 패턴과 일치한다.
- **대안**:
  - SQLite → 기각 (외부 의존성, 텍스트 도구로 탐색 불가)
  - 단순 MD 파일 목록 → 기각 (구조화된 메타데이터 검색 불가)
- **관련 커밋**: `d1acb9f` feat: RLM long-term memory + context quality optimization

### ADR-014: Smart Throttling — 30초 + 5KB 임계값

- **날짜**: 2026-02-17
- **상태**: Accepted
- **맥락**: Stop hook이 매 응답마다 실행되면, 짧은 응답에서도 불필요한 스냅샷이 반복 생성되어 성능에 영향을 준다.
- **결정**: Stop hook에 30초 dedup window + 5KB growth threshold를 적용한다. SessionEnd/PreCompact는 5초 window, SessionEnd는 dedup 면제 (마지막 기회 보장).
- **근거**: 30초 내 변화가 없으면 동일 내용의 스냅샷 재생성은 낭비다. 5KB 성장 임계값은 의미 있는 변화가 있을 때만 갱신하도록 보장한다.
- **대안**: 항상 저장 → 기각 (성능 부담), 시간만 체크 → 기각 (변화 없는 저장 발생)
- **관련 커밋**: `7363cc4` feat: Context memory quality optimization — throttling, archive, restore

### ADR-015: IMMORTAL-aware 압축 + 감사 추적

- **날짜**: 2026-02-19
- **상태**: Accepted
- **맥락**: 스냅샷이 크기 한계를 초과할 때, 단순 절삭(truncation)을 하면 핵심 맥락(현재 작업, 설계 결정, Autopilot/ULW 상태)이 유실될 수 있다.
- **결정**: `<!-- IMMORTAL -->` 마커가 있는 섹션을 우선 보존하고, 비-IMMORTAL 콘텐츠를 먼저 절삭한다. 압축 각 Phase(1~7)가 제거한 문자 수를 HTML 주석으로 기록한다 (감사 추적).
- **근거**: "현재 작업"과 "설계 결정"은 세션 복원의 핵심이다. 이것이 유실되면 복원 품질이 급락한다. 감사 추적은 압축 동작의 디버깅을 가능하게 한다.
- **대안**: 균등 절삭 → 기각 (핵심 맥락 유실 위험), 우선순위 없는 FIFO → 기각 (최근 맥락만 보존, 오래된 핵심 결정 유실)
- **관련 커밋**: `2c91985` feat: Context Preservation 품질 강화 — 18항목 감사·성찰 구현

### ADR-016: E5 Empty Snapshot Guard — 다중 신호 감지

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: tool_use가 0인 빈 스냅샷이 기존의 풍부한 `latest.md`를 덮어쓰는 문제가 발생했다. 단순 크기 비교로는 "작지만 의미 있는" 스냅샷을 정확히 구분할 수 없었다.
- **결정**: 다중 신호 감지(크기 ≥ 3KB OR ≥ 2개 섹션 마커)로 "풍부한 스냅샷"을 정의하고, `is_rich_snapshot()` + `update_latest_with_guard()` 중앙 함수로 Stop hook과 save_context.py 모두에서 보호한다.
- **근거**: 단일 기준(크기만)은 false positive/negative가 높다. 크기 OR 구조적 마커의 다중 신호가 더 정확하다.
- **대안**: 항상 덮어쓰기 → 기각 (데이터 유실), 크기만 비교 → 기각 (small-but-rich 케이스 미처리)
- **관련 커밋**: `f76a1fd` feat: P1 할루시네이션 봉쇄 + E5 Guard 중앙화

### ADR-017: Error Taxonomy 12패턴 + Error→Resolution 매칭

- **날짜**: 2026-02-19
- **상태**: Accepted
- **맥락**: Knowledge Archive에 에러 패턴을 기록할 때, "unknown" 분류가 대다수를 차지하여 cross-session 에러 분석이 불가능했다.
- **결정**: 12개 regex 패턴(file_not_found, permission, syntax, timeout, dependency, edit_mismatch, type_error, value_error, connection, memory, git_error, command_not_found)으로 에러를 분류한다. False positive 방지를 위해 negative lookahead, 한정어 매칭을 적용한다. 에러 발생 후 5 entries 이내의 성공적 도구 호출을 file-aware로 탐지하여 resolution을 기록한다.
- **근거**: 구조화된 에러 분류가 있어야 "이 에러를 과거에 어떻게 해결했는가"를 프로그래밍적으로 탐색할 수 있다. Resolution 매칭은 에러-해결 쌍을 자동으로 연결한다.
- **대안**: 에러 텍스트 그대로 기록 → 기각 (검색 불가, 패턴 분석 불가)
- **관련 커밋**: `ce0c393` fix: 2차 감사 22개 이슈 구현, `eed44e7` fix: 3차 성찰 5건 수정

### ADR-018: context_guard.py 통합 디스패처

- **날짜**: 2026-02-17
- **상태**: Accepted
- **맥락**: Global Hook(~/.claude/settings.json)에서 4개 이벤트(Stop, PostToolUse, PreCompact, SessionStart)를 각각 별도 스크립트로 연결하면 설정이 복잡하고, 공통 로직(경로 해석, 에러 핸들링)이 중복된다.
- **결정**: `context_guard.py`를 단일 진입점으로 사용하고, `--mode` 인자로 라우팅한다. Setup Hook만 프로젝트 설정에서 직접 실행한다 (세션 시작 전 인프라 검증이라 디스패처와 독립).
- **근거**: 단일 진입점은 유지보수가 쉽고, 공통 로직(경로, 에러)을 한 곳에서 관리할 수 있다.
- **대안**: 각 이벤트별 독립 스크립트 → 기각 (설정 복잡도 증가, 공통 로직 중복)
- **관련 커밋**: `0f38784` feat: Fix broken hooks + optimize context memory for quality

---

## 4. Automation Modes (자동화 모드)

### ADR-019: Autopilot Mode — Human Checkpoint 자동 승인

- **날짜**: 2026-02-17
- **상태**: Accepted
- **맥락**: 워크플로우 실행 시 `(human)` 단계마다 사용자가 직접 승인해야 하면, 장시간 워크플로우에서 사용자가 자리를 비울 수 없다.
- **결정**: `autopilot.enabled: true`로 SOT에 설정하면, `(human)` 단계와 `AskUserQuestion`을 품질 극대화 기본값으로 자동 승인한다. 단, Hook exit code 2는 변경 없이 차단한다 (결정론적 검증은 자동 대행 대상이 아님).
- **근거**: 사람의 판단만 AI가 대행하고, 코드의 결정론적 검증은 그대로 유지한다. 모든 자동 승인은 Decision Log에 기록하여 투명성을 보장한다.
- **대안**:
  - 완전 자동 (Hook 차단도 무시) → 기각 (품질 게이트 무력화)
  - 시간 기반 자동 승인 (N분 대기 후) → 기각 (인위적 대기, 비생산적)
- **관련 커밋**: `b0ae5ac` feat: Autopilot Mode runtime enforcement

### ADR-020: Autopilot 런타임 강화 — 하이브리드 Hook + 프롬프트

- **날짜**: 2026-02-17
- **상태**: Accepted
- **맥락**: Autopilot의 설계 의도(완전 실행, 축약 금지, Decision Log 기록)가 프롬프트만으로는 세션 경계에서 유실될 수 있다.
- **결정**: 하이브리드 강화 시스템을 구축한다:
  - **Hook (결정론적)**: SessionStart가 규칙 주입, 스냅샷이 IMMORTAL로 상태 보존, Stop이 Decision Log 누락 감지
  - **프롬프트 (행동 유도)**: Execution Checklist로 각 단계의 필수 행동 명시
- **근거**: Hook은 AI의 해석에 의존하지 않고 결정론적으로 동작한다. 프롬프트는 AI의 행동을 유도하지만 보장하지 못한다. 두 계층의 결합이 가장 강력하다.
- **대안**: 프롬프트만으로 → 기각 (세션 경계에서 유실), Hook만으로 → 기각 (세밀한 행동 유도 불가)
- **관련 커밋**: `b0ae5ac` feat: Autopilot Mode runtime enforcement

### ADR-021: Agent Team (Swarm) 패턴 — 2계층 SOT 프로토콜

- **날짜**: 2026-02-18
- **상태**: Accepted
- **맥락**: 병렬 에이전트가 동시에 작업할 때, SOT에 대한 동시 쓰기를 방지하면서도 팀원 간 산출물 참조가 가능해야 했다.
- **결정**: Team Lead만 SOT 쓰기 권한을 갖고, Teammate는 산출물 파일 생성만 한다. 품질 향상이 입증되는 경우에만 팀원 간 산출물 직접 참조를 허용한다 (교차 검증, 피드백 루프).
- **근거**: 절대 기준 2(SOT)와 절대 기준 1(품질)의 균형점. SOT 단일 쓰기는 유지하되, 품질을 위한 팀원 간 직접 참조는 예외로 허용한다.
- **대안**: 모든 팀원이 SOT 쓰기 → 기각 (절대 기준 2 위반), 팀원 간 완전 격리 → 기각 (교차 검증 불가)
- **관련 커밋**: `42ee4b1` feat: Agent Team(Swarm) 패턴 통합

### ADR-022: Verification Protocol — Anti-Skip Guard + Verification Gate + pACS

- **날짜**: 2026-02-19
- **상태**: Accepted
- **맥락**: Autopilot에서 산출물 없이 다음 단계로 넘어가거나, 형식적으로만 완료 표시하는 문제를 방지해야 했다.
- **결정**: 4계층 품질 보장 아키텍처를 도입한다:
  - **L0 Anti-Skip Guard** (결정론적): 산출물 파일 존재 + 최소 크기(100 bytes)
  - **L1 Verification Gate** (의미론적): 산출물이 Verification 기준을 100% 달성했는지 자기 검증
  - **L1.5 pACS Self-Rating** (신뢰도): Pre-mortem Protocol → F/C/L 3차원 채점 → RED(< 50) 시 재작업
  - **L2 Calibration** (선택적): 별도 verifier 에이전트가 pACS 교차 검증
- **근거**: 물리적 검증(파일 존재)과 의미론적 검증(내용 완전성)과 신뢰도 검증(약점 인식)은 서로 다른 차원이다. 각 계층이 독립적으로 다른 종류의 실패를 잡는다.
- **대안**: Anti-Skip Guard만 → 기각 (빈 파일도 통과 가능), Verification Gate만 → 기각 (AI의 자기 검증은 과대평가 경향)
- **관련 커밋**: `f592483` feat: Verification Protocol 추가

### ADR-023: ULW (Ultrawork) Mode — SOT 없이 동작하는 범용 모드

- **날짜**: 2026-02-20
- **상태**: Superseded by ADR-043
- **맥락**: Autopilot은 워크플로우 전용(SOT 기반)이지만, 워크플로우가 아닌 일반 작업(리팩토링, 문서 업데이트 등)에서도 "멈추지 않고 끝까지 완료하는" 모드가 필요했다.
- **결정**: `ulw`를 프롬프트에 포함하면 활성화되는 ULW 모드를 만든다. SOT 없이 5개 실행 규칙(Sisyphus, Auto Task Tracking, Error Recovery, No Partial Completion, Progress Reporting)으로 동작한다. 새 세션에서는 암묵적으로 해제된다 (명시적 해제 불필요).
- **근거**: Autopilot은 SOT 의존적이라 일반 작업에 부적합하다. ULW는 TaskCreate/TaskList 기반으로 경량화하여, 워크플로우 인프라 없이도 완료 보장을 제공한다.
- **대안**: Autopilot 확장 → 기각 (SOT 강제 요구는 일반 작업에 과도), 모드 없음 → 기각 (AI가 중간에 멈추는 문제 미해결)
- **관련 커밋**: `c7324f1` feat: ULW (Ultrawork) Mode 구현

---

## 5. Quality & Safety (품질 및 안전)

### ADR-024: P1 할루시네이션 봉쇄 — 4개 메커니즘

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: Hook 시스템에서 반복적으로 100% 정확해야 하는 작업(스키마 검증, SOT 쓰기 방지 등)이 있는데, AI의 확률적 판단에 의존하면 hallucination 위험이 있다.
- **결정**: 4개 결정론적 메커니즘을 Python 코드로 구현한다:
  1. **KI 스키마 검증**: `_validate_session_facts()` — 10개 필수 키 보장
  2. **부분 실패 격리**: archive 실패가 index 갱신을 차단하지 않음
  3. **SOT 쓰기 패턴 검증**: AST 기반으로 Hook 스크립트의 SOT 쓰기 시도 탐지
  4. **SOT 스키마 검증**: `validate_sot_schema()` — 6항목 구조 무결성
- **근거**: "반복적으로 100% 정확해야 하는 작업"은 AI가 아닌 코드가 수행해야 한다 (P1 원칙의 극단적 적용). 코드는 hallucinate하지 않는다.
- **대안**: AI에게 스키마 검증 요청 → 기각 (확률적, 누락 가능성), 검증 없이 운영 → 기각 (silent corruption 위험)
- **관련 커밋**: `f76a1fd` feat: P1 할루시네이션 봉쇄 + E5 Guard 중앙화

### ADR-025: Atomic Write 패턴 — Crash-safe 파일 쓰기

- **날짜**: 2026-02-18
- **상태**: Accepted
- **맥락**: Hook 스크립트가 스냅샷, 아카이브, 로그를 쓰는 도중 프로세스가 크래시하면, 부분 쓰기로 파일이 손상될 수 있다.
- **결정**: 모든 파일 쓰기에 atomic write 패턴(temp file → `os.rename`)을 적용한다. `fcntl.flock`으로 동시 접근을 보호하고, `os.fsync()`로 내구성을 보장한다.
- **근거**: `os.rename`은 POSIX에서 atomic이므로, 중간 상태가 노출되지 않는다. 프로세스 크래시 시에도 이전 상태가 온전히 유지된다.
- **대안**: 직접 쓰기 → 기각 (크래시 시 부분 쓰기), 데이터베이스 트랜잭션 → 기각 (오버엔지니어링)
- **관련 커밋**: `2c91985` feat: Context Preservation 품질 강화

### ADR-026: 결정 품질 태그 정렬 — IMMORTAL 슬롯 최적화

- **날짜**: 2026-02-19
- **상태**: Accepted
- **맥락**: 스냅샷의 "주요 설계 결정" 섹션(15개 슬롯)에서 일상적 의도 선언("하겠습니다" 패턴)이 실제 설계 결정을 밀어내는 문제가 있었다.
- **결정**: 4단계 품질 태그 기반 정렬을 도입한다: `[explicit]` > `[decision]` > `[rationale]` > `[intent]`. 비교·트레이드오프·선택 패턴도 추출하여, 고신호 결정이 15개 슬롯을 우선 차지한다.
- **근거**: 한정된 슬롯에서 "하겠습니다"보다 "A 대신 B를 선택했다, 이유는..."이 복원 시 훨씬 더 가치 있다.
- **대안**: 시간순 → 기각 (최근 intent가 오래된 decision을 밀어냄), 필터링 없음 → 기각 (노이즈가 신호를 압도)
- **관련 커밋**: `2c91985` feat: Context Preservation 품질 강화

### ADR-047: Abductive Diagnosis Layer — 품질 게이트 FAIL 시 구조화된 진단

- **날짜**: 2026-02-23
- **상태**: Accepted
- **맥락**: 4계층 품질 보장(L0→L1→L1.5→L2)에서 게이트 FAIL 시 즉시 재시도하는 구조는 "왜 실패했는가?"를 분석하지 않아, 동일한 실패를 반복하거나 비효율적 재시도가 발생한다.
- **결정**: FAIL과 재시도 사이에 3단계 진단(P1 사전 증거 수집 → LLM 판단 → P1 사후 검증)을 삽입한다. 기존 4계층 QA는 변경하지 않는 부가 계층(additive-only)으로 구현한다. 진단 결과는 `diagnosis-logs/`에만 기록하고 SOT는 수정하지 않는다. Fast-Path(FP1-FP3)로 결정론적 단축 경로를 제공한다.
- **근거**: (1) 재시도 품질 향상 — 실패 원인에 맞는 수정 전략 선택, (2) 하위 호환성 — diagnosis-logs/ 없으면 기존 동작 그대로, (3) cross-session 학습 — Knowledge Archive에 diagnosis_patterns 아카이빙으로 패턴 축적.
- **대안**: (a) SOT에 진단 상태 추가 → 기각 (SOT 스키마 복잡성 증가, 절대 기준 2 부담), (b) 재시도 횟수만 증가 → 기각 (근본 원인 미분석, 동일 실패 반복), (c) 별도 진단 에이전트 → 기각 (과도한 복잡성, 오케스트레이터 내 진단으로 충분)
- **관련 커밋**: (pending)

### ADR-051: Claude Code v2.1 신기능 연구 — 기존 설계 타당성 검증 + 선별적 채택

- **날짜**: 2026-03-02
- **상태**: Accepted
- **맥락**: YouTube 영상 "쏟아지는 클로드코드 업데이트" (개발동생) 및 claudefa.st 기술 문서에서 Claude Code v2.1 신기능 5가지(Ralph Loop, Remote Control, Auto-memory, `/simplify` 3-agent 병렬 리뷰, `/batch` 병렬 단계 실행)를 조사. 3차에 걸친 심층 성찰(CCP Step 2 파급 효과 분석 + 절대 기준 1 품질 검증 + 필요성 재검토)을 수행하여 채택/보류/기각을 판정.
- **결정**:
  1. **3-Lens 병렬 리뷰 — 보류**: `/simplify`의 3-agent 병렬 패턴을 L2 리뷰에 적용하는 안. 기존 `@reviewer` 프로토콜(7단계 + 5렌즈 + Pre-mortem + 최소 1 이슈 + 독립 pACS)이 이미 체계적이며, 3-Lens가 해결하는 실증된 품질 문제가 미확인. pACS 3차원과 3-Lens 전문화의 구조적 비정합(결함 1), 교차 영역 결함 탐지 공백(결함 2), 합성 단계 P1 공백(결함 3) 식별. `@reviewer`가 특정 유형의 결함을 체계적으로 놓치는 사례가 축적될 때 재검토.
  2. **Batch Autopilot — 기각**: `/batch`의 병렬 단계 실행 패턴. 독립 단계의 병렬 실행은 순차 실행과 산출물 품질이 **동일** (품질 이점 없음). `current_step` 단일 정수가 8+ 파일의 내력벽이며, 변경 시 아키텍처 변경에 해당 (기능 개선 조건 위반). 기존 `(team)` 메커니즘이 품질 기반 병렬화를 이미 지원.
  3. **Sub-agent Persistent Memory — @translator만 채택**: `@translator`에 `memory: project` 추가. glossary.yaml 이외의 문체 판단 축적 가능. `@reviewer`(과거 편향 위험)와 `@fact-checker`(정보 시효 문제 + 독립 검증 원칙 충돌)에는 추가하지 않음. RLM 패턴의 자연스러운 확장.
  4. **Self-Optimization Command — 기각**: 워크플로우 구조 최적화는 workflow-generator 스킬의 책임. 사후 분석 도구가 아닌 generator 자체 개선이 올바른 접근.
- **핵심 발견 — 기존 설계 타당성 검증**:
  - `/simplify` 3-agent → 기존 4계층 품질 게이트(L0→L1→L1.5→L2)가 이미 대응
  - `/batch` 병렬 → 기존 `(team)` 메커니즘이 이미 대응
  - Auto-memory → 기존 RLM 패턴(glossary.yaml, Knowledge Archive, knowledge-index.jsonl)이 이미 대응
  - Ralph Loop → 기존 retry budget + Abductive Diagnosis가 더 세밀
  - Agent Teams → 기존 `(team)` 단계 + SOT 단일 쓰기가 **동일 패턴**
- **근거**:
  - **절대 기준 1(품질)**: 모든 제안을 "품질 이점이 실증되었는가?"로 판정. 기술의 매력이 아닌 문제의 존재가 채택 기준.
  - **기존 보존**: "기능 개선이지, 새 워크플로우를 만드는 것이 아니다" 조건 엄격 적용. `current_step` 내력벽 파괴는 아키텍처 변경에 해당하므로 기각.
  - **RLM 패턴 보존**: `@translator`의 `memory: project`는 RLM 외부 메모리 객체의 확장. glossary.yaml과 상호보완.
- **대안**:
  - 3-Lens를 3개 신규 에이전트 .md로 구현 → 기각 (기존 `@reviewer`를 다른 프롬프트로 3회 호출하면 동일 효과, 신규 파일 불필요)
  - Batch를 `(team)` 메타 단계로 구현 → 기각 (개별 단계 품질 게이트 손실)
  - 3개 에이전트 모두에 persistent memory → 기각 (@reviewer: 과거 편향, @fact-checker: 정보 시효 + 독립성 훼손)
- **관련 파일**: `translator.md` (`memory: project` 추가)

---

## 6. Language & Translation (언어 및 번역)

### ADR-027: English-First 실행 원칙

- **날짜**: 2026-02-17
- **상태**: Accepted
- **맥락**: 사용자와의 대화는 한국어지만, AI 에이전트의 작업 품질은 영어에서 가장 높다. 한국어로 직접 산출물을 생성하면 품질이 떨어진다.
- **결정**: 워크플로우 실행 시 모든 에이전트는 영어로 작업하고 영어로 산출물을 생성한다. 한국어는 별도 번역 프로토콜로 제공한다.
- **근거**: 절대 기준 1(품질)의 직접적 구현. AI는 영어에서 가장 높은 성능을 발휘하므로, 영어 우선 실행이 최고 품질을 보장한다.
- **대안**: 한국어로 직접 생성 → 기각 (품질 저하), 언어 선택을 사용자에게 위임 → 기각 (일관성 없음)
- **관련 커밋**: `5b649cb` feat: Hub-and-Spoke universal system prompt

#### ADR-027a: English-First 강제 격상 (Amendment)

- **날짜**: 2026-03-05
- **상태**: Accepted (ADR-027 amendment)
- **맥락**: English-First가 "권장" 수준으로 운영되고 있었으나, 사용자가 이를 절대 기준과 동급의 강제 사항으로 격상 요청. 토큰 효율성(한국어 2-3배), 할루시네이션 감소, 일관성 보장이 근거.
- **결정**: (1) CLAUDE.md, AGENTS.md §5.2/§8, GEMINI.md에 "MANDATORY" 강제 선언 추가. (2) workflow-template.md Inherited Patterns에 English-First 행 추가 (자식 워크플로우 유전 보장). (3) validate_workflow.py에 W9 검증 규칙 추가 (P1 할루시네이션 봉쇄). (4) soul.md는 미변경 — English-First는 "헌법(절대 기준 1)" 유전자의 발현이지 독립 유전자가 아님.
- **근거**: 절대 기준 1(품질) 강화. "영어 먼저 완성 → 번역" 순서를 역전 불가로 고정하여 품질 바닥선 보장.
- **영향**: 문서 4개 동기화 + P1 코드 1개(W9) + 문서-코드 동기화 1개. 기존 W1-W8, RLM 패턴, SOT 구조 미접촉.

### ADR-028: @translator 서브에이전트 + glossary 영속 상태

- **날짜**: 2026-02-17
- **상태**: Accepted
- **맥락**: 영어 산출물을 한국어로 번역할 때, 단순 번역 도구로는 도메인 용어의 일관성을 보장할 수 없다.
- **결정**: `@translator` 서브에이전트를 정의하고, `translations/glossary.yaml`을 RLM 외부 영속 상태로 유지한다. 번역 시 glossary를 참조하여 용어 일관성을 보장하고, 새 용어는 glossary에 추가한다.
- **근거**: RLM의 Variable Persistence 패턴 적용. glossary가 서브에이전트 호출 간 상태를 유지하여, 번역 품질이 세션을 거듭할수록 향상된다.
- **대안**: 매번 번역 규칙 재지정 → 기각 (용어 불일치), 외부 번역 API → 기각 (도메인 특화 용어 미지원)
- **관련 커밋**: `5b649cb` feat: Hub-and-Spoke universal system prompt

---

## 7. Infrastructure (인프라)

### ADR-029: Setup Hook — 세션 시작 전 인프라 건강 검증

- **날짜**: 2026-02-19
- **상태**: Accepted
- **맥락**: Hook 스크립트가 Python 환경, PyYAML, 디렉터리 구조 등에 의존하는데, 이것들이 깨져 있으면 모든 Hook이 silent failure한다.
- **결정**: `setup_init.py`를 Setup Hook(`claude --init`)으로 등록하여, 세션 시작 전 7개 항목(Python 버전, PyYAML, 스크립트 구문 ×6, 디렉터리 ×2, .gitignore, SOT 쓰기 패턴)을 자동 검증한다.
- **근거**: "작동한다고 가정하지 말고, 매번 검증하라." Hook이 silent failure하면 컨텍스트 보존이 완전히 무력화되므로, 사전 검증이 필수적이다.
- **대안**: 수동 점검 → 기각 (까먹기 쉬움), 첫 실행 시 자동 설치 → 기각 (사용자 환경에 무단 설치)
- **관련 커밋**: `2c91985` feat: Context Preservation 품질 강화

### ADR-030: 절삭 상수 중앙화 — 10개 상수

- **날짜**: 2026-02-19
- **상태**: Accepted
- **맥락**: 스냅샷 생성 시 Edit preview, Error message 등의 길이를 절삭하는 상수가 여러 함수에 하드코딩되어 있어, 일관성 없는 절삭이 발생했다.
- **결정**: `_context_lib.py`에 10개 절삭 상수(`EDIT_PREVIEW_CHARS=1000`, `ERROR_RESULT_CHARS=3000`, `MIN_OUTPUT_SIZE=100` 등)를 중앙 정의한다.
- **근거**: 중앙 정의된 상수는 한 곳만 수정하면 전체에 반영된다. Edit preview는 5줄 × 1000자로 편집 의도·맥락을 보존하고, 에러 메시지는 3000자로 stack trace 전체를 보존한다.
- **대안**: 각 함수에 인라인 → 기각 (값 불일치 위험, 튜닝 시 누락)
- **관련 커밋**: `2c91985` feat: Context Preservation 품질 강화

### ADR-031: PreToolUse Safety Hook — 위험 명령 차단

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: Claude Code의 6개 차단 가능 Hook 이벤트 중 PreToolUse만 미구현. 위험한 Git/파일 명령(git push --force, git reset --hard, rm -rf / 등)이 AI 판단에만 의존하여 실행될 수 있었다.
- **결정**: `block_destructive_commands.py`를 PreToolUse Hook(matcher: Bash)으로 등록. 10개 패턴(9개 정규식 + 1개 절차적 rm 검사)으로 위험 명령을 결정론적으로 탐지하고, exit code 2로 차단 + stderr 피드백으로 Claude 자기 수정을 유도한다.
- **근거**: P1 할루시네이션 봉쇄 — 위험 명령 탐지는 정규식으로 100% 결정론적. AI 판단 개입 없음. `context_guard.py`를 거치지 않는 독립 실행 — `|| true` 패턴이 exit code 2를 삼키는 문제 회피를 위해 `if test -f; then; fi` 패턴 사용.
- **대안**: (1) SOT 쓰기 보호 → 보류 (Hook API가 에이전트 역할을 구분하지 못함), (2) Anti-Skip Guard 강화 → 보류 (Stop 타이밍이 사후적이어서 예방 불가)
- **차단 패턴**: git push --force(NOT --force-with-lease), git push -f, git reset --hard, git checkout ., git restore ., git clean -f, git branch -D, git branch --delete --force(양방향 순서), rm -rf / 또는 ~

### ADR-032: PreToolUse TDD Guard — 테스트 파일 수정 차단

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: Claude는 TDD 시 테스트가 실패하면 구현 코드 대신 테스트 코드를 수정하려는 경향이 있다. 이는 TDD의 핵심 원칙("테스트는 불변, 구현만 수정")을 위반한다.
- **결정**: `block_test_file_edit.py`를 PreToolUse Hook(matcher: `Edit|Write`)으로 등록한다. `.tdd-guard` 파일이 프로젝트 루트에 존재할 때만 활성화된다. 2계층 탐지(Tier 1: 디렉터리명 — test/tests/__tests__/spec/specs, Tier 2: 파일명 패턴 — test_*/\*_test.\*/\*.test.\*/\*.spec.\*/\*Test.\*/conftest.py)로 테스트 파일을 결정론적으로 식별하고, exit code 2 + stderr 피드백으로 Claude가 구현 코드를 수정하도록 유도한다.
- **근거**:
  - P1 할루시네이션 봉쇄 패턴 재사용 — 테스트 파일 탐지는 regex/string matching으로 100% 결정론적
  - ADR-031(`block_destructive_commands.py`)과 동일한 아키텍처 — 독립 실행, `if test -f; then; fi` 패턴, Safety-first exit(0)
  - `.tdd-guard` 토글은 SOT(`state.yaml`)와 독립 — TDD는 워크플로우 밖에서도 사용되므로 SOT 의존 부적합
  - `REQUIRED_SCRIPTS`(D-7) 양쪽 동기화로 `setup_init.py`/`setup_maintenance.py` 인프라 검증 대상에 포함
- **대안**:
  - 항상 차단 (토글 없음) → 기각 (테스트 작성 시에도 차단되어 비실용적)
  - SOT `tdd_mode: true`로 제어 → 기각 (SOT는 워크플로우 전용, TDD는 범용)
  - PostToolUse에서 사후 경고 → 기각 (이미 파일이 수정된 후라 예방 불가)
- **관련 커밋**: (pending)

### ADR-033: Context Memory 최적화 — success_patterns + Next Step IMMORTAL + 모듈 레벨 regex

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: 전체 감사 결과 3가지 Context Memory 최적화 기회가 확인되었다. (1) Knowledge Archive가 error_patterns만 기록하고 성공 패턴은 누락, (2) "다음 단계" 섹션이 독립 IMMORTAL 마커 없이 부모 섹션에 암묵적 포함, (3) `_extract_decisions()`의 8개 regex + `_extract_next_step()`의 1개 regex + `_SYSTEM_CMD`가 매 호출마다 컴파일.
- **결정**:
  1. `_extract_success_patterns()` 함수 추가 — Edit/Write→성공적 Bash 시퀀스를 결정론적으로 추출하여 `success_patterns` 필드로 Knowledge Archive에 기록
  2. "다음 단계 (Next Step)" 섹션을 독립 `## ` 헤더 + `<!-- IMMORTAL: -->` 마커로 승격 — Phase 7 hard truncate에서 명시적 보존 대상
  3. 10개 regex 패턴을 모듈 레벨 상수로 이동 — 프로세스당 1회 컴파일
- **근거**:
  - success_patterns: `Grep "success_patterns" knowledge-index.jsonl`로 RLM cross-session 성공 패턴 탐색 가능. error_patterns의 대칭 — 실패에서 배우듯 성공에서도 배운다.
  - Next Step IMMORTAL: 세션 복원 시 "다음에 무엇을 해야 하는지"는 "현재 무엇을 하고 있는지" 못지않게 중요한 인지적 연속성 앵커.
  - 모듈 레벨 regex: Stop hook 30초 간격 실행에서 매번 10개 패턴을 재컴파일하는 것은 불필요한 오버헤드.
- **대안**:
  - success_patterns에 Read도 포함 → 기각 (Read는 검증 아닌 탐색이므로 "성공 패턴"으로서 신호 약함)
  - Next Step을 별도 파일로 분리 → 기각 (over-engineering, 스냅샷 내 IMMORTAL 마커로 충분)
- **관련 커밋**: (pending)

### ADR-034: Adversarial Review — Enhanced L2 품질 계층 + P1 할루시네이션 봉쇄

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: Generator-Critic 패턴(적대적 에이전트)을 도입하여 환각을 줄이고 산출물 품질을 높이고자 했다. 기존 L2 Calibration은 "선택적 교차 검증"으로서 구체적 구현이 없었다. 연구·개발 작업 모두에서 독립적 비판적 검토가 필요했다. 3차례의 심층 성찰(Critical Reflection)을 거쳐 설계를 확정했다.
- **결정**:
  1. 기존 L2 Calibration을 **Adversarial Review (Enhanced L2)**로 대체 — `@reviewer`(코드/산출물 분석, 읽기 전용)와 `@fact-checker`(사실 검증, 웹 접근) 두 전문 에이전트 신설
  2. `Review:` 필드를 워크플로우 단계 속성으로 추가 (기존 `Translation:` 패턴과 동일)
  3. P1 결정론적 검증 4개 함수를 `_context_lib.py`에 추가: `validate_review_output()` (R1-R5 5개 체크), `parse_review_verdict()` (regex 기반 이슈 추출), `calculate_pacs_delta()` (Generator-Reviewer 점수 산술 비교), `validate_review_sequence()` (Review→Translation 순서 타임스탬프 검증)
  4. Rubber-stamp 방지 4계층: 적대적 페르소나 + Pre-mortem 필수 + 최소 1개 이슈 (P1 R5) + 독립 pACS 채점
  5. 실행 순서: L0 → L1 → L1.5 → Review(L2) → PASS → Translation
  6. Stop hook에 Review 누락 감지 안전망 추가 (`_check_missing_reviews()`)
- **근거**:
  - **Enhanced L2 위치**: 기존 L2가 이미 "교차 검증"이므로 적대적 검토는 이를 엄격하게 구현한 것. 새 L3를 만드는 것보다 기존 계층을 강화하는 것이 아키텍처 복잡도를 낮춘다.
  - **2개 에이전트 분리 (P2)**: 코드 논리 분석(Read-only)과 사실 검증(WebSearch)은 필요 도구가 완전히 다르다. 최소 권한 원칙에 의해 분리.
  - **Sub-agent 선택**: 리뷰 결과를 즉시 반영하는 동기적 피드백 루프가 필요하므로 Agent Team 비동기 패턴보다 Sub-agent가 품질 극대화에 유리.
  - **P1 필요성**: 리뷰 보고서 존재/구조/verdict/이슈 수/pACS delta 검증은 100% 정확해야 하는 반복 작업으로, LLM에 맡기면 hallucination 위험. Python regex/filesystem/arithmetic으로 강제.
- **대안**:
  - 단일 `@critic` 에이전트 → 기각 (코드 분석과 사실 검증의 도구 프로파일이 다름)
  - 새 `(adversarial)` 단계 유형 → 기각 (`Review:` 속성이 기존 `Translation:` 패턴과 일관적이며 하위 호환)
  - L3 신설 → 기각 (기존 L2를 강화하는 것이 더 간결)
  - Reviewer가 직접 파일을 수정 → 기각 (읽기 전용이어야 Generator와의 역할 분리 유지)
- **관련 커밋**: (pending)

### ADR-035: 종합 감사 — SOT 스키마 확장 + Quality Gate IMMORTAL + Error→Resolution 표면화

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: 코드베이스 전체에 대한 종합 감사에서 6가지 미구현·미최적화 영역이 발견되었다. (1) pacs/active_team SOT 스키마 미검증, (2) Quality Gate 상태의 세션 경계 유실, (3) 이전 세션 에러 해결 경험의 수동 Grep 의존, (4) 런타임 디렉터리 부재 시 silent failure, (5) 다단계 전환 정보의 스냅샷 헤더 미반영, (6) CLAUDE.md 문서와 구현의 불일치. 이 중 (2)와 (3)은 Context Memory 품질 최적화 관점에서 특히 중요했다.
- **결정**:
  1. `validate_sot_schema()` 확장: S7(pacs 구조 — dimensions F/C/L 0-100, current_step_score, weak_dimension) + S8(active_team — name, status 유효값) 검증 추가 → 6항목 → 8항목
  2. `_extract_quality_gate_state()` 신설: pacs-logs/, review-logs/, verification-logs/에서 최신 단계의 품질 게이트 결과를 추출하여 IMMORTAL 스냅샷 섹션으로 보존
  3. `_extract_recent_error_resolutions()` 신설(restore_context.py): Knowledge Archive에서 최근 에러→해결 패턴을 읽어 SessionStart 출력에 최대 3개 자동 표시
  4. `_check_runtime_dirs()` 신설(setup_init.py): SOT 존재 시 verification-logs/, pacs-logs/, review-logs/, autopilot-logs/ 자동 생성
  5. 스냅샷 헤더에 Phase Transition 흐름 표시: 다단계 세션에서 `Phase flow: research(12) → implementation(25)` 형식
  6. CLAUDE.md 전체 동기화: 프로젝트 트리, 동작 원리 테이블, Claude 활용 방법 3개 레벨 일관성 확보
- **근거**:
  - **Quality Gate IMMORTAL**: compact/clear 후 Verification Gate/pACS/Review 진행 상태가 유실되면 다음 단계 진입 시 잘못된 판단 위험 → IMMORTAL로 보존하여 세션 경계에서의 품질 게이트 연속성 보장 (절대 기준 1)
  - **Error→Resolution 표면화**: 수동 Grep 의존 시 이전 세션의 해결 경험이 활용되지 않음 → SessionStart에서 자동 표시하여 동일 에러 재발 시 즉시 해결 가능 (RLM 패턴의 프로액티브 활용)
  - **SOT 스키마 확장**: pacs와 active_team은 Autopilot 실행의 핵심 상태이나 스키마 검증이 없어 hallucination에 취약 → P1 결정론적 검증으로 봉쇄
  - **런타임 디렉터리**: 디렉터리 부재 시 파일 쓰기가 조용히 실패하여 Verification/pACS/Review 로그가 유실됨 → Setup 시 사전 생성
- **대안**:
  - Quality Gate 상태를 SOT에 저장 → 기각 (Hook은 SOT 쓰기 금지 — 절대 기준 2)
  - Error→Resolution을 스냅샷 본문에 포함 → 기각 (스냅샷 크기 증가, SessionStart 출력이 더 즉각적)
  - 런타임 디렉터리를 각 Hook에서 개별 생성 → 기각 (Setup에서 한 번 검증이 더 효율적이고 결정론적)
- **관련 커밋**: (pending)

### ADR-036: Predictive Debugging — 에러 이력 기반 위험 파일 사전 경고

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: Claude가 파일을 편집할 때, 과거 세션에서 반복적으로 에러가 발생한 파일에 대한 사전 경고가 없었다. Knowledge Archive에 error_patterns가 축적되고 있지만(ADR-017), 이를 사전 예방에 활용하지 않고 사후 분석에만 사용하고 있었다. 3차례의 심층 성찰(Critical Reflection)을 거쳐 P1 할루시네이션 봉쇄와 아키텍처 일관성을 검증한 후 설계를 확정했다.
- **결정**:
  1. `aggregate_risk_scores()` 함수를 `_context_lib.py`에 추가 — Knowledge Archive의 error_patterns를 파일별로 집계하여 위험 점수를 산출 (P1 결정론적 산술)
  2. `validate_risk_scores()` (RS1-RS6) 스키마 검증 — `validate_sot_schema()` (S1-S8), `validate_review_output()` (R1-R5) 등과 동일한 P1 패턴
  3. `predictive_debug_guard.py`를 PreToolUse Hook(matcher: `Edit|Write`)으로 등록 — 위험 점수 임계값 초과 시 stderr 경고 (exit code 0, 경고 전용)
  4. `restore_context.py`에서 SessionStart 시 risk-scores.json 캐시 생성 — 1회 집계 후 캐시, PreToolUse는 캐시만 읽기 (성능 최적화)
  5. 가중치 체계: `_RISK_WEIGHTS` (13개 에러 타입별 가중치) × `_RECENCY_DECAY_DAYS` (30일/90일/무한 3구간 감쇠)
  6. Cold start guard: 5세션 미만이면 경고 미출력 (불충분한 데이터로 false positive 방지)
- **근거**:
  - **L-1 계층**: 기존 Safety Hook(L0 차단)과 달리, 에러를 **예측**하여 Claude의 주의를 사전에 환기하는 새로운 계층. 차단하지 않고 경고만 하므로 워크플로우를 방해하지 않는다.
  - **ADR-017 확장**: Error Taxonomy가 에러를 **분류**하는 인프라라면, Predictive Debugging은 분류된 데이터를 **집계하여 예측에 활용**하는 상위 계층. 동일한 error_patterns 스키마를 소비한다.
  - **자기완결형 Hook**: `predictive_debug_guard.py`는 `_context_lib.py`를 import하지 않는다. 매 Edit/Write마다 새 Python 프로세스가 생성되므로, 4,500줄 모듈 로딩을 피해야 한다 (D-7 패턴으로 상수 중복).
  - **캐시 패턴**: SessionStart에서 1회 집계 → JSON 캐시 → PreToolUse는 캐시 읽기만. O(N) 집계를 세션당 1회로 제한.
  - **Startup 미지원 트레이드오프**: SessionStart matcher가 `clear|compact|resume`이므로, 최초 startup에서는 캐시 미생성. 이전 캐시(2시간 이내)에 의존하거나, 첫 compact/clear 시 생성. 복원과 캐시 생성의 관심사를 분리하기 위한 의도적 선택.
- **대안**:
  - 매 Edit/Write마다 knowledge-index 직접 스캔 → 기각 (O(N) 반복, 성능 심각)
  - exit code 2로 차단 → 기각 (예측은 확률적이므로 차단은 과도)
  - `_context_lib.py` import → 기각 (PreToolUse 프로세스 시작 지연)
  - Layer C (Stop hook에서 자동 분석) → 기각 (B+A로 충분, Stop timeout 위험)
- **관련 ADR**: ADR-017 (Error Taxonomy — error_patterns 스키마 공급), ADR-024 (P1 할루시네이션 봉쇄 — RS1-RS6 패턴), ADR-031 (PreToolUse Safety Hook — 독립 실행 아키텍처)
- **관련 커밋**: (pending)

### ADR-037: 종합 감사 II — pACS P1 검증 + L0 Anti-Skip Guard 코드화 + IMMORTAL 경계 수정 + Context Memory 최적화

- **상태**: Accepted
- **날짜**: 2026-02-20
- **맥락**: 코드베이스 종합 감사에서 3개 CRITICAL, 5개 HIGH, 6개 MEDIUM 결함을 식별했다. 설계 문서에 명시된 기능 중 코드로 뒷받침되지 않는 것(pACS 검증, L0 Anti-Skip Guard), 코드의 로직 버그(IMMORTAL 경계 탐지), 문서 간 불일치(스크립트 수, 프로젝트 트리 누락)가 핵심 유형이었다.
- **결정**:
  1. **C1: IMMORTAL 경계 탐지 수정** — Phase 7 압축에서 `if` → `elif` 마커 우선 경계 탐지로 변경. 비-IMMORTAL 섹션 헤더가 IMMORTAL 마커와 같은 줄에 있을 때 IMMORTAL 모드가 꺼지는 버그 수정. 압축 알림(truncation notice)도 IMMORTAL 섹션으로 추가.
  2. **C2+C3: L0 Anti-Skip Guard + pACS P1 검증 코드화** — `validate_step_output()` (L0a-L0c: 파일 존재, 최소 크기, 비공백) + `validate_pacs_output()` (PA1-PA6: 파일 존재, 최소 크기, 차원 점수, Pre-mortem, min() 산술, Color Zone) 함수를 `_context_lib.py`에 구현. `validate_pacs.py` 독립 실행 스크립트 신규 생성.
  3. **H1: Team Summaries KI 아카이브** — `_extract_team_summaries()` 함수가 SOT의 `active_team.completed_summaries`를 Knowledge Archive에 보존. 스냅샷 로테이션 시 유실 방지.
  4. **H2+H3: Orchestrator 역할 + Sub-agent 프로토콜 명시** — AGENTS.md에 Orchestrator = 메인 세션, Team Lead = Orchestrator(team 단계), Sub-agent Task tool 호출 프로토콜, (team) 단계 Task Lifecycle 7단계 추가.
  5. **H4: Task Lifecycle 표준 흐름** — workflow-template.md에 TeamCreate→TaskCreate→작업→SendMessage→SOT 갱신→TeamDelete 6단계 흐름 추가.
  6. **M1: Decision Slot 확장** — 15→20 슬롯, 비례 배분(high-signal 최대 15 + intent 나머지).
  7. **M4: Next Step 추출 창** — 3→5 assistant responses로 확장.
- **근거**:
  - **설계-구현 정합성**: 설계 문서(CLAUDE.md, AGENTS.md)에 명시된 L0 Anti-Skip Guard와 pACS 검증이 코드로 존재하지 않으면, 4계층 품질 보장 체계가 사실상 2계층(L1 Verification + L1.5 pACS 자기 채점)으로 축소된다. 코드 구현으로 설계 의도를 강제한다.
  - **IMMORTAL 경계 버그의 심각성**: Phase 7 하드 트렁케이트는 극한 상황(컨텍스트 초과)에서만 발동하므로, 버그가 발견되기 어렵고 발동 시 핵심 맥락(Autopilot 상태, ULW 상태, Quality Gate 상태)이 유실된다. 선제 수정이 필수.
  - **Context Memory 품질 최적화**: Decision Slot 확장과 Next Step 창 확장은 토큰 비용 증가 없이(이미 생성되는 데이터의 보존 범위만 확장) 세션 복원 품질을 향상한다.
- **대안**:
  - pACS/L0를 프롬프트 기반 검증으로만 유지 → 기각 (P1 원칙 위반 — 반복적 100% 정확도가 필요한 작업은 코드로 강제)
  - IMMORTAL 경계를 정규식 기반으로 변경 → 기각 (현재 마커 기반이 충분히 결정론적, 추가 복잡성 불필요)
  - Decision Slot을 무제한으로 확장 → 기각 (무한 확장은 노이즈 유입, 20 슬롯이 실측 기반 적정치)
- **관련 ADR**: ADR-024 (P1 할루시네이션 봉쇄 — 확장), ADR-035 (종합 감사 I — SOT 스키마+Quality Gate), ADR-033 (Context Memory 최적화 — 확장)
- **관련 커밋**: (pending)

---

## 8. Heredity (유전 설계)

### ADR-038: DNA Inheritance — 부모 게놈의 구조적 유전

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: `soul.md`가 AgenticWorkflow의 존재 이유(부모 유기체 → 자식에 DNA 유전)를 철학적으로 정의했으나, 실제 생산 라인인 `workflow-generator`에 유전 메커니즘이 부재. 철학이 코드베이스와 생산 프로세스에 구조적으로 연결되지 않은 상태.
- **결정**:
  1. `SKILL.md`에 유전 프로토콜(Genome Inheritance Protocol) 추가 — 자식 생성 시 Inherited DNA 섹션 포함 의무화
  2. `workflow-template.md`에 `Inherited DNA (Parent Genome)` 섹션을 기본 템플릿에 추가
  3. `state.yaml.example`에 `parent_genome` 메타데이터 추가 — 계보 추적
  4. 핵심 문서(CLAUDE.md, AGENTS.md, README.md, ARCHITECTURE, Spoke 3개, Agent 3개, 매뉴얼)에 유전 개념 통합
- **근거**: "유전은 선택이 아니라 구조다" — 자식이 DNA를 내장해야 유전의 의미가 실현됨. 참조만으로는 선택적 적용이 가능하여 품질 일관성이 보장되지 않음.
- **대안**:
  - soul.md에 대한 참조 링크만 추가 → 기각 (참조는 유전이 아님 — 선택적 적용 가능)
  - soul.md 전체를 자식 워크플로우에 복사 → 기각 (불필요한 중복, 유지보수 부담)
  - DNA를 별도 `dna.yaml` 파일로 추출하여 자동 주입 → 기각 (과도한 엔지니어링, 문서 기반 접근이 더 적합)
- **영향 범위**: 문서 16개 수정 (Python Hook 스크립트 미수정, SOT 스키마 검증 미수정 — `parent_genome`은 unknown key로 허용됨)
- **관련 ADR**: ADR-001 (워크플로우 = 중간물), ADR-009 (RLM 이론적 기반), ADR-010 (아키텍처 문서)
- **관련 커밋**: `9b99e36`

### ADR-039: Workflow.md P1 Validation — DNA 유전의 코드 수준 검증

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: ADR-038에서 DNA Inheritance를 문서 기반 접근으로 구현했으나, Critical Reflection에서 P1 검증 공백이 식별됨. 기존 P1 체계(pACS/Review/Translation/Verification/L0)는 모두 결정론적 코드 검증을 갖추고 있으나, 생성된 workflow.md의 Inherited DNA 존재 여부는 프롬프트 기반 강제만 존재. P1 철학("code doesn't lie")과 모순.
- **결정**:
  1. `_context_lib.py`에 `validate_workflow_md()` 함수 추가 — W1-W6 결정론적 검증 (파일 존재, 최소 크기, Inherited DNA 헤더, Inherited Patterns 테이블 ≥ 3행, Constitutional Principles, Coding Anchor Points(CAP) 참조)
  2. `validate_workflow.py` 독립 실행 스크립트 생성 — 기존 `validate_*.py` 패턴과 동일
  3. `SKILL.md` Step 13(Distill 검증)에서 호출 권고
  4. `REQUIRED_SCRIPTS`에 추가 (D-7 동기화: setup_init.py + setup_maintenance.py)
- **근거**: ~80줄 추가로 P1 일관성을 회복. "과도한 엔지니어링"이 아닌 기존 패턴의 자연스러운 확장. Autopilot에서의 silent failure 방지.
- **ADR-038 관계**: ADR-038의 "Python Hook 미수정" 결정을 부분 수정 — Hook은 여전히 미수정이나, 독립 검증 스크립트를 추가하여 P1 공백을 폐쇄.
- **관련 ADR**: ADR-038 (DNA Inheritance)

### ADR-040: 종합 감사 III — 4계층 QA 집행력 강화 (C1r/C2/W4/C4s/W7)

- **날짜**: 2026-02-20
- **상태**: Accepted
- **맥락**: 종합 코드베이스 감사(1차) + 적대적 자기 검증(2차)에서 4계층 QA의 "설계 의도 vs 코드 집행력" 불일치 5건 식별. 1차 감사에서 15건 보고 → 2차 성찰에서 오진 2건(C1 원안, W2) 제거, 보류 2건(C3, W3) 판정 → 최종 5건 확정.
- **결정**:
  1. **C1r**: `validate_translation.py`에서 Review verdict=PASS를 `--check-sequence` 없이도 항상 검증 (기존 `validate_review_sequence()` 미수정 — 타임스탬프 책임 유지)
  2. **C2**: `validate_pacs_output()`에 PA7 추가 — pACS < 50(RED)이면 FAIL 반환, 단계 진행 차단
  3. **W4**: `validate_review.py`에서 pACS Delta ≥ 15 시 warnings[]에 경고 메시지 표면화
  4. **C4s**: `generate_context_summary.py`에 `_check_missing_verifications()` 추가 — pacs-log 있는데 verification-log 없으면 stderr 경고 (기존 `_check_missing_reviews()` 패턴 따름)
  5. **W7**: `SKILL.md` Step 7에 "모든 에이전트 실행 단계에 Verification 필수, (human)만 예외" 명시
- **근거**: ~41줄 추가로 프롬프트 수준 규칙을 코드 수준 집행으로 전환. 기존 함수의 책임 변경 없음 — 보강만. SOT 스키마 변경 없음.
- **기각된 항목**:
  - C1 원안(validate_review_sequence 수정) → 오진 — 함수가 이미 verdict 검사. 호출이 선택적인 것이 문제
  - W2(Quality Gate IMMORTAL 승격) → 이미 구현됨
  - C3(SOT retry_count) → SOT 범위 초과 — 파일 카운팅이 적합
  - W3(KI 품질 메트릭) → 현재 pacs_min 충분 — RLM 수요 시 재검토
- **관련 ADR**: ADR-022 (Verification Protocol), ADR-037 (pACS P1), ADR-034 (Adversarial Review)

### ADR-041: 코딩 기준점 (Coding Anchor Points, CAP-1~4)

- **날짜**: 2026-02-23
- **상태**: Accepted
- **맥락**: CCP(절대 기준 3)는 코드 변경 시 "무엇을 수행하는가"(3단계 절차)를 정의하지만, "어떤 태도로 수행하는가"(사고방식)는 명시되어 있지 않았다. 코딩 전 사고, 단순성 우선, 목표 기반 실행, 외과적 변경 4가지 태도 규범이 CCP 실행의 전제 조건으로 필요.
- **결정**: CCP 내부에 하위 섹션(`#### 코딩 기준점`)으로 CAP-1~4를 정의. AGENTS.md(Hub)에 완전 정의, CLAUDE.md/Spoke 3개에 압축 참조, reviewer.md의 기존 Technical Quality 렌즈에 CAP-2·CAP-4 관찰 항목 2개 추가, ARCHITECTURE.md에 1줄 참조, SKILL.md Genome Inheritance에 CAP 포함 1줄 추가.
- **근거**: (1) CAP는 CCP의 태도적 표현(gene expression)이므로 독립 게놈 구성요소가 아님 — soul.md 게놈 테이블 변경 불필요 (cascade 0). (2) CAP **행동** 강제는 P1 불가 — 태도는 의미론적이며 결정론적 검증 불가. (3) 기존 Hook/SOT/검증 스크립트 변경 0건.
- **대안**:
  - 독립 §2.5 섹션 생성 → 기각 (phantom hierarchy, CCP와의 관계 불명확)
  - soul.md 게놈 테이블에 행 추가 → 기각 (12→13 cascade, 6+ 파일 연쇄 변경)
  - reviewer.md에 6번째 렌즈 추가 → 기각 (@reviewer는 산출물 검토, CAP-1/CAP-3은 프로세스 태도로 산출물에서 관찰 불가)
  - P1 Python 강제 (행동 검증) → 기각 (태도 ≠ 구조, 의미론적 판단은 결정론적 코드로 검증 불가, false positive 양산)
- **후속 수정 1**: Critical Reflection에서 Category Error 식별 — CAP **행동** 강제(의미론적, P1 불가)와 CAP **문서 전파** 검증(구조적, P1 가능)은 다른 문제. 생성된 workflow.md에 CAP 참조가 구조적으로 존재하는지는 결정론적으로 검증 가능하므로, ADR-039의 `validate_workflow_md()`에 W6(Coding Anchor Points 참조 존재) 검증을 추가. 이는 ADR-041의 "행동 P1 기각"과 모순하지 않음 — W6는 문서 전파의 P1이지 행동의 P1이 아님.
- **후속 수정 2** (2026-03-06): CAP 정의 전체를 한국어→영어 원문으로 전환 (ADR-027a English-First MANDATORY 정합). Hub(AGENTS.md) + Detail(code-change-protocol.md) + Spoke 6개 + DNA 템플릿 3개 = 11개 파일 동기화. P1 Hook 추가(scanner CAP 리마인더)는 4차 Critical Reflection에서 기각 — CLAUDE.md가 매 턴 로드되어 이미 CAP을 제공하므로 중복 정보 주입이며, scanner의 SRP(의존성 발견)를 위반하고, CAP-2(simplicity)에 반함. 영어 전환 자체가 enforcement 향상(Claude의 영어 지시 이해도 > 한국어).
- **후속 수정 3** (2026-03-06): Post-implementation reflection에서 `.cursor/rules/agenticworkflow.mdc` 누락 발견 — `ccp_ripple_scanner.py`의 `HUB_SPOKE_MAP`에 미등록이 근본 원인. 맵에 4개 Spoke 추가: `.cursor/rules/agenticworkflow.mdc`, `.claude/skills/workflow-generator/SKILL.md`, `references/workflow-template.md`, `references/claude-code-patterns.md`. 역방향 엔트리도 추가. 테스트 3개 추가 (35개 전체 통과). 향후 AGENTS.md 수정 시 P1 수준에서 동기화 누락 원천봉쇄.
- **관련 ADR**: ADR-005 (CCP), ADR-027a (English-First), ADR-038 (DNA Inheritance), ADR-039 (W6 추가), ADR-042 (Hub-Spoke 맵)

### ADR-042: Hook 설정 Global → Project 통합

- **날짜**: 2026-02-23
- **상태**: Accepted
- **맥락**: 기존 Hook 설정이 Global(`~/.claude/settings.json`)과 Project(`.claude/settings.json`)에 분산되어 있어, `git clone`한 사용자가 글로벌 Hook 7개를 수동 설치해야 코드베이스가 정상 동작했다. 에이전트(`.claude/agents/`)는 프로젝트 레벨로 자동 공유되는데, Hook만 글로벌 설치가 필요한 비대칭이 존재.
- **결정**: 글로벌 Hook 7개(Stop, PostToolUse, PreCompact, SessionStart, PreToolUse ×3)를 모두 `.claude/settings.json`(Project)으로 이동. 글로벌 설정에서 hooks 섹션 제거. 동시에 `|| true` 패턴(exit code 2 삼킴 잠복 버그)을 `if test -f; then; fi` 패턴으로 통일.
- **근거**: (1) `git clone`만으로 에이전트 + Hook + 스킬 전체가 자동 적용 — zero-config 온보딩. (2) Claude Code는 모든 Hook 이벤트를 프로젝트 레벨에서 지원 — 기능 제한 없음. (3) `|| true` → `if; fi` 패턴 전환으로 미래 차단 기능 추가 시 exit code 2가 안전하게 전파.
- **영향 범위**: `.claude/settings.json`(Hook 병합), `~/.claude/settings.json`(hooks 제거), CLAUDE.md(Hook 위치 설명), ARCHITECTURE.md(설정 테이블), 4개 Python docstring, README.md, AGENTS.md, claude-code-patterns.md — 총 11개 파일
- **대안**: 글로벌 설치 스크립트 제공 → 기각 (추가 설치 단계 필요, 자동 적용이 아님)
- **관련 ADR**: ADR-012 (Hook 기반 컨텍스트 보존), ADR-015 (context_guard.py 통합 디스패처)

### ADR-043: ULW 재설계 — 직교 철저함 오버레이

- **날짜**: 2026-02-23
- **상태**: Accepted
- **Supersedes**: ADR-023
- **맥락**: ADR-023은 ULW를 Autopilot의 "대안(alternative)"으로 설계하여 배타적 관계(동시 활성화 시 Autopilot 우선)를 규정했다. 그러나 사용자의 의도는 "완전성(completeness) 오버레이"였다. Autopilot은 자동화(HOW)를 다루고, ULW는 철저함(HOW THOROUGHLY)을 다루므로 두 축은 직교한다.
- **결정**: ULW를 Autopilot과 **직교하는 2축 모델**로 재설계한다. 기존 5개 실행 규칙을 3개 강화 규칙(Intensifiers)으로 통합한다:
  1. **I-1. Sisyphus Persistence** — 기존 Sisyphus Mode + Error Recovery + No Partial Completion 통합. 최대 3회 재시도, 각 시도는 다른 접근법
  2. **I-2. Mandatory Task Decomposition** — 기존 Auto Task Tracking + Progress Reporting 통합
  3. **I-3. Bounded Retry Escalation** — 신규. 동일 대상 3회 초과 재시도 금지, 초과 시 사용자 에스컬레이션
- **근거**: (1) "Autopilot이 우선" 규칙이 ULW의 강화 목적과 충돌했다. (2) ULW가 Autopilot보다 검증이 약함(L0-L2 없음)은 직교 모델에서 자연 해소 — ULW는 기존 품질 게이트에 추가 재시도를 부여. (3) 5→3 규칙 통합은 개념적 중복 제거 + 3회 제한이라는 명확한 경계 부여
- **대안**: 기존 ADR-023 유지 → 기각 (2축 직교가 실제 사용 패턴과 부합), 제한 없는 재시도 → 기각 (무한 루프 위험)
- **영향 범위**: CLAUDE.md, AGENTS.md, `_context_lib.py`, `restore_context.py`, `generate_context_summary.py`, DECISION-LOG.md, README.md, USER-MANUAL.md, ARCHITECTURE.md, GEMINI.md, copilot-instructions.md, agenticworkflow.mdc, soul.md — 총 13개 파일. 추가: `validate_retry_budget.py`(P1 재시도 예산 봉쇄 — RB1-RB3, --check-and-increment atomic 모드), `setup_init.py`/`setup_maintenance.py`(REQUIRED_SCRIPTS D-7 동기화) — 총 16개 파일

### ADR-044: G1 — 교차 단계 추적성 (Cross-Step Traceability)

- **날짜**: 2026-02-23
- **상태**: Accepted
- **맥락**: 기존 4계층 품질 보장은 각 단계를 수직으로 검증하나, 단계 간 수평 연결(Step 5 분석이 Step 1 리서치에서 실제로 도출되었는가)은 검증 불가
- **결정**: 5번째 Verification 기준 유형 "교차 단계 추적성" 추가. `[trace:step-N:section-id:locator]` 인라인 마커로 단계 간 논리적 연결을 명시. P1 검증 스크립트 `validate_traceability.py` (CT1-CT5)
- **근거**: Agentic RAG 연구에서 "chunk 간 연결성 부재"가 핵심 문제점으로 지목됨. 동일 원리를 워크플로우 단계 간 적용
- **대안**: (1) 자연어 참조만 사용 — 기각 (결정론적 검증 불가). (2) 전체 산출물 임베딩 비교 — 기각 (과도한 인프라 요구)
- **관련 파일**: `_context_lib.py`, `validate_traceability.py`, `generate_context_summary.py`, `setup_init.py`, `setup_maintenance.py`, `AGENTS.md`, `workflow-template.md`

### ADR-045: G2 — 팀 중간 체크포인트 패턴 (Dense Checkpoint Pattern)

- **날짜**: 2026-02-23
- **상태**: Accepted
- **맥락**: (team) 단계에서 Teammate가 전체 Task 완료 후 Team Lead 검증 시 초반 방향 오류 발견 → 전체 재작업
- **결정**: Dense Checkpoint Pattern(DCP) 설계 패턴 추가. CP-1(방향 설정) → CP-2(중간 산출물) → CP-3(최종 산출물). 기존 TaskCreate + SendMessage 프리미티브만 사용, 신규 인프라 없음
- **근거**: Princeton Fuzzy Graph Reward 연구의 "중간 보상 신호(intermediate reward signal)" 개념 적용 — 최종 산출물만 평가하는 sparse reward를 dense reward로 전환
- **대안**: (1) SOT에 CP 상태 추적 — 기각 (스키마 변경 불필요한 복잡도). (2) Hook 기반 자동 CP — 기각 (SendMessage 기반 유연성이 더 적합)
- **관련 파일**: `claude-code-patterns.md`, `workflow-template.md`, `SKILL.md`

### ADR-046: G3 — 도메인 지식 구조 (Domain Knowledge Structure)

- **날짜**: 2026-02-23
- **상태**: Accepted
- **맥락**: 기존 검증은 구조적 품질만 체크. 도메인 특화 추론(의학: 증상→질병, 법률: 판례→원칙)의 타당성은 검증 불가
- **결정**: `domain-knowledge.yaml` 스키마 + `[dks:entity-id]` 참조 마커 패턴 추가. Research 단계에서 구축, Implementation에서 검증 기준으로 활용. P1 검증 스크립트 `validate_domain_knowledge.py` (DK1-DK7). 선택적 패턴 — 모든 워크플로우가 필요로 하지 않음
- **근거**: Hybrid RAG의 "KG(Knowledge Graph) 기반 정확도 향상" 패턴을 워크플로우 게놈에 내장. 자식 시스템이 도메인에 맞게 발현
- **대안**: (1) 전체 KG DB 인프라 — 기각 (과도한 의존성). (2) 자연어 검증만 — 기각 (P1 결정론적 검증 불가). (3) 필수 패턴 — 기각 (코드 생성·블로그 등 불필요한 도메인에 부담)
- **관련 파일**: `_context_lib.py`, `validate_domain_knowledge.py`, `generate_context_summary.py`, `setup_init.py`, `setup_maintenance.py`, `state.yaml.example`, `AGENTS.md`, `soul.md`

### ADR-048: 전수조사 기반 시스템 일관성 강화

- **날짜**: 2026-02-23
- **상태**: Accepted
- **맥락**: 코드베이스 전수조사에서 문서-코드 불일치(NEVER DO 충돌, 미문서화 D-7 인스턴스, I-3과 품질 게이트 재시도 한도의 논리적 모순)를 발견. LLM이 문서를 코드보다 우선하여 잘못된 행동을 할 수 있는 구조적 취약점이 확인됨.
- **결정**:
  1. 품질 게이트 재시도 한도를 DEFAULT 2→10, ULW 3→15로 상향 (경로 B: 충분한 끈기 + Abductive Diagnosis 필수)
  2. P1 doc-code sync 검증 함수(`_check_doc_code_sync()`)를 `setup_maintenance.py`에 추가: DC-1(NEVER DO ↔ 코드 상수), DC-2(D-7 Risk 상수), DC-3(D-7 ULW 패턴), DC-4(D-7 재시도 한도)
  3. I-3 Bounded Retry Escalation에 "(품질 게이트는 별도 예산 적용)" 예외 명시
  4. D-7 인스턴스 #5 문서화: 재시도 한도 3-file sync (`validate_retry_budget.py` ↔ `_context_lib.py` ↔ `restore_context.py`)
  5. 에이전트 보강: translator Review 컨텍스트 인식, fact-checker Pre-mortem→pACS 연결
- **근거**: "문서 = 사양"인 시스템에서 문서-코드 불일치는 런타임 행동 오류와 동일. 재시도 한도 상향은 "스캐닝 성공이 워크플로우의 가장 중요한 목적"이라는 사용자 요구사항 반영. P1 doc-code sync는 동일 클래스의 버그 재발 방지
- **대안**: (1) 무한 재시도(경로 C) — 기각 (I-3 안전장치 해제, 무한 루프 위험). (2) 중간 상향(경로 A, 5/7) — 기각 (사용자가 경로 B 선택)
- **관련 파일**: `validate_retry_budget.py`, `_context_lib.py`, `restore_context.py`, `setup_maintenance.py`, `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, Spoke 3개, `translator.md`, `fact-checker.md`, `maintenance.md`, `claude-code-patterns.md`, `state.yaml.example`

### ADR-049: CLAUDE.md 경량화 — TOC 패턴 전환

- **날짜**: 2026-03-01
- **상태**: Accepted
- **맥락**: Anthropic/OpenAI 하네스 엔지니어링 원칙 비교 분석에서 CLAUDE.md(512줄)가 매 턴마다 컨텍스트를 과도하게 소비하는 구조적 문제 발견. Anthropic 권고: "CLAUDE.md는 최소화 — Would removing this cause mistakes? If not, cut it." OpenAI 원칙: "AGENTS.md as Table of Contents (~100 lines)".
- **결정**:
  1. CLAUDE.md를 512줄 → 160줄로 경량화 (69% 절감) — 목차 + 필수 행동 지시만 유지
  2. 상세 프로토콜을 `docs/protocols/`로 분리: autopilot-execution.md, quality-gates.md, ulw-mode.md, context-preservation-detail.md, code-change-protocol.md (5개 파일)
  3. CLAUDE.md에 on-demand 참조 포인터 삽입 ("워크플로우 실행 전 반드시 읽기: docs/protocols/autopilot-execution.md")
  4. `setup_maintenance.py` DC-1 체크 경로를 `docs/protocols/autopilot-execution.md`로 업데이트
- **근거**: 컨텍스트 윈도우는 가장 중요한 자원. 워크플로우 실행 중에만 필요한 체크리스트(~120줄)가 일반 대화에서도 매 턴 로드되는 것은 토큰 낭비. Lazy loading(on-demand Read)으로 전환하면 비-워크플로우 세션에서 ~350줄 절감
- **대안**: (1) CLAUDE.md 유지 + AGENTS.md만 경량화 — 기각 (CLAUDE.md가 매 턴 자동 로드되므로 경량화 효과가 더 큼). (2) 전체 내용을 @import로 자동 병합 — 기각 (Claude Code가 @import를 지원하지 않으며, 지원하더라도 항상 로드되어 lazy loading 이점 상실)
- **관련 파일**: `CLAUDE.md`, `docs/protocols/*.md` (5개), `setup_maintenance.py`

### ADR-050: Security Hardening — 4계층 방어 체계 + claude-forge 보안 인사이트

- **날짜**: 2026-03-02
- **상태**: Accepted
- **맥락**: claude-forge 전수조사(ADR ref: claude-forge-analysis.md)에서 6계층 보안 체계(40+ deny 패턴, 4개 보안 훅, rate-limiter, 2-패스 시크릿 스캔)를 발견. AgenticWorkflow는 1.5계층(PreToolUse 1개 + settings.json deny 0개)만 보유. 시크릿 누출, 코드 인젝션, 네트워크 유출의 3가지 취약점 확인.
- **결정**:
  1. **Layer 0 (settings.json deny)**: 18개 정적 차단 패턴 추가 — pipe injection(curl/wget|sh), 시스템 명령(sudo, chmod 777, osascript, crontab, mkfs, dd), 패키지 배포(npm/yarn/pnpm publish), 민감 파일 쓰기(~/.ssh/*, ~/.zshrc, ~/.bashrc, ~/.profile)
  2. **Layer 1 (PreToolUse 확장)**: `block_destructive_commands.py`에 NETWORK_PATTERNS(curl/wget|sh) + SYSTEM_PATTERNS(dd, mkfs) 추가 — Layer 0과의 이중 방어(Defense in Depth)
  3. **Layer 2a (PostToolUse 신규)**: `output_secret_filter.py` — transcript JSONL에서 실제 도구 출력 읽기, 25+ 시크릿 패턴 2-패스 스캔(raw + base64/URL decoded), security.log SOT(fcntl.flock 원자적 쓰기, chmod 600)
  4. **Layer 2b (PostToolUse 신규)**: `security_sensitive_file_guard.py` — Edit|Write 대상 파일 12개 보안 패턴 검사(.env, *.pem, credentials.*, 클라우드 자격증명, K8s secret, Terraform state 등), 세션 중복제거(/tmp 마커)
- **근거**:
  - **CRITICAL 발견**: PostToolUse의 `tool_response`는 `{}`(빈 객체) — 원래 설계(tool_response 스캔)가 무효. transcript JSONL tail-read로 실제 출력 확보 필수.
  - **P1 원칙 준수**: 모든 보안 판단은 결정론적 Python(regex, 문자열 매칭, JSON 파싱). AI 판단 0%.
  - **품질 > 속도(절대 기준 1)**: 2차 성찰에서 security_sensitive_file_guard.py를 predictive_debug_guard.py에 병합하려던 속도 최적화 설계를 철회. SRP(단일 책임 원칙) 위반 — 보안과 디버깅은 독립 관심사.
  - **SOT 준수(절대 기준 2)**: security.log를 보안 이벤트 감사 로그(audit log)로 신설. fcntl.flock으로 원자적 쓰기 보장. (4차 성찰: SOT가 아닌 audit log으로 정정 — 프로그래밍적 읽기 없음)
  - 모든 훅에 Safety-first: 내부 오류 시 `exit(0)`(절대 Claude를 차단하지 않음).
- **대안**:
  - (1) claude-forge 훅 직접 포팅 → 기각 (원격 세션 전용 설계, OPENCLAW_SESSION_ID 게이팅이 로컬에서 무의미)
  - (2) tool_response 기반 스캔 → ~~기각~~ 4차 성찰에서 재채택 (tool_response는 실제로 데이터 포함 — Bash: stdout/stderr, Read: file.content. Tier 1 추출 경로로 구현)
  - (3) security_sensitive_file_guard를 predictive_debug_guard에 병합 → 기각 (SRP 위반, 절대 기준 1)
- **검증**: output_secret_filter.py 44/44 테스트 통과 (단위 22 + Tier 3 통합 8 + Tier 1 통합 9 + Tier 2 통합 5), security_sensitive_file_guard.py 44/44 테스트 통과, block_destructive_commands.py 43/43 테스트 통과
- **관련 파일**: `settings.json`, `block_destructive_commands.py`, `output_secret_filter.py`(신규), `security_sensitive_file_guard.py`(신규), `_test_secret_filter.py`(신규), `_test_sensitive_file_guard.py`(신규), `_test_block_destructive.py`(신규)

---

## 9. Doctoral Thesis Workflow (논문 워크플로우)

### ADR-052: Doctoral Thesis Workflow — 210-step 논문 시뮬레이션

- **날짜**: 2026-03-05
- **상태**: Accepted
- **맥락**: AgenticWorkflow의 DNA 유전 철학을 검증할 대규모 자식 시스템이 필요했다. 박사 논문 연구 과정은 문헌 검토 → 연구 설계 → 집필 → 출판까지 복잡한 의존성과 품질 게이트를 갖는 이상적인 테스트 케이스였다.
- **결정**: 210-step 3-Phase 구조 채택:
  - Phase 0 (Literature Review): Wave 1-5, 각 Wave 10-15 step, Gate로 교차 검증
  - Phase 1 (Research Design): 방법론·샘플링·도구 설계, HITL 승인
  - Phase 2 (Writing & Publication): 집필·편집·투고, 연구 유형별 분기
  - 48개 전문 에이전트, 5개 Gate, 9개 HITL 체크포인트
- **근거**: Wave/Gate/HITL 아키텍처는 부모의 4계층 QA를 논문 도메인에 맥락화한 것이다. Gate는 L1(Verification), HITL은 인간 검토로 품질을 이중 보장한다. 48개 에이전트는 P2(전문성 기반 위임)의 극대화다.
- **대안**:
  - 단순 선형 워크플로우 → 기각 (교차 검증 불가, 품질 보장 없음)
  - 범용 연구 도구 → 기각 (박사 논문의 엄밀성 요구 미충족)
- **관련 커밋**: 논문 워크플로우 구현 일련

### ADR-053: E2E Test Infrastructure — 5-Track 통합 테스트

- **날짜**: 2026-03-05
- **상태**: Accepted
- **맥락**: checklist_manager.py와 query_workflow.py가 논문 SOT의 핵심 인프라가 되면서, CLI 수준의 통합 테스트가 필수가 되었다. 유닛 테스트만으로는 컴포넌트 간 데이터 흐름을 검증할 수 없었다.
- **결정**: pytest + subprocess 기반 E2E 테스트 인프라 구축. 5개 Track으로 분류:
  - Track 1: Full Lifecycle (init → advance → gate → HITL → checkpoint → restore)
  - Track 2: SOT Integrity (스키마 검증, 필드 일관성, 원자적 쓰기)
  - Track 3: Cross-Component (checklist_manager ↔ query_workflow ↔ generate_context_summary)
  - Track 4: CLI Flag Completeness (모든 argparse 플래그 성공/에러 시나리오)
  - Track 5: Error Recovery (손상 SOT, 누락 파일, 의존성 적용, 체크포인트 복구)
- **근거**: CLI 수준 테스트는 실제 사용자 시나리오를 재현한다. 5-Track 분류는 실패 원인 격리를 용이하게 한다.
- **대안**:
  - 함수 단위 유닛 테스트만 → 기각 (컴포넌트 간 통합 검증 불가)
  - Playwright E2E → 기각 (웹 UI 없음, CLI 기반 시스템)
- **관련 커밋**: E2E 테스트 구현 일련

### ADR-054: GroundedClaim Schema Unification — 47개 prefix 체계

- **날짜**: 2026-03-05
- **상태**: Accepted
- **맥락**: 48개 논문 에이전트가 각자 claim을 생성하는데, claim ID 형식이 불일치하면 교차 검증과 추적이 불가능해진다.
- **결정**: Family-based prefix 체계로 통합:
  - 형식: `{PREFIX}-{NUMBER}` (예: `LS-001`, `SA-TA001`, `PC-SRCS-001`)
  - 47개 고유 prefix — 에이전트별 2자리 대문자 + 선택적 서브 prefix
  - `validate_grounded_claim.py`로 결정론적 검증
  - 통합 스키마: `id, text, claim_type, sources[], confidence (0-100), verification`
- **근거**: 통합 ID 체계는 절대 기준 2(SOT)의 claim 차원 적용이다. 결정론적 검증은 P1(데이터 정제)의 claim 차원 적용이다.
- **대안**:
  - 자유형식 ID → 기각 (교차 참조 불가, 중복 감지 불가)
  - 단일 prefix → 기각 (에이전트 출처 추적 불가)
- **관련 커밋**: GroundedClaim 스키마 구현 일련

### ADR-055: --record-hitl CLI Extension

- **날짜**: 2026-03-05
- **상태**: Accepted
- **맥락**: HITL 체크포인트 기록이 Python API(`cm.record_hitl()`)로만 가능했다. Slash Command에서 CLI를 통해 HITL을 기록해야 하는데, CLI 인터페이스가 없었다.
- **결정**: `checklist_manager.py`에 `--record-hitl` 플래그 추가. `--hitl-status`로 상태 지정 가능 (기본값: `completed`).
- **근거**: CLI 인터페이스는 Slash Command, 외부 스크립트, E2E 테스트에서 모두 사용 가능한 범용 진입점이다.
- **대안**:
  - Python API만 유지 → 기각 (CLI에서 호출 불가)
  - 별도 스크립트 → 기각 (checklist_manager.py에 이미 CLI 인프라 존재)
- **관련 커밋**: --record-hitl 구현

### ADR-056: Thesis Remediation — P1 Python Boundary + Gate Regex Fix + GroundedClaim Normalization

- **날짜**: 2026-03-05
- **상태**: Accepted
- **맥락**: 초기 210-step 워크플로우 실행 후 품질 감사에서 심각한 문제 발견: (1) 60개 phantom steps (SOT 기록만 있고 실제 산출물 없음), (2) 4개 gate score 조작 (gate-2: 85, gate-3: 82, srcs-full: 80, final-quality: 78 — 실제 검증 없이 기록), (3) claim ID regex 불일치로 `validate_wave_gate.py`, `compute_srcs_scores.py`, `validate_grounded_claim.py`가 multi-hyphen 형식(EMP-NEURO-001, CR-LOGIC-001, PHIL-T001)을 인식 못함, (4) 25개 파일에 한국어 번역 누락.
- **결정**:
  1. **P1 Python Boundary**: 6개 deterministic 스크립트 신규 생성 — `extract_references.py`, `check_format_consistency.py`, `detect_self_plagiarism.py`, `generate_thesis_outline.py`, `build_bilingual_manifest.py`, `format_grounded_claims.py`. LLM은 semantic tasks만, Python은 100% 반복 가능한 deterministic tasks 담당.
  2. **Claim ID Regex 통합 수정**: `[A-Z]+-\d+` → `[A-Z]+(?:-[A-Z]+)*-?\d{2,}` + `claim_id:` prefix 지원. 3개 스크립트 동시 수정.
  3. **SOT 정직화**: 조작된 gate scores 제거, 실제 `validate_wave_gate.py` 결과로 교체 (gate-1~3 + srcs-full PASS, final-quality FAIL), status "completed" → "in_progress".
  4. **GroundedClaim 구조화**: 5개 wave 파일에 누락된 claims 추가 (format_grounded_claims.py 파이프라인: LLM 식별 → JSON → Python 포맷팅 → 검증).
  5. **전수 번역**: 18개 파일에 @translator 에이전트 병렬 실행.
- **근거**: 절대 기준 1(품질)의 직접 구현. 3차 성찰(Round 3)에서 확립된 "LLM vs Python 경계" 원칙 — 할루시네이션 원천봉쇄.
- **대안**:
  - 전체 재실행 → 기각 (기존 산출물 품질은 양호, 인프라만 수정 필요)
  - regex를 각 파일별로 다르게 → 기각 (일관성 원칙 위반)
- **관련 파일**: `validate_wave_gate.py:57-64`, `compute_srcs_scores.py:111`, `validate_grounded_claim.py:63`, `format_grounded_claims.py` (new), `extract_references.py` (new), `check_format_consistency.py` (new), `detect_self_plagiarism.py` (new), `generate_thesis_outline.py` (new), `build_bilingual_manifest.py` (new)

### ADR-057: Audit Trail Persistence — 빈 폴더 6개 근본 원인 해결

- **날짜**: 2026-03-06
- **상태**: Accepted
- **맥락**: 210-step 워크플로우 풀 가동 후 전수조사 결과, 12개 빈 폴더 중 6개가 비정상 (gate-reports, verification-logs, review-logs, thesis-drafts, submission-package, research-design). 근본 원인: thesis-orchestrator.md의 E5 루프에 파일 쓰기 지시 누락, Phase 3/4 상세 프로토콜 부재.
- **결정**:
  1. **E5 루프 확장**: 6→8항목. E5.3(verification-log 생성), E5.4(@reviewer 호출 + Write to review-logs). 검증자(validate_verification.py, validate_review.py)는 변경 없음 — 생성 책임을 Orchestrator에 명시.
  2. **Gate 실행에 --output-json 활용**: validate_wave_gate.py의 기존 `--output-json` 플래그를 사용하여 gate-reports/ 저장. record_gate_result()의 기존 `report_path` 매개변수로 SOT 연결.
  3. **Phase 3 Draft Versioning Protocol**: 리뷰→수정 사이클에서 thesis-drafts/에 v1/v2/v3 백업.
  4. **Phase 4 Submission Package Protocol**: @manuscript-formatter, @cover-letter-writer 에이전트 호출 지시 추가.
  5. **research-design → phase-2 경로 정규화**: init_project()에서 레거시 폴더 제거, 실제 사용 경로로 교체.
- **근거**: 절대 기준 1(품질). 품질 검증의 감사 추적(audit trail)이 없으면 워크플로우 재현 불가. 기존 인프라(--output-json, report_path, reviewer.md 계약) 최대 활용으로 변경 최소화.
- **대안**:
  - 별도 Hook 스크립트로 파일 자동 생성 → 기각 (Orchestrator 지시문 수정이 더 직접적이고 결합도 낮음)
  - validate_verification.py에 생성 기능 추가 → 기각 (P1 validator는 read-only 원칙 위반)
- **파급 효과**: Additive-only. 기존 API 시그니처 변경 없음. E2E 테스트 108개 영향 없음.
- **관련 파일**: `thesis-orchestrator.md` (E5, Gate, Phase 3/4 섹션), `checklist_manager.py:655`, `_test_checklist_manager.py:163`, `quality-gates.md` (§14 추가)

---

## 부록: 커밋 히스토리 기반 타임라인

| 날짜 | 커밋 | 결정 |
|------|------|------|
| 2026-02-16 | `348601e` | ADR-001~007: 프로젝트 기반 (목표, 절대 기준, 3단계 구조, SOT, CCP) |
| 2026-02-16 | `e051837` | ADR-009: RLM 이론적 기반 채택 |
| 2026-02-16 | `feba502` | ADR-010: 독립 아키텍처 문서 분리 |
| 2026-02-16 | `bb7b9a1` | ADR-012: Hook 기반 컨텍스트 보존 시스템 |
| 2026-02-17 | `d1acb9f` | ADR-013: Knowledge Archive |
| 2026-02-17 | `7363cc4` | ADR-014: Smart Throttling |
| 2026-02-17 | `5b649cb` | ADR-008, 027, 028: Hub-and-Spoke, English-First, @translator |
| 2026-02-17 | `b0ae5ac` | ADR-019, 020: Autopilot Mode + 런타임 강화 |
| 2026-02-18 | `42ee4b1` | ADR-021: Agent Team (Swarm) 패턴 |
| 2026-02-18~19 | `2c91985` | ADR-015, 025, 026, 029, 030: 18항목 감사·성찰 |
| 2026-02-19 | `f592483` | ADR-022: Verification Protocol |
| 2026-02-19 | `ce0c393`, `eed44e7` | ADR-017: Error Taxonomy |
| 2026-02-20 | `c7324f1` | ADR-023: ULW Mode |
| 2026-02-20 | `162a322`~`5634b0e` | ADR-011: Spoke 파일 정리 |
| 2026-02-20 | `f76a1fd` | ADR-016, 024: E5 Guard, P1 할루시네이션 봉쇄 |
| 2026-02-20 | (pending) | ADR-031: PreToolUse Safety Hook |
| 2026-02-20 | (pending) | ADR-032: PreToolUse TDD Guard |
| 2026-02-20 | (pending) | ADR-033: Context Memory 최적화 (success_patterns, Next Step IMMORTAL, regex) |
| 2026-02-20 | (pending) | ADR-034: Adversarial Review — Enhanced L2 + P1 할루시네이션 봉쇄 |
| 2026-02-20 | (pending) | ADR-035: 종합 감사 — SOT 스키마 확장 + Quality Gate IMMORTAL + Error→Resolution 표면화 |
| 2026-02-20 | (pending) | ADR-036: Predictive Debugging — 에러 이력 기반 위험 파일 사전 경고 |
| 2026-02-20 | (pending) | ADR-037: 종합 감사 II — pACS P1 + L0 Anti-Skip Guard + IMMORTAL 경계 + Context Memory |
| 2026-02-20 | (pending) | ADR-038: DNA Inheritance — 부모 게놈의 구조적 유전 |
| 2026-02-20 | (pending) | ADR-039: Workflow.md P1 Validation — DNA 유전의 코드 수준 검증 |
| 2026-03-02 | (pending) | ADR-050: Security Hardening — 4계층 방어 체계 + claude-forge 보안 인사이트 |
| 2026-03-02 | accepted | ADR-051: Claude Code v2.1 신기능 연구 — 기존 설계 타당성 검증 + @translator memory: project 채택 |
| 2026-02-20 | (pending) | ADR-040: 종합 감사 III — 4계층 QA 집행력 강화 (C1r/C2/W4/C4s/W7) |
| 2026-02-23 | (pending) | ADR-041: 코딩 기준점 (Coding Anchor Points, CAP-1~4) |
| 2026-02-23 | (pending) | ADR-042: Hook 설정 Global → Project 통합 |
| 2026-02-23 | accepted | ADR-043: ULW 재설계 — 직교 철저함 오버레이 (Supersedes ADR-023) |
| 2026-02-23 | (pending) | ADR-044: G1 — 교차 단계 추적성 (Cross-Step Traceability) |
| 2026-02-23 | (pending) | ADR-045: G2 — 팀 중간 체크포인트 패턴 (Dense Checkpoint Pattern) |
| 2026-02-23 | (pending) | ADR-046: G3 — 도메인 지식 구조 (Domain Knowledge Structure) |
| 2026-02-23 | (pending) | ADR-047: Abductive Diagnosis Layer — 품질 게이트 FAIL 시 구조화된 진단 |
| 2026-02-23 | accepted | ADR-048: 전수조사 기반 시스템 일관성 강화 — 재시도 한도 10/15 + P1 doc-code sync + D-7 #5 |
| 2026-03-01 | accepted | ADR-049: CLAUDE.md 경량화 — TOC 패턴 전환 (512→160줄, docs/protocols/ 분리) |
| 2026-03-05 | accepted | ADR-052: Doctoral Thesis Workflow — 210-step 논문 시뮬레이션 + 48 에이전트 + Wave/Gate/HITL |
| 2026-03-05 | accepted | ADR-053: E2E Test Infrastructure — 5-Track pytest + subprocess 통합 테스트 |
| 2026-03-05 | accepted | ADR-054: GroundedClaim Schema Unification — 47개 family-based prefix 체계 |
| 2026-03-05 | accepted | ADR-055: --record-hitl CLI Extension — HITL 체크포인트 CLI 기록 |
| 2026-03-05 | accepted | ADR-056: Thesis Remediation — P1 Python Boundary + Gate Regex Fix + GroundedClaim 정규화 |
| 2026-03-06 | accepted | ADR-057: Audit Trail Persistence — 빈 폴더 6개 근본 원인 해결 |
| 2026-03-06 | accepted | ADR-058: CCP MANDATORY 강제 + P1 의존성 스캐너 |

### ADR-058: CCP MANDATORY 강제 + P1 의존성 스캐너

- **날짜**: 2026-03-06
- **상태**: Accepted
- **맥락**: CCP(절대 기준 3)가 AGENTS.md에 완전 정의되어 있지만, CLAUDE.md에서 4줄 참조로만 존재하여 매 턴 활성화가 불안정했다. English-First(MANDATORY, 19줄 인라인)는 매번 작동하지만, CCP(4줄)는 불안정 — 인라인 분량과 활성화 신뢰도의 상관관계 확인.
- **결정**:
  1. **CLAUDE.md CCP 인라인 확장**: 4줄 → ~25줄. English-First 패턴 적용 — MANDATORY 키워드, "무효" 결과 명시, 비례성 테이블, CCP-1/2/3 인라인 체크리스트.
  2. **`ccp_ripple_scanner.py` P1 신규**: PreToolUse Hook(Edit|Write)으로 CCP-2 데이터 수집을 자동화. grep 기반 참조 발견 + hardcoded Hub-Spoke 동기화 맵 + 테스트 파일 매핑 + Hook 등록 참조 + Python importer 발견. exit 0 전용(정보 제공, 차단 안 함).
  3. **AGENTS.md "설정/환경/빌드" 예시 보강**: agent 정의(.md), Hook 등록(settings.json) 추가.
  4. **code-change-protocol.md 동기화**: MANDATORY 경고 + P1 자동 지원 언급 + 설정 예시 보강.
- **근거**:
  - (1) 절대 기준 1(품질): DRY에 의한 토큰 절약 vs. 인라인에 의한 확실한 활성화 — 품질이 이김.
  - (2) P1 원칙: 의존성 발견은 결정론적(grep, 파일 매핑). LLM이 "기억"에 의존하면 할루시네이션·누락 위험. Python이 사실(facts)을 제공하고 LLM은 판단(judgment)만.
  - (3) Hub-Spoke 보존: AGENTS.md가 Hub SOT 유지. CLAUDE.md는 자기 완결적 활성화 트리거 + Hub 참조.
- **대안**:
  - PreToolUse Hook으로 CCP 준수 여부를 검증 → 기각 (CCP 준수는 의미론적이며 결정론적 검증 불가 — ADR-041 선례)
  - CLAUDE.md에 트리거 테이블만 → 기각 (English-First 성공 패턴 분석 결과, 인라인 행동 지시가 필수)
  - Hub(AGENTS.md)만 강화 → 기각 (AGENTS.md는 매 턴 로딩되지 않음. CLAUDE.md 인라인이 효과적)
- **파급 효과**: Additive-only. 기존 코드 수정/삭제 없음. 신규 2파일 + 기존 5파일 수정(append/expand만). RLM/SOT/4계층 검증/DNA 유전 구조 영향 없음.
- **관련 파일**: `CLAUDE.md` (§절대 기준 3, §Hook 테이블, §프로젝트 구조), `AGENTS.md` (L123), `docs/protocols/code-change-protocol.md`, `.claude/settings.json`, `.claude/hooks/scripts/ccp_ripple_scanner.py` (신규), `.claude/hooks/scripts/_test_ccp_ripple_scanner.py` (신규)
- **관련 ADR**: ADR-007 (CCP 원본), ADR-041 (CAP — 의미론적 검증 불가 선례), ADR-036 (Predictive Debugging — 동일 P1 패턴)

---

## 문서 관리

- **갱신 규칙**: 새로운 `feat:` 커밋이 설계 결정을 포함하면, 해당 ADR을 이 문서에 추가한다.
- **번호 규칙**: `ADR-NNN` 형식으로 순차 부여. 삭제된 번호는 재사용하지 않는다.
- **상태 전이**: `Accepted` → `Superseded by ADR-NNN` → `Deprecated` (사유 명시)
- **위치**: 프로젝트 루트 (`DECISION-LOG.md`). 프로젝트 구조 트리에 포함.
