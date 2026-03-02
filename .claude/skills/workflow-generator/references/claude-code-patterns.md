# Claude Code Implementation Patterns

workflow.md를 Claude Code에서 실행하기 위한 구현 패턴.

## 핵심 구성요소

### 1. Sub-agents

`.claude/agents/` 디렉터리에 `.md` 파일로 정의하는 전문 에이전트.
단일 세션 내에서 컨텍스트를 위임하여 독립적 작업 수행.

```markdown
# .claude/agents/researcher.md
---
name: researcher
description: 웹 검색 및 자료 조사 전문. 리서치 작업 시 자동 위임.
model: sonnet
tools: Read, Glob, Grep, WebSearch, WebFetch
maxTurns: 30
memory: project
---

당신은 리서치 전문가입니다.
주어진 주제에 대해 체계적으로 자료를 수집하고 요약합니다.

## 작업 원칙
- 모든 정보에 출처(URL) 필수
- 핵심 인사이트를 구조화된 형식으로 정리
- 수집 결과를 마크다운 파일로 저장
```

```markdown
# .claude/agents/writer.md
---
name: writer
description: 컨텐츠 작성 전문
model: opus
tools: Read, Write, Edit, Glob, Grep
skills:
  - writing-style
memory: project
---

당신은 전문 작가입니다.
리서치 자료를 기반으로 고품질 콘텐츠를 작성합니다.
```

```markdown
# .claude/agents/reviewer.md
---
name: reviewer
description: 품질 검토 및 피드백 생성. 코드/문서 변경 후 자동 리뷰.
model: sonnet
tools: Read, Glob, Grep
permissionMode: plan
---

당신은 엄격한 편집자입니다.
다음 기준으로 검토하세요:
- 정확성, 일관성, 완성도
- 출처 검증 여부
- 대상 독자 적합성
```

**Frontmatter 주요 필드:**

| 필드 | 설명 | 예시 |
|-----|------|------|
| `name` | 고유 식별자 | `researcher` |
| `description` | 자동 위임 트리거 설명 | `"리서치 작업 시 자동 위임"` |
| `model` | 사용 모델 | `opus`, `sonnet`, `haiku` |
| `tools` | 허용 도구 (쉼표 구분) | `Read, Write, Bash` |
| `disallowedTools` | 차단 도구 | `Write, Edit` |
| `permissionMode` | 권한 모드 | `default`, `plan`, `dontAsk` |
| `maxTurns` | 최대 턴 수 | `30` |
| `memory` | 영속 메모리 범위 | `user`, `project`, `local` |
| `skills` | 주입할 스킬 목록 | `[writing-style]` |
| `mcpServers` | 사용 가능 MCP 서버 | `[slack, github]` |
| `hooks` | 에이전트 스코프 훅 | (아래 Hooks 섹션 참조) |

**설계 원칙:**
- 단일 책임: 에이전트당 하나의 역할
- 명확한 입출력: Task 단위로 정의
- 도구 최소화: 필요한 도구만 할당
- 모델 적정 배치: 복잡도에 따라 opus/sonnet/haiku 선택

**모델 선택 프로토콜 (절대 기준 1 기반):**

> 모델 선택의 유일한 기준은 **해당 작업의 품질 요구 수준**이다. "비용이 싸서"가 아니라 "품질이 충분한가"로 판단한다.

| 모델 | 적합한 작업 | 품질 특성 |
|-----|-----------|----------|
| `opus` | 복잡한 분석, 연구, 작문 — 최고 품질이 필요한 핵심 작업 | 최고 수준 |
| `sonnet` | 수집, 스캐닝, 구조화 — 안정적 품질의 반복 작업 | 높은 수준 |
| `haiku` | 대시보드, 상태 확인, 단순 판단 — 복잡도가 낮은 보조 작업 | 충분한 수준 |

**모델 선택 판단 절차:**

1. 해당 작업의 **핵심 품질 요인**이 무엇인가? (정확성? 창의성? 분석 깊이? 패턴 인식?)
2. 해당 품질 요인에서 **모델 간 품질 차이가 유의미**한가?
   - **예** → 상위 모델 선택 (품질 차이가 존재하면 최고를 써야 함)
   - **아니오** → 하위 모델 허용 (탐색 결과의 품질은 모델 무관 — haiku 허용)
3. **확신이 없으면** → 상위 모델 선택 (절대 기준 1 — 품질 보장 원칙)

**구체적 예시:**

| 작업 | 품질 요인 | 모델 간 차이 | 선택 | 근거 |
|------|----------|-------------|------|------|
| 파일 탐색/디렉토리 구조 파악 | 탐색 정확도 | 무의미 | `haiku` | 탐색 결과는 모델 무관 |
| 리서치 결과 종합 분석 | 분석 깊이·뉘앙스 | 유의미 | `opus` | 분석 깊이가 품질의 핵심 |
| 코드 리뷰/품질 검증 | 패턴 인식 | 유의미 | `sonnet`+ | 구조적 문제 감지 능력 필요 |
| 데이터 포맷 변환 | 규칙 준수 | 무의미 | `haiku` | 결정론적 변환은 모델 무관 |
| 전문 콘텐츠 작성 | 창의성·정확성 | 유의미 | `opus` | 작문 품질이 최종 산출물 품질 |

---

### 2. Agent Teams (Swarm)

여러 독립 세션이 협업하는 팀 기반 병렬 작업 시스템.
Sub-agent와 달리 각 팀원이 완전히 독립된 컨텍스트를 가짐.

> **실험적 기능** — `settings.json`에서 활성화 필요

```json
// settings.json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

**아키텍처:**

```
┌──────────────────────────────────────────────────────┐
│                    Team Lead                          │
│  (TaskCreate → 할당 → SendMessage → 조율)              │
│  ★ SOT 쓰기 권한: state.yaml 갱신은 Team Lead만 수행    │
├──────────┬──────────┬────────────────────────────────┤
│ Teammate │ Teammate │ Teammate                       │
│@researcher│ @writer │ @data-processor                │
│(독립 세션) │(독립 세션)│ (독립 세션)                     │
│ 읽기 전용  │ 읽기 전용 │ 읽기 전용                       │
└──────────┴──────────┴────────────────────────────────┘
     │            │           │
     ├── Shared Task List ────┤  ← 작업 할당/추적 도구
     │  (~/.claude/tasks/)    │
     └── SOT (state.yaml) ───┘  ← 워크플로우 상태 (Team Lead만 쓰기)
```

**팀 생성 → 작업 → 종료 흐름:**

```markdown
## workflow.md 내 Agent Team 정의

### Team: content-pipeline
- **Members**:
  - `@researcher` (sonnet): 자료 수집
  - `@writer` (opus): 콘텐츠 작성
  - `@fact-checker` (opus): 사실 검증
- **Shared Tasks**: `~/.claude/tasks/content-pipeline/`
- **Coordination**: Team Lead가 TaskCreate로 할당, 완료 시 자동 통보
```

**워크플로우에서의 표기법:**

```markdown
### 2. (team) 병렬 리서치
- **Team**: `content-pipeline`
- **Tasks**:
  - `@researcher`: 웹 소스에서 최신 트렌드 수집
  - `@data-processor`: 기존 데이터 정리 및 통계 분석
- **Join**: 모든 팀원 완료 후 Step 3으로
```

**Sub-agent vs Agent Team — 품질 기준 선택:**

> 속도나 비용이 아니라, **어떤 구조가 최종 결과물의 품질을 가장 높이는가**로 선택한다.

**품질 판단 매트릭스 (5개 요인):**

| 품질 요인 | Sub-agent 우위 | Agent Team 우위 | 판단 질문 |
|----------|---------------|----------------|----------|
| **맥락 깊이** | 선행 단계 결과를 깊이 참조해야 할 때 | 각 작업이 독립적 전문성을 요구할 때 | "이전 단계의 뉘앙스를 잃으면 품질이 떨어지는가?" |
| **교차 검증** | 단일 관점이 일관성을 보장할 때 | 다관점 분석이 편향을 제거할 때 | "한 사람의 분석으로 충분한가, 복수 전문가 의견이 필요한가?" |
| **산출물 일관성** | 문체/톤의 통일이 중요할 때 | 각 산출물이 독립적으로 완결될 때 | "산출물이 합쳐져야 하는가, 각각 독립적인가?" |
| **에러 격리** | 전체 맥락에서 에러를 잡아야 할 때 | 개별 작업 실패가 다른 작업에 영향 없어야 할 때 | "하나가 실패하면 전체를 재시작해야 하는가?" |
| **정보 전달 손실** | 파일 전달 시 뉘앙스 유실 위험이 클 때 | 구조화된 데이터만 전달해도 충분할 때 | "전달 파일에 담기지 않는 암묵적 맥락이 있는가?" |

**판단 규칙:**
1. 5개 요인 중 Sub-agent 우위가 3개 이상이면 → **Sub-agent**
2. Agent Team 우위가 3개 이상이면 → **Agent Team**
3. 동점이면 → **맥락 깊이** 요인이 tiebreaker (맥락 손실은 복구 불가능)
4. 확신이 없으면 → **Sub-agent** (안전한 기본값 — 맥락 보존이 품질의 바닥선)

**Agent Team이 품질을 높이는 경우:**
- 서로 다른 전문 영역을 각각 최고 수준으로 깊이 처리해야 할 때
- 다관점 분석/교차 검증으로 단일 에이전트보다 풍부한 결과를 얻을 수 있을 때
- 각 전문가가 독립 컨텍스트에서 100% 집중해야 품질이 나올 때

**Sub-agent가 품질을 높이는 경우:**
- 하나의 전문가가 깊은 맥락을 유지하며 일관되게 처리해야 할 때
- 단계 간 맥락 전달의 정확성이 결과 품질의 핵심일 때
- 순차적 의존성이 강해 앞 단계의 품질이 뒤 단계에 직결될 때

**Teammate 산출물 품질 요건:**

> Agent Team 사용 시, 컨텍스트 격리로 인한 정보 단절을 방지하기 위해 각 Teammate의 산출물 파일은 반드시 다음 구조를 포함한다.

```markdown
# [산출물 제목]

