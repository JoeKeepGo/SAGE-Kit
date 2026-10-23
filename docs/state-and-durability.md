# 状态与持久化

**实现状态：P0 文件模式已实现；M2 SQLite foundation（tasks/runs/events/leases/API/恢复）已实现；M2b 备份导出/UI/提案评估实体、M3 定时循环仍是 `TARGET`。**
本文定义 SAGE-Kit 的两套状态模式、数据模型、恢复规则和并发约束。P0 只实现文件模式，布局与字段以 §2.1、§3、§4、§5 的 `[P0 已实现]` 为准（代码：`src/core/paths.ts`、`src/core/tasks.ts`、`src/core/runs.ts`、`src/core/events.ts`、`src/core/worktree.ts`）；`[TARGET]` 部分是设计目标，不构成实现声明。验收依据见 `docs/p0-acceptance.md`。

## 1. 范围与原则

- 目标环境：单机、单用户、单仓库、多任务并发。
- 不涉及：多机同步、分布式事务、租户隔离、跨用户权限。

原则与 P0 现状：

1. **一个事实只有一个权威来源** `[P0 已实现]`：文件模式只有 `.sage-kit/` 一个权威源，P0 无 SQLite/控制面，不存在双写。
2. **持久写入可重试且幂等** `[TARGET]`：P0 只用“临时文件 + `fsync` + `rename`”保证单文件原子替换；没有跨文件事务，也没有通用 idempotencyKey（重复运行同一命令会产生新的 run/task 记录）。
3. **状态可从事件/记录恢复，不依赖内存** `[P0 部分]`：run 记录 + `doctor` 的 stale-run 扫描可恢复中断；事件是追加日志但 P0 没有重放器（`[TARGET]`）。
4. **单写者** `[P0 约定，未强制]`：控制面模式下由控制面单进程写 SQLite（`[TARGET]`）；文件模式的 P0 代码**没有任务锁/lease**，同一任务并发写是“最后写入者胜”，依赖单用户不并发操作同一状态（见 §5、D-008 的差异说明）。
5. **文件模式与控制面模式不双写** `[P0 已实现]`：控制面尚不存在，P0 天然满足；模式切换命令属于 `[TARGET]`。

## 2. 两种模式

### 2.1 文件模式（P0 默认，已实现）

实际目录结构（`src/core/paths.ts` 的 `statePaths()`）：

```text
<project-root>/
  .sage-kit/
    config.json                  # init 写入；本地状态配置，不是要求提交的基线文件（见下方“提交策略”）
    state/
      tasks/<task-id>.json       # 任务定义/状态/验收/证据
      runs/<run-id>.json         # 运行记录
      events/events.jsonl        # 追加事件；只追加不覆盖
    worktrees/<task-id>/         # git worktree
    cache/                       # 可删除缓存
  SESSION_BRIEF.md               # init 生成的会话摘要快照（项目根；派生视图）
```

`<project-root>` 的解析：从当前目录向上找最近一个包含 `.git` 的目录；找不到则使用当前工作目录（`src/core/paths.ts` 的 `findProjectRoot()`）。

P0 未实现、不要写进布局的东西：

- `feedback/<id>.json`：`[TARGET]` M1 反馈缓存。
- `locks/`：`[TARGET]`；P0 无任务锁/仓库锁。
- `brief.md`（`.sage-kit/` 下）：实际 brief 路径是项目根的 `SESSION_BRIEF.md`；`state/` 下也没有 `events.jsonl`，事件文件在 `state/events/events.jsonl`。
- `state export/import/migrate` 命令：`[TARGET]`，P0 无这些命令。

#### 提交策略（P0 实际）

- `init` **不会**修改目标仓库的 `.gitignore`；`.sage-kit/` 是否提交由使用方决定。
- 本仓库自己的 `.gitignore` 忽略 `.sage-kit/`（以及 `work/`、`dist/`、`node_modules/`），所以本仓库没有提交的 `.sage-kit/config.json`。
- `config.json` 含绝对路径（`projectRoot`、`skill.path`），按原样提交会把本机路径带进仓库；P0 的推荐策略是**把 `.sage-kit/`、`SESSION_BRIEF.md` 当本地状态/派生文件，不提交**。若使用方选择提交，需要自行接受路径可移植性问题。
- 这不改变 D-005 的“文件模式是本地状态”定位；早期文档“config.json 提交到仓库”的表述与实现/本仓库策略不一致，已在此更正。

#### 原子写、格式与字段

