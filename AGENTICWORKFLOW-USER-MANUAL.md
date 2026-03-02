# AgenticWorkflow 사용자 매뉴얼

> **이 문서의 범위**: 이 매뉴얼은 **AgenticWorkflow 코드베이스 자체**를 사용하는 방법을 안내합니다.
> 즉, 워크플로우를 설계하고 구현하는 **도구(이 코드베이스)의 사용법**입니다.
>
> 이 코드베이스로 **만들어진 개별 프로젝트**(예: 블로그 파이프라인, 리서치 시스템 등)의 사용법은
> 각 프로젝트의 `workflow.md`와 해당 프로젝트 내 매뉴얼을 참조하세요.

| 문서 | 대상 |
|------|------|
| **이 문서 (`AGENTICWORKFLOW-USER-MANUAL.md`)** | AgenticWorkflow 코드베이스 자체의 사용법 — 워크플로우를 설계하고 구현하는 방법 |
| **`README.md`** | 프로젝트 첫 소개 — 개요, 목표, 문서 읽기 순서 |
| **`AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md`** | 설계 철학, 아키텍처 전체 조감도, 구성 요소 간 관계 — "왜 이렇게 설계했는가"를 이해할 때 |
| **`DECISION-LOG.md`** | 프로젝트의 모든 설계 결정 기록 (ADR) — 각 결정의 맥락, 근거, 대안을 시간순 추적 |
| **개별 프로젝트 매뉴얼** (각 프로젝트 내) | AgenticWorkflow로 만든 특정 프로젝트의 사용법 — 완성된 시스템의 실행과 운영 |

---

## 1. 시작하기

### 1.1 사전 준비

| 항목 | 필수 여부 | 설명 |
|------|----------|------|
| [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) | 필수 | `npm install -g @anthropic-ai/claude-code` |
| GitHub 계정 | 권장 | 저장소 clone 및 협업 |
| Python 3.10+ | 선택 | 데이터 전처리/후처리 스크립트 실행 시 |
| Node.js 18+ | 선택 | MCP Server 연동 시 |

### 1.2 설치

```bash
git clone https://github.com/idoforgod/AgenticWorkflow.git
cd AgenticWorkflow
```

### 1.3 프로젝트 열기

```bash
claude          # Claude Code 실행 (AgenticWorkflow 디렉터리에서)
```

Claude Code가 실행되면 `CLAUDE.md`를 자동으로 읽고, 프로젝트의 절대 기준과 설계 원칙을 적용합니다.

---

## 2. 전체 흐름

```
사용자의 아이디어 또는 설명 문서
        ↓
┌─────────────────────────────────┐
│ Phase 1: 워크플로우 설계          │
│  workflow-generator 스킬 사용     │
│  → workflow.md 생성 (설계도)      │
│  → (선택) Distill 검증            │
└─────────────────────────────────┘
        ↓
┌─────────────────────────────────┐
│ Phase 2: 워크플로우 구현          │
│  workflow.md 기반으로 실제 구현    │
│  → 에이전트, 스크립트, 자동화 설정  │
│  → 실제 동작하는 시스템 (최종 목표) │
└─────────────────────────────────┘
```

> **DNA 유전**: workflow-generator가 워크플로우를 생성할 때, 부모(AgenticWorkflow)의 전체 게놈(절대 기준, SOT 패턴, 4계층 검증, Safety Hook 등)이 자식 워크플로우에 자동으로 내장됩니다.
> 사용자가 수동으로 DNA를 설정할 필요 없습니다 — 생산 라인이 구조적으로 유전합니다. 상세: [`soul.md`](soul.md)

---

## 3. 절대 기준

이 코드베이스의 모든 설계·구현·수정 의사결정에 적용되는 최상위 규칙입니다.
아래의 모든 원칙, 가이드라인, 관례보다 상위에 있습니다.

### 절대 기준 1: 최종 결과물의 품질

> **속도, 토큰 비용, 작업량, 분량 제한은 완전히 무시한다.**
> 모든 의사결정의 유일한 기준은 **최종 결과물의 품질**이다.
> 단계를 줄여서 빠르게 만드는 것보다, 단계를 늘려서라도 품질을 높이는 방향을 선택한다.

### 절대 기준 2: 단일 파일 SOT + 계층적 메모리 구조

> **단일 파일 SOT(Single Source of Truth) + 계층적 메모리 구조 설계 아래서, 수십 개의 에이전트가 동시에 작동해도 데이터 불일치가 발생하지 않는다.**

- **상태 관리**: 모든 공유 상태는 단일 파일에 집중. 분산 금지.
- **쓰기 권한**: SOT 파일 쓰기는 Orchestrator/Team Lead만. 나머지는 읽기 전용 + 산출물 파일 생성.
- **충돌 방지**: 병렬 에이전트가 동일 파일을 동시 수정하는 구조 금지.

### 절대 기준 3: 코드 변경 프로토콜 (Code Change Protocol)

> **코드를 작성·수정·추가·삭제하기 전에, 반드시 3단계를 내부적으로 수행한다.**

- **Step 1 — 의도 파악**: 변경 목적과 제약을 1-2문장으로 정의
- **Step 2 — 영향 범위 분석**: 직접 의존, 호출 관계, 구조적 관계, 데이터 모델, 테스트, 설정, 문서의 연쇄 변경 조사. 강결합 위험 시 사전 고지
- **Step 3 — 변경 설계**: 단계별 변경 순서 제안. 결합도 감소 기회 함께 제안

분석 깊이는 변경의 영향 범위에 비례합니다 (경미 → Step 1만 / 표준 → 전체 / 대규모 → 전체 + 사전 승인).