## 핵심 결과 (Main Output)
[작업 결과 본문 — 절대 기준 1: 완전한 품질, 축약 금지]

## 판단 근거 (Decision Rationale)
- 불확실성이 있는 항목: [명시적 표기]
- 제외한 정보와 제외 이유: [왜 포함하지 않았는가]
- 데이터의 유효 범위/제약: [시간 범위, 소스 한계 등]

## 교차 참조 단서 (Cross-Reference Cues)
- 다른 Teammate가 알아야 할 맥락: [의존성 정보]
- 후속 단계에 영향을 미치는 조건: [전제조건, 주의사항]
```

이 요건은 **파일 기반 전달의 뉘앙스 유실 문제**를 해결한다. 구조화된 사실뿐 아니라 판단의 맥락까지 전달하여, 독립 컨텍스트에서도 품질 저하를 방지한다.

**Team 생명주기 패턴:**

> 기본 권장은 **Step-scoped Team** (단계별 팀 생성·소멸). SOT 정합성과 에러 격리를 보장한다.

| 패턴 | 설명 | SOT 정합성 | 에러 격리 | 사용 조건 |
|------|------|-----------|----------|----------|
| **Step-scoped** (기본) | 워크플로우 단계 시작 시 TeamCreate, 완료 시 TeamDelete | 간단 (단계 전환 시 SOT 갱신) | 높음 (단계 실패가 전파 안 됨) | 대부분의 경우 |
| **Multi-step** | 여러 단계에 걸쳐 Team 유지 | 복잡 (중간 상태 관리 필요) | 낮음 (전파 위험) | 팀원 간 교차 참조가 품질의 핵심일 때만 |

```markdown
## Step-scoped Team 흐름

### N. (team) 병렬 리서치
- TeamCreate("research-pipeline") → SOT active_team 기록
- Task 할당 → Teammate 실행 → 산출물 생성
- 모든 Task 완료 → 산출물 검증 (Anti-Skip Guard)
- SOT outputs 기록 + current_step +1
- TeamDelete → SOT active_team 제거, completed_teams에 이동
```

> **참조**: 에이전트에 컨텍스트를 전달하는 3가지 패턴(Full Delegation, Filtered Delegation, Recursive Decomposition)은 `references/context-injection-patterns.md`에서 상세히 다룬다.

#### Dense Checkpoint Pattern (DCP)

`(team)` 단계에서 Teammate가 전체 Task 완료 후에야 Team Lead가 검증하는 기본 구조는, 초반 방향 오류 시 전체 재작업을 야기한다. DCP는 중간 체크포인트(CP)를 삽입하여 조기에 방향 오류를 감지한다.

**기존 인프라만 사용**: `TaskCreate` + `SendMessage` 프리미티브. 신규 Hook/스크립트 불필요.

**적용 기준:**

| 조건 | 패턴 |
|------|------|
| Task 예상 턴 수 ≤ 10 | `standard` (기존 방식) |
| Task 예상 턴 수 > 10 | `dense` (CP-1/2/3) |
| Task에 방향 결정 포인트 존재 | `dense` 권장 |
| Task 실패 시 재작업 비용이 큼 | `dense` 강력 권장 |

**체크포인트 구조 (최대 3개):**

| CP | 역할 | 산출물 |
|----|------|--------|
| CP-1 | Discovery/Setup — 방향 설정 | 대상 목록, 데이터 소스, 방법론 보고 |
| CP-2 | Collection/Draft — 중간 산출물 | 수집 데이터 요약, 초안, 갭 식별 |
| CP-3 | Final — 최종 산출물 | 완성된 분석 + pACS 자기 평가 |

**TaskCreate Description에 CP 프로토콜 임베드:**

```markdown
### Checkpoint Protocol (Dense Checkpoint Pattern)
You MUST report at each checkpoint BEFORE proceeding.
Wait for Team Lead acknowledgment before continuing.

**CP-1: [Phase Name]**
- [What to do]
- Report via SendMessage: [what to report]
- STOP and wait for Team Lead response

**CP-2: [Phase Name]** (after CP-1 approval)
- [What to do]
- Report via SendMessage: [what to report]
- STOP and wait for Team Lead response

**CP-3: [Phase Name]** (after CP-2 approval)
- [Final work + output]
- SendMessage: final report + pACS self-rating
- TaskUpdate(completed)
```

**SOT 영향**: 없음. `active_team` 스키마 변경 없음. CP는 `SendMessage` 기반 임시 조율이며 SOT에 기록하지 않는다. `completed_summaries`의 `summary` 필드에 CP 이력을 자연어로 포함 가능 (선택적).

---

### 3. Hooks

워크플로우 라이프사이클의 특정 시점에 자동으로 실행되는 결정론적 자동화.
코드 포맷팅, 품질 검증, 보안 게이트 등에 활용.

#### 3-1. Setup Hooks (인프라 검증)

세션 시작 **전에** 실행되는 결정론적 인프라 검증 Hook.
`--init` 또는 `--maintenance` CLI 플래그로 트리거되며, 세션 컨텍스트에 접근하지 않는다.

> **Quality Impact Path (절대 기준 1)**:
> Infrastructure validation → Silent Failure prevention →
> Context Preservation integrity → Session recovery accuracy →
> Infrastructure floor for workflow output quality

**3-Level Progressive Execution (계층적 실행 모델):**

| 레벨 | CLI 명령 | 실행 내용 | 용도 |
|------|---------|----------|------|
| **Level 1** — Deterministic Only | `claude --init` | Setup Hook 스크립트만 실행 (Python) | CI/CD, 자동 검증 |
| **Level 2** — Deterministic + Agentic | `claude --init "/install"` | Setup Hook → 에이전트가 로그 분석·수정 | 문제 해결 |
| **Level 3** — Interactive | `claude` (일반 세션) | Setup + 전체 세션 | 일상 작업 |

**Setup Hook 설정 형식:**

```json
// .claude/settings.json (Project — 프로젝트별 인프라 검증)
{
  "hooks": {
    "Setup": [
      {
        "matcher": "init",
        "hooks": [{
          "type": "command",
          "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/scripts/setup_init.py",
          "timeout": 30
        }]
      },
      {
        "matcher": "maintenance",
        "hooks": [{
          "type": "command",
          "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/scripts/setup_maintenance.py",
          "timeout": 30
        }]
      }
    ]
  }
}
```

**hookSpecificOutput 프로토콜:**

Setup Hook의 stdout JSON 출력 형식. Claude Code가 파싱하여 세션 시작 시 컨텍스트에 주입한다:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "Setup",
    "additionalContext": "Infrastructure validation: 10/12 passed (1 critical, 1 warning)"
  }
}
```

**Exit Code 규칙 (일반 Hook과 동일):**

| 코드 | 동작 | Setup Hook에서의 의미 |
|------|------|---------------------|
| `0` | 성공 | 인프라 정상 — 세션 시작 허용 |
| `2` | 차단 | Critical 문제 감지 — 세션 시작 전 수정 필요 |
| 기타 | 논블로킹 에러 | Hook 자체 오류 (세션은 시작) |

**워크플로우에서의 적용 기준:**

| 포함 조건 | 설명 |
|----------|------|
| Hook 스크립트가 3개 이상 | 스크립트 구문 오류가 Silent Failure를 유발 가능 |
| 외부 의존성 필요 (PyYAML 등) | 런타임에 의존성 누락 시 기능 저하 |
| 런타임 디렉터리 필요 | Context Preservation 등 런타임 인프라 사전 생성 |
| CI/CD 파이프라인 통합 | `--init-only`로 headless 검증 가능 |

| 제외 조건 | 설명 |
|----------|------|
| Hook 없는 단순 워크플로우 | 검증 대상이 없음 |
| 외부 의존성 없음 | 환경 검증 불필요 |

**SOT 비접근 원칙:**

Setup Hook은 SOT(`state.yaml`)에 **접근하지 않는다**.
Setup은 인프라 계층이고, SOT는 워크플로우 상태 계층이다.
인프라 검증은 워크플로우 실행보다 하위 계층에서 작동한다.

**context_guard.py 우회 근거:**

Setup Hook은 Project 설정(`.claude/settings.json`)에서 직접 실행된다.
Global 디스패처(`context_guard.py`)를 거치지 않는 이유:
1. Setup은 프로젝트 고유 인프라 검증 — Global 관심사가 아님
2. 세션 시작 **전**에 실행 — 세션 내 이벤트 라우팅과 무관
3. `--init`/`--maintenance` 트리거는 SessionStart/Stop Hook과 독립

**Slash Command 연동 (Level 2):**

Setup Hook의 로그 파일을 분석하는 Slash Command:

| Slash Command | 트리거 | 분석 대상 |
|--------------|--------|----------|
| `/install` | `claude --init "/install"` | `setup.init.log` — 문제 진단·수정 |
| `/maintenance` | `claude --maintenance "/maintenance"` | `setup.maintenance.log` — 건강 검진·정리 |

**설정 위치:**

| 위치 | 범위 | 공유 가능 |
|------|------|----------|
| `~/.claude/settings.json` | 전역 (모든 프로젝트) | 아니오 |
| `.claude/settings.json` | 프로젝트 | 예 (커밋 가능) |
| `.claude/settings.local.json` | 프로젝트 (로컬) | 아니오 |
| Agent frontmatter `hooks:` | 에이전트 스코프 | 예 |

**주요 Hook 이벤트:**

