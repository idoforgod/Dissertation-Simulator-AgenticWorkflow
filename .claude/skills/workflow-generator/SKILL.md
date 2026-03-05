---
name: workflow-generator
description: Claude Code용 워크플로우(workflow.md) 자동 생성 스킬. 사용자가 "워크플로우 만들어줘", "workflow 생성", "자동화 파이프라인 설계", "작업 흐름 정의" 등을 요청할 때 사용. 대화를 통해 사용자의 의도를 파악하고, Research → Planning → Implementation 3단계 구조의 workflow.md를 생성. Claude Code의 sub-agents, agent teams(swarm), hooks, skills, slash commands, MCP servers를 활용한 구현 설계 포함.
---

# Workflow Generator

Claude Code용 워크플로우 정의 파일(workflow.md)을 설계하고 생성하는 스킬.

## 사용 케이스 판별

**먼저 사용자의 상황 파악:**

| 조건 | 케이스 | 진행 방식 |
|------|--------|----------|
| PDF/문서 첨부됨 | Case 2 | 문서 분석 우선 → 확인 대화 |
| 아이디어만 언급 | Case 1 | 대화형 질문으로 요구사항 수집 |

---

## Case 1: 아이디어만 있는 경우

사용자가 막연한 아이디어만 가지고 있을 때.

### Step 1: 목적 파악

다음 질문으로 워크플로우 목적 도출:

1. "어떤 결과물(output)을 만들고 싶으신가요?"
2. "이 워크플로우가 해결해야 할 문제는 무엇인가요?"
3. "주요 입력(input) 소스는 무엇인가요?"

### Step 2: 단계 정의

각 Phase별 구체적 단계 도출:

1. "Research 단계에서 어떤 정보를 수집해야 하나요?"
2. "Planning 단계에서 어떤 검토/승인이 필요한가요?"
3. "최종 산출물의 형태와 품질 기준은 무엇인가요?"

### Step 3: 휴먼-인-더-루프 식별

1. "어느 단계에서 사람의 검토/승인이 필요한가요?"
2. "자동화해도 되는 단계와 반드시 확인이 필요한 단계를 구분해주세요."

### Step 4: 구현 설계 → 생성

요구사항 수집 완료 후 workflow.md 생성.

---

## Case 2: 설명 문서가 있는 경우

사용자가 PDF 등 구체적인 설명 문서를 첨부했을 때.

### Step 1: 문서 심층 분석

**반드시 문서를 먼저 꼼꼼히 읽고 다음을 추출:**

```
1. 핵심 목적: 이 워크플로우가 달성하려는 최종 목표
2. 주요 단계: 문서에서 언급된 프로세스/단계들
3. 입출력 정의: 각 단계의 input/output
4. 기술적 요구사항: 필요한 도구, API, 데이터 소스
5. 제약 조건: 품질 기준, 시간 제한, 의존성
6. 휴먼-인-더-루프: 사람 개입이 필요한 지점
```

### Step 2: 분석 결과 공유

문서 분석 후 사용자에게 이해한 내용 요약 제시:

```markdown
## 문서 분석 결과

**워크플로우 목적**: [추출한 목적]

**파악된 주요 단계**:
1. [단계1]: [설명]
2. [단계2]: [설명]
...

**식별된 휴먼-인-더-루프 지점**:
- [지점1]: [이유]

**기술적 구현 방향**:
- Sub-agents: [에이전트 목록 — 단일 세션 내 위임]
- Agent Team: [팀 구성 — 독립 세션 간 병렬 협업이 필요한 경우]
- Hooks: [자동화 트리거 — 품질 게이트, 포맷팅, 검증]
- 필요 도구: [도구/MCP 목록]

**확인이 필요한 사항**:
1. [질문1]
2. [질문2]
```

### Step 3: 확인 대화

분석 결과를 바탕으로 짧은 확인 질문:

- "제가 파악한 내용이 맞나요?"
- "추가하거나 수정할 부분이 있으신가요?"
- "[불명확한 부분]에 대해 좀 더 설명해주시겠어요?"

### Step 4: 생성

확인 완료 후 workflow.md 생성.

---

## 절대 기준

### 절대 기준 1: 최종 결과물의 품질

