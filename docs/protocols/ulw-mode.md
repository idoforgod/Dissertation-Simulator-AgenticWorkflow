# ULW (Ultrawork) Mode

> 이 문서는 ULW 모드의 상세 명세이다.
> CLAUDE.md에서 분리됨 — ULW 활성 시 참조.

## 개요

프롬프트에 `ulw`를 포함하면 **Ultrawork 모드**가 활성화된다. ULW는 Autopilot과 **직교하는 철저함 강도(thoroughness intensity) 오버레이**이다.

- **Autopilot** = 자동화 축(HOW) — `(human)` 승인 건너뛰기
- **ULW** = 철저함 축(HOW THOROUGHLY) — 빠짐없이, 에러 해결까지 완벽 수행

두 축은 독립적이므로, 어떤 조합이든 가능하다:

|  | **ULW OFF** (보통) | **ULW ON** (최대 철저함) |
|---|---|---|
| **Autopilot OFF** | 표준 대화형 | 대화형 + Sisyphus Persistence(3회 재시도) + 필수 태스크 분해 |
| **Autopilot ON** | 표준 자동 워크플로우 | 자동 워크플로우 + Sisyphus 강화(재시도 3회) + 팀 철저함 |

## 2축 비교

| 축 | 관심사 | 활성화 | 비활성화 | 적용 범위 |
|----|--------|--------|---------|----------|
| **Autopilot** | 자동화(HOW) | SOT `autopilot.enabled: true` | SOT 변경 | 워크플로우 단계 |
| **ULW** | 철저함(HOW THOROUGHLY) | 프롬프트에 `ulw` | 암묵적 (새 세션 시 `ulw` 없으면 비활성) | 모든 작업 (대화형 + 워크플로우) |

## 활성화 패턴

| 사용자 명령 | 동작 |
|-----------|------|
| "ulw 이거 해줘", "ulw 리팩토링해줘" | 트랜스크립트에서 `ulw` 감지 → ULW 모드 활성화 |
| 새 세션에서 `ulw` 없는 프롬프트 | ULW 비활성 (암묵적 해제 — 명시적 해제 불필요) |

## 3가지 강화 규칙 (Intensifiers)

ULW가 활성화되면 아래 3가지 강화 규칙이 **현재 컨텍스트에 오버레이**된다:

| 강화 규칙 | 설명 | 대화형 효과 | Autopilot 결합 효과 |
|----------|------|-----------|-------------------|
| **I-1. Sisyphus Persistence** | 최대 3회 재시도, 각 시도는 다른 접근법. 100% 완료 또는 불가 사유 보고 | 에러 시 3회까지 대안 시도 | 품질 게이트(Verification/pACS) 재시도 한도 10→15회 상향 |
| **I-2. Mandatory Task Decomposition** | TaskCreate → TaskUpdate → TaskList 필수 | 비-trivial 작업 시 태스크 분해 강제 | 변경 없음 (Autopilot은 이미 SOT 기반 추적) |
| **I-3. Bounded Retry Escalation** | 동일 대상 3회 초과 연속 재시도 금지(품질 게이트는 별도 예산 적용) — 초과 시 사용자 에스컬레이션 | 무한 루프 방지 | Safety Hook 차단은 항상 존중 |

## 런타임 강화 메커니즘

| 계층 | 메커니즘 | 강화 내용 |
|------|---------|----------|
| **Hook** (결정론적) | `_context_lib.py` — `detect_ulw_mode()` | 트랜스크립트 정규식으로 `ulw` 감지 |
| **Hook** (결정론적) | `generate_snapshot_md()` — 스냅샷 | ULW 상태 섹션을 IMMORTAL 우선순위로 보존 |
| **Hook** (결정론적) | `extract_session_facts()` — Knowledge Archive | `ulw_active: true` 태깅 → RLM 쿼리 가능 |
| **Hook** (결정론적) | `restore_context.py` — SessionStart | ULW 활성 시 3개 강화 규칙을 컨텍스트에 주입 (startup source 제외 — 암묵적 해제) |
| **Hook** (결정론적) | `_context_lib.py` — `check_ulw_compliance()` | 3개 강화 규칙 준수를 결정론적으로 검증 → 스냅샷 IMMORTAL에 경고 포함 |
| **Hook** (결정론적) | `generate_context_summary.py` — Stop | ULW Compliance 안전망 — 위반 시 stderr 경고 |

## NEVER DO
- 동일 대상에 3회 초과 연속 재시도 금지(품질 게이트는 별도 예산 적용) — I-3 위반, 사용자 에스컬레이션 필수
- Safety Hook(`(hook)` exit code 2) 차단을 ULW 명목으로 override 금지
- ULW 활성 상태에서 Task를 "일부 완료"로 남기고 멈추기 금지 — I-1 위반
- 에러 발생 시 대안 시도 없이 포기 금지 — I-1 위반
- TaskCreate 없이 암묵적으로 작업 진행 금지 (비-trivial 작업 시) — I-2 위반
