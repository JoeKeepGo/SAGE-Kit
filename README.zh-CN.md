# SPEC-Kit

[English](README.md) | [中文](README.zh-CN.md)

SPEC-Kit 是一套可复用的软件项目规范系统和 AI Agent 执行治理框架。

它帮助团队定义项目是什么、应该如何演进，以及 AI Agent 应该如何在项目中安全地执行开发、评审、交接和收尾工作。SPEC-Kit 将长期稳定的项目规范和执行治理分离，让产品目标、架构边界、测试证据和 Agent 工作流可以在多轮会话中保持一致。

## SPEC-Kit 提供什么

- 核心项目规范模型。
- 项目 profile、milestone、phase、ledger、closeout、quality gate、approval gate、completion report 模板。
- Project Owner Entry，用于把非工程化的想法转换成轻量 intake、project profile draft、capability map 和候选 milestones。
- 用于上下文控制、文件所有权、验证、交接和评审的 AI Agent Harness。
- Phase 内安全并行开发的 Wave Execution。
- Milestone 级 Project Manager、Coder、Final Review 控制器工作流的 Session Orchestration。
- Project Manager 授权下的 Worktree Isolation，用于受控的 phase、lane 或 review 独立工作区。
- Task Dispatch Profile，用于在复杂 milestone 中维护结构化 task record、evidence record、资源锁、Run/Attempt/Lease 和 validator gate closeout。
- Capability Routing，让控制器把任务路由给合适的 skill、plugin、connector 或 tool，而不是让治理文档挤掉专业能力。
- 强制先做 capability map，并拆细 milestone 与 phase 的规划规则，让工作可评审、可测试、边界明确。
- 针对低保障或未知模型族的 Strict Mode。
- 可选的项目形态 profile，例如状态机系统、控制后台加执行 agent 系统。
- 项目可自行收紧的默认模型保障策略。

## 核心思想

SPEC 定义项目契约。

Harness 定义 AI Agent 如何在这个契约内执行。

Project profile 用来把通用规则适配到具体架构，避免污染可复用核心。

## Kit 内容

```text
docs/
  SPEC_CORE.md
  *_TEMPLATE.md
  agent/
    AGENT_HARNESS.md
    MODEL_ASSURANCE_POLICY.md
    STRICT_MODE.md
    PROJECT_OWNER_ENTRY.md
    WAVE_EXECUTION.md
    SESSION_ORCHESTRATION.md
    WORKTREE_ISOLATION.md
    MILESTONE_PLANNING.md
  profiles/
    state-machine/
    control-plane-agent/
    task-dispatch/
  templates/
    PROJECT_OWNER_INTAKE_TEMPLATE.md
    CAPABILITY_MAP_TEMPLATE.md
    *_TEMPLATE.md
scripts/
  validate_task_dispatch.py
skills/
  spec-kit-governance/
```

## 内置 Skill

SPEC-Kit 包含 `skills/spec-kit-governance`，这是一个 Codex skill，用来帮助 Agent 在采用、规划、实现、评审、交接和 milestone closeout 时保持 SPEC-Kit 对齐。

这个 skill 是治理入口，不是所有 SPEC-Kit 文档的复制品。它要求 Agent 先读取 `ACTIVE_CONTEXT.md` 和 `DOC_ROUTING.md`，再根据任务只加载必要的 milestone、phase、gate、packet 或历史 closeout 文件。

在其他环境中使用时，可以将 `skills/spec-kit-governance` 复制到 Codex skills 目录，然后显式调用：

```text
Use $spec-kit-governance to plan and execute this task under SPEC-Kit.
```

这个 skill 设计为显式调用，避免在普通开发中挤掉更具体的 coding、frontend、document、GitHub 或 review skills。

Skill 可以帮助新项目引入 SPEC-Kit，但项目仍然需要采用相关模板并维护自己的 SPEC 文档。

## 推荐项目结构

```text
docs/
  ACTIVE_CONTEXT.md
  DOC_ROUTING.md
  PROJECT_PROFILE.md
  TECHNICAL_DESIGN.md
  ENGINEERING_SYSTEM.md
  QUALITY_GATES.md
  APPROVAL_GATES.md
  CAPABILITY_MAP.md       # 宽泛、非工程化启动或 roadmap 颗粒度偏粗时使用
  MILESTONE_ROADMAP.md
  agent/
    AGENT_HARNESS.md
    MODEL_ASSURANCE_POLICY.md
    STRICT_MODE.md
    PROJECT_OWNER_ENTRY.md
    WAVE_EXECUTION.md
    SESSION_ORCHESTRATION.md
    WORKTREE_ISOLATION.md
    MILESTONE_PLANNING.md
  templates/
    PROJECT_OWNER_INTAKE_TEMPLATE.md
    CAPABILITY_MAP_TEMPLATE.md
    PHASE_TEMPLATE.md
    MILESTONE_LEDGER_TEMPLATE.md
    MILESTONE_CLOSEOUT_TEMPLATE.md
    MILESTONE_EXECUTION_PACKET_TEMPLATE.md
    MILESTONE_RESULT_PACKET_TEMPLATE.md
    STRUCTURAL_GATE_TEMPLATE.md
    FINAL_REVIEW_PACKET_TEMPLATE.md
    CORRECTIVE_PACKET_TEMPLATE.md
    COMPLETION_REPORT_TEMPLATE.md
    LANE_PACKET_TEMPLATE.md
  M<ID>/
    00-entry-gate.md
    MILESTONE_LEDGER.md
    MILESTONE_CLOSEOUT.md  # milestone 关闭时创建
    01-phase-name.md
    dispatch/              # 可选 task-dispatch profile records
      DISPATCH_BOARD.md
      TASK-001/
        task.yaml
        evidence.yaml
```