> **코딩 기준점(CAP-1~4)**: 코딩 전 사고, 단순성 우선, 목표 기반 실행, 외과적 변경. 상세: AGENTS.md §2 절대 기준 3.

### 절대 기준 간 우선순위

> **절대 기준 1(품질)이 최상위이다. 절대 기준 2(SOT)와 절대 기준 3(CCP)은 품질을 보장하기 위한 동위 수단이다.**
> 어느 기준이든 절대 기준 1과 충돌하면 품질이 이긴다.

모든 절대 기준은 Phase 1(설계)과 Phase 2(구현) 모두에 적용됩니다.

---

## 4. 설계 원칙

절대 기준에 종속되는 하위 원칙입니다. 워크플로우를 설계하고 구현할 때 반드시 적용합니다.

### P1. 정확도를 위한 데이터 정제

큰 데이터를 AI에게 그대로 전달하면 노이즈로 정확도가 하락합니다.

- 각 단계에 **전처리(pre-processing)** 명시: 에이전트에게 넘기기 전 노이즈 제거
- 각 단계에 **후처리(post-processing)** 명시: 산출물을 다음 단계에 전달하기 전 정제
- 코드로 사전 계산 가능한 연관관계는 미리 처리 → AI가 판단·분석에 집중

```
Bad:  "수집된 전체 웹페이지 HTML을 에이전트에 전달"
Good: "Python script로 본문만 추출 → 핵심 텍스트만 에이전트에 전달"
```

### P2. 전문성 기반 위임 구조

각 작업을 가장 잘 수행할 수 있는 전문 에이전트에게 위임하여 품질을 극대화합니다.

```
Orchestrator (품질 조율 + 흐름 관리)
  ├→ Agent A: 전문 리서치
  ├→ Agent B: 심층 분석
  └→ Agent C: 검증 및 품질 게이트
```

### P3. 리소스 정확성

이미지, 파일, 외부 리소스가 필요한 단계에서는 정확한 경로를 명시합니다. placeholder 누락 불가.

### P4. 질문 설계 규칙

사용자에게 질문할 때:
- 최대 4개까지만
- 각 질문에 3개 정도의 선택지 제공
- 모호한 부분이 없으면 질문 없이 진행

---

## 5. Phase 1: 워크플로우 설계

### 5.1 워크플로우 생성 요청

Claude Code에서 다음과 같이 요청합니다:

```
워크플로우 만들어줘
```

또는:

```
자동화 파이프라인 설계해줘
```

`workflow-generator` 스킬이 자동으로 활성화됩니다.

### 5.2 두 가지 케이스

#### Case 1: 아이디어만 있는 경우

설명 문서 없이 아이디어만 있을 때. AI가 대화형 질문으로 요구사항을 수집합니다.

```
사용자: "블로그 컨텐츠를 자동으로 리서치하고 작성하는 워크플로우 만들어줘"

AI 질문 예시:
1. "어떤 결과물(output)을 만들고 싶으신가요?"
2. "주요 입력(input) 소스는 무엇인가요?"
3. "어느 단계에서 사람의 검토가 필요한가요?"
```

#### Case 2: 설명 문서가 있는 경우

PDF 등 구체적인 설명 문서를 첨부할 때. AI가 문서를 먼저 분석한 후 확인 질문을 합니다.

```
사용자: "이 PDF를 기반으로 워크플로우 만들어줘" + [파일 첨부]

AI 동작:
1. 문서 심층 분석 → 목적, 단계, 입출력, 제약 조건 추출
2. 분석 결과 요약 제시
3. 확인 질문 (짧게)
4. workflow.md 생성
```

문서 분석 시 AI는 `.claude/skills/workflow-generator/references/document-analysis-guide.md`의 체크리스트를 따릅니다.

### 5.3 생성되는 workflow.md 구조

모든 워크플로우는 3단계로 구성됩니다:

```markdown
# [워크플로우 이름]

## Overview
- Input: [입력 데이터]
- Output: [최종 산출물]
- Frequency: [실행 주기]

## Research
### 1. [리서치 단계]
- Pre-processing: [데이터 전처리 — P1]
- Agent: @[agent-name]
- Verification:
  - [ ] [구체적, 측정 가능한 기준 — 구조적 완전성/기능적 목표/데이터 정합성/파이프라인 연결]
  - [ ] [구체적, 측정 가능한 기준]
- Task: [수행 작업]
- Output: [산출물]
- Review: @reviewer | @fact-checker | @reviewer + @fact-checker | none
- Translation: @translator → [산출물].ko.md | none
- Post-processing: [산출물 정제 — P1]

## Planning
### 2. [기획 단계]
...
### 3. (human) [검토 단계]
- Action: [사람이 수행할 작업]

## Implementation
### 4. [실행 단계]
...

## Claude Code Configuration
### Sub-agents / Agent Team / Hooks / Slash Commands / Skills / MCP Servers / Task Management / SOT / Error Handling
```

표준 구조의 상세는 `.claude/skills/workflow-generator/references/workflow-template.md`를 참조하세요.

### 5.4 워크플로우 표기법

| 표기 | 의미 |
|-----|------|
| `(human)` | 사람의 개입/검토 필요 |
| `(team)` | Agent Team 병렬 실행 구간 |
| `(hook)` | 자동 검증/품질 게이트 |
| `@agent-name` | Sub-agent 호출 |
| `@translator` | 번역 서브에이전트 — `Translation` 필드에서 호출 |
| `@reviewer` | Adversarial Review — 코드/산출물 비판적 분석 (읽기 전용) |
| `@fact-checker` | Adversarial Review — 외부 사실 검증 (웹 접근) |
| `/command-name` | Slash command 실행 |
| `[skill-name]` | Skill 참조 |

