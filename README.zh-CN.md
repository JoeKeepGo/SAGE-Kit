# SAGE-Kit

[English](README.md) | [中文](README.zh-CN.md)

AI 写代码很快，但让长期项目长期保持一致更难。

SAGE-Kit 用项目自有 SPEC 合同和可嵌入的 Harness 核心，让项目继续在自己掌握的
合同中前进。

本仓库不再依赖公开 CLI 作为产品入口。项目的范围、授权、门禁和验收标准仍由项
目文档决定；SAGE-Kit 提供可嵌入的共享执行模型，供本地工具与 Agent 在其边界
内协作。

SAGE-Kit 运行时只用标准库，开源；配套 Skill 可在 Codex、Claude Code、OpenCode
和 Kimi Work 及兼容的运行时配置中使用。

## 去掉公开 CLI 后的定位

- 项目自有的 SPEC 与配置是权威来源；Markdown 文档只是可选的 source 格式，
  不是 authority 模型本身。
- Harness 以嵌入方式绑定到项目，但不拥有或替代项目策略。
- 项目绑定配置决定项目如何解析 authority、ACTIVE_CONTEXT 与可执行范围。
- 完成状态由项目 SPEC、配置、门禁与审批决定，而不是某条工具命令。
- `ACTIVE_CONTEXT` 仍有价值，但保持可配置、可替换，不再强绑定固定拓扑。
- 外部工具和插件仍是执行手段，不能成为项目决策来源。

## 典型接入流程

1. 在项目运行时引入 SAGE-Kit 作为依赖。
2. 在项目配置中明确 SPEC source 来源路径（本地文档、可选适配器、legacy 布局）。
3. 初始化并绑定项目级 Harness 配置。
4. 所有执行与验收都走项目合同与审批门禁，而不是把外部运行结果当作完成判定。

要求 Python 3.10+。

## SPEC 来源与运行模型

SAGE-Kit 规范 SPEC 语义与执行合同，但不要求固定文档目录。

兼容的旧项目在不迁移下可继续使用，只要保留可授权的 source 路径即可。

项目可选择：

- 本项目原生 SPEC 文档；
- 显式配置的 legacy `docs/<M>`；
- 外部适配器提供的显式 source。

source path 是 provenance，项目 authority、history 与 acceptance 规则仍在项目自有
SPEC 和配置里。

## 可选传统布局与连续性

为兼容旧项目和便于人工阅读，项目可以保留以下传统 Markdown 布局，但这不是
Harness 的强制目录；配置化 SPEC source 或 adapter 可以提供同一 normalized facts：

- `docs/PROJECT_PROFILE.md`
- `docs/QUALITY_GATES.md`
- `docs/APPROVAL_GATES.md`
- 可配置 `ACTIVE_CONTEXT`
- `docs/DOC_ROUTING.md`
- `docs/MILESTONE_ROADMAP.md`
- milestone ledger、phase 文档、closeout 文档

模板仍放在 [`docs`](docs) 和 [`docs/templates`](docs/templates)。

## 集成方式

项目可启用以下能力：

- 本地 Harness 执行；
- 连续性/检查点；
- 可选插件：skill、CI、MCP、Reviewer（带授权与回退策略）。

外部能力只产出执行证据，不替换项目自身通过门禁决定的完成判断。

## 兼容性

- `thin-v1` execution-document 与 `legacy-markdown` 保持兼容；
- `legacy-markdown` 与既有 `SAGE_PROJECT.json` 流程兼容；
- 已接受历史不做静默迁移；
- 兼容性例外仅适用于项目本地策略，不得用于弱化目标项目门禁。

Installed Skill 是可选执行辅助，不是项目权威。

## 工作流程

```mermaid
flowchart LR
  A["当前项目事实"] --> B["已批准范围"]
  B --> C["人或 Agent 执行"]
  C --> D["验证与证据"]
  D --> E["评审或修订"]
  E --> F["接受、交接或继续"]
```

建议先读 `ACTIVE_CONTEXT`（或项目配置的当前上下文入口），确认范围和授权，再做最小
授权变更，最后补齐证据并更新 handoff。

## 可选 Skill 使用方式

仓库提供的 Skill 在 [`skills/sage-kit`](skills/sage-kit)。如果你希望让 Assistant
拥有固定的工作流提示入口，可在你的运行时按需安装。

Skill 只是入口，不能替代项目合同与治理决定。

## 其他技能与工具关系

Coding skill、插件、MCP、CI、浏览器自动化、Reviewer 都是执行输入。它们可在批准边界内工
作，但不能：

- 扩大范围；
- 绕过锁与审批；
- 由它们单独判定完成。

## 仓库结构

```text
docs/                 框架规则、模板与可选 Profile
sagekit/              Harness 核心与打包资源
skills/sage-kit/      runtime 技能入口与环境画像
scripts/              独立验证脚本
tests/                单元与兼容测试
```

完整契约先看：

- [`docs/SAGE_CORE.md`](docs/SAGE_CORE.md)
- [`docs/design/EXECUTION_ECONOMY_REDESIGN.md`](docs/design/EXECUTION_ECONOMY_REDESIGN.md)

## 适用性

- 多会话、多人协作、AI 与人混合执行的项目。
- 范围/授权/证据错位代价高的项目。
- 需要跨会话持久事实与可审计 handoff 的项目。

短脚本、一次性原型、或一人可完整记忆状态的项目通常不需要这一整套治理。
