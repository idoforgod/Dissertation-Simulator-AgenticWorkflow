# Dissertation Simulator 사용자 매뉴얼

> **이 문서의 범위**: AgenticWorkflow에서 태어난 자식 시스템 **Dissertation Simulator**의 사용법을 안내합니다.
> 부모 프레임워크(AgenticWorkflow) 자체의 사용법은 [`AGENTICWORKFLOW-USER-MANUAL.md`](AGENTICWORKFLOW-USER-MANUAL.md)를 참조하세요.

| 문서 | 대상 |
|------|------|
| **이 문서** (`DISSERTATION-SIMULATOR-USER-MANUAL.md`) | Dissertation Simulator 사용법 — 논문 연구 워크플로우 실행과 운영 |
| **`DISSERTATION-SIMULATOR-ARCHITECTURE-AND-PHILOSOPHY.md`** | 설계 철학, 아키텍처 조감도, 5계층 품질 체계 |
| **`AGENTICWORKFLOW-USER-MANUAL.md`** | 부모 프레임워크의 사용법 — 워크플로우 설계와 구현 도구 |

---

## 1. 시작하기

### 1.1 사전 준비

| 항목 | 필수 여부 | 설명 |
|------|----------|------|
| [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) | 필수 | `npm install -g @anthropic-ai/claude-code` |
| Python 3.10+ | 필수 | checklist_manager.py 및 인프라 스크립트 실행 |
| PyYAML | 필수 | `pip install pyyaml` (setup_init.py가 자동 검증) |

### 1.2 프로젝트 초기화

```bash
# Claude Code 실행
claude

# 논문 프로젝트 초기화
/thesis-init
```

초기화 시 다음이 생성됩니다:
- `thesis-output/[project-name]/session.json` — 논문 SOT
- `thesis-output/[project-name]/todo-checklist.md` — 211-step 체크리스트
- `thesis-output/[project-name]/research-synthesis.md` — 연구 합성 파일
- `thesis-output/[project-name]/wave-results/` — Wave별 산출물 디렉터리
- `thesis-output/[project-name]/checkpoints/` — 체크포인트 디렉터리

---

## 2. 전체 흐름

```
/thesis-init                          ← 프로젝트 초기화
    ↓
/thesis-start                         ← 워크플로우 시작
    ↓
Phase 0: 주제 탐색 + 연구 질문 확인
    ↓ HITL-0/1
Phase 1: 문헌 검토 (Wave 1→2→3→4→5, Gate로 품질 보장)
    ↓ HITL-2 (Context Reset Point 1)
/thesis-review-literature             ← 문헌 검토 결과 승인
    ↓
Phase 2: 연구 설계 (quantitative/qualitative/mixed 분기)
    ↓ HITL-3/4 (Context Reset Point 2)
/thesis-approve-design                ← 연구 설계 승인
    ↓
Phase 3: 논문 집필
    ↓ HITL-5/6/7 (Context Reset Point 3)
/thesis-review-draft                  ← 초고 리뷰
    ↓
Phase 4: 출판 전략
    ↓ HITL-8 (Context Reset Point 4)
/thesis-finalize                      ← 최종 확정
```

---

## 3. Slash Commands 완전 가이드

### 3.1 핵심 워크플로우 명령

| 명령 | 설명 | 사용 시점 |
|------|------|---------|
| `/thesis-init` | 새 논문 프로젝트 초기화 | 최초 1회 |
| `/thesis-start` | 워크플로우 시작 또는 계속 | SOT의 current_step에서 재개 |
| `/thesis-status` | 진행 상태 표시 (step, gate, HITL) | 언제든지 |
| `/thesis-resume` | 컨텍스트 리셋 후 워크플로우 재개 | `/clear` 또는 세션 만료 후 |
| `/thesis-checkpoint` | 체크포인트 저장 또는 복원 | 주요 마일스톤 전후 |

### 3.2 HITL 체크포인트 명령

| 명령 | HITL | 승인 대상 |
|------|------|---------|
| `/thesis-set-research-question` | HITL-1 | 연구 질문 확인·수정 |
| `/thesis-review-literature` | HITL-2 | 문헌 검토 결과 합성·승인 |
| `/thesis-set-research-type` | HITL-3 | 연구 유형 (quantitative/qualitative/mixed) |
| `/thesis-approve-design` | HITL-4 | 연구 설계 (방법론, 샘플링, 도구) |
| `/thesis-set-format` | HITL-5 | 논문 형식 (APA/Chicago/MLA, 5-chapter/3-paper) |
| `/thesis-approve-outline` | HITL-6 | 논문 개요 (챕터 구조, 논증 흐름) |
| `/thesis-review-draft` | HITL-7 | 논문 초고 검토 |
| `/thesis-finalize` | HITL-8 | 최종 확정 + 워크플로우 완료 |

