# Context Preservation System — 상세 명세

> 이 문서는 Context Preservation System의 내부 메커니즘 상세이다.
> CLAUDE.md에서 분리됨 — Hook 수정·디버깅·확장 시 참조.

## Claude의 활용 방법

- 세션 시작 시 `[CONTEXT RECOVERY]` 메시지가 표시되면, 안내된 경로의 파일을 **반드시 Read tool로 읽어** 이전 맥락을 복원한다.
- 스냅샷은 `.claude/context-snapshots/latest.md`에 저장된다.
- **Knowledge Archive**: `knowledge-index.jsonl`은 세션 간 축적되는 구조화된 인덱스이다. Stop hook과 SessionEnd/PreCompact 모두에서 기록된다. 각 엔트리에는 completion_summary(도구 성공/실패), git_summary(변경 상태), session_duration_entries(세션 길이), phase(세션 전체 단계), phase_flow(다단계 전환 흐름, 예: `research → implementation`), primary_language(주요 파일 확장자), error_patterns(Error Taxonomy 12패턴 분류 + resolution 매칭), success_patterns(Edit/Write→Bash 성공 시퀀스), tool_sequence(RLE 압축 도구 시퀀스), final_status(success/incomplete/error/unknown), tags(경로 기반 검색 태그)가 포함된다. Grep tool로 프로그래밍적 탐색이 가능하다 (RLM 패턴).
- **Resume Protocol**: 스냅샷에 포함된 "복원 지시" 섹션은 수정/참조 파일 목록과 세션 정보를 결정론적으로 제공한다. `[CONTEXT RECOVERY]` 출력에는 완료 상태(도구 성공/실패)와 Git 변경 상태도 표시된다. **동적 RLM 쿼리 힌트**: 수정 파일 경로에서 추출한 태그(`extract_path_tags()`)와 에러 정보를 기반으로 세션별 맞춤 Grep 쿼리 예시를 자동 생성한다.
- Hook 스크립트는 SOT(`state.yaml`)를 **읽기 전용**으로만 접근한다 (절대 기준 2 준수). SOT 파일 경로는 `sot_paths()` 헬퍼로 중앙 관리되며, `SOT_FILENAMES` 상수(`state.yaml`, `state.yml`, `state.json`)에서 파생된다.

## 절삭 상수 중앙화

`_context_lib.py`에 10개 절삭 상수를 중앙 정의:
- `EDIT_PREVIEW_CHARS=1000` — Edit preview는 5줄×1000자로 편집 의도·맥락을 보존
- `ERROR_RESULT_CHARS=3000` — 에러 메시지는 3000자로 stack trace 전체를 보존
- `MIN_OUTPUT_SIZE=100` — 최소 산출물 크기

## 다단계 전환 감지

`detect_phase_transitions()` 함수가 sliding window(20개 도구, 50% 오버랩)로 세션 내 단계 전환(research → planning → implementation 등)을 결정론적으로 감지한다. Knowledge Archive의 `phase_flow` 필드에 기록된다.

## 결정 품질 태그 정렬

스냅샷의 "주요 설계 결정" 섹션(IMMORTAL 우선순위)은 품질 태그 기반으로 정렬된다 — `[explicit]` > `[decision]` > `[rationale]` > `[intent]` 순으로 15개 슬롯을 채워, 일상적 의도 선언(`하겠습니다` 패턴)이 실제 설계 결정을 밀어내지 않는다.

## IMMORTAL-aware 압축

스냅샷 크기 초과 시 Phase 7 hard truncate에서 IMMORTAL 섹션을 우선 보존한다. 비-IMMORTAL 콘텐츠를 먼저 절삭하고, 극단적 경우에도 IMMORTAL 텍스트의 시작 부분을 보존한다.

**압축 감사 추적**: 각 압축 Phase가 제거한 문자 수를 HTML 주석(`<!-- compression-audit: ... -->`)으로 스냅샷 끝에 기록한다 (Phase 1~7 단계별 delta + 최종 크기).

