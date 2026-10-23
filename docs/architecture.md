# SAGE-Kit 架构

**状态：架构基线；P0 文件模式已实现，控制面/反馈/RSI 仍是设计目标。**  
本文描述目标架构与已实现的 P0 边界。实现状态以 `docs/p0-acceptance.md` 和实际测试为准。

## 1. 定位

SAGE-Kit 是一个**单用户、本地、可移植**的 Agent 开发工具包，解决三件事：

1. 把一套可复用的开发方法以 Skill 形式安装到不同宿主 Agent；
2. 为需要持久状态的工作提供可选的本地控制面（任务、运行、反馈、提案、评估）；
3. 让 Agent 能从外部反馈中提出改进，但必须经过**独立评估 + 人工批准**才能发布。

它不试图成为团队协作平台、Agent 托管平台或多租户服务。团队任务系统只作为外部数据源/出口接入。

## 2. 目标与非目标

### 2.1 目标

- **单用户单机**：一个开发者在本地项目中使用，不要求账号、组织、租户。
- **单仓库多任务并发**：同一台机器上可以同时跑多个任务/Agent，但不要求多机分布式。
- **可恢复**：进程崩溃、宿主超时、机器重启后，任务状态可判断、可恢复或可安全重试。
- **可移植**：Skill 不绑定单一宿主；Codex、Claude Code、OpenCode、DSH 通过适配器接入。
- **反馈驱动改进**：能读取 GitHub/Gitea 的 Issue、PR 评论、CI 状态，形成可评估的提案。
- **可治理**：每次改进有独立评估、版本、变更记录和回滚路径。
- **轻量**：核心 CLI 无重型运行时依赖；控制面可选，不引入 PostgreSQL/Redis/Kubernetes。

### 2.2 非目标

- 多机部署、集群、高可用、水平扩缩容。
- 团队协作、组织/租户、RBAC、成员管理、实时协同编辑。
- 远程共享 API 或托管服务。
- 通用插件市场、通用事件总线、通用规则引擎。
- 自动合并、无人值守发布、无独立评估的递归自我修改。
- 模型训练/微调；SAGE-Kit 只改 Skill、代码、模板和流程，不改模型权重。

## 3. 设计原则

1. **Skill 无状态**：Skill 是指令和模板，不持有数据库、不启动守护进程、不在文本中隐藏网络调用。
2. **状态单一写入源**：文件模式或控制面模式，二选一；任何时刻只有一个权威写入者。
3. **确定性操作放 CLI**：安装、任务、worktree、hook 分发、同步等可测试逻辑不交给模型自由发挥。
4. **判断/写作放 Agent**：需求理解、方案、代码修改、评审由 Agent 完成，但必须受任务范围和验收标准约束。
5. **最薄 hook**：只在关键生命周期注入上下文/记录事实，不承担状态和复杂逻辑。
6. **反馈是数据，不是指令**：外部文本可能包含提示注入，不能直接执行。
7. **改进必须有裁判**：Builder 与 Evaluator 分离；候选版本不能自己判断自己。
8. **默认人工批准**：自我改进上限为 L2；不自动合并、不自动发布。

## 4. 总体架构

```text
┌─────────────────────────────────────────────────────────────┐
│ 宿主 Agent：Codex / Claude Code / OpenCode / DSH            │
│  └─ SAGE-Kit Skill：SKILL.md + references + templates       │
│     无状态；使用宿主已有的工具、权限与模型                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ 普通工具调用 / 命令
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 仓库 + task worktree                                        │
│ 每个任务独立分支/工作区；由 CLI/控制面创建和回收             │
└──────────────────────────┬──────────────────────────────────┘
                           │ hooks / 事件
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ sage-kit CLI（核心，目标零运行时依赖）                       │
│ init / update / doctor / task / run / hook / feedback        │
│ 只做确定性操作；不内置模型，不做 UI                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ 可选：localhost API
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 可选本地控制面（持续开发时必需）                             │
│ HTTP/SSE + Web UI + SQLite WAL                               │
│ tasks / runs / events / leases / feedback / proposals /      │
│ evals / artifacts / sync_cursors                             │
│ 本地 Worker：子进程运行 Agent/命令，写结构化事件             │
└──────────────────────────┬──────────────────────────────────┘
                           │ 适配器契约
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 边界适配层（可选、可替换）                                   │
│ TaskSourceAdapter / FeedbackSourceAdapter / EventSink /      │
│ Bundle 导入导出                                              │
│ GitHub / Gitea / 外部任务系统 / 本地文件                     │
└─────────────────────────────────────────────────────────────┘
```

