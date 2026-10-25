# 参考项目与取舍

**状态：设计参考（DESIGN REFERENCE）**  
本文件记录做架构取舍时调研过的公开项目，以及“借用什么/不借用什么”。这些项目不是运行依赖；代码/许可证在真正复用前必须重新核对。

## 1. 参考矩阵

| 项目 | 类型 | 值得借鉴 | 不直接采用的原因 |
|---|---|---|---|
| [Agent Skills 规范](https://agentskills.io/) | 开放标准 | Skill 目录、`SKILL.md`、渐进式加载、跨宿主分发 | 规范本身不提供 CLI/状态/控制面 |
| [vercel-labs/skills](https://github.com/vercel-labs/skills) | npm CLI | `skills add/list/update/remove`、多宿主检测、从 npm 包同步 Skill、安装 provenance | 它是通用 Skill 安装器，不包含任务/控制面；不把它的状态模型强加给 SAGE-Kit |
| [github/spec-kit](https://github.com/github/spec-kit) | Python CLI + 流程 | 一个 CLI + 项目内 `.specify/`；扩展/预设/模板；多 Agent 集成 | Python 栈、流程较重；SAGE-Kit 要 Node 单包、更轻 |
| [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) | npm CLI | 单包安装、项目内 `openspec/`、多工具集成、init/update、轻量工作流 | 偏 spec-driven change，不覆盖本地任务执行/RSI 评估 |
| [buildermethods/agent-os](https://github.com/buildermethods/agent-os) | 规则/工作流 | 把团队标准注入 Agent、按任务加载上下文 | 没有控制面/持久任务/评估闭环 |
| [BloopAI/vibe-kanban](https://github.com/BloopAI/vibe-kanban) | 本地看板 | worktree/workspace、任务看板、diff review、并行 Agent 的 UX | 项目已宣布 sunset；只借鉴交互，不作为依赖 |
| [smtg-ai/claude-squad](https://github.com/smtg-ai/claude-squad) | Go/TUI | tmux + git worktree 的极简任务隔离、profile、提交/推送流程 | TUI/单机假设强；AGPL-3.0，复用需评估 |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | 控制面/Agent 平台 | Agent Server/控制面/Worker 分离、会话恢复、Docker 运行、REST 边界 | 多仓库、重基础设施、多用户/云端取向；不适合单包本地工具 |
| [microsoft/RD-Agent](https://github.com/microsoft/RD-Agent) | R&D 自动化 | “提出假设→实现→反馈→迭代”的研究循环、评估思路 | Python/Linux/Docker 重；面向模型研发，不是通用开发治理 |
| [Taskmaster](https://github.com/eyaltoledano/claude-task-master) | npm CLI + MCP | 任务图/依赖/状态、PRD 解析、多工具接入 | token 开销大、工具面过宽；许可证含 Commons Clause，不能直接复制实现 |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | Skill + 多宿主适配器 | 单一 canonical 提示词、SessionStart 注入、模式切换、命令薄封装、安装/卸载矩阵 | 核心是行为提示词，不是任务/证据/RSI 系统；只借鉴分发层，不复制提示词、品牌或 20 宿主适配面 |

## 2. 对 SAGE-Kit 的具体取舍

### 2.1 包装与安装

借鉴 `skills` CLI 和 OpenSpec：

- 一个 npm 包、一个 `npx` 入口；
- `init` 检测宿主并安装 Skill；
- 安装 manifest 记录来源/版本/路径，可更新/卸载；
- 不为每个宿主建一个包。

不采用：

- 通用插件市场；
- 强制 Python/uv；
- 运行时依赖多个框架。

### 2.2 流程/规范

借鉴 Spec Kit 的“项目内工件 + 显式阶段”，但压缩为：

- 任务/验收/证据三件套；
- 反馈/提案/评估/发布四阶段；
- 不引入完整 spec-driven 平台或大量命令。

### 2.3 工作区/并发

借鉴 Vibe Kanban/Claude Squad 的 worktree 隔离，但：

- 用本地 CLI + 控制面，不依赖 TUI；
- 不自动 merge/push；
- 用文件锁/lease 和 SQLite 单写者，不引入分布式锁。

### 2.4 控制面

借鉴 OpenHands 的“控制面/执行器/适配器”分离，但：

- 只做 localhost、单用户；
- 不引入多租户/远程 API/容器编排；
- 控制面可选，文件模式默认。

### 2.5 RSI

借鉴 RD-Agent 的“反馈驱动迭代”与评估思路，但：

- 只改 Skill/CLI/模板/测试，不训练模型；
- L2 上限，人工批准发布；
- 必须有独立 Evaluator 和隐藏用例；
- 不自动合并/发布。

### 2.6 宿主插件化

借鉴 ponytail 的**分发层**，不借鉴其提示词内核：

- 一份 canonical Skill + 每宿主薄适配器；
- SessionStart / pre-step 注入，而不是每轮手动读文件；
- `off/brief/strict` 模式；
- 命令/工具只映射 CLI；
- 安装/卸载幂等、owned 文件、每宿主验收。

不采用：

- 把 SAGE-Kit 重写成单一提示词；
- 一次支持 20 个宿主；
- 复制 statusline/band/webhook/遥测；
- 用“自动激活”代替“用户确认 + 标记任务门禁”。

实现状态见 [`host-plugin-upgrade.md`](host-plugin-upgrade.md)（DSH 插件、宿主包与 RSI 门禁已实现；未验证宿主路径仍标 `NOT_EXECUTED`）。

## 3. 明确不作为依赖

- 不把 `vibe-kanban` 作为运行依赖（项目 sunset）。
- 不复制 `claude-squad` 代码（AGPL；如需复用需单独评估）。
- 不把 OpenHands/RD-Agent 作为运行时（栈不匹配、过重）。
- 不复制 Taskmaster 实现（许可证限制）；只借鉴任务图/依赖的产品思路。
- 不把 Agent Skills 规范当作完整产品规范；它只解决 Skill 包装。

## 4. 复用检查清单

真正引入第三方代码/依赖前：

1. 记录来源、commit/版本、许可证；
2. 确认与单用户/本地/Node 栈兼容；
3. 评估体积、维护活跃度、安全记录；
4. 优先复制“思路/接口形状”，不复制大段实现；
5. 在 `docs/decisions.md` 新增 ADR 说明为什么需要它。