## Error Taxonomy

도구 에러를 12개 패턴으로 분류:
`file_not_found`, `permission`, `syntax`, `timeout`, `dependency`, `edit_mismatch`, `type_error`, `value_error`, `connection`, `memory`, `git_error`, `command_not_found`

Knowledge Archive의 error_patterns 필드에 기록되어, "unknown" 분류를 ~30%로 감소시킨다. False positive 방지를 위해 negative lookahead, 한정어 매칭 등을 적용한다.

**Error→Resolution 매칭**: 에러 발생 후 5 entries 이내의 성공적 도구 호출을 file-aware 매칭으로 탐지하여 `resolution` 필드에 기록한다. `Grep "resolution" knowledge-index.jsonl`로 cross-session 탐색 가능.

## Quality Gate 상태 IMMORTAL 보존

`_extract_quality_gate_state()` 함수가 `pacs-logs/`, `review-logs/`, `verification-logs/`에서 최신 단계의 품질 게이트 결과를 추출하여 스냅샷에 IMMORTAL 섹션으로 보존한다.

## Phase Transition 스냅샷 헤더

다단계 전환이 감지된 세션에서는 스냅샷 헤더에 `Phase flow: research(12) → implementation(25)` 형식의 전환 흐름을 표시한다.

## Error→Resolution 자동 표면화

`restore_context.py`의 `_extract_recent_error_resolutions()` 함수가 Knowledge Archive의 최근 세션에서 error_patterns을 읽어 SessionStart 출력에 최대 3개의 에러→해결 패턴을 직접 표시한다.

## 런타임 디렉터리 자동 생성

`setup_init.py`의 `_check_runtime_dirs()` 함수가 SOT 파일 존재 시 `verification-logs/`, `pacs-logs/`, `review-logs/`, `autopilot-logs/`, `translations/`, `diagnosis-logs/` 6개 디렉터리를 자동 생성한다.

## 시스템 명령 필터링

스냅샷의 "현재 작업" 섹션에서 `/clear`, `/help` 등 시스템 명령을 자동 필터링하여 실제 사용자 작업 의도만 캡처한다.

## Autopilot 런타임 강화

Autopilot 활성 시 SessionStart가 실행 규칙을 컨텍스트에 주입하고, 스냅샷에 Autopilot 상태 섹션(IMMORTAL 우선순위)을 포함하며, Stop hook이 Decision Log 누락을 감지·보완한다.

## ULW 모드 감지·보존

`detect_ulw_mode()` 함수가 트랜스크립트에서 word-boundary 정규식으로 `ulw` 키워드를 감지한다. **암묵적 해제**: 새 세션(`source=startup`)에서는 이전 스냅샷에 ULW 상태가 있어도 규칙을 주입하지 않는다 — `clear`/`compact`/`resume` source만 ULW를 계승한다.

## Predictive Debugging

`aggregate_risk_scores()`가 Knowledge Archive의 error_patterns를 파일별로 집계하여 위험 점수를 산출한다 (가중치 × 감쇠). SessionStart 시 1회 실행되어 `risk-scores.json` 캐시를 생성하고, `predictive_debug_guard.py`가 매 Edit/Write마다 캐시를 읽어 임계값 초과 시 경고를 출력한다.

**Startup 트레이드오프**: SessionStart matcher가 `clear|compact|resume`이므로 최초 startup에서는 캐시 미생성 (ADR-036).

**Basename merge**: bare name과 relative path가 혼재할 때, 동일 basename 엔트리를 자동 병합하여 risk score 과소평가를 방지한다.

---

## Hook 설정 위치

모든 Hook은 **Project** (`.claude/settings.json`)에 통합 정의되어 있다. `git clone`만으로 Hook 인프라가 자동 적용된다.