| 이벤트 | 발생 시점 | 차단 가능 | 워크플로우 용도 |
|--------|---------|----------|-------------|
| `Setup` | **세션 시작 전** (`--init`/`--maintenance`) | 예 (exit 2) | 인프라 검증, 건강 검진 (§3-1 상세) |
| `SessionStart` | 세션 시작/재개 | 아니오 | 컨텍스트 복원, 환경변수 설정 |
| `PreToolUse` | 도구 실행 전 | 예 | 위험 명령 차단, 입력 수정 |
| `PostToolUse` | 도구 실행 후 | 아니오 | 자동 포맷팅, 로그 기록 |
| `Stop` | Claude 응답 완료 | 예 | 컨텍스트 저장, 요약 생성 |
| `SessionEnd` | 세션 종료 (`/clear`) | 아니오 | 전체 스냅샷 저장, Knowledge Archive |
| `UserPromptSubmit` | 사용자 입력 후 | 예 | 입력 검증, 전처리 |
| `SubagentStart` | 서브에이전트 생성 | 아니오 | 환경 준비 |
| `SubagentStop` | 서브에이전트 종료 | 예 | 결과 검증 |
| `TeammateIdle` | 팀원 대기 전환 | 예 | 추가 작업 할당 |
| `TaskCompleted` | 태스크 완료 | 예 | 품질 게이트 (exit 2로 차단) |
| `PreCompact` | 컨텍스트 압축 전 | 아니오 | 중요 상태 보존 |

**Hook 타입:**

```json
// Type 1: Command — 셸 스크립트 실행
{
  "type": "command",
  "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/scripts/validate.py",
  "timeout": 30
}

// Type 2: Prompt — LLM 단일턴 판단
{
  "type": "prompt",
  "prompt": "이 변경이 기존 API 호환성을 깨뜨리는지 평가하세요. $ARGUMENTS",
  "model": "haiku"
}

// Type 3: Agent — 서브에이전트 기반 검증 (최대 50턴)
{
  "type": "agent",
  "prompt": "테스트 스위트를 실행하고 결과를 검증하세요. $ARGUMENTS",
  "timeout": 120
}
```

**워크플로우 적용 예시:**

```json
// .claude/settings.json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | xargs prettier --write 2>/dev/null || true",
            "statusMessage": "자동 포맷팅 중..."
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/scripts/block-destructive.sh && bash \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/scripts/block-destructive.sh || true"
          }
        ]
      }
    ],
    "TaskCompleted": [
      {
        "hooks": [
          {
            "type": "agent",
            "prompt": "완료된 태스크의 산출물 품질을 검증하세요. 기준 미달 시 거부하세요.",
            "timeout": 60
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "test -f \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/scripts/restore_context.py && python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/scripts/restore_context.py || true"
          }
        ]
      }
    ]
  }
}
```

**Exit Code 규칙:**

| 코드 | 동작 | 사용 시점 |
|------|------|---------|
| `0` | 허용 (JSON 출력 파싱) | 정상 통과 |
| `2` | 차단 (stderr → Claude에 피드백) | 위험 행동 방지, 품질 미달 |
| 기타 | 논블로킹 에러 (로그만) | 디버그 정보 |

**에이전트 내장 Hook (frontmatter):**

```markdown
---
name: db-reader
description: 읽기 전용 DB 쿼리 실행
tools: Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-readonly-query.sh"
---
```

---

### 4. Slash Commands

사용자 인터랙션 및 워크플로우 제어.
`.claude/commands/` 디렉터리에 `.md` 파일로 정의.

```markdown
# .claude/commands/start-workflow.md
---
description: "워크플로우 실행 시작"
---

workflow.md에서 $ARGUMENTS 워크플로우를 읽고
순차적으로 각 단계를 실행합니다.
```

```markdown
# .claude/commands/review-output.md
---
description: "산출물 검토 및 승인/반려"
---

현재 단계의 산출물을 표시하고 사용자의 승인/반려를 대기합니다.
- 승인 시: 다음 단계로 자동 진행
- 반려 시: 피드백을 에이전트에 전달하여 재작업
```

**Command 파라미터 전달:**

Slash Command는 `$ARGUMENTS`로 사용자 입력을 받을 수 있다:

```markdown
# .claude/commands/select-topic.md
---
description: "주제 선택 후 워크플로우 진행"
---

선택된 주제 번호: $ARGUMENTS

이 주제를 기반으로 워크플로우의 다음 단계를 진행합니다.
- state.yaml의 selected_topic 필드를 업데이트
- 해당 주제에 맞는 @deep-researcher에게 리서치 위임
```

---

### 4-1. AskUserQuestion (사용자 질문)

워크플로우 실행 중 사용자에게 구조화된 질문을 프로그래밍적으로 전달하는 도구.
Slash Command가 사용자 개입점을 "정의"하는 것이라면, AskUserQuestion은 에이전트가 "능동적으로" 사용자에게 질문하는 도구이다.

> **P4 규칙 적용**: 최대 4개 질문, 각 질문에 2-4개 선택지. 모호함이 없으면 질문 없이 진행.

**워크플로우 적용 예시:**

```markdown
### 1. (research) 요구사항 수집
- **Agent**: Orchestrator (직접 수행)
- **Tool**: AskUserQuestion
- **Strategy**: 반복적 질문으로 요구사항 구체화

#### 질문 설계:

**Round 1: 목적 파악**
1. "이 워크플로우의 주요 목적은 무엇입니까?"
   - (a) 신규 콘텐츠 생성
   - (b) 기존 콘텐츠 리팩토링
   - (c) 데이터 분석 및 보고서 생성

2. "대상 독자는 누구입니까?"
   - (a) 기술 전문가
   - (b) 비즈니스 의사결정권자
   - (c) 일반 사용자

**Round 2: 제약조건 파악** (Round 1 결과에 따라 동적 질문)
3. "우선순위가 높은 품질 기준은?"
   - (a) 정확성 (출처 검증 필수)
   - (b) 가독성 (쉬운 표현 우선)
   - (c) 포괄성 (모든 측면 커버)

- **Output**: `requirements.md` (구조화된 요구사항 문서)
- **SOT Update**: state.yaml에 수집된 요구사항 요약 기록
```

**Case 1 (idea-only) 워크플로우에서의 활용:**

사용자가 아이디어만 제공하고 구체적 요구사항이 없는 경우, AskUserQuestion을 Research Phase의 핵심 도구로 사용한다:

```markdown
### Research Phase — 요구사항 구체화
1. AskUserQuestion으로 핵심 방향 2-3개 질문 (P4 규칙 준수)
2. 응답 기반으로 @researcher가 관련 자료 수집
3. 수집 결과를 바탕으로 AskUserQuestion 2차 질문 (옵션 제시)
4. 최종 요구사항 문서 생성 → Planning Phase로 전달
```

**Slash Command vs AskUserQuestion:**

| 특성 | Slash Command | AskUserQuestion |
|------|-------------|-----------------|
| **트리거** | 사용자가 직접 실행 | 에이전트가 능동적으로 호출 |
| **정의 위치** | `.claude/commands/*.md` | 워크플로우 단계 내 |
| **용도** | 검토/승인/선택 (사전 정의된 개입점) | 요구사항 수집/옵션 선택 (동적 질문) |
| **적합한 Phase** | Planning (검토), Implementation (승인) | Research (요구사항 수집), Planning (옵션 선택) |
| **P4 규칙** | 해당 없음 (사용자 주도) | 적용 (최대 4질문, 2-4선택지) |
| **상태 관리** | 사용자 입력을 SOT에 반영 | 사용자 입력을 SOT에 반영 |

---

### 5. Skills 연동

재사용 가능한 지식/로직 패키지. 두 가지 실행 컨텍스트를 제공한다.

#### Inline Skill (기본)

Skill 내용이 메인 대화에 직접 주입된다. 대화 이력에 접근 가능.

```markdown
# workflow.md 내 inline skill 참조

### 5. 글 작성
- **Agent**: `@writer`
- **Skills**: `[writing-style]`, `[seo-optimization]`
- **Task**: 개요를 기반으로 최종 글 작성
```

- **적합**: 가이드라인, 대화형 워크플로우, 도메인 전문성 주입
- **SOT**: 메인 대화 컨텍스트에서 직접 접근

#### Forked Skill (`context: fork`)

Skill 내용이 **별도 sub-agent의 task prompt**가 된다. 격리된 컨텍스트에서 실행.

```yaml
# SKILL.md frontmatter
---
name: code-analyzer
description: Analyzes codebase structure and produces reports.
context: fork
agent: general-purpose    # Explore | Plan | general-purpose | <custom-agent>
---
```

- **적합**: 독립 분석, 대량 처리, 코드베이스 탐색, 파일 변환
- **대화 이력**: 없음 (격리)
- **SOT 접근**: 간접 — `!`command`` 전처리로 SOT 상태 주입

**Agent 타입 선택:**

| Agent 타입 | 모델 | 도구 | 용도 |
|-----------|------|------|------|
| `Explore` | Haiku | 읽기 전용 | 파일 탐색, 코드 검색 |
| `Plan` | 상속 | 읽기 전용 | 아키텍처 연구, 구현 계획 |
| `general-purpose` | 상속 | 전체 | 다단계 작업, 파일 생성 |
| 커스텀 에이전트 | 설정 따름 | 설정 따름 | `.claude/agents/`에 정의된 특화 역할 |

#### Fork + SOT 통합 패턴

Forked skill은 SOT를 직접 수정할 수 없다. 데이터 정합성을 위해:

1. **전처리로 SOT 주입**: Skill 내용에서 `!`cat state.yaml`` 구문으로 SOT 스냅샷 주입
2. **파일로 출력**: Fork가 산출물을 파일로 저장 → Orchestrator가 SOT `outputs`에 경로 기록
3. **SOT 쓰기 금지**: Fork에서 SOT 직접 수정은 절대 금지 (절대 기준 2)

#### Skill Hot-Reload

`~/.claude/skills/` 또는 `.claude/skills/`에서 스킬 파일 수정 시 **세션 재시작 없이 즉시 반영**. Sub-agent(`.claude/agents/`)는 `/agents` 명령 또는 세션 재시작 필요.

**Inline vs Fork 선택 기준:**

| 기준 | Inline | Fork |
|------|--------|------|
| 사용자 대화 필요 (Q&A, 확인) | ✅ | ❌ |
| 대화 컨텍스트에서 작업 (진행 중인 글, 토론) | ✅ | ❌ |
| 독립적 분석/변환 작업 | ❌ | ✅ |
| 실행 상세가 메인 대화를 어지럽힘 | ❌ | ✅ |
| SOT 상태 접근 | 직접 | 간접 (`!`cmd`` 전처리) |

