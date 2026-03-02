# Quality Gates & P1 Validation

> 이 문서는 4계층 품질 보장 아키텍처와 P1 할루시네이션 봉쇄의 상세 명세이다.
> CLAUDE.md에서 분리됨 — 품질 게이트 설계·디버깅·확장 시 참조.

## 4계층 품질 보장 아키텍처 (L0 → L1 → L1.5 → L2)

Orchestrator는 `current_step`을 순차적으로만 증가. 각 단계 완료 시 최대 4계층 검증을 통과해야 진행한다:

1. **L0 Anti-Skip Guard** (결정론적) — 산출물 파일 존재 + 최소 크기(100 bytes). Hook 계층의 `validate_step_output()` 함수가 수행.
2. **L1 Verification Gate** (의미론적) — 산출물이 `Verification` 기준을 100% 달성했는지 에이전트 자기 검증. 실패 시 해당 부분만 재실행(최대 10회). `verification-logs/step-N-verify.md`에 기록.
3. **L1.5 pACS Self-Rating** (신뢰도) — Pre-mortem Protocol 수행 후 F/C/L 3차원 채점. `pacs-logs/step-N-pacs.md`에 기록. RED(< 50) 시 재작업.
4. **[L2 Calibration]** (선택적) — 별도 `@verifier` 에이전트가 pACS 점수 교차 검증. 고위험 단계만.

> `Verification` 필드가 없는 단계는 Anti-Skip Guard만으로 진행 (하위 호환). 상세: `AGENTS.md §5.3`, `§5.4`

---

## P1 할루시네이션 봉쇄 (Hallucination Prevention)

반복적으로 100% 정확해야 하는 작업을 Python 코드로 강제한다.

### (1) KI 스키마 검증
`_validate_session_facts()`가 knowledge-index 쓰기 직전 RLM 필수 키(session_id, tags, final_status, diagnosis_patterns 등 11개) 존재를 보장 — 누락 시 안전 기본값 채움.

### (2) 부분 실패 격리
`archive_and_index_session()`에서 archive 파일 쓰기 실패가 knowledge-index 갱신을 차단하지 않음 — RLM 핵심 자산 보호.

### (3) SOT 쓰기 패턴 검증
`setup_init.py`의 `_check_sot_write_safety()`가 Hook 스크립트에서 SOT 파일명 + 쓰기 패턴 공존을 AST 함수 경계 기반으로 탐지 (Tier 1: 비-SOT 스크립트의 SOT 참조 차단, Tier 2: SOT-aware 스크립트의 함수별 쓰기 패턴 검사).

### (4) SOT 스키마 검증
`validate_sot_schema()`가 워크플로우 state.yaml의 구조적 무결성을 8항목으로 검증:
- **S1-S6**: current_step 타입·범위, outputs 타입·키 형식, 미래 단계 산출물 탐지, workflow_status 유효값, auto_approved_steps 정합성
- **S7**: pacs 5개 필드 검증 (S7a dimensions F/C/L 0-100, S7b current_step_score 0-100, S7c weak_dimension F/C/L, S7d history dict→{score, weak}, S7e pre_mortem_flag string)
- **S8**: active_team 5개 필드 검증 (S8a name string, S8b status partial|all_completed, S8c tasks_completed list, S8d tasks_pending list, S8e completed_summaries dict→dict)

SessionStart와 Stop hook 양쪽에서 실행.

### (5) Adversarial Review P1 검증
`validate_review_output()`이 리뷰 보고서의 구조적 무결성을 검증:
- R1: 파일 존재
- R2: 최소 크기
- R3: 필수 섹션 4개
- R4: PASS/FAIL 명시적 추출
- R5: 이슈 테이블 ≥ 1행

`parse_review_verdict()` — regex로 이슈 심각도 카운트 추출.
`calculate_pacs_delta()` — Generator-Reviewer pACS 차이(Delta ≥ 15 → 재조정).
`validate_review_sequence()` — Review PASS → Translation 순서를 파일 타임스탬프로 강제.
독립 실행 스크립트: `validate_review.py`.

### (6) Translation P1 검증
`validate_translation_output()`이 번역 산출물을 7항목으로 검증:
- T1: 파일 존재, T2: 최소 크기, T3: 영어 원본 존재, T4: .ko.md 확장자, T5: 비-공백, T6: 헤딩 수 ±20%, T7: 코드 블록 수 일치