## 复制映射

采用 SPEC-Kit 时可以参考：

| SPEC-Kit Source | Project Destination |
|---|---|
| `docs/PROJECT_PROFILE_TEMPLATE.md` | `docs/PROJECT_PROFILE.md` |
| `docs/TECHNICAL_DESIGN_TEMPLATE.md` | `docs/TECHNICAL_DESIGN.md` |
| `docs/ENGINEERING_SYSTEM_TEMPLATE.md` | `docs/ENGINEERING_SYSTEM.md` |
| `docs/QUALITY_GATES_TEMPLATE.md` | `docs/QUALITY_GATES.md` |
| `docs/APPROVAL_GATES_TEMPLATE.md` | `docs/APPROVAL_GATES.md` |
| `docs/ACTIVE_CONTEXT_TEMPLATE.md` | `docs/ACTIVE_CONTEXT.md` |
| `docs/DOC_ROUTING_TEMPLATE.md` | `docs/DOC_ROUTING.md` |
| `docs/templates/PROJECT_OWNER_INTAKE_TEMPLATE.md` | 可选 `docs/PROJECT_OWNER_INTAKE.md` |
| `docs/templates/CAPABILITY_MAP_TEMPLATE.md` | 面向宽泛、非工程化启动或 roadmap 颗粒度偏粗项目的 `docs/CAPABILITY_MAP.md` |
| `docs/templates/MILESTONE_ROADMAP_TEMPLATE.md` | `docs/MILESTONE_ROADMAP.md` |
| `docs/templates/ENTRY_GATE_TEMPLATE.md` | `docs/M<ID>/00-entry-gate.md` |
| `docs/templates/MILESTONE_LEDGER_TEMPLATE.md` | `docs/M<ID>/MILESTONE_LEDGER.md` |
| `docs/templates/MILESTONE_CLOSEOUT_TEMPLATE.md` | `docs/M<ID>/MILESTONE_CLOSEOUT.md` |
| `docs/templates/PHASE_TEMPLATE.md` | `docs/M<ID>/<NN>-<phase-name>.md` |
| `docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md` | Milestone 级 Project Manager 到 Coder packet |
| `docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md` | Milestone 级 Coder result packet |
| `docs/templates/STRUCTURAL_GATE_TEMPLATE.md` | Project Manager structural gate checklist |
| `docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md` | Final Review verdict packet |
| `docs/templates/CORRECTIVE_PACKET_TEMPLATE.md` | Bounded corrective work packet |
| `docs/agent/PROJECT_OWNER_ENTRY.md` | 可选轻量 Project Owner 入口策略 |
| `docs/agent/WORKTREE_ISOLATION.md` | 可选 worktree isolation policy |
| `docs/profiles/task-dispatch/` | 可选结构化任务调度 profile |
| `scripts/validate_task_dispatch.py` | 可选 task dispatch validator |

当 AI Agent 会执行或评审工作时，复制 `docs/agent/`。仅当项目使用对应形态时，才复制相关 `docs/profiles/<profile>/` 模板。

## 采用流程

1. 如果项目从宽泛或非工程化想法开始，先用 Project Owner Entry 生成 intake、project profile draft 和 capability map。
2. 填写或完善 `PROJECT_PROFILE.md`。
3. 编写或适配 `TECHNICAL_DESIGN.md`。
4. 定义 `QUALITY_GATES.md` 和 `APPROVAL_GATES.md`。
5. 添加 `ACTIVE_CONTEXT.md` 和 `DOC_ROUTING.md`。
6. 对宽泛、非工程化启动或 roadmap 颗粒度偏粗的项目创建 `CAPABILITY_MAP.md`。
7. 当使用 `CAPABILITY_MAP.md` 时，从中生成候选 milestones。
8. 只有通过 Milestone Granularity Gate 的候选 milestone 才能进入可执行 roadmap。
9. 用 `00-entry-gate.md` 创建第一个 milestone。
10. 将 milestone 拆成边界明确、可评审、可测试的 phases。
11. 通过保留的 phase docs 和 completion reports 执行每个 phase。
12. 当 Phase 内存在安全并行 lane 时使用 Wave Execution。
13. 当大型 milestone 需要 Project Manager、Coder、Final Review 控制器交接时使用 Session Orchestration。
14. 只有 Project Manager 授权时，才使用 Worktree Isolation 创建独立 phase、lane 或 review 工作区。
15. 只有当 milestone 需要结构化 task/evidence records、资源锁、lease tracking 或 validator closeout 时，才启用 Task Dispatch Profile。
16. 在 `MILESTONE_LEDGER.md` 中维护 milestone 状态。
17. Milestone 关闭时，写入 `MILESTONE_CLOSEOUT.md` 作为紧凑的历史结果索引。

历史 closeout 不属于默认启动上下文。只有当 `DOC_ROUTING.md` 指向 prior milestone outcomes、decisions、gaps 或 provenance 时才读取。

## 适用性

SPEC-Kit 并不适用于所有项目。采用前请先阅读内容，确认它的规划深度、文档结构和 AI Agent 工作流是否与你要运行的项目匹配。

## 非目标

- SPEC-Kit 不是项目管理应用。
- SPEC-Kit 不能替代测试、评审或 runtime verification。
- SPEC-Kit 不规定某一种编程语言、框架、托管方式、数据库或 Agent provider。
