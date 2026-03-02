# Autopilot Execution Protocol

> 이 문서는 Autopilot 모드에서 워크플로우를 실행할 때의 상세 체크리스트이다.
> CLAUDE.md에서 분리됨 — 워크플로우 실행 시에만 참조.

## 활성화 패턴

| 사용자 명령 | 동작 |
|-----------|------|
| "autopilot 모드로 실행", "자동 모드로 워크플로우 실행", "전자동으로 실행" | SOT에 `autopilot.enabled: true` 설정 후 워크플로우 시작 |
| "autopilot 해제", "수동 모드로 전환" | SOT에 `autopilot.enabled: false` — 다음 `(human)` 단계부터 적용 |

## Checkpoint별 동작

| Checkpoint | Autopilot 동작 |
|-----------|---------------|
| `(human)` + Slash Command | 완전한 산출물 생성 → 품질 극대화 기본값으로 자동 승인 → 결정 로그 기록 |
| AskUserQuestion | 선택지 중 품질 극대화 옵션 자동 선택 → 결정 로그 기록 |
| `(hook)` exit code 2 | **변경 없음** — 그대로 차단, 피드백 전달, 재작업 |

## 결정 로그

자동 승인된 결정은 `autopilot-logs/step-N-decision.md`에 기록: 단계, 옵션, 선택 근거(절대 기준 1 기반).
Decision Log 표준 템플릿: `references/autopilot-decision-template.md`

## 런타임 강화 메커니즘

| 계층 | 메커니즘 | 강화 내용 |
|------|---------|----------|
| **Hook** (결정론적) | `restore_context.py` — SessionStart | Autopilot 활성 시 6개 실행 규칙 + 이전 단계 산출물 검증 결과를 컨텍스트에 주입 |
| **Hook** (결정론적) | `generate_snapshot_md()` — 스냅샷 | Autopilot 상태 + Agent Team 상태 섹션을 IMMORTAL 우선순위로 보존 |
| **Hook** (결정론적) | `generate_context_summary.py` — Stop | 자동 승인 패턴 감지 → Decision Log 누락 시 보완 생성 (안전망) |
| **Hook** (결정론적) | `update_work_log.py` — PostToolUse | `autopilot_step` 필드로 단계 진행 추적 |
| **프롬프트** (행동 유도) | Execution Checklist (아래) | 각 단계의 시작/실행/완료 시 필수 행동 명시 |

> Hook 계층은 SOT를 읽기 전용으로만 접근하며 (절대 기준 2 준수), 쓰기는 `context-snapshots/`와 `autopilot-logs/`에만 수행한다.

---

## Execution Checklist (MANDATORY)

Autopilot 모드에서 워크플로우를 실행할 때, 각 단계마다 아래 체크리스트를 **반드시** 수행한다.

### 각 단계 시작 전
- [ ] SOT `current_step` 확인
- [ ] 이전 단계 산출물 파일 존재 + 비어있지 않음 확인
- [ ] 이전 단계 산출물 경로가 SOT `outputs`에 기록 확인
- [ ] 해당 단계의 `Verification` 기준 읽기 — "100% 완료"의 정의를 먼저 인식 (AGENTS.md §5.3)

### 단계 실행 중
- [ ] 단계의 모든 작업을 **완전히** 실행 (축약 금지 — 절대 기준 1)
- [ ] 산출물을 **완전한 품질**로 생성

### 단계 완료 후 (Verification Gate — `Verification` 필드 있는 단계만)
- [ ] 산출물 파일을 디스크에 저장
- [ ] 산출물을 각 `Verification` 기준 대비 자기 검증
- [ ] 실패 기준 있으면:
  - [ ] P1 재시도 예산 확인+소비: `python3 .claude/hooks/scripts/validate_retry_budget.py --step N --gate verification --project-dir . --check-and-increment`
  - [ ] `can_retry: true` → **Abductive Diagnosis 수행** (아래 진단 서브섹션 참조) → 진단 기반 재실행
  - [ ] `can_retry: false` → 사용자 에스컬레이션 (재시도 예산 소진, 카운터 미증가)
- [ ] 모든 기준 PASS 확인
- [ ] `verification-logs/step-N-verify.md` 생성
- [ ] P1 검증 실행: `python3 .claude/hooks/scripts/validate_verification.py --step N --project-dir .`
- [ ] P1 검증 결과 `valid: true` 확인 (V1a-V1c 모두 통과)