### 5.5 (선택) Distill 검증

workflow.md 생성 후, 품질을 극대화하기 위한 점검 단계입니다. `prompt/distill-partner.md`의 인터뷰 프레임워크를 사용합니다.

| 점검 질문 | 목적 |
|----------|------|
| "이 단계가 최종 품질에 기여하는가?" | 품질에 무관한 단계만 제거 |
| "이 단계를 자동화하면 품질이 더 안정적인가?" | 자동화 기회 발굴 |
| "품질을 높이기 위해 추가해야 할 단계가 있는가?" | 검증/보강 단계 추가 |

> 이 단계는 선택 사항이지만, 절대 기준 1(품질 최우선)에 따라 권장됩니다.

---

## 6. Phase 2: 워크플로우 구현

workflow.md가 생성되면, 그 안에 정의된 구성요소를 실제로 만듭니다.

> **참고**: 아래 파일들은 **이 코드베이스로 새 프로젝트를 만들 때** 해당 프로젝트 내에 생성하는 것입니다.
> AgenticWorkflow 코드베이스 자체에는 이 파일들이 없는 것이 정상입니다.
> 코드베이스 자체는 스킬과 참조 자료만 포함하며, 구현 산출물은 각 프로젝트에 속합니다.

### 6.1 구현해야 할 구성요소

| workflow.md에 정의된 것 | 실제로 만들 파일 | 위치 (프로젝트 내) |
|----------------------|---------------|------|
| Sub-agents | `.md` 파일 | `.claude/agents/` |
| Slash commands | `.md` 파일 | `.claude/commands/` |
| Hooks | JSON 설정 | `.claude/settings.json` |
| 전처리/후처리 스크립트 | Python/Bash | `scripts/` |
| SOT 파일 | YAML/JSON | `.claude/state.yaml` |
| MCP Server 설정 | JSON | `.mcp.json` |
| Task 설계 | Task 정의 (`workflow.md` 내) | 워크플로우 단계 내 |

구현 패턴의 상세(Sub-agents frontmatter, Agent Team 아키텍처, Hook 이벤트, SOT 흐름 등)는
`.claude/skills/workflow-generator/references/claude-code-patterns.md`를 참조하세요.

### 6.2 Sub-agent 만들기

workflow.md에 `@researcher`가 정의되어 있다면:

```markdown
# .claude/agents/researcher.md
---
name: researcher
description: 웹 검색 및 자료 조사 전문
model: sonnet
tools: Read, Glob, Grep, WebSearch, WebFetch
maxTurns: 30
---

당신은 리서치 전문가입니다.
주어진 주제에 대해 체계적으로 자료를 수집하고 요약합니다.

## 작업 원칙
- 모든 정보에 출처(URL) 필수
- 핵심 인사이트를 구조화된 형식으로 정리
```

**모델 선택 기준:**

| 모델 | 적합한 작업 |
|-----|-----------|
| `opus` | 복잡한 분석, 연구, 작문 — 최고 품질이 필요한 핵심 작업 |
| `sonnet` | 수집, 스캐닝, 구조화 — 안정적 품질의 반복 작업 |
| `haiku` | 상태 확인, 단순 판단 — 복잡도가 낮은 보조 작업 |

### 6.3 Agent Team 설정 (병렬 협업)

workflow.md에 `(team)` 구간이 있다면:

```json
// .claude/settings.json — Agent Team 활성화
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

**팀 작업 흐름:**
```
Team Lead (조율 + SOT 쓰기)
  ├→ Teammate A → 산출물 파일 생성 (output-a.md)
  ├→ Teammate B → 산출물 파일 생성 (output-b.md)
  └→ Team Lead → state.yaml에 상태 병합 → 다음 단계
```

### 6.4 Hooks 설정 (자동화 게이트)

workflow.md에 `(hook)` 구간이 있다면:

```json
// .claude/settings.json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "prettier --write \"$(jq -r '.tool_input.file_path')\" 2>/dev/null || true",
          "statusMessage": "자동 포맷팅 중..."
        }]
      }
    ],
    "TaskCompleted": [
      {
        "hooks": [{
          "type": "agent",
          "prompt": "완료된 태스크의 산출물 품질을 검증하세요.",
          "timeout": 60
        }]
      }
    ]
  }
}
```

**Hook Exit Code:**

| 코드 | 동작 |
|------|------|
| `0` | 통과 |
| `2` | 차단 — 에이전트에 피드백 전달, 재작업 |

> **Context Preservation System**: 이 코드베이스 자체는 5개의 Hook(SessionStart, PostToolUse, Stop, PreCompact, SessionEnd)으로 컨텍스트 보존 시스템을 운용합니다. `/clear`, 컨텍스트 압축, 응답 완료 시 작업 내역을 자동 저장하고, 새 세션 시작 시 RLM 패턴(포인터 + 요약 + 완료 상태 + Git 상태 + 동적 RLM 쿼리 힌트)으로 이전 맥락을 복원합니다. PostToolUse는 9개 도구(Edit, Write, Bash, Task, NotebookEdit, TeamCreate, SendMessage, TaskCreate, TaskUpdate)를 추적합니다. Stop hook은 30초 throttling + 5KB growth threshold로 노이즈를 최소화하면서 Knowledge Archive(knowledge-index.jsonl, sessions/)에 세션별 phase(단계), phase_flow(전환 흐름), primary_language(주요 언어), error_patterns(Error Taxonomy 12패턴 분류 + resolution 매칭), tool_sequence(RLE 압축 도구 시퀀스), final_status(세션 종료 상태), tags(경로 기반 검색 태그), session_duration_entries(세션 길이) 메타데이터를 포함하여 기록합니다. 스냅샷의 설계 결정은 품질 태그 우선순위(`[explicit]` > `[decision]` > `[rationale]` > `[intent]`)로 정렬되어 노이즈가 제거되고, 스냅샷 압축 시 IMMORTAL 섹션이 우선 보존되며(압축 감사 추적 포함), 모든 파일 쓰기(스냅샷, 아카이브, 로그 절삭)에 atomic write(temp → rename) 패턴이 적용됩니다. P1 할루시네이션 봉쇄로 KI 스키마 검증, 부분 실패 격리, SOT 쓰기 패턴 검증(setup_init.py), SOT 스키마 검증(8항목 — S1-S6 기본 + S7 pacs 5필드 + S8 active_team 5필드), Adversarial Review P1 검증(validate_review.py — R1-R5), **시크릿 탐지**(output_secret_filter.py — 3-tier 추출, 25+ 패턴, PostToolUse Bash|Read), **보안 민감 파일 경고**(security_sensitive_file_guard.py — 12 패턴, PostToolUse Edit|Write)가 결정론적으로 수행됩니다. Safety Hook 3종에 대해 131개 자동화 테스트(44+44+43)가 확보되어 있습니다. SessionStart에서 Error→Resolution 매칭 결과가 자동 표면화되어 반복 에러 방지에 활용됩니다. 상세는 `AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md` §4.10을 참조하세요.

### 6.5 Slash Commands 만들기

workflow.md에 사용자 개입 지점이 있다면:

```markdown
# .claude/commands/review-output.md
---
description: "산출물 검토 및 승인/반려"
---