### 6. MCP Server 연동

외부 서비스 통합. `.claude/settings.json` 또는 `.mcp.json`에 정의.

```json
// .mcp.json
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "@notionhq/mcp-server"],
      "env": { "NOTION_TOKEN": "${NOTION_TOKEN}" }
    },
    "slack": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-slack"],
      "env": { "SLACK_TOKEN": "${SLACK_TOKEN}" }
    }
  }
}
```

---

## 워크플로우 실행 패턴

### Pattern 1: Sequential Pipeline (Sub-agent)

단계가 순차적으로 실행되는 기본 패턴.

```
@agent-1 → @agent-2 → (human) → @agent-3 → @agent-4
```

**품질 근거:** 단일 전문가의 깊은 맥락 유지가 결과 일관성·정확도를 높임

### Pattern 2: Parallel Branches (Agent Team)

독립적인 단계가 병렬 실행.

```
               ┌→ @teammate-a ─┐
(team-lead) ──┤                ├→ (human) → @agent-merge
               └→ @teammate-b ─┘
```

**품질 근거:** 각 전문가의 독립 집중 + 다관점 결합이 단일 에이전트보다 풍부한 품질 달성

### Pattern 3: Conditional Flow

조건에 따라 분기.

```
@agent-1 → Condition? ─┬→ Path A → @agent-3
                        └→ Path B → @agent-3
```

### Pattern 4: Hook-gated Pipeline

자동 검증 게이트가 포함된 파이프라인.

```
@agent-1 → [Hook: 포맷 검증] → @agent-2 → [Hook: 품질 검증] → (human)
                 ↓ fail                          ↓ fail
            자동 재시도                      Claude에 피드백
```

**적합한 경우:** 코드 품질, 보안 검증, 산출물 표준 준수가 중요할 때

### Pattern 5: Team + Hook 결합

팀 작업에 품질 게이트를 결합한 고급 패턴.

```
(team-lead)
  ├→ @researcher [TaskCompleted hook: 출처 검증]
  ├→ @writer [TaskCompleted hook: 품질 검증]
  └→ @fact-checker [SubagentStop hook: 결과 병합]
       ↓ all complete
  (human) → @editor → 최종본
```

---

## Human-in-the-Loop 패턴

### 검토 후 진행

```markdown
### 3. (human) 검토 및 승인
- **Pause**: 자동 일시정지
- **Display**: 이전 단계 결과물 표시
- **Input**: 승인/반려/수정요청
- **Resume**: `/approve` 또는 `/request-revision "피드백"`
```

### 선택형 입력

```markdown
### 3. (human) 옵션 선택
- **Display**: 옵션 목록 표시
- **Input**: 번호 또는 항목 선택
- **Command**: `/select 1,3,5`
```

### Hook 기반 자동 품질 게이트

사람 개입 없이 자동으로 품질을 검증하는 패턴.

```markdown
### 3. (hook) 자동 품질 검증
- **Event**: `TaskCompleted`
- **Type**: `agent`
- **Check**: 산출물이 품질 기준 충족 여부
- **Pass**: 다음 단계로 자동 진행
- **Fail**: exit 2 → 에이전트에 피드백 전달, 재작업
```

## Autopilot Execution Pattern

Autopilot 모드에서 Orchestrator의 `(human)` 단계 처리 패턴.

### Auto-Approve with Full Execution

```markdown
### 3. (human) 인사이트 검토 및 선정
- **Autopilot 동작**:
  1. 이전 단계의 산출물을 **완전히** 생성 (축약 금지)
  2. 산출물을 검토하여 품질 극대화 기본값 결정 (절대 기준 1)
  3. 결정을 `autopilot-logs/step-3-decision.md`에 기록
  4. SOT 갱신: `auto_approved_steps`에 3 추가
  5. 다음 단계로 진행
- **Interactive 동작 (기본값)**:
  - 위와 동일하되, 3단계에서 사용자 입력 대기
```

### Anti-Skip Invariant

```
FOR step IN workflow.steps:
  EXECUTE(step)                    # 모든 단계 실행 — 생략 금지
  ASSERT output_exists(step)       # 산출물 존재 확인
  ASSERT output_not_empty(step)    # 빈 산출물 금지
  IF step.is_human AND autopilot.enabled:
    auto_approve(step)             # 자동 승인
    log_decision(step)             # 결정 로그
  UPDATE_SOT(step)                 # SOT 갱신
```

### Anti-Skip Execution Protocol (구체적 실행 의사코드)

```python
MAX_VERIFICATION_RETRIES = 2

def execute_workflow_step(step, sot):
    """Orchestrator가 각 워크플로우 단계를 실행하는 프로토콜.

    절대 기준 1: 모든 산출물은 완전한 품질로 생성.
    절대 기준 2: SOT만이 상태의 단일 진실 원천.
    Verification Protocol: 기능적 목표 100% 달성 확인 (AGENTS.md §5.3).
    """
    # 1. Pre-validation (이전 단계 산출물 검증)
    if step.number > 1:
        prev_key = f"step-{step.number - 1}"
        prev_path = sot.outputs.get(prev_key)
        assert prev_path, f"Step {step.number - 1} output not in SOT"
        assert file_exists(prev_path), f"Step {step.number - 1} output missing"
        assert file_size(prev_path) >= 100, f"Step {step.number - 1} output too small (< 100 bytes)"

    # 1b. Read Verification Criteria BEFORE execution
    verification_criteria = step.get_verification_criteria()  # None if absent

    # 2. Execute step FULLY (Anti-Abbreviation Rule)
    output = step.execute()  # 완전 실행, 축약 금지

    # 3. Save output to disk
    write_file(step.output_path, output)

    # 4. Handle (human) checkpoint
    if step.is_human and sot.autopilot.enabled:
        decision = auto_approve_with_quality_default(step, output)
        write_decision_log(step.number, decision)
        # Decision Log: autopilot-logs/step-N-decision.md
        sot.autopilot.auto_approved_steps.append(step.number)

    # 5. Handle (hook) — NEVER override exit code 2
    if step.is_hook and result.exit_code == 2:
        handle_hook_failure(step, result.stderr)
        return  # BLOCKED — do NOT advance

    # 6. Verification Gate (AGENTS.md §5.3 — 하위 호환: 기준 없으면 건너뜀)
    if verification_criteria:
        verify_result = self_verify(step.output, verification_criteria)
        retry_count = 0
        while not verify_result.all_pass and retry_count < MAX_VERIFICATION_RETRIES:
            # 실패 기준만 식별하여 해당 부분만 재실행 (전체 재작업 아님)
            remediate(step.output, verify_result.failed_criteria)
            write_file(step.output_path, step.output)  # 갱신된 산출물 저장
            verify_result = self_verify(step.output, verification_criteria)
            retry_count += 1

        if not verify_result.all_pass:
            escalate_to_user(step, verify_result)  # 2회 초과 시 사용자 에스컬레이션
            return  # BLOCKED — do NOT advance

        write_verification_log(step.number, verify_result, retry_count)
        # Verification Log: verification-logs/step-N-verify.md

    # 6b. pACS Self-Rating (AGENTS.md §5.4)
    # ... (기존 pACS 로직 — 생략)

    # 6c. Adversarial Review — Enhanced L2 (AGENTS.md §5.5)
    if step.review_agent:  # Review: @reviewer | @fact-checker | none
        review_output = invoke_subagent(step.review_agent, {
            "artifact": step.output_path,
            "context": step.context_files,
            "generator_pacs": pacs_score,
        })
        write_file(f"review-logs/step-{step.number}-review.md", review_output)

        # P1 Validation (deterministic — validate_review.py)
        validation = run_bash(f"python3 .claude/hooks/scripts/validate_review.py "
                              f"--step {step.number} --project-dir .")
        if not validation.valid:
            escalate_to_user(step, validation.warnings)
            return  # BLOCKED

        if validation.verdict == "FAIL":
            retry_count = 0
            while validation.verdict == "FAIL" and retry_count < MAX_VERIFICATION_RETRIES:
                remediate(step.output, review_output.critical_issues)
                write_file(step.output_path, step.output)
                review_output = invoke_subagent(step.review_agent, {...})
                write_file(f"review-logs/step-{step.number}-review.md", review_output)
                validation = run_bash(f"python3 validate_review.py --step {step.number}")
                retry_count += 1
            if validation.verdict == "FAIL":
                escalate_to_user(step, "Review FAIL after max retries")
                return  # BLOCKED

    # 6d. Translation (Review PASS 후에만 — AGENTS.md §5.5 순서 제약)
    if step.translation_agent and (not step.review_agent or validation.verdict == "PASS"):
        invoke_subagent(step.translation_agent, step.output_path)

    # 7. Update SOT (순차적으로만 +1 증가)
    sot.outputs[f"step-{step.number}"] = step.output_path
    sot.current_step += 1  # NEVER increment by more than 1
```