- `[P0 已实现]` 任务/运行/配置文件：写入 `<path>.<pid>.<random>.tmp` → 写入 → `fsync` → `rename` 覆盖（`src/core/fs-utils.ts` 的 `atomicWrite`/`writeJsonAtomic`）。这是单文件原子性，不是多文件事务。
- `[P0 已实现]` 事件：每行一个 JSON 追加到 `state/events/events.jsonl`（`appendLine` 以追加模式打开、`fsync`；无文件锁）。
- `[P0 已实现]` 任务 JSON 字段（`src/core/tasks.ts` 的 `Task`）：`schemaVersion: 1`、`id`、`title`、`description`、`status`、`acceptance: string[]`、`evidence: { at, note, source? }[]`、可选 `branch`/`worktree`、`createdAt`、`updatedAt`。
- `[P0 已实现]` 运行 JSON 字段（`src/core/runs.ts` 的 `RunRecord`）：`schemaVersion: 1`、`id`、`taskId`、`command: string[]`、`cwd`、`status: running | exited | failed | interrupted`、可选 `pid`/`exitCode`/`signal`、`startedAt`、可选 `endedAt`。
- `[P0 已实现]` 事件行字段（`src/core/events.ts` 的 `SageEvent`）：`ts`（UTC ISO 8601）、`type`、可选 `taskId`、可选 `data`。**没有** `id`、`seq`、`at`、`runId` 顶层字段；runId 只出现在 `data.runId` 里。`data` 会经过 `redactRecord` 尽力脱敏（见 `docs/security.md` §2）。
- `[P0 已实现]` 已产生的事件类型：`task.created`、`task.status_changed`、`task.worktree_attached`、`task.worktree_removed`、`worktree.created`、`worktree.removed`、`run.started`、`run.finished`、`hook.session.start`、`hook.command.after`、`hook.stop`。

#### P0 文件模式限制

- 无任务锁/lease/仓库锁：并发 CLI 进程可能互相覆盖任务文件；`doctor` 只能恢复 stale run，不能裁决并发写。
- 无幂等键：重复 `run`/`hook` 调用会追加重复事件/run 记录。
- `SESSION_BRIEF.md` 只在 `init` 时写入一次；任务变化后它可能过期。`sage-kit brief` 每次按当前状态渲染到 stdout，不写文件。
- `cache/` 当前没有清理命令；`worktrees/` 只由显式 `worktree remove` 清理（见 §5）。

### 2.2 控制面模式（`TARGET`，M2）

设计目标（P0 无此模式、无 `control` 命令、无 SQLite 依赖）：

```text
.sage-kit/
  config.json                 # mode = "control"
  control.db                  # SQLite；不提交
  control.db-wal / -shm       # SQLite WAL 文件；不提交
  artifacts/                  # 提案/评估证据/版本 manifest（可配置）
```

- 控制面是唯一写者；Worker 和 CLI 都通过本地 API 操作。
- SQLite 开 WAL、`foreign_keys=ON`、`busy_timeout=5000`、`synchronous=FULL`。
- 默认绑定 `127.0.0.1`；变更操作需要本地 token；不监听公网。
- 进程崩溃后 WAL 自动恢复；启动时执行恢复扫描。

### 2.3 模式切换（`TARGET`）

- 计划只允许显式命令：`sage-kit state export` / `sage-kit state import` / `sage-kit state migrate`；P0 **没有**这些命令。
- 切换前必须保证没有运行中的 run；迁移完成后旧模式文件保留为只读备份。
- 禁止运行时自动双写。

## 3. 任务状态机

### 3.1 P0 已实现

`src/core/tasks.ts` 的 `TASK_STATUSES` 与 `TRANSITIONS` 是权威实现；允许的转换如下：

```text
imported    → ready | blocked | failed
ready       → running | blocked | failed | cancelled
running     → review | blocked | failed | cancelled | interrupted
review      → done | running | blocked | failed | cancelled
blocked     → ready | running | failed | cancelled
failed      → ready | running
interrupted → ready | running | failed
done        → （终态）
cancelled   → （终态）
```

`[P0 已实现]` 规则：

- 新任务默认 `ready`；`task create --status done` 被拒绝。
- 非法转换被拒绝并返回 `E_BAD_TRANSITION`（可读错误）。
- `done` 要求任务累计至少一条 evidence，否则 `E_DONE_WITHOUT_EVIDENCE`；`done` 只能从 `review` 进入（`running → done` 会被拒绝）。
- `failed` 保留记录但 P0 不强制“失败原因+可重试标志”字段；重试会创建新 run，不覆盖旧 run 记录。
- `interrupted` 是“状态未知但可恢复”的中间态：P0 由 `doctor` 的 stale-run 恢复写入；恢复后用户决定重跑/取消（无自动 resume 命令）。