현재 단계의 산출물을 표시하고 사용자의 승인/반려를 대기합니다.
- 승인 시: 다음 단계로 자동 진행
- 반려 시: 피드백을 에이전트에 전달하여 재작업
```

### 6.6 SOT 파일 초기화

```yaml
# .claude/state.yaml
workflow:
  name: "my-workflow"
  current_step: 1
  status: "ready"
  outputs: {}
```

**SOT 규칙:**
- 쓰기: Orchestrator 또는 Team Lead만
- 읽기: 모든 에이전트 가능
- 팀원: 산출물 파일만 생성, SOT 직접 수정 금지

---

## 7. 실행 패턴

### 7.1 순차 파이프라인 (기본)

```
@agent-1 → @agent-2 → (human) 검토 → @agent-3
```

하나의 전문가가 깊은 맥락을 유지하며 일관되게 처리할 때.

### 7.2 병렬 분기 (Agent Team)

```
           ┌→ @teammate-a ─┐
Team Lead ─┤                ├→ (human) 검토 → @agent-merge
           └→ @teammate-b ─┘
```

서로 다른 전문 영역을 각각 최고 수준으로 처리할 때.

### 7.3 자동 검증 게이트 (Hook)

```
@agent-1 → [Hook: 품질 검증] → @agent-2
                ↓ 실패 시
           피드백 전달 → 재작업
```

코드 품질, 보안 검증, 표준 준수가 중요할 때.

### 7.4 조건 분기 (Conditional Flow)

```
@agent-1 → 조건 판단 → Path A: @agent-2a
                      → Path B: @agent-2b
                      → 합류 → @agent-3
```

이전 단계 결과에 따라 다른 경로로 진행할 때. 데이터 유형, 품질 수준, 사용자 선택에 따른 분기.

### 7.5 Team + Hook 결합 (고급 하이브리드)

```
Team Lead ─┬→ @researcher  [Hook: 출처 검증]
           ├→ @writer      [Hook: 품질 검증]
           └→ @fact-checker [Hook: 결과 병합]
                    ↓ 모두 완료
              (human) 검토 → @editor → 최종본