**Verification Gate 설계 원칙:**
- **배치**: Hook(#5) 이후, SOT 갱신(#7) 이전 — 결정론적 게이트 → 의미론적 게이트 순서
- **하위 호환**: `verification_criteria`가 `None`이면 Gate를 건너뛰어 기존 동작 유지
- **부분 재실행**: 전체 재작업이 아닌, 실패한 기준에 해당하는 부분만 보완
- **SOT 영향 없음**: 검증 상태는 `verification-logs/`에 기록. SOT 구조 변경 불필요 — `current_step` 진행이 이미 검증 완료를 의미

**Adversarial Review 설계 원칙:**
- **배치**: pACS(#6b) 이후, Translation(#6d) 이전 — 리뷰 통과 후에만 번역 실행
- **하위 호환**: `step.review_agent`가 `None`이면 Review를 건너뛰어 기존 동작 유지
- **P1 검증**: `validate_review.py`가 리뷰 보고서의 구조적 무결성을 결정론적으로 검증
- **Rework 루프**: Review FAIL 시 Critical 이슈만 보완 후 재리뷰 (최대 10회)

### Anti-Abbreviation Rule

Autopilot 모드에서도 에이전트는 사람이 검토하는 것처럼 완전한 산출물을 생성한다.
"자동이니까 간략하게"는 **절대 기준 1 위반**이다.

### Hook 동작 (변경 없음)

```
(human) → Autopilot 자동 승인 대상
(hook)  → Autopilot 영향 없음 — 그대로 차단/통과
(team)  → Autopilot: Team Lead가 Task 할당·모델 선택·산출물 검증 자동 수행
```

### Autopilot + Agent Team 체크리스트

> Autopilot 모드에서 `(team)` 단계를 실행할 때 추가로 수행해야 하는 항목.

```
#### (team) 단계 시작 전
- [ ] TeamCreate 후 SOT active_team에 팀 정보 기록
- [ ] 각 Task의 owner 할당 근거를 Decision Log에 기록
- [ ] 모델 선택 근거를 Decision Log에 기록 (모델 선택 프로토콜 참조)

#### (team) 단계 실행 중
- [ ] 각 Teammate는 보고 전 자기 검증 수행 (L1 — AGENTS.md §5.3)
- [ ] 각 Teammate 완료 시 SOT active_team 즉시 갱신
- [ ] Team Lead가 각 Teammate 산출물을 단계 검증 기준 대비 검증 (L2)
- [ ] L2 FAIL 시 SendMessage로 구체적 피드백 + 재실행 지시
- [ ] 실패 시 Team 에러 처리 프로토콜 적용

#### (team) 단계 완료 후
- [ ] 모든 산출물 교차 검증 수행 (품질 게이트)
- [ ] verification-logs/step-N-verify.md 생성 (Verification 기준 있는 경우)
- [ ] SOT outputs에 최종 산출물 경로 기록
- [ ] SOT current_step +1
- [ ] TeamDelete → SOT active_team을 completed_teams로 이동
- [ ] autopilot-logs/step-N-decision.md에 팀 결정 사항 기록
```

### 런타임 강화 메커니즘

Autopilot의 설계 의도를 런타임에서 강화하는 하이브리드(Hook + 프롬프트) 구조:

| 계층 | 메커니즘 | 역할 |
|------|---------|------|
| **Hook** | `restore_context.py` | SessionStart 시 AUTOPILOT EXECUTION RULES 주입 |
| **Hook** | `generate_context_summary.py` | Stop 시 Decision Log 누락 자동 보완 + Review 누락 감지 |
| **Hook** | `_context_lib.py` | 스냅샷에 Autopilot 상태 섹션 보존 (IMMORTAL) + Review P1 검증 함수 |
| **Hook** | `update_work_log.py` | work_log에 autopilot 단계 추적 필드 |
| **프롬프트** | `docs/protocols/autopilot-execution.md` | Autopilot Execution Checklist (MANDATORY) |
| **프롬프트** | 이 파일 | Anti-Skip Execution Protocol + Verification Gate 의사코드 |
| **프롬프트** | `AGENTS.md §5.3` | Verification Protocol — 검증 기준 유형, 실행 프로토콜, 로그 형식 |

---

## 상태 관리 (SOT 설계)

> **절대 기준 2 적용**: 워크플로우의 모든 공유 상태는 **단일 파일(SOT)**에 집중한다. 쓰기 권한은 Orchestrator(또는 Team Lead)만 갖는다.
>
> **절대 기준 1 우선**: SOT 구조가 최종 결과물의 품질을 저하시키는 경우(예: 단일 쓰기 지점이 정보 병목을 일으켜 에이전트가 stale data로 작업하는 경우), 품질을 위한 구조 조정이 허용된다. SOT는 품질을 보장하기 위한 **수단**이지, 품질을 제약하는 **목적**이 아니다.

### SOT 파일 구조

```yaml
# .claude/state.yaml — 단일 SOT 파일
workflow:
  name: "blog-pipeline"
  current_step: 3
  status: "paused"               # running | paused | completed | escalated
  outputs:
    step-1: "raw-contents.md"
    step-2: "insights-list.md"
  pending_input:
    type: "selection"
    options: [...]

  # Agent Team 상태 (team 단계 진행 중일 때만 존재)
  active_team:
    name: "research-pipeline"       # TeamCreate에 전달한 team_name
    status: "partial"               # partial | all_completed
    tasks_completed: ["task-1"]     # 완료된 Task ID 목록
    tasks_pending: ["task-2", "task-3"]  # 미완료 Task ID 목록
    completed_summaries:            # RLM 호환 — 팀원 작업 요약 (세션 복원용)
      task-1:
        agent: "@researcher"
        model: "sonnet"
        output: "research/trends.md"
        summary: "10개 출처에서 5개 핵심 트렌드 도출"
  completed_teams: []               # 종료된 팀 이력 (감사 추적)

  # Autopilot 필드 — workflow 하위 (AGENTS.md §5.1 정본 스키마)
  autopilot:
    enabled: true
    activated_at: "2026-02-16T10:30:00"
    auto_approved_steps: [3, 6]  # 자동 승인된 (human) 단계 목록
```

### SOT State Management Protocol (C-1)

워크플로우 실행 시 SOT를 안전하게 관리하기 위한 운영 프로토콜.

#### SOT 접근 규칙

| 역할 | 읽기 | 쓰기 | 비고 |
|------|------|------|------|
| Orchestrator / Team Lead | O | O | 유일한 쓰기 주체 |
| Sub-agent | O | X | 산출물 파일만 생성 |
| Teammate | O | X | 결과를 Team Lead에 보고 |
| Hook 스크립트 | O | X | `context-snapshots/`에만 쓰기 |

#### SOT 생명주기

```
1. 워크플로우 시작 → SOT 생성 (state.yaml)
2. 각 단계 완료 → outputs에 경로 기록, current_step +1
3. (team) 단계 → active_team 생성 → 팀원 작업 → completed_summaries 갱신
4. (human) + autopilot → auto_approved_steps에 추가
5. 워크플로우 완료 → status: "completed"
```

#### Anti-Skip Guard 검증 (MIN_OUTPUT_SIZE: 100 bytes)

```python
# 단계 전진 전 반드시 수행
assert os.path.exists(output_path), "산출물 파일 없음"
assert os.path.getsize(output_path) >= 100, "산출물 크기 부족 (최소 100 bytes)"
sot.outputs[f"step-{N}"] = output_path
sot.current_step += 1  # 반드시 +1만
```

### SOT 갱신 프로토콜 (Team 사용 시)

> Team Lead가 SOT를 **언제** 갱신하는지의 결정론적 프로토콜. 시점 모호성으로 인한 상태 불일치를 방지한다.

```
SOT 갱신 타이밍 (결정론적):

1. TeamCreate 직후:
   → SOT active_team에 팀 정보 기록 (name, status: "partial", tasks_pending)

2. 각 Teammate 완료 통보 수신 시 (즉시):
   → 산출물 파일 존재 검증 (Anti-Skip Guard)
   → SOT active_team.tasks_completed에 추가
   → SOT active_team.completed_summaries에 요약 기록
   → SOT active_team.tasks_pending에서 제거

3. 해당 단계의 모든 Task 완료 시 (즉시):
   → SOT active_team.status = "all_completed"
   → SOT outputs에 단계 산출물 경로 기록
   → SOT current_step +1 증가

4. TeamDelete 직후:
   → SOT active_team 전체를 completed_teams에 이동
   → SOT active_team 필드 제거

불변량 (Invariant):
  - SOT 갱신 전에 반드시 산출물이 디스크에 존재해야 함
  - current_step 증가 전에 반드시 모든 Task가 completed여야 함
  - active_team은 하나만 존재 가능 (동시 다중 팀 금지 — SOT 단일 쓰기 원칙)
```

> **SOT와 Task System의 관계**: Task System(`.claude/tasks/`)은 런타임 실행 레이어다. SOT(`state.yaml`)가 유일한 진실이며, Task System은 에이전트 간 작업 조율 도구다. SOT의 `active_team`이 Task System의 상태를 요약 반영하므로, 세션 복원 시 SOT만 읽어도 팀 작업의 전체 맥락을 파악할 수 있다.

> **스키마 정본**: AGENTS.md §5.1에 정의된 `workflow.autopilot` 구조가 정본이다. `_context_lib.read_autopilot_state()`는 양쪽 스키마(`workflow.autopilot` 및 top-level `autopilot`)를 모두 지원하되, AGENTS.md 위치를 우선 탐색한다. PyYAML이 없는 환경에서는 regex fallback으로 동작한다.

### 쓰기 권한 규칙

| 구조 | SOT 쓰기 권한자 | 다른 에이전트 |
|------|----------------|-------------|
| Sub-agent 순차 | Orchestrator | 결과를 Orchestrator에 반환 → Orchestrator가 SOT 갱신 |
| Agent Team | Team Lead | 팀원은 산출물 파일만 생성 → Team Lead가 SOT에 상태 병합 |
| Hook 기반 | Hook script | SOT 읽기만 (검증용). 상태 변경 불가 |

> **절대 기준 1 우선 예외**: 위 규칙이 품질 병목을 일으키는 경우(예: Team Lead가 유일한 쓰기 지점이라 팀원이 stale data로 작업), 다음 조건 하에 구조를 조정할 수 있다:
> 1. **산출물 파일 직접 참조**: 팀원 간 산출물 파일(`.md`, `.json` 등)은 SOT를 거치지 않고 직접 읽기 허용 — SOT에는 최종 상태만 기록
> 2. **판단 근거 문서화**: 왜 기본 SOT 패턴이 품질을 저하시키는지 워크플로우에 명시
> 3. **SOT 자체는 유지**: 구조를 조정하더라도 SOT 파일 자체를 제거하지 않는다 — 최종 상태 기록의 단일 지점은 보존

### 계층적 메모리 구조

```
전역 메모리 (SOT — 단일 파일)
  └─ .claude/state.yaml
       ├─ workflow 상태 (current_step, status)
       ├─ 단계별 산출물 경로 (outputs)
       └─ 에러/롤백 정보

로컬 메모리 (에이전트별 — 각자의 작업 컨텍스트)
  ├─ Sub-agent: 위임받은 Task + 이전 단계 산출물 (읽기 전용)
  ├─ Teammate: 할당된 Task + 필요 입력 파일 (읽기 전용)
  └─ Hook: 검증 대상 산출물 (읽기 전용)
```

### Agent Team에서의 SOT 흐름

**기본 패턴 (Default):**

```
Teammate A → 산출물 파일 생성 (output-a.md)
Teammate B → 산출물 파일 생성 (output-b.md)
     ↓ 완료 통보 (SendMessage)
Team Lead → state.yaml에 상태 병합 (유일한 쓰기 지점)
     ↓
다음 단계로 진행
```

**품질 우선 패턴 (절대 기준 1 우선 적용 시):**

```
Teammate A → 산출물 파일 생성 (output-a.md)
     ↓ Teammate B가 output-a.md를 직접 참조 (품질을 위한 교차 검증)
Teammate B → 산출물 파일 생성 (output-b.md, output-a.md 참조 반영)
     ↓ 완료 통보 (SendMessage)
Team Lead → state.yaml에 최종 상태 병합 (SOT 단일 기록 지점은 유지)
     ↓
다음 단계로 진행
```

> **적용 조건**: 팀원 간 산출물 직접 참조는 교차 검증, 피드백 루프 등 **품질 향상이 입증되는 경우**에만 허용한다. 단순 편의를 위한 직접 참조는 허용하지 않는다. SOT 파일 자체의 단일 쓰기 지점은 어떤 경우에도 보존한다.

> **주의**: Claude Code의 Task List(`~/.claude/tasks/{team-name}/`)는 **작업 할당/추적 도구**이지, 워크플로우 상태(SOT)가 아니다. 워크플로우의 진행 상태·산출물 경로·에러 정보는 반드시 SOT 파일(`state.yaml`)에서 관리한다.

## Task Management System (TaskCreate/TaskUpdate/TaskList)

Claude Code의 내장 Task 관리 도구. Agent Team에서 작업 할당·추적·조율에 사용.

> **SOT와의 관계**: Task List(`~/.claude/tasks/{team-name}/`)는 **작업 할당/추적 도구**이다. 워크플로우 상태(current_step, status, outputs)는 반드시 SOT(`state.yaml`)에서 관리한다. Task List는 SOT를 대체하지 않는다.

### TaskCreate — 작업 생성

```markdown
## workflow.md 내 Task 설계

### 2. (team) 병렬 리서치
- **Team**: `research-pipeline`
- **Task 정의**:

  #### Task 1: 웹 트렌드 수집
  - **subject**: "최신 AI 트렌드 웹 리서치"
  - **description**: "2024-2025 AI 산업 트렌드를 웹에서 수집. 최소 10개 출처 필요. 결과를 research/trends.md에 저장"
  - **activeForm**: "AI 트렌드 리서치 중"
  - **owner**: `@researcher`
  - **blocks**: [Task 3]  ← Task 3은 이 결과에 의존

  #### Task 2: 기존 데이터 분석
  - **subject**: "내부 데이터 통계 분석"
  - **description**: "data/ 디렉터리의 CSV 파일 분석. 주요 지표 추출. 결과를 research/analysis.md에 저장"
  - **activeForm**: "데이터 분석 중"
  - **owner**: `@data-processor`
  - **blocks**: [Task 3]

  #### Task 3: 종합 인사이트 도출
  - **subject**: "리서치 결과 종합 및 인사이트 도출"
  - **description**: "research/trends.md + research/analysis.md를 종합. 핵심 인사이트 5개 도출"
  - **blockedBy**: [Task 1, Task 2]  ← 의존성 명시
  - **owner**: `@writer`
```

### TaskUpdate — 상태 관리 및 의존성

**상태 전이 규칙:**

```
pending → in_progress → completed
                     → (blocked → pending)  ← blockedBy 해소 시 자동 전환
```

**Team Lead의 Task 조율 패턴:**

```markdown
## Orchestrator 역할
1. TaskCreate로 모든 Task 생성 + 의존성(blocks/blockedBy) 설정
2. TaskUpdate로 owner 할당 → 팀원에게 SendMessage로 시작 통보
3. 팀원이 완료 시:
   a. TaskUpdate(status: completed) 호출
   b. Team Lead에게 SendMessage로 완료 통보
   c. Team Lead가 SOT(state.yaml) 갱신
   d. blockedBy가 해소된 Task의 owner에게 시작 통보
4. 모든 Task 완료 시 → 다음 워크플로우 단계로
```

### TaskList — 진행 상황 모니터링

```markdown
## Orchestrator 점검 패턴
- 주기적으로 TaskList 호출하여 전체 진행 상황 파악
- blocked Task가 있으면 차단 원인 분석
- 완료된 Task의 산출물 품질 검증 후 SOT 갱신
```

---

## Context Memory 연동 패턴

워크플로우 실행 중 Context Preservation System을 활용하는 패턴.

### 워크플로우 단계별 컨텍스트 전략

```markdown
## workflow.md 내 컨텍스트 명시

### Phase 1: Research (컨텍스트 축적 단계)
- **Context Strategy**: 최대 보존 모드
- 모든 리서치 결과와 의사결정 근거를 스냅샷에 포함
- Stop Hook이 매 응답 후 증분 스냅샷 자동 생성

### Phase 2: Planning (컨텍스트 활용 단계)
- **Context Strategy**: 선별적 참조 모드
- Phase 1의 스냅샷을 참조하되, 계획 수립에 필요한 부분만 Read
- SOT에 계획 상태 기록

### Phase 3: Implementation (컨텍스트 분산 단계)
- **Context Strategy**: 에이전트별 최소 컨텍스트
- 각 에이전트는 자신의 Task description + 필요 입력 파일만 참조
- Team Lead만 전체 맥락 유지 (SOT + 스냅샷)
```

### Agent Team과 RLM 호환 패턴

> Agent Team의 Teammate들은 독립 세션이므로, 메인 세션의 스냅샷에 포함되지 않을 수 있다. 이 문제를 해결하기 위한 2계층 RLM 패턴.

```markdown
## 2계층 RLM (Recursive Language Model) 패턴

### 계층 1 (기존): 메인 세션 자동 보존
- Stop hook → latest.md 스냅샷 (자동)
- SessionEnd/PreCompact → 전체 스냅샷 + Knowledge Archive (자동)
- 이 계층은 Team Lead(=Orchestrator)의 세션만 캡처

### 계층 2 (신규): Team Lead의 능동적 팀 맥락 보존
- 각 Teammate 완료 시 → SOT active_team.completed_summaries에 작업 요약 기록
- Team 종료 시 → SOT completed_teams에 팀 이력 보존
- 이 계층은 Team Lead가 SOT 쓰기로 수행 (절대 기준 2 준수)

### 세션 복원 시 흐름:
1. SessionStart hook → latest.md 포인터 출력
2. Claude가 latest.md 읽기 → 메인 세션 맥락 복원
3. latest.md 스냅샷에 Team State 섹션 존재 → 팀 작업 상태 파악
4. SOT active_team 읽기 → 팀 진행 상태 + 각 Teammate 작업 요약 확인
5. **보존적 재개 프로토콜** (아래 상세)

### 보존적 재개 프로토콜 (Preserving Resumption):
> 세션 크래시·/clear·compact 후 팀 작업을 재개할 때, 기존 RLM Layer 2 데이터를 보존하며 재개한다.

**Step 5a — SOT 상태 판별:**
- SOT `active_team`이 존재하는가? → 팀이 진행 중이었음
- `active_team.status`가 `"partial"`인가? → 중단된 팀 작업 재개 필요
- `active_team`이 없거나 `status: "all_completed"`면 → 팀 재개 불필요, 다음 워크플로우 단계로

**Step 5b — 완료 작업 파일 검증 (Anti-Duplicate Guard):**
- `tasks_pending` 목록의 각 Task에 대해:
  - 워크플로우 정의(workflow.md)에서 해당 Task의 expected output 경로 확인
  - 해당 output 파일이 디스크에 이미 존재하는가?
  - 파일이 존재하고 100 bytes 이상인가? (Anti-Skip Guard 기준 동일)
  - **존재하면**: 해당 Task를 `tasks_completed`로 이동, `completed_summaries`에 `"(restored from disk)"` 기록
  - **존재하지 않으면**: 진짜 미완료 Task → 새 Teammate 생성 대상

**Step 5c — 팀 재생성 (Merge, Not Overwrite):**
- `TeamCreate` 호출 시 **기존 SOT의 `completed_summaries`를 반드시 보존**
- 구체적 절차:
  1. SOT에서 기존 `active_team` 전체를 변수에 저장
  2. 새 팀 생성 (TaskCreate로 미완료 Task만 등록)
  3. SOT `active_team` 갱신 시 기존 `completed_summaries`를 merge
  4. 기존 `tasks_completed` 목록도 유지 (Step 5b 결과 반영)
- **절대 금지**: `active_team`을 빈 객체로 초기화하여 `completed_summaries` 유실

**Step 5d — Teammate 생성 및 재개:**
- Step 5b에서 진짜 미완료로 확인된 Task에만 새 Teammate 생성
- 각 Teammate의 Task description에 "이전 세션에서 중단된 작업 재개" 맥락 포함
- 이전에 부분 완료된 산출물이 있으면 해당 경로를 입력으로 전달
```

**핵심**: Teammate의 독립 세션은 RLM 스냅샷에 직접 포함되지 않지만, SOT의 `completed_summaries`가 "외부 메모리 객체"로서 팀 맥락을 영속화한다. 이것이 RLM의 "외부 메모리 → 포인터 기반 복원" 원칙과 정합한다.

### 장기 워크플로우에서의 세션 복구

```markdown
## 세션 복구 패턴 (워크플로우가 여러 세션에 걸칠 때)

### 복구 흐름:
1. SessionStart Hook이 latest.md 포인터 출력
2. Claude가 Read tool로 스냅샷 로드
3. SOT(state.yaml)에서 current_step 확인
4. 해당 단계의 산출물 파일 존재 여부 검증
5. 중단된 지점부터 워크플로우 재개

### 워크플로우 설계 시 고려사항:
- 각 단계의 산출물은 **반드시 파일로 저장** (메모리 내 데이터 금지)
- SOT에 단계별 산출물 경로 기록 (outputs 필드)
- 세션 복구 시 SOT만 읽으면 전체 상태 파악 가능하도록 설계
```

---

## Orchestrator 고급 패턴

### 재시도 패턴 (Retry with Feedback)

```markdown
### 3. 콘텐츠 작성 (재시도 포함)
- **Agent**: `@writer`
- **Task**: 리서치 기반 콘텐츠 작성
- **Quality Gate**: TaskCompleted Hook (agent 타입)
- **On Failure**:
  - 시도 1: Hook 피드백을 에이전트에 전달 → 자동 재작업
  - 시도 2: 추가 컨텍스트 제공 후 재시도
  - 시도 3: (human) 수동 개입 요청
- **Max Attempts**: 3
- **SOT Update**: 각 시도의 결과를 state.yaml에 기록
```

### 에스컬레이션 패턴

```markdown
### Orchestrator 에스컬레이션 규칙:
1. **자동 해결**: Hook 피드백 기반 재시도 (시도 1-2)
2. **Team Lead 개입**: 에이전트 교체 또는 Task 분할 (시도 3)
3. **Human 에스컬레이션**: AskUserQuestion으로 사용자 판단 요청 (시도 4+)

### 에스컬레이션 시 SOT 기록:
```yaml
workflow:
  current_step: 3
  status: "escalated"
  escalation:
    reason: "3회 품질 검증 실패"
    failed_attempts: 3
    last_feedback: "출처 검증 미흡"
```
```

### 조건부 라우팅 패턴

```markdown
### 4. 조건부 처리
- **Input**: Step 3의 산출물
- **Condition**: 산출물의 길이/복잡도에 따라 분기
  - **Path A** (간단한 경우): `@quick-editor`로 직접 편집
  - **Path B** (복잡한 경우): Agent Team으로 병렬 처리
- **Condition Evaluator**:
  - Hook (command 타입): 파일 크기/구조 검사 (결정론적)
  - 또는 Hook (prompt 타입): haiku로 복잡도 판단 (의미적)
- **SOT Update**: 선택된 경로를 state.yaml에 기록
```

---

## 에러 처리

```yaml
error_handling:
  on_agent_failure:
    action: retry_with_feedback
    max_attempts: 3
    escalation: human  # 3회 초과 시 사용자에게 에스컬레이션

  on_tool_failure:
    action: notify_and_pause
    message: "도구 실행 실패. 수동 개입 필요."
    sot_update: true  # SOT에 에러 상태 기록

  on_validation_failure:
    action: retry_or_rollback
    retry_with_feedback: true  # Hook 피드백을 에이전트에 전달
    rollback_after: 3  # 3회 실패 후 이전 단계로 롤백

  on_hook_failure:
    action: log_and_continue
    message: "Hook 실행 실패. 워크플로우는 계속 진행."

  on_context_overflow:
    action: save_and_recover
    description: "컨텍스트 초과 시 자동 저장 후 세션 복구 패턴 적용"

  # Agent Team 에러 처리 (Gap 6 보완)
  on_teammate_failure:
    action: escalating_retry
    protocol:
      attempt_1: "SendMessage로 피드백 전달 → 같은 Teammate 재작업"
      attempt_2: "Teammate shutdown → 새 Teammate 생성 (동일 또는 상위 모델)"
      attempt_3: "Human 에스컬레이션 (AskUserQuestion)"
    sot_update:
      - "active_team.errors에 실패 정보 기록"
      - "retry_count, last_feedback 포함"
    partial_output: "실패한 Teammate의 부분 산출물은 보존 (다음 시도에서 참조 가능)"
```

### Agent Team 에러 처리 상세 흐름

```
Teammate 실패 감지
  ├── 방법 1: TaskCompleted hook exit code 2 (품질 미달)
  ├── 방법 2: SendMessage로 에러 보고
  └── 방법 3: Teammate idle 전환 (작업 미완료 상태)
      ↓
Team Lead 대응 프로토콜:
  1. SOT active_team.errors에 실패 정보 즉시 기록
  2. 시도 1: 같은 Teammate에게 SendMessage로 피드백 + 재작업 지시
     → 성공 시: SOT active_team.tasks_completed에 추가
     → 실패 시: 시도 2로
  3. 시도 2: 실패 Teammate shutdown → 새 Teammate 생성
     → 상위 모델로 교체 고려 (haiku→sonnet, sonnet→opus)
     → 부분 산출물을 새 Teammate에게 전달 (작업 재개, 처음부터 재시작 아님)
  4. 시도 3: Human 에스컬레이션 (AskUserQuestion)
     → SOT status를 "escalated"로 변경
```

---

## 데이터 전처리/후처리 패턴

AI에게 전달하기 전에 code-level에서 데이터를 정제하여 분석 정확도와 결과 품질을 높이는 패턴.

### 워크플로우 단계별 전처리 명시법

```markdown
### 2. 컨텐츠 분석
- **Pre-processing**: `scripts/extract_body.py` — HTML에서 본문만 추출, 광고/네비게이션 제거
- **Agent**: `@insight-extractor`
- **Task**: 추출된 본문에서 핵심 인사이트 도출
- **Output**: `insights-list.md`
- **Post-processing**: `scripts/dedup_insights.py` — 중복 인사이트 제거, 유사도 0.9 이상 병합
```

### 전처리 스크립트 설계 기준

| 기준 | Code-level 처리 | AI 에이전트 처리 |
|------|----------------|----------------|
| 데이터 필터링 (날짜, 키워드) | O | X |
| 중복 제거 (hash, 유사도) | O | X |
| 포맷 변환 (HTML→텍스트) | O | X |
| 연관관계 계산 (그래프, 통계) | O | X |
| 의미 분석, 판단, 요약 | X | O |
| 창의적 생성, 작문 | X | O |

### Hook 기반 자동 전처리

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [{
          "type": "command",
          "command": "python3 \"$CLAUDE_PROJECT_DIR\"/scripts/preprocess_input.py",
          "statusMessage": "데이터 전처리 중..."
        }]
      }
    ]
  }
}
```

---

## 구성요소 비교 요약

| 특성 | Sub-agent | Agent Team | Hook | Setup Hook | Slash Command | AskUserQuestion | Task System | Skill (inline) | Skill (forked) | MCP Server |
|------|-----------|------------|------|------------|---------------|-----------------|-------------|----------------|----------------|------------|
| **역할** | 전문가 위임 | 병렬 협업 | 자동 검증 | 인프라 검증 | 사용자 개입점 | 동적 질문 | 작업 추적 | 지식 주입 | 독립 분석/변환 | 외부 연동 |
| **세션** | 단일 (위임) | 다중 (독립) | N/A | 세션 전 | N/A | N/A | N/A | N/A | 단일 (격리) | N/A |
| **컨텍스트** | 부모와 분리 | 완전 독립 | 없음 | 없음 (세션 전) | 없음 | 현재 세션 | 팀 공유 | 세션 주입 | 부모와 분리 | 세션 주입 |
| **SOT 관계** | Orchestrator가 갱신 | Team Lead만 갱신 | 읽기 전용 | 비접근 | 사용자 입력 반영 | 사용자 입력 반영 | SOT와 분리 | 무관 | 간접 (전처리 주입) | 무관 |
| **품질 기여** | 전문 집중 | 다관점 병렬 | 결정론적 검증 | Silent Failure 방지 | 사람의 판단 | 구조화된 수집 | 의존성 관리 | 검증된 패턴 | 격리된 분석 | 외부 데이터 |
| **정의 위치** | .claude/agents/*.md | Task tool | settings.json | settings.json (Setup) | .claude/commands/*.md | 워크플로우 내 | Task tool | .claude/skills/ | .claude/skills/ | .mcp.json |

---

## 절대 기준 준수 가이드

워크플로우를 구현할 때 **모든 절대 기준이 적용**된다.

### 절대 기준 1 (품질): 구성요소 선택 기준
- Sub-agent vs Agent Team 선택은 **오직 품질**으로 판단한다
- 단계 수를 줄이는 것보다 품질을 높이는 방향을 선택한다
- 검증 단계가 반복되어도 결과물이 나아지면 반복을 허용한다

### 절대 기준 2 (SOT): 상태 관리 원칙
- §상태 관리 (SOT 설계) 섹션의 모든 규칙이 적용된다
- Task List는 작업 할당 도구이지 SOT가 아니다

### 절대 기준 3 (CCP): 코드 변경 프로토콜
워크플로우 구현 시 **Hook 설정 변경, 에이전트 프롬프트 수정, MCP 설정 변경** 등은 코드 변경에 해당한다.

| 변경 대상 | CCP 적용 | 분석 항목 |
|----------|---------|----------|
| Hook JSON 추가/수정 | 전체 3단계 | 기존 Hook과의 충돌, exit code 영향, 다른 이벤트와의 상호작용 |
| Agent .md 수정 | 전체 3단계 | tools 변경의 파급, model 변경의 품질 영향, 호출 관계 |
| MCP 설정 변경 | 전체 3단계 | 환경변수 의존, 에이전트 접근 권한, 보안 영향 |
| Slash Command 수정 | Step 1만 (경미) | 사용자 인터랙션 경로 확인 |
| SOT 스키마 변경 | 전체 3단계 + 사용자 승인 | 모든 에이전트의 SOT 읽기 코드, Hook 검증 로직, 롤백 영향 |

> **참조**: 절대 기준 3 상세 프로토콜은 `AGENTS.md §2 절대 기준 3`에 정의되어 있다.
> CCP의 모든 단계는 **코딩 기준점(CAP-1~4)** — 코딩 전 사고, 단순성 우선, 목표 기반 실행, 외과적 변경 — 을 내면화한 상태에서 수행한다.

---

## pACS 실행 패턴 (predicted Agent Confidence Score)

워크플로우 실행 중 에이전트가 자기 산출물의 신뢰도를 구조적으로 자기 평가하는 패턴.

> **참조**: `AGENTS.md §5.4 pACS — predicted Agent Confidence Score`

### 단계별 pACS 실행 흐름

```
┌─ Step N 실행 ──────────────────────────────────────────┐
│  @specialist-agent (작업 수행)                          │
│  → output: analysis/report.md                          │
│                                                        │
│  ── L0: Anti-Skip Guard ──                             │
│  파일 존재 + ≥ 100 bytes ✓                             │
│                                                        │
│  ── L1: Verification Gate ──                           │
│  Verification 기준 대비 자기 검증 → PASS               │
│  → verification-logs/step-N-verify.md                  │
│                                                        │
│  ── L1.5: pACS Self-Rating ──                          │
│  Pre-mortem Protocol:                                  │
│    Q1: 가장 불확실한 부분?                              │
│    Q2: 빠뜨렸을 가능성?                                │
│    Q3: 가장 약한 논증 연결?                             │
│  → F: 72, C: 85, L: 78                                │
│  → pACS = min(72, 85, 78) = 72 → GREEN               │
│  → pacs-logs/step-N-pacs.md                           │
│  → SOT pacs 필드 갱신                                  │
│                                                        │
│  [L2: Calibration — 선택적]                             │
│  @verifier가 교차 검증 (고위험 단계만)                   │
├─ Step N+1로 진행 ─────────────────────────────────────┤
│  SOT: current_step += 1                                │
└────────────────────────────────────────────────────────┘
```

### pACS 행동 트리거별 실행 패턴

```
pACS ≥ 70 (GREEN):
  → 자동 진행
  → SOT pacs.history.step-N 기록

