# 状态与持久化

**状态：设计基线；P0 文件模式已实现，控制面/SQLite 尚未实现。**  
本文定义 SAGE-Kit 的两套状态模式、数据模型、恢复规则和并发约束。实现必须满足这些不变量；细节 schema 可以在实现时微调，但不能破坏“单一写入源”和“可恢复”。P0 已实现的文件布局见 §2.1；§3 的 SQLite schema 是 M2 目标，不是当前代码。

## 1. 范围与原则

- 目标环境：单机、单用户、单仓库、多任务并发。
- 不涉及：多机同步、分布式事务、租户隔离、跨用户权限。
- 核心原则：
  1. **一个事实只有一个权威来源**；
  2. **任何持久写入可重试且幂等**；
  3. **状态可从事件/记录恢复，不依赖内存**；
  4. **单写者**：控制面模式下只有控制面进程写 SQLite；
  5. **文件模式与控制面模式不双写**。

## 2. 两种模式

### 2.1 文件模式（默认）

目录结构：

```text
.sage-kit/
  config.json                 # 提交到仓库：宿主、模式、保留策略
  state/
    tasks/<task-id>.json      # 任务定义/状态/验收
    runs/<run-id>.json        # 运行记录
    events.jsonl              # 追加事件；只追加不覆盖
    feedback/<id>.json        # 反馈缓存（M1 起）
    locks/                    # 任务锁/仓库锁；进程退出可清理
  brief.md                    # 生成的会话摘要（派生视图）
  cache/                      # 可删除缓存
```

规则：

- 任务文件用“临时文件 + `fsync` + `rename`”原子替换；写前获取任务锁。
- `events.jsonl` 只追加；每行一个 JSON；事件带 `id`、`type`、`at`、`taskId`、`runId`（可选）。
- 文件模式不提供跨进程强一致队列；同一任务同一时间只允许一个执行者。
- 文件模式支持导入/导出，不承诺崩溃后自动恢复正在执行的命令。

### 2.2 控制面模式（可选，持续开发推荐）

```text
.sage-kit/
  config.json                 # 提交：mode = "control"
  control.db                  # SQLite；不提交
  control.db-wal / -shm       # SQLite WAL 文件；不提交
  brief.md                    # 生成
  artifacts/                  # 提案/评估证据/版本 manifest（可配置）
```

规则：

- 控制面是唯一写者；Worker 和 CLI 都通过本地 API 操作。
- SQLite 开 WAL、`foreign_keys=ON`、`busy_timeout=5000`、`synchronous=FULL`（本地单用户，优先恢复正确性）。
- 默认绑定 `127.0.0.1`；需要本地 token；不监听公网。
- 进程崩溃后 WAL 自动恢复；启动时执行恢复扫描。

### 2.3 模式切换

- 只允许显式命令：`sage-kit state export` / `sage-kit state import` / `sage-kit state migrate`。
- 切换前必须保证没有运行中的 run；迁移完成后旧模式文件保留为只读备份。
- 禁止“运行时自动双写”或“发现控制面就同时写文件”。

## 3. 任务状态机

```text
imported → ready → running → review → done
  │        │        ├→ blocked（等待依赖/人工输入）
  │        │        ├→ failed
  │        │        ├→ cancelled
  │        │        └→ interrupted（崩溃/超时/lease 过期）
  │        └→ cancelled
  └→ cancelled
```

规则：

- `running` 必须有一条 active run 和 lease。
- `done` 必须有验收证据（命令输出、测试结果、人工确认之一）；否则最多到 `review`。
- `failed` 保留失败原因和可重试标志；重试创建新 run，不覆盖旧 run。
- `interrupted` 是“状态未知但可恢复”的中间态：先检查 worktree/分支/日志，再决定 resume 或重跑。
- 非法状态转换必须被拒绝并返回可读错误。

## 4. 数据模型（控制面）

以下是逻辑 schema；实现可用 migration 管理。所有表带 `created_at` / `updated_at`（UTC ISO 8601）。

### 4.1 任务与依赖

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

### 4.2 运行、事件与 lease

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

### 4.3 反馈与同步游标

```sql
feedback(
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,          -- github/gitea/local
  repo TEXT NOT NULL,
  external_id TEXT NOT NULL,
  kind TEXT NOT NULL,             -- issue/pr_review/check_run/discussion/local
  title TEXT,
  body TEXT,
  author TEXT,
  labels_json TEXT,
  state TEXT,
  url TEXT,
  fingerprint TEXT NOT NULL,       -- provider:repo:kind:external_id:updated_at 的哈希
  status TEXT NOT NULL DEFAULT 'new', -- new/triaged/ignored/proposed
  created_at TEXT,
  updated_at TEXT,
  synced_at TEXT NOT NULL,
  UNIQUE(provider, repo, kind, external_id, fingerprint)
)

sync_cursors(
  provider TEXT NOT NULL,
  repo TEXT NOT NULL,
  cursor TEXT,
  etag TEXT,
  last_sync_at TEXT,
  PRIMARY KEY (provider, repo)
)
```

规则：