`[TARGET]`（未实现）：

- `running` 当前不强制存在 active run/lease（可以手动 `task status <id> running`）。
- 没有自动 lease 过期扫描；只有 stale-run 的 pid 存活检查。
- 没有 `blocked_reason`/重试标志/依赖字段。

### 3.2 控制面 schema（`TARGET`）

任务、依赖、runs、events、leases、feedback、sync_cursors、proposals、evals、artifacts、outbox 的 SQL 设计见 `docs/decisions.md` D-007 与早期设计稿；P0 没有对应实现或迁移。控制面实现时以该里程碑的设计评审为准。

## 4. 恢复与故障（`TARGET` 中标注例外）

| 场景 | P0 现状 | 目标 |
|---|---|---|
| 进程被 kill / 宿主超时 | `[P0 已实现]` `doctor` 扫描 `state/runs/*.json` 中 `running` 且 pid 不存活的记录，把 run 标 `interrupted`，并把仍为 `running` 的任务标 `interrupted`（`recoverStaleRuns`） | 控制面启动时扫描；用户选择 resume/重跑/取消 |
| lease 过期 | `[TARGET]` P0 无 lease | 不自动重跑；标中断 |
| SQLite 被锁/损坏 | `[TARGET]` P0 无 SQLite | 单写者 + `busy_timeout`；`PRAGMA integrity_check` + 备份恢复 |
| worktree 脏/冲突 | `[P0 已实现]` `worktree remove` 默认拒绝脏 worktree（`E_WORKTREE_DIRTY`），`--force` 才删除；不自动覆盖 | 保留现场/恢复分支 |
| 重复反馈 | `[TARGET]` P0 无反馈同步 | 唯一约束 + fingerprint |
| 外部同步失败 | `[TARGET]` | 保留游标 |
| hook 失败/缺失 | `[P0 已实现]` hook 失败默认 fail-open（`--strict` 的 `stop` 才 block）；brief 可由 CLI 手动生成；hook 失败不会写失败事件（只记录成功调用） | 可观测但不致命 |
| 发布后回归 | `[TARGET]` P0 无发布流程 | artifact 记录 + 回滚 |

恢复原则：**先判断副作用是否已发生，再决定重试**；不确定时默认不重复执行，要求人工确认。

## 5. 并发与 worktree（`[P0 已实现]`）

- 一个任务最多一个 worktree：路径固定为 `.sage-kit/worktrees/<task-id>`（不是可配置外部目录）；已挂 worktree 的任务再次 `worktree create` 会报 `E_WORKTREE_EXISTS`。
- 分支命名：`sage-kit/<task-id>`，从当前 `HEAD` 创建（P0 不支持 `base branch` 配置，也没有 `sage/<task-id>-<slug>` 命名；后者是早期设计稿，未实现）。
- Git 操作**没有**仓库锁/串行化（`git worktree add/remove/list` 直接调用）；`git` 子进程有 60 秒超时（`src/core/process.ts`）。
- 没有任务 lease：P0 防止同一任务被两个 Worker 写靠“单用户 + 不并发操作”的约定，不是强制锁。D-008 说“P0 用文件锁”，但**当前 P0 代码没有实现锁**；AGENTS.md 也明确 P0 只实现 worktree 与 run 记录、lease/SQLite 属 M2。这里记录该差异为已知缺口（`NOT_IMPLEMENTED`），不把文件锁写成已实现。
- `worktree create/remove/list` 是显式命令；`run` 默认在任务没有 worktree 时自动创建，`--no-worktree` 可直接在项目根运行。
- 完成后不自动 push/merge/publish（P0 没有这些命令）；worktree 只由 `worktree remove` 清理。
- 清理：默认拒绝删除有未提交改动的 worktree；`--force` 才会 `git worktree remove --force`。

## 6. 数据模型（控制面 SQLite，`TARGET`，M2）

以下是逻辑 schema，未实现；实现时用 migration 管理。所有表带 `created_at` / `updated_at`（UTC ISO 8601）。

### 6.1 任务与依赖

```sql
tasks(
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL,           -- imported/ready/running/review/done/failed/cancelled/interrupted/blocked
  priority INTEGER DEFAULT 0,
  acceptance_json TEXT,           -- 验收标准数组
  source TEXT,                    -- local/github-issues/gitea/linear/...
  external_id TEXT,
  external_url TEXT,
  worktree_path TEXT,
  branch TEXT,
  blocked_reason TEXT,
  idempotency_key TEXT UNIQUE,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)

task_dependencies(
  task_id TEXT NOT NULL,
  depends_on_task_id TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'blocks',
  PRIMARY KEY (task_id, depends_on_task_id)
)
```