### 단계 완료 후 (Cross-Step Traceability — Verification에 "교차 단계 추적성" 기준이 포함된 단계만)
- [ ] 산출물에 `[trace:step-N:section-id]` 마커가 최소 3개 이상 포함 확인
- [ ] 모든 마커가 이전 단계만 참조 (순방향 참조 금지)
- [ ] P1 검증 실행: `python3 .claude/hooks/scripts/validate_traceability.py --step N --project-dir .`
- [ ] P1 검증 결과 `valid: true` 확인 (CT1-CT5 모두 통과)
- [ ] CT3 WARNING(섹션 ID 미해결) 있으면 마커 정확성 재확인

### 단계 완료 후 (Domain Knowledge Structure — DKS 패턴 사용 워크플로우만, 선택적)
- [ ] `domain-knowledge.yaml` 구축 단계: P1 검증 실행: `python3 .claude/hooks/scripts/validate_domain_knowledge.py --project-dir .`
- [ ] P1 검증 결과 `valid: true` 확인 (DK1-DK5 모두 통과)
- [ ] DKS 참조 단계 (산출물에 `[dks:xxx]` 마커 포함): P1 교차 검증 실행: `python3 .claude/hooks/scripts/validate_domain_knowledge.py --project-dir . --check-output --step N`
- [ ] P1 교차 검증 결과 `valid: true` 확인 (DK6-DK7 포함 모두 통과)

### 단계 완료 후 (pACS — Verification Gate 통과 후 수행)
- [ ] Pre-mortem Protocol 3개 질문에 답하기 (AGENTS.md §5.4)
- [ ] F, C, L 3차원 채점 → pACS = min(F, C, L) 산출
- [ ] `pacs-logs/step-N-pacs.md` 생성
- [ ] SOT `pacs` 필드 갱신 (current_step_score, dimensions, weak_dimension, history)
- [ ] pACS RED(< 50) 시:
  - [ ] P1 재시도 예산 확인+소비: `python3 .claude/hooks/scripts/validate_retry_budget.py --step N --gate pacs --project-dir . --check-and-increment`
  - [ ] `can_retry: true` → **Abductive Diagnosis 수행** (아래 진단 서브섹션 참조) → 진단 기반 재작업 + 재채점
  - [ ] `can_retry: false` → 사용자 에스컬레이션 (재시도 예산 소진, 카운터 미증가)
- [ ] pACS YELLOW(50-69) 시: Decision Log에 약점 차원 기록 후 진행
- [ ] P1 검증 실행: `python3 .claude/hooks/scripts/validate_pacs.py --step N --check-l0 --project-dir .`
- [ ] P1 검증 결과 `valid: true` 확인 (PA1-PA7 + L0 모두 통과)
- [ ] SOT `outputs`에 산출물 경로 기록
- [ ] SOT `current_step` +1 증가
- [ ] `(human)` 단계: `autopilot-logs/step-N-decision.md` 생성
- [ ] `(human)` 단계: SOT `auto_approved_steps`에 추가

### `(team)` 단계 추가 체크리스트
- [ ] `TeamCreate` 직후 → SOT `active_team` 기록 (name, status, tasks_pending)
- [ ] 각 Teammate는 보고 전 자기 Task의 검증 기준 대비 자기 검증 수행 (L1 — AGENTS.md §5.3)
- [ ] 각 Teammate는 L1 통과 후 pACS 자기 채점 수행 (L1.5 — 세션 내부 완결, 점수를 보고 메시지에 포함)
- [ ] 각 Teammate 완료 시 → Team Lead가 단계 검증 기준 대비 종합 검증 (L2) + 단계 pACS 산출
- [ ] L2 FAIL 또는 Teammate pACS RED 시 → SendMessage로 구체적 피드백 + 재실행 지시
- [ ] 각 Teammate 완료 시 → SOT `active_team.tasks_completed` + `completed_summaries` 갱신
- [ ] 모든 Task 완료 시 → SOT `outputs` 기록, `current_step` +1, `active_team.status` → `all_completed`
- [ ] `TeamDelete` 직후 → SOT `active_team` → `completed_teams` 이동
- [ ] Teammate 산출물에 판단 근거(Decision Rationale) + 교차 참조 단서(Cross-Reference Cues) 포함 확인

### 단계 완료 후 (Adversarial Review — `Review: @reviewer|@fact-checker`인 단계만)
- [ ] `Review:` 필드에 지정된 에이전트를 Sub-agent로 호출 (권장: `isolation: "worktree"` — Orchestrator 컨텍스트 보호, 상세: `reviewer.md § Context Isolation`)
- [ ] 리뷰 보고서를 `review-logs/step-N-review.md`에 저장
- [ ] P1 검증 실행: `python3 .claude/hooks/scripts/validate_review.py --step N --project-dir . --check-pacs-arithmetic`
- [ ] P1 검증 결과 `valid: true` 확인 (R1-R5 모두 통과)
- [ ] Verdict 확인:
  - [ ] PASS → 다음 단계 진행 (Translation 포함)
  - [ ] FAIL → P1 재시도 예산 확인+소비: `python3 .claude/hooks/scripts/validate_retry_budget.py --step N --gate review --project-dir . --check-and-increment`
  - [ ] `can_retry: true` → **Abductive Diagnosis 수행** (아래 진단 서브섹션 참조) → 진단 기반 재작업
  - [ ] `can_retry: false` → 사용자 에스컬레이션 (재시도 예산 소진, 카운터 미증가)