pACS 50-69 (YELLOW):
  → 진행하되 약점 차원 플래그
  → Decision Log에 weak_dimension 기록
  → SOT pacs.pre_mortem_flag 기록

pACS < 50 (RED):
  → 약점 차원 식별
  → 해당 부분만 재작업 (전체 재작업 아님)
  → 재채점 (최대 10회)
  → 10회 후에도 RED → 사용자 에스컬레이션
```

### Translation pACS 패턴

```
@translator 번역 완료 후:
  Pre-mortem (번역 특화):
    Q1: 의미 왜곡 위험이 가장 높은 부분?
    Q2: 누락 가능성이 있는 섹션?
    Q3: 번역체가 남아있는 문장?
  → Ft: 85, Ct: 90, Nt: 72
  → Translation pACS = min(85, 90, 72) = 72 → GREEN
  → pacs-logs/step-N-translation-pacs.md
```

### SOT pacs 필드 스키마

```yaml
workflow:
  pacs:
    current_step_score: 72
    dimensions: {F: 72, C: 85, L: 78}
    weak_dimension: "F"
    pre_mortem_flag: "데이터 출처 2건 미확인"
    history:
      step-1: {score: 85, weak: "C"}
      step-2: {score: 72, weak: "F"}
```

- `pacs` 필드가 없는 SOT도 정상 동작 (하위 호환)
- Hook의 `capture_sot()`가 자동으로 스냅샷에 포함
- `validate_step_output()`은 `pacs` 필드를 무시 (기존 동작 유지)

---

## 이중언어 실행 패턴 (English-First + Korean Translation)

워크플로우 실행 시 모든 에이전트가 영어로 작업하고, 각 단계 완료 후 `@translator` 서브에이전트가 한국어 번역을 생성하는 패턴.

> **근거**: AI는 영어에서 가장 높은 성능을 발휘한다. 영어 우선 실행은 절대 기준 1(품질)의 직접적 구현이다.
> **참조**: `AGENTS.md §5.2 English-First 실행 및 번역 프로토콜`

### 번역 서브에이전트 정의

```markdown
# .claude/agents/translator.md
---
name: translator
description: English-to-Korean translation specialist with glossary-based terminology consistency
model: opus
tools: Read, Write, Glob, Grep
maxTurns: 20
---
```

**모델 선택 근거**: 번역은 원문의 심층 이해 + 문화적 적응 + 용어 일관성을 요구하는 고난도 작업. §모델 수준 선택에서 "핵심 작업 — 최종 품질에 직접 영향"에 해당하므로 최고 수준(opus) 선택.

**서브에이전트 선택 근거**: §품질 판단 매트릭스의 5개 요인 중 "맥락 깊이"(용어 누적), "산출물 일관성"(통일된 문체), "정보 전달 손실"(원문 뉘앙스 보존) 3개가 전문 에이전트 우위 → 에이전트 그룹이 아닌 서브에이전트.

### 용어 사전 관리 패턴 (Glossary — RLM 외부 지속 상태)

```yaml
# translations/glossary.yaml — 번역 에이전트의 지속적 외부 메모리
terms:
  "Single Source of Truth": "단일 소스 오브 트루스(Single Source of Truth)"
  "Anti-Skip Guard": "Anti-Skip Guard"  # 영어 유지
  "Recursive Language Model": "재귀적 언어 모델(Recursive Language Model)"
  "sub-agent": "서브에이전트"