### 6.2 运行、事件与 lease

```sql
runs(
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  host TEXT NOT NULL,
  status TEXT NOT NULL,           -- starting/running/exited/failed/cancelled/interrupted
  command TEXT,
  worktree_path TEXT,
  exit_code INTEGER,
  cost_usd REAL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  error_code TEXT,
  error_message TEXT,
  started_at TEXT,
  ended_at TEXT,
  idempotency_key TEXT UNIQUE
)

events(
  id TEXT PRIMARY KEY,
  seq INTEGER NOT NULL,           -- 每个 run/task 内单调递增
  task_id TEXT,
  run_id TEXT,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
)

leases(
  task_id TEXT PRIMARY KEY,
  owner TEXT NOT NULL,            -- control process / worker id
  run_id TEXT,
  acquired_at TEXT NOT NULL,
  heartbeat_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
)
```

- 事件是追加日志；UI/派生状态可以从事件重放，但任务表是当前状态的便捷投影。
- lease 默认 30 秒，心跳 10 秒；过期后恢复扫描把任务标 `interrupted`，不直接重跑。
- 幂等键用于“创建任务/启动 run/同步反馈/发布”等副作用；重复请求返回原结果。
- 文件模式对应的 P0 事件字段与 §2.1 的 `SageEvent` 相同（`ts/type/taskId/data`），不是本节的 `id/seq/at` 设计。

### 6.3 反馈、提案、评估、发布、outbox

`feedback`、`sync_cursors`、`proposals`、`evals`、`artifacts`、`outbox` 的表设计保持早期设计稿（见 `docs/feedback-and-rsi.md` 与 `docs/decisions.md`）；P0 未实现，M1/M2 实现前需重新评审字段。

## 7. 备份、导出与保留（`TARGET`）

- P0 **没有** `export`/`backup`/`import` 命令；`uninstall` 会删 skill、受管说明块、`SESSION_BRIEF.md` 和 `config.json`，`--purge` 还会删除整个 `.sage-kit/`（这是唯一接近“清理”的 P0 行为，且不是备份）。
- 计划（`TARGET`）：
  - `sage-kit export --format bundle`：生成可移植 bundle（manifest + tasks + feedback + artifacts 索引）。
  - `sage-kit backup`：控制面模式用 SQLite backup API 或 `VACUUM INTO`；文件模式直接打包。
  - 恢复：先校验 manifest/hash，再导入到空状态；不覆盖现有运行中的任务。
  - 保留策略：任务/提案/评估/发布长期；run 日志 90 天；feedback 保留链接与摘要；outbox 成功记录 30 天。
  - 清理只删可再生成数据；不删审计/版本记录。

## 8. 不变量

`[P0 已实现/已测试]`（`tests/cli.test.mjs`）：

1. 文件模式只有一个写入源（无控制面、无双写）。
2. 任务文件原子替换；事件追加不覆盖。
3. 非法状态转换被拒绝；无 evidence 不能 `done`（A5）。
4. stale run 可被 `doctor` 恢复为 `interrupted`，不会误标 `done`（A11/A11b）。
5. run 结束一定写回 run 记录（`run.finished` + run 文件状态；A12 覆盖正常路径）。
6. 路径穿越的任务 id 被拒绝；命令参数不经 shell（A12）。
7. 删除脏 worktree 默认被拒绝（A6）。
8. `uninstall` 不删除用户自己的说明内容；只删受管块/自己的 skill（A2/A3）。

`[TARGET]`（未实现，不能写成已满足）：

1. 跨进程单写者/文件锁：同一任务不会被两个执行者同时写。
2. 幂等：重复创建/同步/重试不产生重复任务、反馈或副作用。
3. 事件重放可重建状态。
4. lease 唯一性；SQLite 崩溃恢复。
5. 导入/导出不破坏状态；bundle 校验失败不部分写入。
6. 发布/回滚记录不可覆盖。

## 9. 相关文档

- 架构与运行模式：`docs/architecture.md`
- 接口契约：`docs/extension-contracts.md`
- 反馈/评估/发布：`docs/feedback-and-rsi.md`
- P0 验收：`docs/p0-acceptance.md`
- 决策：`docs/decisions.md`（D-005 文件模式、D-007 SQLite、D-008 worktree+lease）