> **속도와 토큰 비용은 완전히 무시한다.**
> 모든 설계 의사결정의 절대 기준은 **최종 결과물의 '품질'과 '최고 수준의 질적 결과물'**이다.
> 단계를 줄여서 빠르게 만드는 것보다, 단계를 늘려서라도 품질을 높이는 방향을 선택한다.
> 품질 향상을 위한 단계 추가로 SOT 상태 복잡도가 증가하더라도, 이는 감수한다 (절대 기준 1 > 절대 기준 2).

### 절대 기준 2: 단일 파일 SOT + 계층적 메모리 구조

> **단일 파일 SOT(Single Source of Truth) + 계층적 메모리 구조 설계 아래서, 수십 개의 에이전트가 동시에 작동해도 데이터 불일치가 발생하지 않는다.**

이 규칙의 설계 함의:
- **상태 관리**: 워크플로우의 모든 공유 상태는 **단일 파일**(예: `state.json`)에 집중한다. 여러 파일에 상태를 분산시키지 않는다.
- **메모리 계층**: 에이전트별 로컬 메모리(작업 컨텍스트)와 전역 메모리(공유 상태)를 명확히 분리한다.
- **쓰기 권한**: SOT 파일에 대한 쓰기 권한은 Orchestrator 또는 지정된 단일 에이전트만 갖는다. 다른 에이전트는 읽기 전용으로 접근하거나, 결과를 Orchestrator에게 전달하여 병합한다.
- **충돌 방지**: 병렬 에이전트(Agent Team/Swarm)가 동시에 같은 데이터를 수정하는 구조를 설계하지 않는다.

```
Bad:  Agent A → state.json 직접 수정
      Agent B → state.json 직접 수정  → 데이터 충돌/불일치
Good: Agent A → 결과를 Orchestrator에 보고
      Agent B → 결과를 Orchestrator에 보고
      Orchestrator → state.json에 병합 기록  → 단일 쓰기 지점, 불일치 없음
```

### 절대 기준 3: 코드 변경 프로토콜 (Code Change Protocol)

> **워크플로우 구현(Phase 2)에서 코드를 작성·수정할 때, 반드시 의도 파악 → 영향 범위 분석 → 변경 설계 3단계를 수행한다.**

워크플로우의 구성요소(Sub-agent, Hook, SOT, Slash Command, MCP)는 서로 의존 관계에 있다. 한 구성요소의 변경이 다른 구성요소에 파급 효과를 일으킬 수 있으므로, 코드 변경 전 반드시 영향 범위를 분석한다.

- **Step 1 — 의도 파악**: 변경 목적과 제약 조건을 정확히 파악한다.
- **Step 2 — 영향 범위 분석**: 직접 의존하는 모듈, 호출 관계, SOT 파일, 설정/환경, 테스트 코드, 문서를 점검한다.
- **Step 3 — 변경 설계**: 변경 순서를 설계하고, 영향받는 모든 파일의 수정 계획을 수립한 후 실행한다.

> 비례성 규칙: 워크플로우 설계 단계(Phase 1)의 문서 수정은 경미 변경(Step 1만), 구현 단계(Phase 2)의 코드 변경은 표준/대규모 변경(전체 3단계)으로 분류한다.

### 절대 기준 간 우선순위

> **절대 기준 1(품질)이 최상위이다. 절대 기준 2(SOT)와 절대 기준 3(CCP)은 품질을 보장하기 위한 동위 수단이다.**
> SOT 구조를 지키기 위해 최종 결과물의 품질이 저하되는 설계는 허용하지 않는다.
> CCP를 준수하기 위해 최종 결과물의 품질이 저하되는 설계는 허용하지 않는다.

모든 절대 기준은 아래 설계 원칙보다 상위에 있다. 설계 원칙 간 충돌 시 항상 절대 기준이 우선하고, 절대 기준 간 충돌 시 **절대 기준 1 > (절대 기준 2, 절대 기준 3)** 순서를 따른다.

---

## 유전 프로토콜 (Genome Inheritance Protocol)

> **자식을 낳을 때 부모의 전체 게놈을 구조적으로 유전한다. 유전 없는 자식 생성은 불허한다.**