- [ ] pACS Delta ≥ 15 시 → Decision Log에 기록 + 재조정 사유 문서화
- [ ] Review FAIL 상태에서 Translation 실행 금지

### 품질 게이트 FAIL 시 진단 (Abductive Diagnosis — 재시도 가능 시 수행)
- [ ] Step A — P1 사전 증거 수집: `python3 .claude/hooks/scripts/diagnose_context.py --step N --gate {verification|pacs|review} --project-dir .`
- [ ] Fast-Path 확인: `fast_path.eligible == true` → FP1/FP2는 즉시 재실행, FP3는 사용자 에스컬레이션
- [ ] Fast-Path 해당 없으면 → Step B — LLM 진단: 증거 번들 + 가설 우선순위 기반으로 원인 분석
- [ ] 진단 로그 생성: `diagnosis-logs/step-N-{gate}-{timestamp}.md`
- [ ] Step C — P1 사후 검증: `python3 .claude/hooks/scripts/validate_diagnosis.py --step N --gate {verification|pacs|review} --project-dir .`
- [ ] P1 검증 결과 `valid: true` 확인 (AD1-AD10 모두 통과)
- [ ] 진단 결과에 따라 선택된 가설(H1/H2/H3/H4) 기반 재작업 실행

### 단계 완료 후 (번역 — `Translation: @translator`인 단계만)
- [ ] `@translator` 서브에이전트 호출 (`translations/glossary.yaml` 참조 포함)
- [ ] 번역 파일(`*.ko.md`) 디스크에 존재 확인
- [ ] 번역 파일 비어있지 않음 확인
- [ ] SOT `outputs.step-N-ko`에 번역 경로 기록
- [ ] `translations/glossary.yaml` 갱신 확인
- [ ] Translation pACS 채점 완료 (Ft/Ct/Nt — `@translator` Step 4, AGENTS.md §5.4)
- [ ] Translation pACS 로그 생성 (`pacs-logs/step-N-translation-pacs.md`)
- [ ] P1 검증 실행: `python3 .claude/hooks/scripts/validate_translation.py --step N --project-dir . --check-pacs --check-sequence`
- [ ] P1 검증 결과 `valid: true` 확인 (T1-T9 + sequence 모두 통과)

---

## NEVER DO

- `current_step`을 2 이상 한 번에 증가 금지
- 산출물 없이 다음 단계 진행 금지
- "자동이니까 간략하게" 금지 — 절대 기준 1 위반
- `(hook)` exit code 2 차단 무시 금지
- `(team)` 단계에서 Teammate가 SOT를 직접 수정 금지 — Team Lead만 SOT 갱신
- 세션 복원 시 `active_team`을 빈 객체로 초기화 금지 — 기존 `completed_summaries` 보존 필수 (보존적 재개 프로토콜)
- Verification 기준 FAIL인 채로 다음 단계 진행 금지 — 최대 10회(ULW 활성 시 15회) 재시도 후 사용자 에스컬레이션
- Verification 기준을 "모두 PASS"로 허위 기록 금지 — 각 기준에 구체적 Evidence 필수
- Pre-mortem Protocol 생략하고 pACS 점수만 부여 금지 — 약점 인식이 점수의 전제
- pACS를 Verification Gate 없이 단독 수행 금지 — L1 통과가 L1.5의 전제
- pACS 점수를 전부 90+ 부여 금지 — Pre-mortem에서 식별한 약점과 점수 정합성 필수
- Review FAIL 상태에서 Translation 실행 금지 — Review PASS가 Translation의 전제
- Review 이슈 0건으로 PASS 처리 금지 — P1 검증이 자동 거부 (R5 체크)
- Reviewer pACS를 Generator pACS 참조 후 채점 금지 — 독립 채점이 필수
- 품질 게이트 FAIL 재시도 시 진단 없이 동일 접근법으로 재시도 금지 — Abductive Diagnosis 또는 Fast-Path 필수
- 진단 로그에 가설 1개만 기록 금지 — 최소 2개 가설 비교 (AD8)
- 진단에서 이전 진단과 동일 가설 3회 연속 선택 금지 — FP3 에스컬레이션 (I-3 연동)