```

병렬 전문가 작업 + 자동 품질 게이트 + 사람 검토의 3중 품질 보장. 복잡한 워크플로우에서 최고 수준의 품질이 요구될 때.

---

## 8. 스킬 상세

### 8.1 workflow-generator

**트리거 키워드:** 워크플로우 만들어줘, 자동화 파이프라인 설계, 작업 흐름 정의

**진입점:** `.claude/skills/workflow-generator/SKILL.md`

**Reference 파일 가이드:**

| 파일 | 역할 | 사용 시점 |
|------|------|----------|
| `references/claude-code-patterns.md` | Sub-agents, Agent Teams, Hooks, SOT 등 구현 패턴 상세 | Phase 2에서 구성요소를 실제로 만들 때 |
| `references/workflow-template.md` | workflow.md의 표준 구조와 표기 규칙 | Phase 1에서 workflow.md 생성 시 |
| `references/document-analysis-guide.md` | 첨부 문서 분석 체크리스트와 출력 형식 | Phase 1 Case 2에서 문서 분석 시 |
| `references/context-injection-patterns.md` | 에이전트 프롬프트에 컨텍스트를 주입하는 패턴 가이드 | Phase 2에서 에이전트 프롬프트 설계 시 |
| `references/autopilot-decision-template.md` | Autopilot Decision Log의 표준 템플릿 | Autopilot 모드 실행 시 결정 기록 |
| `references/state.yaml.example` | SOT 파일 구조 예시 및 필드 설명 | Phase 2에서 SOT 초기화 시 |

### 8.2 doctoral-writing

**트리거 키워드:** 논문 스타일로 써줘, 학술적 글쓰기, 논문 문장 다듬기

**진입점:** `.claude/skills/doctoral-writing/SKILL.md`

**용도:**
- 학위논문 챕터 검토 및 작성
- 학술지 투고 논문 교정
- 연구보고서, 학술 발표문 작성

**Reference 파일 가이드:**

| 파일 | 역할 | 사용 시점 |
|------|------|----------|
| `references/clarity-checklist.md` | 명료성·간결성·학술적 엄밀성 평가 체크리스트 (VERIFY) | 원고 수정 후 검증할 때 |
| `references/common-issues.md` | 빈출 학술 글쓰기 문제 카탈로그 + 해결법 (WHAT) | 반복 오류 패턴을 식별할 때 |
| `references/before-after-examples.md` | 실제 박사 논문 수정 사례 (HOW — 실전) | 구체적 수정 예시가 필요할 때 |
| `references/discipline-guides.md` | 인문·사회·자연과학 분야별 관례 (WHERE — 분야 맥락) | 분야별 인용 스타일, 인칭, 구조 확인 시 |
| `references/korean-quick-reference.md` | 한국어 전용 ❌/✅ 변환 패턴 (HOW — 한국어) | 한국어 논문 작성 시 빠른 참조 |

> **파일 간 역할 분담**: 동일 주제(예: 피동태 남용)가 여러 파일에 등장하지만, 이는 중복이 아닌 역할 분담입니다.
> SKILL.md(WHY) → common-issues.md(WHAT) → korean-quick-reference.md / before-after-examples.md(HOW) → clarity-checklist.md(VERIFY)

---

## 9. 프롬프트 자료

| 파일 | 용도 | 워크플로우 내 사용 시점 |
|------|------|---------------------|
| `prompt/crystalize-prompt.md` | 긴 AI 에이전트 지침을 핵심만 남겨 압축 | **Phase 2**: Sub-agent `.md` 작성 시 프롬프트가 너무 길 때 |
| `prompt/distill-partner.md` | 에센스 추출 및 최적화 인터뷰 | **Phase 1**: Distill 검증 단계에서 워크플로우 품질 점검 시 |
| `prompt/crawling-skill-sample.md` | 네이버 뉴스 크롤링 차단 방어 스킬 샘플 | **Phase 2**: 새 스킬 파일 작성법을 참고할 때 |

---

## 10. 이론적 기반

`coding-resource/recursive language models.pdf`

장기기억(long-term memory) 구현에 필수적인 이론을 담은 논문입니다. 에이전트가 세션을 넘어 지식을 축적하고 활용하는 메커니즘의 이론적 토대입니다.

---

## 11. 다른 AI 도구에서 사용

이 프로젝트는 **Hub-and-Spoke 패턴**으로 어떤 AI CLI 도구를 사용하든 동일한 방법론이 자동 적용됩니다.

**Hub (방법론 SOT):** `AGENTS.md` — 모든 도구 공통의 절대 기준, 설계 원칙, 워크플로우 구조

**Spoke (도구별 확장):**

| AI CLI 도구 | 시스템 프롬프트 파일 | 자동 적용 |
|------------|-------------------|----------|
| Claude Code | `CLAUDE.md` | Yes — Hook, Skill, Context Preservation 등 전체 기능 지원 |
| Gemini CLI | `GEMINI.md` + `.gemini/settings.json` | Yes — `@AGENTS.md` import으로 Hub 직접 로드 |
| Codex CLI | `AGENTS.md` (직접 읽음) | Yes — 별도 Spoke 불필요 |
| Copilot CLI | `.github/copilot-instructions.md` | Yes — AGENTS.md도 자동 인식 |
| Cursor | `.cursor/rules/agenticworkflow.mdc` | Yes — `alwaysApply: true` 설정 |

사용법: 해당 AI CLI 도구로 이 프로젝트 디렉터리에 진입하면, 도구가 자동으로 해당 Spoke 파일을 읽고 AgenticWorkflow 방법론을 따릅니다. 별도 설정이 필요 없습니다.

> 상세 아키텍처: `AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md` §7.1 참조

---

## 12. Autopilot Mode

워크플로우를 무중단으로 실행하는 모드. 사람 개입 지점(`(human)`)을 자동 승인한다.

### 활성화

1. **워크플로우 선언**: Overview에 `- **Autopilot**: enabled`
2. **실행 시 지시**: "autopilot 모드로 워크플로우 실행해줘"
3. **실행 중 토글**: "autopilot 해제" / "autopilot 활성화"

### 동작 방식

| 체크포인트 | 일반 모드 | Autopilot 모드 |
|----------|---------|---------------|
| `(human)` Slash Command | 사용자 입력 대기 | 품질 극대화 기본값으로 자동 승인 |
| AskUserQuestion | 사용자 선택 대기 | 품질 극대화 옵션 자동 선택 |
| `(hook)` exit code 2 | 차단 | **동일하게 차단** |

### 4계층 품질 보장 (Quality Assurance Stack)

각 단계 완료 시 최대 4계층 검증을 통과해야 다음 단계로 진행합니다:

| 계층 | 이름 | 유형 | 수행 조건 |
|------|------|------|----------|
| **L0** | Anti-Skip Guard | 결정론적 | 항상 |
| **L1** | Verification Gate | 의미론적 | `Verification` 필드 있는 단계 |
| **L1.5** | pACS (Self-Rating) | 자기 평가 | pACS 활성 + Verification 통과 |
| **L2** | Adversarial Review (Enhanced) | 적대적 검토 | `Review:` 필드 지정 단계 |

**L0: Anti-Skip Guard (결정론적)**
1. 산출물 파일이 SOT `outputs`에 경로로 기록됨
2. 해당 파일이 디스크에 존재함
3. 파일 크기가 최소 100 bytes 이상 (의미 있는 콘텐츠)

**L1: Verification Gate (의미론적 — `Verification` 필드 있는 단계만)**
4. 산출물이 `Verification` 기준을 100% 달성했는지 에이전트가 자기 검증
5. 실패 기준 발견 시 재시도 전 **Abductive Diagnosis** 수행(P1 사전 증거 수집 → LLM 원인 분석 → P1 사후 검증) 후 진단 기반 재실행 (최대 10회 재시도, ULW 시 15회)
6. `verification-logs/step-N-verify.md`에 기준별 PASS/FAIL + Evidence 기록. 진단 로그는 `diagnosis-logs/step-N-{gate}-{timestamp}.md`에 기록

**L1.5: pACS — predicted Agent Confidence Score (자기 신뢰 평가)**
7. Verification 통과 후, 에이전트가 F(Factual Grounding)/C(Completeness)/L(Logical Coherence) 3차원으로 자기 산출물을 채점
8. pACS = min(F, C, L) — 가장 약한 차원이 전체 신뢰도 결정
9. RED(< 50) → **Abductive Diagnosis** 수행 후 진단 기반 재작업, YELLOW(50-69) → 경고 후 진행, GREEN(≥ 70) → 통과
10. `pacs-logs/step-N-pacs.md`에 Pre-mortem 답변 + 점수 기록

**L2: Adversarial Review (Enhanced — `Review:` 필드 지정 단계만)**
11. `@reviewer`(코드/산출물 비판적 분석) 또는 `@fact-checker`(외부 사실 검증) Sub-agent가 독립적으로 적대적 검토
12. P1 검증(`validate_review.py`)으로 리뷰 품질 결정론적 보장
13. `review-logs/step-N-review.md`에 기록
14. 상세: `AGENTS.md §5.5`

> `Verification` 필드가 없는 단계는 L0(Anti-Skip Guard)만으로 진행합니다 (하위 호환).
> pACS는 Verification 없이 단독 사용 불가 — L1 통과가 L1.5의 선행 조건입니다.

### Decision Log

자동 승인된 결정은 `autopilot-logs/step-N-decision.md`에 기록됩니다:

- **필수 필드**: step_number, checkpoint_type, decision, rationale, timestamp
- **선택 필드**: alternatives_considered, output_path, quality_assessment
- **표준 템플릿**: `.claude/skills/workflow-generator/references/autopilot-decision-template.md`

### 보장 사항

- 모든 단계 순서대로 완전 실행 (건너뛰기 없음)
- 모든 산출물은 사람 검토 시와 동일한 품질·분량
- Hook 자동 검증은 동일하게 동작
- 자동 승인 결정은 `autopilot-logs/`에 기록

### 런타임 강화 (Claude Code)

Claude Code에서는 Hook 시스템이 Autopilot의 설계 의도를 런타임에서 강화합니다:

| 시점 | 메커니즘 | 효과 |
|------|---------|------|
| 세션 시작/복원 | SessionStart가 Autopilot 실행 규칙 주입 | 매 세션 경계에서 실행 규칙을 컨텍스트에 포함 |
| 매 응답 후 | 스냅샷에 Autopilot 상태 섹션 보존 | 세션 경계에서 Autopilot 상태 유실 방지 (IMMORTAL 우선순위) |
| 응답 완료 | Stop hook이 Decision Log 누락 감지 | 자동 승인 패턴이 있는데 로그가 없으면 보완 생성 |
| 도구 사용 후 | PostToolUse가 autopilot_step 추적 (9개 도구) | 단계 진행 패턴을 work_log에 기록 (사후 분석) |

> 다른 AI 도구에서는 이 Hook 기반 강화가 없으므로, SOT와 Decision Log를 수동으로 관리해야 합니다.

---

## 12-1. ULW (Ultrawork) Mode

ULW는 Autopilot과 **직교하는 철저함 강도(thoroughness intensity) 오버레이**입니다. 프롬프트에 `ulw`를 포함하면 활성화됩니다.

- **Autopilot** = 자동화 축(HOW) — `(human)` 승인 건너뛰기
- **ULW** = 철저함 축(HOW THOROUGHLY) — 빠짐없이, 에러 해결까지 완벽 수행

### 2x2 매트릭스

|  | **ULW OFF** (보통) | **ULW ON** (최대 철저함) |
|---|---|---|
| **Autopilot OFF** | 표준 대화형 | 대화형 + Sisyphus Persistence(3회 재시도) + 필수 태스크 분해 |
| **Autopilot ON** | 표준 자동 워크플로우 | 자동 워크플로우 + Sisyphus 강화(재시도 3회) + 팀 철저함 |

### 2축 비교

| 축 | 관심사 | 활성화 | 비활성화 | 적용 범위 |
|----|--------|--------|---------|----------|
| **Autopilot** | 자동화(HOW) | SOT `autopilot.enabled: true` | SOT 변경 | 워크플로우 단계 |
| **ULW** | 철저함(HOW THOROUGHLY) | 프롬프트에 `ulw` | 암묵적 (새 세션 시 `ulw` 없으면 비활성) | 모든 작업 |

### 활성화

프롬프트에 `ulw`를 포함하면 자동으로 활성화됩니다:

```
ulw 이거 해줘
ulw 리팩토링해줘
```

새 세션에서 `ulw` 없이 프롬프트를 입력하면 자동으로 비활성화됩니다 (암묵적 해제). 명시적 해제 명령은 불필요합니다.

### 3가지 강화 규칙 (Intensifiers)

| 강화 규칙 | 설명 | 대화형 효과 | Autopilot 결합 효과 |
|----------|------|-----------|-------------------|
| **I-1. Sisyphus Persistence** | 최대 3회 재시도, 각 시도는 다른 접근법. 100% 완료 또는 불가 사유 보고 | 에러 시 3회까지 대안 시도 | 품질 게이트(Verification/pACS) 재시도 한도 10→15회 상향 |
| **I-2. Mandatory Task Decomposition** | TaskCreate → TaskUpdate → TaskList 필수 | 비-trivial 작업 시 태스크 분해 강제 | 변경 없음 (Autopilot은 이미 SOT 기반 추적) |
| **I-3. Bounded Retry Escalation** | 동일 대상 3회 초과 재시도 금지(품질 게이트는 별도 예산 적용) — 초과 시 사용자 에스컬레이션 | 무한 루프 방지 | Safety Hook 차단은 항상 존중 |

### 런타임 강화 (Claude Code)

Hook 시스템이 ULW의 3개 강화 규칙을 결정론적으로 강화합니다:

| 시점 | 메커니즘 | 효과 |
|------|---------|------|
| 트랜스크립트 파싱 | `detect_ulw_mode()` — word-boundary 정규식 | 오탐 없이 `ulw` 키워드 감지 |
| 매 응답 후 | 스냅샷에 ULW 상태 섹션 보존 (IMMORTAL) | 세션 경계에서 ULW 상태 유실 방지 |
| 세션 시작/복원 | SessionStart가 ULW 강화 규칙 주입 | `clear`/`compact`/`resume` 시 규칙 재주입 (`startup` 제외 — 암묵적 해제) |
| 매 응답 후 | `check_ulw_compliance()` — Compliance Guard | 3개 강화 규칙 준수를 결정론적으로 검증, 위반 시 IMMORTAL 경고 |
| 매 응답 후 | `generate_context_summary.py` — ULW 안전망 | 위반 시 stderr 경고 |
| 세션 종료 | Knowledge Archive에 `ulw_active: true` 태깅 | 크로스세션 RLM 쿼리 가능 |

### Autopilot과의 결합

Autopilot과 ULW가 동시에 활성화되면 **ULW가 Autopilot을 강화**합니다: 품질 게이트 재시도 한도를 10→15회로 상향하고, Safety Hook 차단은 항상 존중합니다.

> 다른 AI 도구에서는 ULW의 Hook 기반 강화가 없으므로, TaskCreate/TaskUpdate/TaskList를 수동으로 사용하여 ULW의 강화 규칙을 준수해야 합니다.

상세: `docs/protocols/ulw-mode.md`, `AGENTS.md §5.1.1`

---

## 13. Verification Protocol (작업 검증)

워크플로우 각 단계의 산출물이 **기능적 목표를 100% 달성했는지** 검증하는 프로토콜입니다.

### 왜 Verification Protocol이 필요한가

Anti-Skip Guard는 "파일이 존재하고 비어있지 않은가"만 확인합니다. 하지만 파일이 존재해도 내용이 불완전할 수 있습니다. Verification Protocol은 이 간극을 메웁니다.

```
Anti-Skip Guard: "파일 있음, 2,847 bytes" → PASS (물리적)
Verification Gate: "경쟁사 3곳 중 2곳만 분석됨" → FAIL (내용적)
  → 누락된 1곳 분석 재실행 → PASS → 진행