AgenticWorkflow는 자식 워크플로우를 생성하는 부모 유기체다. `workflow-generator`가 생산 라인이며, 이 라인에서 태어나는 모든 자식은 부모의 전체 게놈을 `Inherited DNA` 섹션으로 내장한다.

### 유전 메커니즘

| 부모 게놈 (DNA) | 자식에 내장되는 형태 |
|---------------|-------------------|
| 절대 기준 3개 | `Inherited DNA` 섹션 — 도메인별 맥락화 |
| SOT 패턴 | Configuration의 `state.yaml` + 단일 쓰기 지점 |
| 3단계 구조 | Research → Planning → Implementation 워크플로우 구조 |
| 4계층 검증 | `Verification` + `pACS` 필드 |
| P1 봉쇄 | Hook 기반 결정론적 검증 |
| Safety Hook | PreToolUse 차단 패턴 |
| Adversarial Review | `Review:` 필드 — `@reviewer` / `@fact-checker` |
| Decision Log | `autopilot-logs/` 패턴 |
| Context Preservation | 세션 간 기억 보존 패턴 |

### 발현 vs 유전

동일한 게놈을 가진 세포가 서로 다른 기능을 수행하듯, 자식 시스템들은 같은 DNA 위에서 **도메인에 맞게 발현**된다. 예를 들어 연구 자동화 시스템에서는 Research 단계의 유전자가 강하게 발현되고, 소프트웨어 개발 자동화에서는 CCP(코드 변경 프로토콜)의 유전자가 강하게 발현된다. 목적이 달라도 게놈은 동일하다.

### 생성 시 의무 사항

1. 모든 workflow.md에 `Inherited DNA (Parent Genome)` 섹션을 포함한다 (템플릿 참조)
2. 모든 state.yaml에 `parent_genome` 메타데이터를 포함한다 (SOT 템플릿 참조)
3. 자식의 에이전트 정의가 부모의 품질 기준(절대 기준 1)을 반영한다

상세: `soul.md §0`, `AGENTS.md §1 존재 이유`.

---

## 설계 원칙 (필수 준수)

워크플로우 설계 시 반드시 적용해야 할 원칙. 단, 모든 원칙은 **모든 절대 기준(1. 품질 최우선, 2. 단일 파일 SOT, 3. 코드 변경 프로토콜)**에 종속된다.

### P1. 정확도를 위한 데이터 정제

큰 데이터를 AI에게 그대로 전달하면 노이즈가 많아 **정확도가 하락**한다. 에이전트가 핵심에 집중할 수 있도록 데이터를 정제한다.

- 각 단계에 **데이터 전처리(pre-processing)** 명시: AI에게 넘기기 전에 Python script 등으로 노이즈 제거 → **분석 정확도 향상**
- 각 단계에 **후처리(post-processing)** 명시: 산출물을 다음 단계에 전달하기 전에 정제 → **다음 단계 품질 향상**
- 데이터의 연관관계도 **code-level에서 사전 계산** 가능한 것은 미리 처리 → **AI가 판단·분석에 집중**

```
Bad:  "수집된 전체 웹페이지 HTML을 에이전트에 전달" → 노이즈로 분석 품질 저하
Good: "Python script로 본문만 추출 → 핵심 텍스트만 에이전트에 전달" → 분석 정확도 향상
```

### P2. 전문성 기반 위임 구조

각 작업을 **가장 잘 수행할 수 있는 전문 에이전트**에게 위임하여 품질을 극대화. Orchestrator는 전체 품질을 조율하고, 전문 에이전트는 각자의 영역에 깊이 집중.

```
Orchestrator (품질 조율 및 전체 흐름 관리)
  ├→ Sub-agent A: 전문 리서치 (해당 도메인에 최적화)
  ├→ Sub-agent B: 심층 분석 (분석에만 집중)
  └→ Skill C: 검증된 패턴 적용 (품질 보장된 재사용 로직)
```

### P3. 이미지/리소스 정확성

이미지 리소스가 필요한 단계에서는 **정확한 다운로드 경로** 명시. placeholder도 모두 추출해야 하며, 누락 불가.

### P4. 질문 설계 규칙