- Stop → `context_guard.py --mode=stop` → `generate_context_summary.py`
- PostToolUse → `context_guard.py --mode=post-tool` → `update_work_log.py` (matcher: `Edit|Write|Bash|Task|NotebookEdit|TeamCreate|SendMessage|TaskCreate|TaskUpdate`)
- PreCompact → `context_guard.py --mode=pre-compact` → `save_context.py --trigger precompact`
- SessionStart → `context_guard.py --mode=restore` → `restore_context.py` (matcher: `clear|compact|resume`)
- **PreToolUse** → `block_destructive_commands.py` (matcher: `Bash`, 독립 실행 — exit code 2 보존)
- **PreToolUse** → `block_test_file_edit.py` (matcher: `Edit|Write`, 독립 실행 — `.tdd-guard` 토글)
- **PreToolUse** → `predictive_debug_guard.py` (matcher: `Edit|Write`, 독립 실행 — 경고 전용)
- **PostToolUse** → `output_secret_filter.py` (matcher: `Bash|Read`, 독립 실행 — 시크릿 탐지, exit 0 경고)
- **PostToolUse** → `security_sensitive_file_guard.py` (matcher: `Edit|Write`, 독립 실행 — 민감 파일 경고, exit 0)
- SessionEnd → `save_context.py --trigger sessionend` (matcher: `clear`)
- Setup (init) → `setup_init.py` — 인프라 건강 검증 (`claude --init`)
- Setup (maintenance) → `setup_maintenance.py` — 주기적 건강 검진 (`claude --maintenance`)

### Hook 설계 결정

> **`if test -f; then; fi` 패턴 통일**: 모든 Hook 명령이 `if test -f; then; fi` 패턴을 사용한다. 이전의 `|| true` 패턴(exit code 2 차단 신호를 삼키는 잠복 버그)을 제거.
> **PreToolUse Safety Hook의 독립 실행 근거**: `block_destructive_commands.py`와 `block_test_file_edit.py`는 컨텍스트 보존과는 다른 도메인이다. exit code 2 보존이 필수이므로, `context_guard.py`를 거치지 않고 직접 실행한다.
> **PostToolUse Security Hook의 독립 실행 근거 (ADR-050)**: `output_secret_filter.py`와 `security_sensitive_file_guard.py`는 보안 도메인이며, 컨텍스트 보존(`update_work_log.py`)과는 독립된 관심사다. transcript JSONL 직접 읽기, 세션 중복제거 등 자체 데이터 소스를 사용하므로 `context_guard.py` 디스패처를 거칠 필요 없이 직접 실행한다.

### D-7 의도적 중복 인스턴스

| # | 인스턴스 | 위치 A | 위치 B |
|---|---------|--------|--------|
| 1 | `REQUIRED_SCRIPTS` (20개) | `setup_init.py` | `setup_maintenance.py` |
| 2 | `RISK_THRESHOLD`/`MIN_SESSIONS` | `predictive_debug_guard.py` | `_context_lib.py` |
| 3 | `ERROR_TAXONOMY` 타입명 (12개) | `_classify_error_patterns()` | `_RISK_WEIGHTS` (13개) |
| 4 | ULW 감지 패턴 | `_gather_retry_history()` | `validate_retry_budget.py` + `restore_context.py` |
| 5 | 재시도 한도 상수 | `validate_retry_budget.py` | `_context_lib.py` + `restore_context.py` |
| 6 | `SOT_FILENAMES` 튜플 | `_context_lib.py` `SOT_FILENAMES` | `setup_init.py` + `query_workflow.py` `_SOT_FILENAMES` |

각 D-7 인스턴스는 코드에 cross-reference 주석이 있으며, 한쪽 변경 시 반드시 대응 쪽도 동기화해야 한다.

**자동 검증**: `setup_maintenance.py`의 `_check_doc_code_sync()`가 DC-1~DC-5를 결정론적으로 검증한다:
- DC-1: 재시도 한도 문서 ↔ 코드
- DC-2: Risk 상수 동기화
- DC-3: ULW 감지 패턴 동기화
- DC-4: Retry 한도 상수 동기화
- DC-5: SOT_FILENAMES 3자 동기화 (`_context_lib.py` ↔ `setup_init.py` ↔ `query_workflow.py`)