```

**아키텍처 정합성**:
- glossary는 번역 에이전트의 **로컬 작업 파일** (SOT 아님)
- 계층적 메모리의 Local Memory 계층: `per-agent 작업 맥락`
- Orchestrator가 관리하지 않음 — 번역 에이전트가 자체 Read/Write
- 동시 쓰기 위험 없음 — 번역은 순차 실행

### SOT 기록 패턴

```yaml
# state.yaml — outputs에 영어 원본 + 한국어 번역 기록
workflow:
  outputs:
    step-1: "research/raw-contents.md"          # 영어 원본
    step-1-ko: "research/raw-contents.ko.md"    # 한국어 번역
    step-2: "data/processed.json"               # 번역 불필요 → -ko 없음
    step-3: "analysis/report.md"
    step-3-ko: "analysis/report.ko.md"
```

**Anti-Skip Guard 호환성**: `step-N-ko` 키는 `restore_context.py`의 정렬 람다에서 `.isdigit()` 가드로 자동 건너뛰어짐. `validate_step_output()`은 `f"step-{step_number}"`로 영어 원본만 검증. Hook 코드 변경 없음.

### 워크플로우 단계 실행 흐름

```
┌─ Step N 실행 (영어) ──────────────────────────────┐
│  @specialist-agent (English prompt)               │
│  → output: research/raw-contents.md               │
│  → SOT: outputs.step-N = "research/raw-..."       │
│  → Anti-Skip Guard: 파일 존재 + ≥100 bytes ✓     │
├─ 번역 (Translation: @translator인 단계만) ─────────┤
│  @translator (opus)                               │
│  ① Read translations/glossary.yaml                │
│  ② Read research/raw-contents.md (English)        │
│  ③ Translate — 확립된 용어 사용, 축약 금지         │
│  ④ Self-review — 원문 대조, 완전성 확인            │
│  ⑤ Write translations/glossary.yaml (용어 갱신)    │
│  ⑥ Write research/raw-contents.ko.md (Korean)     │
│  → SOT: outputs.step-N-ko = "research/...ko.md"  │
│  → 번역 검증: 파일 존재 + 비어있지 않음 ✓         │
├─ Step N+1로 진행 ──────────────────────────────────┤
│  SOT: current_step += 1                           │
└───────────────────────────────────────────────────┘
```

### `(team)` 단계 번역

```
Team Lead ──────────────────────────────────────────
  ├→ @teammate-a → output-a.md (영어, 작업 파일)
  ├→ @teammate-b → output-b.md (영어, 작업 파일)
  └→ Team Lead:
       1. 병합 → merged-output.md (공식 산출물)
       2. SOT outputs.step-N = "merged-output.md"
       3. Anti-Skip Guard ✓
       4. @translator → merged-output.ko.md
       5. SOT outputs.step-N-ko = "merged-output.ko.md"
       6. current_step += 1