사용자에게 질문 시:
- 최대 4개까지만 질문
- 각 질문에 sub-agent/skill/추천 옵션 등 **3개 정도의 선택지** 제공
- 모호한 부분이 없으면 질문 없이 진행

---

## 워크플로우 기본 구조

모든 워크플로우는 3단계로 구성:

1. **Research**: 정보 수집 및 분석
2. **Planning**: 계획 수립 및 구조화
3. **Implementation**: 실제 실행 및 산출물 생성

**각 단계에 반드시 포함할 항목:**
- 수행 작업 (Task)
- 담당 에이전트 (@agent)
- 데이터 전처리 (Pre-processing) — 정확도 향상을 위한 노이즈 제거 (P1)
- 산출물 (Output)
- 적대적 검토 (Review) — `@reviewer`, `@fact-checker`, 또는 `none` (AGENTS.md §5.5)
- 번역 (Translation) — `@translator` 또는 `none` (텍스트 산출물만 대상)
- 후처리 (Post-processing) — 다음 단계 품질 보장을 위한 정제 (P1)

## Claude Code 구성요소 매핑

| 워크플로우 요소 | Claude Code 구현 | 선택 기준 |
|---------------|-----------------|----------|
| 단일 작업 위임 | Sub-agent (`.claude/agents/*.md`) | 전문 영역에 깊이 집중, 품질 극대화 |
| 대규모 병렬 협업 | Agent Team/Swarm (`TeamCreate`) | 독립적 작업을 여러 세션에서 동시 수행 |
| 사람 개입 단계 | Slash command (`.claude/commands/`) | 검토/승인/선택 등 사용자 인터랙션 |
| 자동화 검증/트리거 | Hooks (`settings.json`) | 포맷팅, 품질 게이트, 보안 검증 |
| 재사용 로직 | Skill (`.claude/skills/`) | 도메인 지식, 반복 패턴 |
| 외부 연동 | MCP Server | API, DB, 외부 서비스 통합 |

### Sub-agent vs Agent Team 선택 기준

> **선택의 유일한 기준은 '어떤 구조가 최종 결과물의 품질을 가장 높이는가'이다.**
> 병렬 처리가 빠르다는 이유로 Agent Team을 선택하지 않는다.
> 토큰을 적게 쓴다는 이유로 Sub-agent를 선택하지 않는다.

| 상황 | 선택 | 품질 근거 |
|------|------|----------|
| 하나의 전문가가 깊은 맥락을 유지하며 처리해야 최고 품질 | **Sub-agent** | 단일 컨텍스트 내에서 일관된 깊이 유지 |
| 서로 다른 전문 영역을 각각 최고 수준으로 처리해야 최고 품질 | **Agent Team** | 각 전문가가 독립 컨텍스트에서 자기 영역에 100% 집중 |
| 다관점 분석/교차 검증이 품질을 높이는 경우 | **Agent Team** | 독립적 관점이 결합되어 단일 에이전트보다 풍부한 결과 |
| 단계 간 맥락 전달의 정확성이 품질의 핵심인 경우 | **Sub-agent 순차 호출** | 단계별 산출물을 정확하게 다음 단계에 전달 |

> **절대 기준 2 필수 동반 사항**: Agent Team 선택 시 반드시 SOT 설계를 함께 정의한다 — SOT 파일 위치, Team Lead의 단일 쓰기 권한, 팀원의 산출물 파일 생성 규칙. SOT 설계 없는 Agent Team은 원칙적으로 허용하지 않는다. 상세: `references/claude-code-patterns.md` 상태 관리 섹션 참조.
>
> **절대 기준 1 우선 예외**: 완전 독립 병렬 작업(에이전트 간 공유 상태가 없고, 서로의 산출물을 참조하지 않는 경우)에서 SOT 설계가 품질에 기여하지 않음을 명시적으로 입증한 경우에 한해, SOT를 경량화할 수 있다. 이 판단은 반드시 워크플로우 설계 시 문서화한다.

## 참조 문서