### 3.3 품질·평가 명령

| 명령 | 설명 |
|------|------|
| `/thesis-gate` | Cross-Validation Gate 실행 또는 상태 확인 |
| `/thesis-wave-status` | Wave별 상세 상태 (에이전트 출력, claim 수, Gate 결과) |
| `/thesis-srcs` | SRCS 4축 품질 평가 실행 |
| `/thesis-check-plagiarism` | 표절 검사 실행 |
| `/thesis-fallback-log` | Fallback 이력 조회 (tier 전환, 사유, 품질 영향) |
| `/thesis-translate` | 특정 step의 한국어 번역 수동 트리거 (3-Layer 품질 검증 포함) |

### 3.4 시스템 명령

| 명령 | 설명 |
|------|------|
| `/self-improve` | KBSI (Knowledge-Based Self-Improvement) — 에러 분석 → 개선안 추출 → AGENTS.md 영구 반영 |
| `/predict-failures` | Predictive Debugging — 코드 구조 스캔 → 실패 예측 → 적대적 검증 → 사전 조치 |
| `/install` | Hook 인프라 검증 + 설치 상태 확인 |
| `/maintenance` | 시스템 건강 검진 + doc-code 동기화 확인 |

### 3.5 학습 모드 명령

| 명령 | 설명 |
|------|------|
| `/thesis-learn` | 학습 모드 진입 (8 Track 방법론 교육) |
| `/thesis-learn-quiz` | 학습 이해도 퀴즈 |
| `/thesis-learn-practice` | 실습 연습 |
| `/thesis-learn-progress` | 학습 진행률 표시 |

### 3.6 출판 명령

| 명령 | 설명 |
|------|------|
| `/thesis-journal-search` | 적합 학술지 검색 |
| `/thesis-format-manuscript` | 타겟 저널 스타일로 원고 포맷팅 |

---

## 4. Input Modes (진입 경로)

초기화 시 `--input-mode` 옵션으로 진입 경로를 선택합니다:

### Mode A (기본) — 연구 주제에서 시작

```bash
/thesis-init
# → 연구 주제 입력 → @topic-explorer가 연구 질문 생성 → HITL-1에서 승인
```

### Mode B — 연구 질문에서 시작

```bash
/thesis-init
# → 연구 질문 직접 입력 → 바로 Phase 1 (문헌 검토) 진입
```

### Mode C — 기존 문헌 리뷰에서 시작

```bash
/thesis-init
# → 기존 문헌 리뷰 파일 업로드 → @literature-analyzer가 분석 → Gap 식별
```

### Mode D — 학습 모드

```bash
/thesis-learn
# → 8 Track 방법론 교육 (문헌검색 → 통계 → 질적연구 → 혼합연구 → 윤리 → 글쓰기 → 출판 → 도구)
```

### Mode E-G — 고급 진입

- **E**: 선행 논문 업로드 → 분석 기반 시작
- **F**: 연구 제안서 업로드 → 설계부터 시작
- **G**: 커스텀 입력 + 사용자 해석

---

## 5. 컨텍스트 리셋과 복구

### 5.1 Context Reset Points

장시간 워크플로우에서 컨텍스트 윈도우 한계에 도달하면, HITL 체크포인트에서 안전하게 리셋합니다:

| Reset Point | 위치 | 복구 방법 |
|-------------|------|---------|
| CR-1 | HITL-2 (문헌 검토 후) | `/thesis-resume` → session.json + research-synthesis.md에서 복원 |
| CR-2 | HITL-4 (연구 설계 후) | `/thesis-resume` → 설계 결과 + SOT에서 복원 |
| CR-3 | HITL-6 (개요 승인 후) | `/thesis-resume` → 개요 + 이전 산출물에서 복원 |
| CR-4 | HITL-8 (최종 확정) | 워크플로우 완료 |

### 5.2 수동 체크포인트

```bash
# 체크포인트 저장
/thesis-checkpoint save pre-gate-2

# 체크포인트 복원
/thesis-checkpoint restore pre-gate-2
```

### 5.3 세션 만료 후 복구