```

> Teammate 개별 산출물은 SOT 미기록 중간 작업물이므로 번역하지 않는다.

### 독립 번역 검증 패턴 (선택적)

최종 납품물 등 품질이 특히 중요한 단계에서 선택적으로 적용:

```
@translator → output.ko.md
  → @translation-verifier (별도 서브에이전트, model: opus)
    ① Read 영어 원본 + 한국어 번역 동시
    ② 정확성, 완전성, 용어 일관성, 자연스러움 검증
    ③ Pass/Fail + 피드백
  → Fail: @translator에게 피드백 + 재번역 요청
  → Pass: SOT 기록 후 진행
```

이 패턴은 워크플로우 설계 시 해당 단계에 `Verification: @translation-verifier`를 명시하여 적용한다.

---

## DNA Inheritance Pattern

모든 생성된 워크플로우가 부모(AgenticWorkflow)의 게놈을 구조적으로 내장하는 패턴.

> **원칙**: "유전은 선택이 아니라 구조다." — 자식 워크플로우는 부모의 DNA를 참조하는 것이 아니라 내장한다.

### 필수 포함 항목

| 워크플로우 구성요소 | DNA 내장 형태 | 검증 방법 |
|-------------------|-------------|----------|
| `workflow.md` | `## Inherited DNA (Parent Genome)` 섹션 포함 | 섹션 존재 확인 |
| `state.yaml` | `parent_genome` 메타데이터 포함 | 필드 존재 확인 |
| Sub-agent 정의 | 부모의 품질 기준을 에이전트 프롬프트에 반영 | Absolute Rules에 품질 원칙 포함 |
| Hook 설계 | P1 할루시네이션 봉쇄 패턴을 자식 Hook에도 적용 | exit code 2 차단 패턴 존재 |

### 유전자 발현 (Gene Expression)

도메인에 따라 발현 강도가 다르지만 게놈 자체는 동일하다:

```
리서치 자동화  → P1(데이터 정제) 강발현, P2(전문가 위임) 강발현
SW 개발       → CCP(코드 변경 프로토콜) 강발현, Safety Hook 강발현
콘텐츠 생성   → P2(전문가 위임) 강발현, Adversarial Review 강발현
데이터 분석   → P1(데이터 정제) 강발현, SOT(상태 관리) 강발현
```

> **참조**: `soul.md §0` — 게놈 구성요소 12개 정의, `AGENTS.md §1` — 존재 이유와 유전 메커니즘