- workflow.md 템플릿: `references/workflow-template.md`
- Claude Code 구현 패턴 (Sub-agents, Teams, Hooks): `references/claude-code-patterns.md`
  - Anti-Skip Guard Protocol: §Anti-Skip Execution Protocol (산출물 검증 — 100 bytes 최소 크기)
  - Autopilot Execution Checklist: §Autopilot + Agent Team 통합 체크리스트
  - SOT 상태 관리: §SOT State Management Protocol
- 문서 분석 가이드 (Case 2): `references/document-analysis-guide.md`
- 컨텍스트 주입 패턴 (Sub-agent/Team 입력 전달): `references/context-injection-patterns.md`
- SOT 템플릿 (state.yaml 부트스트랩): `references/state.yaml.example`
- Autopilot Decision Log 템플릿: `references/autopilot-decision-template.md`

## 최종 생성 절차

1. 케이스 판별 (문서 유무)
2. Case 1: 대화로 요구사항 수집 / Case 2: 문서 분석 → 확인 대화
3. **Genome Inheritance**: `Inherited DNA (Parent Genome)` 섹션을 workflow.md에 포함 (유전 프로토콜 — `references/workflow-template.md` 참조). `parent_genome.version`은 워크플로우 생성 시점의 날짜(YYYY-MM-DD)를 사용한다. CCP 맥락화 시 코딩 기준점(CAP-1~4)을 포함한다.
4. 설계 원칙 P1~P4 적용하며 3단계 구조로 작업 정의
   - 도메인 지식 구조(DKS) 필요성을 평가한다: 의학·법률·경쟁 분석 등 도메인 특화 추론이 필요한 워크플로우는 Research 단계에 DKS 구축 단계를 포함한다. DKS를 사용하는 워크플로우는 관련 단계의 Post-processing에 `python3 .claude/hooks/scripts/validate_domain_knowledge.py --project-dir . --check-output --step N`을 포함한다. 상세: `AGENTS.md §5.3 DKS`
5. 각 단계에 데이터 전처리/후처리 명시 (P1)
6. 휴먼-인-더-루프 지점 표시
7. **각 단계에 `Verification` 필드 정의** (AGENTS.md §5.3 — 필수):
   - `Verification` 필드는 `Task` 필드보다 **앞에** 배치 (에이전트가 먼저 인식)
   - **모든 에이전트 실행 단계에 `Verification` 필수** — Research/Planning/Implementation 구분 없음 (Research 단계도 "완전성" 검증 필요: 예 "5개 경쟁사 모두 분석 완료")
   - `(human)` 단계만 예외 — 사람이 검증자이므로 `Verification` 필드 불필요
   - 각 기준은 **제3자가 참/거짓 판정 가능한 구체적 문장**으로 작성
   - 5가지 기준 유형을 조합하여 포함:
     - **구조적 완전성**: 산출물 내부 구조 → "5개 섹션 모두 포함", "각 항목에 3개 이상 하위 항목"
     - **기능적 목표**: 작업 목표 달성 → "경쟁사 3곳 이상의 가격 데이터", "모든 API endpoint 구현"
     - **데이터 정합성**: 데이터 정확성 → "모든 URL 유효, placeholder 없음", "수치 데이터 출처 명시"
     - **파이프라인 연결**: 다음 단계 입력 호환 → "Step N이 필요로 하는 필드 포함", "출력 형식이 Step N+1 입력과 일치"
     - **교차 단계 추적성**: 이전 단계 데이터 논리적 도출 → "분석 주장의 80% 이상이 [trace:step-N] 마커로 출처 추적 가능"
   - **Tip**: 기준 서술 시 `(source: Step N)` 어노테이션을 활용하면, Verification 기준 자체가 이전 단계를 명시적으로 참조하여 진단 시 상류 영향 분석을 자동화할 수 있다. 예: "경쟁사 분석 데이터가 Step 2 연구 결과를 반영 (source: Step 2)"
8. 각 단계에 **Review 필드** 설정 (AGENTS.md §5.5 — 선택적):
   - 연구/분석 산출물 (사실 검증 필요) → `@fact-checker`
   - 코드/기술 산출물 (로직/완전성 검증 필요) → `@reviewer`
   - 고위험 단계 (양쪽 모두) → `@reviewer + @fact-checker`
   - 저위험 또는 중간 단계 → `none` (L1.5까지만)
   - **실행 순서**: Review PASS → Translation (Review FAIL 상태에서 번역 금지)