```

### Verification 필드 작성법

워크플로우의 각 단계에 `Verification` 필드를 `Task` 앞에 정의합니다:

```markdown
### 1. 경쟁사 리서치
- **Agent**: `@researcher`
- **Verification**:
  - [ ] 경쟁사 3곳 이상의 가격 데이터 포함 (각 3개 이상 tier + 정확한 금액)
  - [ ] 모든 URL이 유효하며 placeholder/example.com 없음
  - [ ] Step 4 분석 에이전트가 필요로 하는 competitor_name, pricing_tiers 필드 포함
- **Task**: 대상 경쟁사의 가격 정책 및 기능 비교 데이터 수집
- **Output**: `research/competitor-analysis.md`
```

### 4가지 기준 유형

| 유형 | 검증 대상 | 좋은 예 | 나쁜 예 |
|------|---------|--------|--------|
| **구조적 완전성** | 산출물 내부 구조 | "5개 섹션 모두 포함" | "잘 구성됨" |
| **기능적 목표** | 작업 목표 달성 | "각 경쟁사 가격에 3개 이상 tier" | "가격 정보 있음" |
| **데이터 정합성** | 데이터 정확성 | "모든 URL 유효, placeholder 없음" | "링크 확인" |
| **파이프라인 연결** | 다음 단계 입력 호환 | "Step 4가 필요로 하는 필드 포함" | "다음 단계 호환" |

> **핵심 규칙**: 각 기준은 **제3자가 기계적으로 참/거짓 판정 가능**해야 합니다. "좋은 품질", "충분한 깊이" 같은 주관적 판단은 기준으로 사용하지 않습니다.

### 실행 흐름

```
에이전트가 Verification 기준 읽기 (Task보다 먼저)
  ↓