```bash
# Claude Code 재실행 후
/thesis-resume
# → session.json + todo-checklist.md + research-synthesis.md에서 상태 복원
# → 마지막 완료 step에서 자동 재개
```

복원 시 Context Memory Quality Optimization (QO-1~5)이 자동으로 작동합니다:
- **QO-1**: 최근 Gate FAIL/WARN 사유가 IMMORTAL 섹션에 표면화 → 가이드된 수정
- **QO-2**: 지난 5개 step의 제목·워드카운트·섹션 구조 → 서사적 일관성 유지
- **QO-3**: 11개 scoring signal로 가장 관련 높은 과거 세션 3개 자동 검색
- **QO-4**: 다음 step의 output_path, min_bytes, tier, pCCS 모드 메타데이터 표면화

---

## 6. CLI 직접 사용

Slash Command 대신 Python CLI를 직접 호출할 수도 있습니다:

```bash
# 프로젝트 초기화
python .claude/hooks/scripts/checklist_manager.py \
  --init --project-dir thesis-output/my-thesis \
  --research-type mixed --input-mode A

# 진행 상태 확인
python .claude/hooks/scripts/checklist_manager.py \
  --status --project-dir thesis-output/my-thesis

# 스텝 전진
python .claude/hooks/scripts/checklist_manager.py \
  --advance --step 5 --project-dir thesis-output/my-thesis

# Gate 기록
python -c "
import sys; sys.path.insert(0, '.claude/hooks/scripts')
import checklist_manager as cm
cm.record_gate_result('thesis-output/my-thesis', 'gate-1', 'pass')
"

# HITL 기록
python .claude/hooks/scripts/checklist_manager.py \
  --record-hitl hitl-1 --project-dir thesis-output/my-thesis

# 체크포인트 저장/복원
python .claude/hooks/scripts/checklist_manager.py \
  --save-checkpoint --checkpoint pre-gate \
  --project-dir thesis-output/my-thesis

python .claude/hooks/scripts/checklist_manager.py \
  --restore-checkpoint --checkpoint pre-gate \
  --project-dir thesis-output/my-thesis

# SOT 검증
python .claude/hooks/scripts/checklist_manager.py \
  --validate --project-dir thesis-output/my-thesis

# 워크플로우 대시보드
python .claude/hooks/scripts/query_workflow.py \
  --dashboard --project-dir thesis-output/my-thesis

# 차단 요인 확인
python .claude/hooks/scripts/query_workflow.py \
  --blocked --project-dir thesis-output/my-thesis

# pCCS 이력 조회
python .claude/hooks/scripts/query_workflow.py \
  --pccs --project-dir thesis-output/my-thesis

# Step Execution Registry — 특정 step의 실행 파라미터 조회
python .claude/hooks/scripts/query_step.py \
  --step 45 --project-dir thesis-output/my-thesis --json

# 특정 에이전트에 할당된 step 목록
python .claude/hooks/scripts/query_step.py \
  --list-steps --agent literature-searcher

# 전체 에이전트 목록
python .claude/hooks/scripts/query_step.py --list-agents

# 통합 프롬프트 생성 (Step Consolidation)
python .claude/hooks/scripts/query_step.py \
  --consolidated-prompt --step 39 --topic "AI in Education" \
  --checklist thesis-output/my-thesis/todo-checklist.md --json

# 단일 Step 프롬프트 생성 (P1 결정론적 — H-8)
python .claude/hooks/scripts/query_step.py \
  --single-prompt --step 55 --topic "AI in Education" \
  --context "Gate 1 evaluation" --json

# 다음 실행 step 결정 (mid-consolidation restart 자동 감지)
python .claude/hooks/scripts/query_step.py \
  --next-step --project-dir thesis-output/my-thesis --json

# Invocation Plan 조회 (17개 Orchestrator 호출 계획)
python .claude/hooks/scripts/query_step.py \
  --invocation-plan --project-dir thesis-output/my-thesis --json

# 통합 그룹 원자적 전진
python .claude/hooks/scripts/checklist_manager.py \
  --advance-group --first-step 39 --last-step 42 \
  --output-path "wave-results/wave-1/step-039-to-042-literature-searcher.md" \
  --project-dir thesis-output/my-thesis

# 스킬 산출물 검증
python .claude/hooks/scripts/validate_skill_output.py \
  --skill-dir .claude/skills/my-skill/

# 전체 스킬 일괄 검증
python .claude/hooks/scripts/validate_skill_output.py \
  --skills-root .claude/skills/

# pCCS Pipeline 실행
python .claude/hooks/scripts/run_pccs_pipeline.py \
  --step-output thesis-output/my-thesis/wave-results/wave-1/literature-search.md \
  --project-dir thesis-output/my-thesis --step 40

# Step 산출물 검증 (VO-1~VO-7 — Hallucination Containment)
python .claude/hooks/scripts/verify_step_output.py \
  --step 42 --project-dir thesis-output/my-thesis

# Phase 2 step은 연구 유형 명시 필요
python .claude/hooks/scripts/verify_step_output.py \
  --step 125 --project-dir thesis-output/my-thesis --research-type quantitative

# Dialogue 루프 종료 판단 (P1 결정론적)
python .claude/hooks/scripts/determine_dialogue_outcome.py \
  --step 5 --round 2 --max-rounds 3 --project-dir thesis-output/my-thesis

# 통합 그룹 분할 (Consolidation Fallback)
python .claude/hooks/scripts/fallback_controller.py \
  --project-dir thesis-output/my-thesis --split-group --group-steps "39,40,41,42"
```