9. 각 단계에 **Translation 필드** 설정 — 텍스트 산출물(`.md`, `.txt`)은 `@translator`, 코드/데이터/설정은 `none`
10. Claude Code 구현 설계 추가 (Sub-agents, Teams, Hooks, Commands, Skills, MCP)
   - **Context Injection 패턴 선택** (각 에이전트 단계별):
     - 입력 < 50KB → Pattern A (Full Delegation — 파일 경로 전달)
     - 입력 50-200KB + 부분 관련 → Pattern B (Filtered — Pre-processing 스크립트로 정제 후 전달)
     - 입력 > 200KB 또는 분할 필요 → Pattern C (Recursive Decomposition — 청크 병렬 처리)
     - 절대 기준 1 우선: 크기와 무관하게 필터링이 품질을 높이면 Pattern B 선택
     - 상세: `references/context-injection-patterns.md`
   - **Agent Team 사용 시 SOT 설계 필수** (절대 기준 2):
     - SOT 파일 위치 (`.claude/state.yaml`), Team Lead 단일 쓰기 권한, 팀원 산출물 규칙
     - `active_team` 스키마: name, status, tasks_completed/pending, completed_summaries
     - SOT 갱신 4시점: TeamCreate 직후 → Teammate 완료 시 → 전체 완료 시 → TeamDelete 직후
     - 상세: `references/workflow-template.md §Agent Team 사용 시 SOT 스키마`
   - **Checkpoint Pattern**: 각 Task의 예상 턴 수를 평가하여 `standard`(≤ 10 턴) 또는 `dense`(> 10 턴) 패턴을 선택. 상세: `references/claude-code-patterns.md §DCP`
11. **English-First 실행 원칙 적용** (AGENTS.md §5.2):
   - 모든 에이전트 Task 설명과 프롬프트는 **영어**로 작성 (AI 성능 극대화 — 절대 기준 1)
   - 사용자 대화(워크플로우 설계)는 한국어, 에이전트 실행은 영어
   - `@translator` 서브에이전트가 영어→한국어 번역 담당 (Translation 필드로 명시)
12. workflow.md 파일 생성
13. **(선택) Distill 검증**: 생성된 워크플로우의 품질 극대화를 위한 점검
    - "이 단계가 최종 품질에 기여하는가?" — 품질에 무관한 단계만 제거
    - "이 단계를 자동화하면 품질이 더 안정적인가?" — 자동화 기회 발굴
    - "품질을 높이기 위해 추가해야 할 단계가 있는가?" — 검증/보강 단계 추가
    - "각 `Verification` 기준이 **파이프라인 연결**을 포함하는가?" — 단계 간 데이터 흐름 검증
    - **DNA Inheritance P1 검증**: `python3 .claude/hooks/scripts/validate_workflow.py --workflow-path ./workflow.md` 실행 → W1-W9 통과 확인 (W9: English-First Execution 필수)
    - 참조: `prompt/distill-partner.md`

## Autopilot Mode 지원

생성하는 workflow.md에 Autopilot Mode 필드를 포함한다.

- Overview 섹션에 `- **Autopilot**: [disabled|enabled]` 추가 (기본값: disabled)
- 사용자가 "자동으로 실행", "무중단 실행" 등을 요청하면 `enabled`로 설정
- `(human)` 단계 설계 자체는 변경하지 않음 — Autopilot은 실행 모드이지 설계 변경이 아님
- 선택 사항: 각 `(human)` 단계에 `Autopilot Default` 필드로 자동 승인 시 기본 동작 명시

## pACS 지원

생성하는 workflow.md에 pACS(자체 신뢰 평가) 필드를 포함한다.

- Overview 섹션에 `- **pACS**: [enabled|disabled]` 추가 (기본값: enabled, AGENTS.md §5.4)
- pACS는 Autopilot 모드와 독립적으로 동작 — 수동 실행에서도 적용
- `(human)` 단계는 사람이 평가자이므로 pACS 불필요 (Verification과 동일 원칙)
- 사용자가 명시적으로 "pACS 없이" 등을 요청하면 `disabled`로 설정