## 5. 分层职责

### 5.1 Skill 层

包含：

- `SKILL.md`：工作流、质量门槛、何时使用控制面、何时停止并请求人工确认。
- `references/`：按需加载的详细规则（例如评估、反馈处理、任务拆分）。
- `templates/`：提案、任务、验收记录、评审清单。

不包含：

- 数据库连接、状态文件、后台任务、网络客户端、密钥。
- 宿主特定路径的硬编码（由适配器处理）。

Skill 的默认安装是轻量的：只装 Skill 文件，不要求安装控制面。行为合同见 [`skill-contract.md`](skill-contract.md)。

### 5.2 CLI 层

CLI 是确定性的“手和脚”：

- `init`：安装 Skill、写配置、初始化 `.sage-kit/`。
- `update`：更新 Skill/模板，迁移配置。
- `doctor`：检查 Node 版本、宿主、权限、配置、控制面健康。
- `task`：任务创建/列出/状态/验收记录。
- `run`：在指定 worktree 中启动宿主 Agent（或包装命令）。
- `hook`：接收宿主事件，输出 `SESSION_BRIEF` 或记录事实。
- `feedback`：同步/列出/查看反馈（M1 起）。
- `control`：启动/停止本地控制面（可选）。

CLI 目标：Node.js 内置能力优先，核心零运行时依赖；启动开销低；命令可组合；所有外部调用有超时和明确错误。

### 5.3 控制面层（可选）

控制面解决“跨会话、跨进程、可恢复”的问题：

- 本地 HTTP API（只绑定 `127.0.0.1` + loopback Host 校验；本地单用户不设 token）。
- Web UI：M2 提供本地控制面板（任务列表/详情、新建任务、状态转换、lease、恢复）；运行记录只读展示，不提供 run 启动/监督，也不提供提案/评估 UI。
- SQLite（WAL）作为唯一权威存储；单进程写入。
- 本地 Worker 子进程运行 Agent/命令，记录事件；不依赖远程队列。
- 调度/恢复：启动时恢复未完成任务，处理过期 lease。

控制面不是默认必需：只用 Skill + CLI + 文件状态也能完成简单任务；当需要反馈同步、评估、可恢复执行时再启用。

### 5.4 适配器层

- **HostAdapter**：识别宿主、解析 Skill 安装路径、安装/卸载、生成启动命令、映射 hook 事件。
- **TaskSourceAdapter / FeedbackSourceAdapter**：外部任务/反馈的拉取（可选推送）。
- **EventSink**：把本地事件以 webhook/JSONL 形式发给外部系统，失败进入 outbox。
- **Bundle**：`.sage-kit` 的导入/导出格式，用于备份、迁移和与团队系统交换。

接口细节见 `docs/extension-contracts.md`。

## 6. 运行模式

### 6.1 文件模式（默认，轻量）

- 状态在 `.sage-kit/` 下，人类可读。
- 适合单任务/少任务、快速开始、离线环境。
- 无后台进程、无 UI；hook 读取当前任务生成 brief；`init` 写一份 `SESSION_BRIEF.md` 作为初始快照。
- 限制：并发写入能力弱；没有持久 job queue；崩溃恢复依赖文件原子写和可重放事件。

### 6.2 控制面模式（可选，持续开发推荐）

- `sage-kit control` 启动本地控制面；SQLite 是权威状态。
- CLI 通过 localhost API 操作，不直接写 SQLite。
- 支持任务队列、lease、运行记录、反馈同步、评估、发布记录。
- 目标仍是单用户单机；不做远程访问、账号、租户。

**不双写**：检测到控制面运行，CLI 使用 API；否则使用文件。两者之间只允许显式导入/导出，不做隐式双向同步。

## 7. 状态与事实来源