`check_glossary_freshness()` — glossary 타임스탬프 신선도 (T8).
`verify_pacs_arithmetic()` — 모든 pACS 로그의 min() 산술 정확성 (T9 — 범용).
`validate_verification_log()` — 검증 로그 V1a-V1c.
`validate_translation.py`는 Review verdict=PASS를 필수 체크.
독립 실행 스크립트: `validate_translation.py`.

### (7) pACS P1 검증
`validate_pacs_output()`이 pACS 로그를 6항목으로 검증:
- PA1: 파일 존재, PA2: 최소 크기 50 bytes, PA3: 차원 점수 ≥ 3개(0-100 범위), PA4: Pre-mortem 섹션 존재, PA5: min() 산술 정확성, PA7: RED 차단(pACS < 50 → FAIL)
- PA6(선택): 점수-색상 영역 정합성

독립 실행 스크립트: `validate_pacs.py`.

### (8) L0 Anti-Skip Guard 코드 구현
`validate_step_output()` — L0 검증 3항목:
- L0a: SOT outputs.step-N 경로의 파일 존재
- L0b: 파일 크기 ≥ MIN_OUTPUT_SIZE(100 bytes)
- L0c: 비-공백 확인

`validate_pacs.py --check-l0`으로 pACS + L0 동시 검증 가능.

### (9) Predictive Debugging P1 검증
`validate_risk_scores()` — risk-scores.json 6항목:
- RS1: 필수 키, RS2: data_sessions 정수, RS3: risk_score 범위, RS4: error_count 산술 정합, RS5: resolution_rate 범위, RS6: top_risk_files 정렬+존재

### (10) Retry Budget P1 검증
`validate_retry_budget.py` — 재시도 예산 결정론적 판정:
- RB1: 카운터 파일 읽기, RB2: ULW 활성 감지, RB3: 예산 비교 (`retries_used < max_retries`)
- `max_retries`: ULW 활성 시 3, 비활성 시 2
- `--increment` 모드로 카운터 atomic write 증가

### (11) Abductive Diagnosis P1 검증
`validate_diagnosis_log()` — 진단 로그 10항목:
- AD1: 파일 존재, AD2: 최소 크기 100 bytes, AD3: Gate 필드 일치, AD4: 선택 가설 존재, AD5: 증거 ≥ 1개, AD6: Action Plan 존재, AD7: 순방향 참조 금지, AD8: 가설 ≥ 2개, AD9: 선택 가설 일관성, AD10: 이전 진단 참조(재시도 > 0)

`diagnose_failure_context()` — 사전 증거 수집 (retry_history, upstream_evidence, hypothesis_priority, fast_path, raw_evidence). Fast-Path(FP1-FP3)로 결정론적 단축.
독립 실행 스크립트: `diagnose_context.py`(사전 분석), `validate_diagnosis.py`(사후 검증).

### (12) Cross-Step Traceability P1 검증
`validate_cross_step_traceability()` — 교차 단계 추적성 5항목:
- CT1: trace 마커 존재, CT2: 참조 단계 산출물 존재, CT3: 섹션 ID 해결(Warning), CT4: 최소 밀도 ≥ 3, CT5: 순방향 참조 금지

독립 실행 스크립트: `validate_traceability.py`.

### (13) Domain Knowledge Structure P1 검증
`validate_domain_knowledge()` — domain-knowledge.yaml 7항목:
- DK1: 파일 존재+YAML 유효, DK2: metadata 필수 키, DK3: entities 구조, DK4: relations 참조 무결성, DK5: constraints 구조, DK6: 산출물 DKS 참조 해결, DK7: 제약 조건 비위반

독립 실행 스크립트: `validate_domain_knowledge.py`. 선택적 — 모든 워크플로우가 필요로 하지 않음.

### (14) Workflow.md DNA Inheritance P1 검증
`validate_workflow_md()` — 8항목:
- W1: 파일 존재, W2: 최소 크기 500 bytes, W3: `## Inherited DNA` 헤더, W4: Inherited Patterns 테이블 ≥ 3행, W5: Constitutional Principles 섹션, W6: CAP 참조, W7: CT Verification-Validator 정합성, W8: DKS Verification-Validator 정합성

독립 실행 스크립트: `validate_workflow.py`. workflow-generator 완료 후 수동 호출.