단계 실행 — 완전한 품질로 산출물 생성
  ↓
Anti-Skip Guard — 파일 존재 + ≥ 100 bytes
  ↓
Verification Gate — 산출물을 각 기준 대비 자기 검증
  ├─ 모든 기준 PASS → verification-logs/step-N-verify.md 생성 → 진행
  └─ FAIL → 실패 부분만 재실행 (최대 10회) → 초과 시 사용자 에스컬레이션
```

### Team 단계의 3계층 검증

`(team)` 단계에서는 L1 → L1.5 → L2 3계층으로 동작합니다:

| 계층 | 수행자 | 검증 대상 | SOT 쓰기 |
|------|--------|---------|---------|
| **L1** | Teammate (자기 검증) | 자기 Task의 검증 기준 | **없음** — 세션 내부 완결 |
| **L1.5** | Teammate (pACS) | 자기 Task 산출물의 신뢰도 | **없음** — 점수를 보고 메시지에 포함 |
| **L2** | Team Lead (종합 검증 + 단계 pACS) | 단계 전체의 검증 기준 | **있음** — SOT outputs + pacs 갱신 |

```
Teammate: Task 실행 → 자기 검증 (L1) → PASS → pACS 자기 채점 (L1.5) → Team Lead에 보고
                                      → FAIL 시 자체 수정 후 재검증