| 事实 | 权威来源 | 说明 |
|---|---|---|
| 任务定义、状态、验收标准、依赖 | 文件模式：`.sage-kit/state/tasks/*.json`；控制面：SQLite `tasks` | 只能有一个写入源 |
| 运行记录、退出码、成本、错误 | `runs` / `events` | 追加写；UI 只读派生 |
| 任务 lease / 当前执行者 | `leases`（M2 控制面）；文件模式单用户单写者，不以 lease 强制互斥 | 文件模式不双写；M2 lease 已实现 |
| 反馈原始项 | `feedback` + `sync_cursors` | 来自外部；不可信；保留来源 URL |
| 提案、评估、版本、回滚点 | `proposals` / `evals` / `artifacts` | 改进链路的事实 |
| Skill 版本 | 包版本 + 安装 manifest | 必须可查询、可回滚 |
| 会话摘要 | `SESSION_BRIEF.md` / `brief` 快照 | 派生视图；不是权威事实 |

详细 schema 与恢复规则见 `docs/state-and-durability.md`。

## 8. 核心流程

### 8.1 初始化

```text
sage-kit init --host <host>
  → 选择/检测宿主
  → 复制 Skill 到宿主目录（适配器决定路径）
  → 写 .sage-kit/config.json
  → 写/追加受管 AGENTS.md 块（可用 --no-instructions 跳过）
  → 打印下一步（如何开始任务；brief 由 sage-kit brief 或 session.start 输出）
```

> P0 只安装 Skill 与受管说明块；宿主 hook 配置的自动安装属于 M1。`hook` 命令本身可由宿主显式调用，未安装时 Skill + CLI 仍可工作。

### 8.2 任务生命周期

```text
imported → ready → running → review → done
                    │  └→ failed / cancelled / interrupted
                    └→ blocked（等待依赖或人工输入）
```

- 一个任务一个 worktree/分支；任务结束（done/cancelled）后才清理。
- P0 只要求 `running` 时有 run 记录；任务锁/lease 与“锁过期自动恢复”是 M2 目标。当前崩溃恢复依赖 `doctor` 对 stale run 的显式恢复，不能阻止两个进程同时写同一任务。
- 完成必须有验收证据；没有证据只能标记 `review`，不能标记 `done`。

### 8.3 反馈与改进

```text
sync feedback → normalize/dedupe → triage → proposal
→ build in worktree → independent eval → human approval
→ release/version bump → rollback point
```

细节见 `docs/feedback-and-rsi.md`。默认只读同步；提案和发布是 M1/M2 能力。

### 8.4 Hook 上下文

```text
session.start → 读取当前任务并生成 SESSION_BRIEF → 输出给宿主（≤ 2KB）
command.after（测试/构建）→ 记录结果（控制面或文件）
stop → 检查完成证据 → 提醒/阻断（--strict）
```

Hook 是尽力而为的适配层；状态和恢复不依赖 Hook 是否成功。细节见 `docs/hooks-and-host-adapters.md`。

## 9. 包结构与依赖策略

目标：**一个 npm 包、一个仓库、多个懒加载入口**。

```text
SAGE-Kit/
  package.json
  tsconfig.json
  src/
    cli.ts                     # 参数解析、命令分发、JSON/human 输出
    core/
      config.ts paths.ts fs-utils.ts errors.ts
      tasks.ts hooks.ts brief.ts events.ts
      worktree.ts runs.ts doctor.ts install.ts
    adapters/
      types.ts index.ts dsh.ts codex.ts claude.ts fake.ts
  skills/sage-kit/
    SKILL.md                   # P0 只带 Skill 正文；references/templates 在 M1 按需补
  tests/
    cli.test.mjs
  reports/p0/
    README.md                  # 本地证据，不随 npm 包发布
  docs/
```

依赖规则：

- 核心 `dependencies` 目标为 0；只使用 Node.js 内置模块。
- 控制面所需的 `better-sqlite3` 放 `optionalDependencies`，通过动态 `import()` 懒加载；缺失时 CLI 给出清晰提示并回退文件模式。
- UI 构建产物随包携带；不引入运行时 UI 框架依赖。
- Feedback 使用内置 `fetch`；GitHub/Gitea 优先复用 `gh`/`tea` 登录态，REST 作为回退。
- Node.js `>=22`；ESM；TypeScript 构建到 `dist/`；CLI 启动路径不做重型初始化。