- 反馈只读同步；写回外部系统必须显式开启且有独立权限。
- 反馈正文不直接拼进系统提示；进入 Agent 前标记为不可信数据，并截断/摘要。
- 删除外部反馈时不删除本地记录；标 `state=deleted` 或 `status=ignored`，保留审计。

### 4.4 提案、评估、发布

```sql
proposals(
  id TEXT PRIMARY KEY,
  feedback_id TEXT,
  base_version TEXT NOT NULL,
  title TEXT NOT NULL,
  hypothesis TEXT,
  diff_path TEXT,
  status TEXT NOT NULL,            -- draft/building/eval_pending/approved/rejected/released
  created_at TEXT,
  updated_at TEXT
)

evals(
  id TEXT PRIMARY KEY,
  proposal_id TEXT NOT NULL,
  suite_version TEXT NOT NULL,
  status TEXT NOT NULL,            -- running/passed/failed/error
  metrics_json TEXT,
  verdict TEXT,
  evidence_path TEXT,
  created_at TEXT,
  updated_at TEXT
)

artifacts(
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,              -- skill/cli/template/bundle
  version TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  manifest_json TEXT,
  status TEXT NOT NULL,            -- candidate/released/rolled_back
  released_at TEXT
)
```

- `proposals.base_version` 必填；候选改动必须相对一个稳定版本。
- 评估证据保存到 `artifacts/`（或 `.sage-kit/evidence/`），不进提示词全文。
- 发布记录不可覆盖；回滚创建新记录，指向旧版本。

### 4.5 出站事件

```sql
outbox(
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT,
  delivered_at TEXT,
  last_error TEXT
)
```

`EventSink.emit` 失败不阻塞主流程；写入 outbox，由控制面重试。成功投递后保留一段时间用于排障。

## 5. 崩溃与故障恢复

| 场景 | 处理 |
|---|---|
| 进程被 kill / 宿主超时 | 启动时扫描未结束的 `runs`；把关联任务标 `interrupted`；检查 worktree 和分支；用户选择 resume/重跑/取消 |
| lease 过期 | 不自动重跑；标记中断；若确认无副作用，可手动释放后重试 |
| SQLite 被锁 | 单写者 + `busy_timeout`；API 返回可重试错误；不无限重试 |
| SQLite 损坏 | `PRAGMA integrity_check`；从最近备份/导出恢复；记录数据丢失范围 |
| worktree 脏/冲突 | 不自动覆盖；保留现场；提示用户或创建恢复分支 |
| 重复反馈 | 唯一约束 + fingerprint；重复同步变成 no-op |
| 外部同步失败 | 保留游标；下次从上次成功位置继续；错误可见但不丢本地状态 |
| hook 失败/缺失 | 主流程继续；brief 仍可由 CLI 生成；不把 hook 当唯一状态源 |
| 发布后回归 | 根据 artifact 记录回滚到上一稳定版本；保留候选证据 |

恢复原则：**先判断副作用是否已发生，再决定重试**；不确定时默认不重复执行，要求人工确认。

## 6. 并发与 worktree

- 一个任务一个 worktree（默认 `.sage-kit/worktrees/<task-id>`，可通过配置改到外部目录）。
- 分支命名：`sage/<task-id>-<slug>`；从配置的 base branch 创建。
- 同一仓库的 git 操作串行化（仓库锁），避免 index.lock 冲突。
- 任务 lease + worktree 锁双重防止同一任务被两个 Worker 写。
- 完成后由用户/合并队列合并；SAGE-Kit 不自动 push/merge，除非显式命令。
- 清理：只清理已 done/cancelled 且无未提交改动的 worktree；失败/中断的 worktree 保留现场。

## 7. 备份、导出与保留

- `sage-kit export --format bundle`：生成可移植 `.sage-kit/bundle/`（manifest + tasks + feedback + artifacts 索引）。
- `sage-kit backup`：控制面模式下使用 SQLite backup API 或 `VACUUM INTO`；文件模式直接打包。
- 恢复：先校验 manifest/hash，再导入到空状态；不覆盖现有运行中的任务。
- 默认保留：
  - 任务、提案、评估、发布记录：长期保留；
  - run 日志/大输出：默认 90 天，可配置；
  - feedback 原文：保留来源链接和摘要，正文可按保留策略截断；
  - outbox 成功记录：30 天。
- 清理任务必须只删可再生成的数据；不删审计/版本记录。

## 8. 不变量（实现必须测试）

1. 任一时刻只有一个写入源；不存在文件与 SQLite 同时作为权威。
2. 同一任务不会有两个 active lease。
3. 重复创建/重复同步/重试不会产生重复任务、重复反馈或重复副作用。
4. 崩溃后不会把未知状态直接标为 done。
5. 事件日志可定位最后已知状态；run 的结束一定落库。
6. 评估/发布/回滚记录不可覆盖。
7. 清理 worktree 不删除未提交改动；失败现场可恢复。
8. 导入/导出不破坏现有状态；校验失败时不部分写入。

## 9. 相关文档

- 架构与运行模式：`docs/architecture.md`
- 接口契约：`docs/extension-contracts.md`
- 反馈/评估/发布：`docs/feedback-and-rsi.md`
- P0 验收：`docs/p0-acceptance.md`