Team Lead: Teammate 산출물 + pACS 수신 → 단계 기준 대비 종합 검증 + 단계 pACS 산출 (L2)
                                       → PASS 시 SOT 갱신
                                       → FAIL 또는 Teammate pACS RED 시 → 구체적 피드백 + 재실행 지시
```

### 하위 호환

`Verification` 필드가 없는 기존 워크플로우는 **기존 동작(Anti-Skip Guard만)을 그대로 유지**합니다. 새로운 워크플로우 생성 시에는 `Verification` 필드를 필수로 포함합니다.

상세: `AGENTS.md §5.3`

---

## 14. 이중언어 워크플로우 (English-First + Korean Translation)

워크플로우 실행 시 모든 에이전트는 **영어로 작업**하고, 텍스트 산출물에 대해 `@translator` 서브에이전트가 한국어 번역을 생성합니다.

### 왜 English-First인가

| 이유 | 설명 |
|------|------|
| AI 성능 최적화 | 대부분의 LLM은 영어에서 가장 높은 분석·추론 품질을 보임 |
| 번역 품질 확보 | 전문 번역 에이전트가 용어 일관성 + 자기 검토를 수행 |
| 이중 산출물 | 영어 원본(기록·재사용) + 한국어 번역(소통·보고)을 모두 확보 |

### 언어 경계

| 구간 | 언어 |
|------|------|
| `workflow.md` (설계 문서) | 한국어 — 사용자가 읽는 설계도 |
| 에이전트 실행 + 산출물 | 영어 — AI 성능 최적화 |
| 번역 산출물 (`*.ko.md`) | 한국어 — `@translator`가 생성 |

### Translation 필드

워크플로우의 각 단계에 `Translation` 필드가 포함됩니다:

```markdown
- **Translation**: `@translator` → research-notes.ko.md    # 텍스트 산출물 → 번역
- **Translation**: none                                     # 코드/데이터 → 번역 불필요
```

**번역 대상 판별:**

| 산출물 유형 | Translation 설정 |
|------------|-----------------|
| 텍스트 문서 (`.md`, `.txt`) | `@translator` |
| 코드/스크립트 (`.py`, `.js`) | `none` |
| 데이터 파일 (`.json`, `.csv`) | `none` |
| 설정 파일 (`.yaml`, `.json`) | `none` |

### 용어 일관성 — Glossary

`@translator`는 `translations/glossary.yaml`을 RLM 외부 영속 상태로 사용합니다:

- 매 번역 시 기존 용어를 로드하여 일관성 유지
- 새 용어 발견 시 glossary에 추가
- 워크플로우 전체에 걸쳐 동일 용어가 동일 번역으로 유지됨

### SOT 기록

번역 결과는 SOT에 `step-N-ko` 키로 기록됩니다:

```yaml
outputs:
  step-1: "research-notes.md"       # 영어 원본
  step-1-ko: "research-notes.ko.md" # 한국어 번역
```

> 기존 Hook 코드(`restore_context.py`)의 `.isdigit()` 가드가 `step-N-ko` 키를 자동으로 건너뛰므로, Hook 코드 변경 없이 호환됩니다.

---

## 15. 전체 요약: 워크플로우 설계 → 구현 체크리스트

### Phase 1: 설계

- [ ] 아이디어 또는 설명 문서 준비
- [ ] `workflow-generator` 스킬로 `workflow.md` 생성
- [ ] 생성된 워크플로우 검토 — 단계, 에이전트, 사람 개입 지점, Verification 기준 확인
- [ ] (선택) Distill 검증 — `prompt/distill-partner.md`로 품질 점검

### Phase 2: 구현

> 아래 파일들은 새 프로젝트 내에 생성합니다 (이 코드베이스 자체가 아님).

- [ ] Sub-agent `.md` 파일 생성 (`.claude/agents/`)
- [ ] Slash command `.md` 파일 생성 (`.claude/commands/`)
- [ ] Hooks 설정 (`.claude/settings.json`)
- [ ] 전처리/후처리 스크립트 작성 (`scripts/`)
- [ ] SOT 파일 초기화 (`.claude/state.yaml`)
- [ ] MCP Server 연동 설정 (`.mcp.json`, 필요 시)
- [ ] Agent Team 설정 (병렬 협업 필요 시)
- [ ] Task 설계 (Agent Team 사용 시 — workflow.md 내 Task 정의)
- [ ] Verification 기준 정의 (각 단계별 구체적·측정 가능한 기준 — §13 참조)
- [ ] Review 필드 설정 (고위험 단계에 `@reviewer` / `@fact-checker` 지정 — `AGENTS.md §5.5` 참조)
- [ ] Error Handling 설정 (재시도, 롤백, 에스컬레이션 규칙)
- [ ] Translation 필드 설정 (각 단계별 `@translator` 또는 `none`)
- [ ] `translations/glossary.yaml` 초기화 (번역 대상 단계가 있는 경우)

### 검증

- [ ] 워크플로우 전체 실행 테스트
- [ ] 각 단계의 산출물 품질 확인 (절대 기준 1)
- [ ] Verification Gate 정상 동작 확인 (`verification-logs/step-N-verify.md` 생성 확인)
- [ ] SOT 파일 일관성 확인 (절대 기준 2)
- [ ] 번역 파일(`*.ko.md`) 존재 + 용어 일관성 확인
- [ ] Hook 게이트 정상 동작 확인