## 10. 健壮性要求（单机范围）

- **崩溃恢复**：任何 run 可从事件日志判断最后状态；不依赖内存。
- **幂等**：创建任务、同步反馈、执行副作用都有幂等键；重试不重复。
- **单写者**：控制面单进程写 SQLite；Worker 不直写数据库。
- **本机并发**：P0 文件模式是单用户单写者（无数据库，不需要跨进程 lease）；M2 控制面用 SQLite lease/单写者；两种模式不双写。文件模式不接控制面 lease，避免出现第二套权威。
- **可观测**：run id、结构化事件、错误分类、成本/耗时；`doctor` 和 `trace` 可定位问题。
- **可回滚**：Skill/CLI/模板版本不可变；发布记录和回滚命令。
- **可测试**：每个关键行为有 fixture/集成测试；不依赖真实 GitHub/模型做 CI。

不做：分布式一致性、跨机锁、HA、租户隔离、远程多用户鉴权。

## 11. 安全边界（摘要；控制面为 M2 目标）

- 控制面默认只绑定 `127.0.0.1`；本地单用户不设 token；不提供远程共享。P0 没有控制面监听；M2 的 `control serve` 提供 loopback API + 本地可写控制面板；备份/导出属于范围外。
- 反馈/网页/Issue 文本是不可信数据；不执行其中的命令；进入模型前做数据标记。
- GitHub/Gitea 读 token 与写 token 分离；密钥不落盘、不进日志、不进提示词。
- 执行外部命令/生成代码时使用最小权限；高风险动作要显式确认。
- 第三方依赖锁定版本、记录许可证；不复制来源不明代码。

完整威胁模型见 `docs/security.md`。

## 12. 里程碑

| 里程碑 | 内容 | 完成标志 |
|---|---|---|
| **M0 / P0** | 包骨架、Skill、`init/doctor`、文件任务/worktree、`brief`、三类 hook、卸载、P0 安全基线 | A1–A12 自动化覆盖 + A13 真实宿主；真实 DSH 0.2.1-rc.2 + 真实模型 GUI、`bash`→CLI、卸载/重装、真实 stop 已验证；DSH 不提供 hook 自动注入（AGENTS/手动路径可用） |
| **M1** | GitHub/Gitea 只读反馈同步、反馈列表/详情、brief 带入最新反馈 | **已实现**：13 项测试通过；真实 `api.github.com` 与 WSL2 自建 Gitea 1.27.3 已验证；残余真实边界见 `docs/m1-feedback.md` |
| **M2** | 本地控制面（SQLite/API/UI）、任务/运行/lease、恢复 | **控制面已实现**：38 项测试通过；任务创建/状态转换/lease/恢复面板可用；run 启动监督与备份/导出明确不在本控制面范围 |
| **M3** | L2 受控 RSI：评估闭环、人工批准/回滚 | **评估闭环已实现**：19 项测试通过；真实 worktree/基线/重复/预算/导出；无定时器/自动批准/发布 |

P0 文件模式、M1 只读反馈、M2 本地控制面、M3 评估闭环均已落地。A13 已在真实 DSH 0.2.1-rc.2 + 真实模型上验证 GUI、真实 `bash`→CLI、卸载/重装与真实 `stop`；DSH 不提供 hook 自动注入，记录为宿主边界（AGENTS 指令或手动 `hook` 可用）。run 启动监督、备份/导出、定时自动循环属于设计范围外。发布仍需用户授权。

## 13. 未决问题

以下问题不阻塞文档定稿，但必须在对应里程碑前决定：

- 首批宿主：已确定 **DSH 优先**（Taluvia 主开发环境），Codex、Claude Code 其次；OpenCode 后续。
- Skill 安装路径与宿主目录的权威映射：DSH 已按固定版本源码核对 `.dsh/skills` 与 `AGENTS.md`；Codex/Claude 的路径仍需按各自实际安装验证，不凭记忆硬编码。
- UI 技术选型：M2 已确定原生 HTML/CSS/JS、同源、无框架/无 CORS；后续若需要复杂控制台另立契约。
- 许可证：发布前确定；未定前不复制第三方实现代码。