---

## 7. 산출물 구조

```
thesis-output/my-thesis/
├── session.json                  ← 논문 SOT
├── todo-checklist.md             ← 211-step 체크리스트
├── research-synthesis.md         ← 연구 합성 (3000-4000 단어)
├── wave-results/                 ← Wave별 산출물 (통합 모드)
│   ├── wave-1/                   ← 기초 문헌 검색 결과
│   │   ├── step-039-to-042-literature-searcher.md
│   │   ├── step-043-to-046-seminal-works-analyst.md
│   │   ├── step-047-to-050-trend-analyst.md
│   │   └── step-051-to-054-methodology-scanner.md
│   ├── wave-2/                   ← 심층 분석 결과
│   ├── wave-3/                   ← 비판적 분석 결과
│   ├── wave-4/                   ← 통합 합성 결과
│   └── wave-5/                   ← 품질 보증 결과
├── research-design/              ← 연구 설계 산출물
├── thesis-draft/                 ← 논문 초고
├── publication/                  ← 출판 전략 산출물
├── checkpoints/                  ← 체크포인트 스냅샷
├── verification-logs/            ← 검증 로그
├── pacs-logs/                    ← pACS 자기 평가 로그
├── pccs-logs/                    ← pCCS per-claim 신뢰도 로그
├── review-logs/                  ← L2 Adversarial Review 로그
├── dialogue-logs/                ← Adversarial Dialogue 반복 로그
├── diagnosis-logs/               ← Abductive Diagnosis 로그
├── failure-predictions/          ← Predictive Debugging 결과
│   └── index.jsonl               ← 실패 예측 SOT (append-only)
├── self-improvement/             ← KBSI 개선 로그
└── autopilot-logs/               ← Autopilot 결정 로그
```

---

## 8. 문제 해결

### Gate 실패

```bash
# 현재 차단 요인 확인
/thesis-status

# 상세 차단 요인
python .claude/hooks/scripts/query_workflow.py --blocked --project-dir thesis-output/my-thesis

# 이전 체크포인트로 복원 후 재시도
/thesis-checkpoint restore pre-gate-1
```

### Fallback 발생

```bash
# Fallback 이력 확인
/thesis-fallback-log

# Team → Sub-agent → Direct 강등 과정과 사유 확인
```

### SOT 손상

```bash
# 번역 진행률 확인
python .claude/hooks/scripts/checklist_manager.py \
  --translation-progress --project-dir thesis-output/my-thesis

# SOT 검증
python .claude/hooks/scripts/checklist_manager.py --validate --project-dir thesis-output/my-thesis

# 체크포인트에서 복원
python .claude/hooks/scripts/checklist_manager.py --restore-checkpoint --checkpoint [name] --project-dir thesis-output/my-thesis
```

---

## 부록: 학습 Track 목록

| Track | 주제 | 에이전트 |
|-------|------|---------|
| 1 | 문헌 검색과 데이터베이스 활용 | @methodology-tutor |
| 2 | 연구 설계 기초 | @methodology-tutor |
| 3 | 양적 연구 방법론 | @methodology-tutor |
| 4 | 질적 연구 방법론 | @methodology-tutor |
| 5 | 혼합 연구 방법론 | @methodology-tutor |
| 6 | 연구 윤리와 IRB | @methodology-tutor |
| 7 | 학술 글쓰기 | @methodology-tutor |
| 8 | 출판과 저널 전략 | @methodology-tutor |
