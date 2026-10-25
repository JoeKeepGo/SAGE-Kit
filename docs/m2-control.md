# M2 控制面基础（SQLite + lease + 本地 HTTP）

**状态：M2 本地可写控制面已实现并验证（`IMPLEMENTED` / `VERIFIED`）：任务创建/状态转换/lease/恢复与本地控制面板可用；run 启动监督、备份导出、配置模式切换、提案/评估实体不属于本控制面（设计上不在此处实现）。**
本文只描述 `src/control/**` 这一个可选层。它不改变 P0 文件模式，不写 `.sage-kit/state/`，不做模式切换。Lead 已接入 `sage-kit control serve/status/recover`（lazy import）；全局设计基线仍是 `docs/state-and-durability.md` §2.2/§6 与 `docs/decisions.md` D-005/D-006/D-007/D-008/D-022。

验证环境与证据（2026-10-24，Windows Node v24.22.0；WSL2 Ubuntu Node v22.22.1 上 `node:sqlite` 可用）：

```text
npm run build                     # tsc -p tsconfig.json，exit 0
node --test tests/control.test.mjs
# tests 39, pass 39, fail 0（含 HTTP 写端点与 UI 断言）
node <temp>/sage-ui-write-e2e.mjs
# headless Edge 27 项断言全过：自动加载、新建任务（校验/Esc）、状态转换（合法目标过滤/证据/409 错误回显）、
# lease acquire/renew/release、recover stale、移动端单列、无 token、无页面 JS 异常
```

`node:sqlite` 在本机可用（`DatabaseSync` 导入与建表/查询均已由测试覆盖），未新增任何依赖。全量 `npm test` 中本模块占 39 项；其他 slice 的测试由各自 owner 维护。

## 1. 范围与实现状态

| 能力 | 状态 | 说明 |
|---|---|---|
| `node:sqlite` `DatabaseSync` + `.sage-kit/control/control.db` | `IMPLEMENTED` | 无 native/第三方依赖 |
| WAL / `foreign_keys=ON` / `busy_timeout=5000` / `synchronous=FULL` | `IMPLEMENTED` | 在 open 时设置并校验；测试断言实际值 |
| `PRAGMA user_version` 迁移（v0 → v1） | `IMPLEMENTED` | 只支持 v1；更高版本拒绝（`E_DB_SCHEMA_NEWER`） |
| `tasks` / `runs` / `events` / `leases` schema（§6.1/§6.2） | `IMPLEMENTED` | 见 §3；`tasks.evidence_json` 为 M2 加法扩展 |
| 任务 CRUD、状态机、evidence、blocked_reason、乐观版本 | `IMPLEMENTED` | 状态转换与 `src/core/tasks.ts` 一致 |
| `recordRun` / `finishRun`（幂等终态） | `IMPLEMENTED` | 不自动改任务状态（见 §6 限制） |
| `appendEvent` / `listEvents`、per-scope `seq`、payload 脱敏 | `IMPLEMENTED` | 32KB payload 上限 |
| lease acquire/renew/release/expire（30s/10s 可配置） | `IMPLEMENTED` | 同任务单 lease；过期不自动重跑 |
| `recoverStale()` 恢复扫描 | `IMPLEMENTED` | 过期 lease + 无活 lease 的 active run → interrupted |
| 单写者 `writer.lock`（死进程可接管） | `IMPLEMENTED` | 同进程第二次 open 拒绝；read-only open 不持锁 |
| 本地 HTTP JSON API（9 条路由 / 10 个操作） | `IMPLEMENTED` | GET health/tasks/task-detail/events；POST tasks/task-status/lease-acquire·renew·release/recover；仅 127.0.0.1 + loopback Host 校验，写请求再校验 Origin/Sec-Fetch-Site/JSON Content-Type；本地单用户不要求 token |
| 写操作（任务创建、状态转换、lease、恢复） | `IMPLEMENTED` | 仅经 loopback UI/API；复用 `ControlStore` 方法与 P0 状态机；事件留痕；无自动重跑 |
| CLI `control` 子命令 / `src/cli.ts` 接线 | `IMPLEMENTED`（Lead） | `serve/status/recover`，lazy import；P0 默认启动不加载 SQLite |
| `config.json` 的 `mode = "control"` 与模式切换 | 非目标 | 绝不双写；本模块不碰 config |
| `state export/import/migrate`、备份（`VACUUM INTO`） | 非目标（本控制面） | 见 `docs/state-and-durability.md` §7 |
| 提案/评估/RSI 实体与控制台、多用户/远程 | 非目标 | RSI 由 `src/rsi/**` 文件模式负责；控制面不承载提案/评估，也不提供远程访问 |
| 任务依赖表、feedback/outbox/artifacts 表 | 非目标 | 本控制面只建 4 张最小表 |
| run 进程监督、UI 内运行 run | 非目标 | 恢复依据 lease，不依据 pid；面板只读展示 runs，不创建/监督 run |
| HTTP events 分页 cursor、run 独立查询端点 | 非目标 | events 已支持 task/run/type/limit 过滤，无 cursor |

## 2. 文件布局与写入边界

```text
<project-root>/.sage-kit/control/
  control.db        # SQLite（WAL）
  control.db-wal    # SQLite WAL；运行时存在
  control.db-shm    # SQLite shared memory；运行时存在
  writer.lock       # 单写者锁；JSON {pid, owner, startedAt}
```

- 路径由 `controlPaths(projectRoot)` / `controlDbPath(projectRoot)` 给出；`openControl()` 会创建 `.sage-kit/control/`（0700）。
- 本模块**只**写 `.sage-kit/control/`；不读写 `.sage-kit/state/**`、`.sage-kit/config.json`、worktree、Skill 文件。
- 本 repo 的 `.gitignore` 忽略 `.sage-kit/`，所以 `control.db*` 和 `writer.lock` 均为本地状态，不进提交。
- 同一 project root 只允许一个写者；跨进程/跨机器协作不在范围内（D-001/D-007）。

## 3. 数据库与 schema

打开顺序：建目录 → 单写者锁（非 read-only）→ `DatabaseSync` → PRAGMA → 迁移。

```sql
PRAGMA busy_timeout = 5000;
PRAGMA journal_mode = WAL;      -- 只读连接不设置，只校验
PRAGMA synchronous = FULL;      -- 只读连接不设置
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;        -- 迁移完成后
```

- 迁移只有 v1：`tasks`、`runs`、`events`、`leases`（`STRICT` 表）+ 索引；`v0 → v1` 在同一事务内完成。
- 未知/更高版本直接拒绝；不存在“降级”或“猜测 schema”。
- 行读取失败（类型/JSON 损坏）抛 `E_BAD_DB_ROW`，不会静默返回半条记录。

字段与 §6.1/§6.2 的对应（代码使用 camelCase API，DB 用 snake_case）：

```text
tasks: id, title, description, status, priority, acceptance_json,
       evidence_json*, source, external_id, external_url, worktree_path, branch,
       blocked_reason, idempotency_key UNIQUE, version, created_at, updated_at
runs:  id, task_id → tasks, host, status, command(JSON string[]), worktree_path,
       exit_code, cost_usd, input_tokens, output_tokens, error_code, error_message,
       started_at, ended_at, idempotency_key UNIQUE
events: id, seq, task_id, run_id, type, payload_json, created_at
        UNIQUE(run_id, seq); UNIQUE(task_id, seq) WHERE run_id IS NULL; UNIQUE(seq) WHERE 两者皆 NULL
leases: task_id PRIMARY KEY → tasks, owner, run_id → runs (ON DELETE SET NULL),
        acquired_at, heartbeat_at, expires_at
```

`*` **M2 加法扩展**：`tasks.evidence_json` 不在 §6.1 里，但 P0 不变量“`done` 至少一条 evidence”（§3.1）需要在控制面复用时保留，故加列；`version` 同时承担乐观锁。

事件类型（本 slice 产生的）：`task.created`、`task.status_changed`、`run.started`、`run.finished`、`lease.acquired`、`lease.renewed`、`lease.released`、`lease.expired`、`control.recovered`。
事件 payload 经 `redactRecord` 处理（token/secret/authorization 等字段与 `sk-*`/凭据样式字符串会被 `[REDACTED]`，字符串截断到 500 字符），事件不进入日志/模型上下文。

## 4. 公共 API（`src/control/index.ts`）

```ts
import {
  openControl, createControlServer, controlDbPath, controlPaths,
  acquireLease, renewLease, releaseLease, expireLeases, getLease, listLeases,
  recoverStale, DEFAULT_LEASE_TTL_MS, DEFAULT_HEARTBEAT_MS, CONTROL_SCHEMA_VERSION,
} from "<pkg>/dist/control/index.js";
```

### 4.1 Store

```ts
const store = openControl(projectRoot, {
  // 均可选
  readOnly?: boolean,        // true：不持写锁；缺失 DB 抛 E_CONTROL_DB_NOT_FOUND
  leaseTtlMs?: number,       // 默认 30_000
  heartbeatMs?: number,      // 默认 10_000（提示值，不自动心跳）
  clock?: () => Date,        // 测试注入；默认系统时钟
  dbPath?: string,           // 测试/高级用，默认 .sage-kit/control/control.db
});

store.close();                     // 幂等；释放 SQLite 连接与 writer.lock
store.nowIso();                    // 注入时钟的当前 UTC ISO
store.transaction(fn);             // BEGIN IMMEDIATE; 可嵌套（内层直接执行）
store.debugInfo();                 // {dbPath, journalMode, foreignKeys, busyTimeout, synchronous, userVersion, leaseTtlMs, heartbeatMs, readOnly, projectRoot}
store.db;                          // 低层逃生口（测试/诊断）；业务代码优先用方法

// 任务
store.createTask({ title, description?, acceptance?, status?, priority?, source?,
                   externalId?, externalUrl?, worktreePath?, branch?, id?, idempotencyKey? });
store.getTask(id);                 // E_TASK_NOT_FOUND
store.listTasks({ status?, limit? });   // updated_at DESC，limit 默认 100、上限 1000
store.updateTaskStatus(id, next, { evidence?: string[], note?, source?, blockedReason?,
                                   expectedVersion?, now? });

// 运行
store.recordRun({ taskId, host?, status?: "starting"|"running", command?: string[],
                  worktreePath?, startedAt?, id?, idempotencyKey? });
store.getRun(id);
store.listRuns({ taskId?, status?, limit? });
store.finishRun(id, { status: "exited"|"failed"|"cancelled"|"interrupted",
                      exitCode?, costUsd?, inputTokens?, outputTokens?,
                      errorCode?, errorMessage?, endedAt? });

// 事件
store.appendEvent({ type, data?, taskId?, runId?, createdAt? });
store.listEvents({ taskId?, runId?, type?, limit? });   // created_at ASC, seq ASC

// lease
store.acquireLease(taskId, { owner, runId?, ttlMs?, now? });
store.renewLease(taskId, { owner, ttlMs?, now? });
store.releaseLease(taskId, { owner?, now? });
store.getLease(taskId);            // 无则 undefined
store.listLeases({ includeExpired?: boolean, now? });
store.expireLeases({ now? });      // 扫描并中断所有 expires_at <= now

// 恢复
store.recoverStale({ now?, staleRunAfterMs? });
// 同签名独立导出也提供：recoverStale(store, options)
// → { scannedAt, expiredLeases: ControlLease[], interruptedRuns: ControlRun[],
//     interruptedTasks: string[] }
```

`acquireLease` / `renewLease` / `releaseLease` / `expireLeases` / `getLease` / `listLeases` 也以独立函数导出，签名统一为 `(store, taskId, options)`，便于在不持有 `ControlStore` 类的地方注入/测试。

### 4.2 语义约定

- 时间全部为 UTC ISO 8601；`now` 参数只用于确定性测试/恢复扫描。
- 任务 id、run id 均匹配 `[a-z0-9][a-z0-9-]{0,63}`；外部输入先校验再进 SQL。
- 状态转换表与 `src/core/tasks.ts` 的 `TRANSITIONS` 完全一致（见 §5）；`done` 额外要求 evidence。
- `updateTaskStatus(expectedVersion)` 做乐观并发；每次成功更新 `version + 1`。
- `createTask` / `recordRun` 支持 `idempotencyKey`：重复请求返回原记录，不产生第二条。
- `finishRun` 对相同终态幂等；把已结束 run 改成其他终态抛 `E_RUN_ALREADY_FINISHED`。
- 写方法内部使用 `BEGIN IMMEDIATE`；抛错回滚；嵌套调用合并进外层事务。

### 4.3 HTTP server

```ts
const server = await createControlServer({ store, host?, port? });
// host 只允许 "127.0.0.1"（默认）；其他值在 listen 前抛 E_BAD_HOST
// port 默认 0（临时端口），server.port / server.url 返回实际值
server.url;      // http://127.0.0.1:<port>
server.close();  // 幂等
```

端点（本地 loopback 单用户，不需要 token）：

| 方法 | 路径 | 请求 | 成功响应 |
|---|---|---|---|
| GET | `/v1/health` | — | `{ok:true, service:"sage-kit-control", apiVersion:1, schemaVersion, now}` |
| GET | `/v1/tasks` | `?status=<TaskStatus>` 可选 | `{tasks:[ControlTask...]}` |
| GET | `/v1/tasks/:id` | — | `{task, runs, events, lease}` |
| GET | `/v1/events` | `?taskId=&runId=&type=&limit=` 可选 | `{events:[ControlEvent...]}`（created_at/seq 升序） |
| POST | `/v1/tasks` | `{title, description?, acceptance?, priority?, source?}` | `{task}` |
| POST | `/v1/tasks/:id/status` | `{status, evidence?, note?, blockedReason?, expectedVersion?}` | `{task}` |
| POST | `/v1/leases/acquire` | `{taskId, owner, runId?, ttlMs?}` | `{lease: ControlLease}` |
| POST | `/v1/leases/renew` | `{taskId, owner, ttlMs?}` | `{lease: ControlLease}` |
| POST | `/v1/leases/release` | `{taskId, owner?}` | `{released:true, lease}` |
| POST | `/v1/recover` | `{staleRunAfterMs?}`（可空 body） | `{report: RecoveryReport}` |

`GET /v1/tasks/:id` 的 `runs` 是该任务的全部 run，`events` 是该任务的事件（按 seq 升序），`lease` 是当前租约或 `null`。它是只读详情，不改变任何状态；所有写操作只由表中的 POST 端点触发。

写端点语义（复用 `ControlStore` 方法，不另造状态机）：

- `POST /v1/tasks`：`title` 必填（≤200），`description` ≤2000，`acceptance` 最多 20 条、每条 ≤500，`priority` 为整数，`source` ≤200；创建任务默认 `status = "ready"`（不接受 `done`），返回 HTTP 200 `{task}`。`description/acceptance/priority/source` 为空时不写入。
- `POST /v1/tasks/:id/status`：直接调用 `store.updateTaskStatus`。`evidence` 最多 20 条、每条 ≤1000；`note`/`blockedReason` ≤1000；`expectedVersion` 有值时做乐观并发校验；`done` 至少一条 evidence。成功返回更新后的 `{task}`（`version + 1`）。
- `POST /v1/leases/renew`：校验 owner 后刷新 `heartbeat_at`/`expires_at`；过期/owner 不匹配按 §6 语义报错（过期副作用先提交后返回 `E_LEASE_EXPIRED`）。
- `GET /v1/events`：`taskId`/`runId`/`type` 可选，`limit` 必须是正整数（默认 100、上限 1000）；非法参数 → 400。
- `POST /v1/recover`：等价于 `store.recoverStale({ staleRunAfterMs? })`；报告里的过期/中断副作用已经提交，重复调用返回空报告。

错误统一为 `{error:{code, message}}`，HTTP 状态映射：

```text
403 E_NON_LOOPBACK      404 E_NOT_FOUND / E_TASK_NOT_FOUND / E_RUN_NOT_FOUND / E_LEASE_NOT_HELD
405 E_METHOD_NOT_ALLOWED（带 Allow）
409 E_LEASE_HELD / E_LEASE_EXPIRED / E_LEASE_OWNER_MISMATCH / E_BAD_TRANSITION /
    E_TASK_EXISTS / E_RUN_EXISTS / E_TASK_VERSION_CONFLICT / E_RUN_ALREADY_FINISHED /
    E_DONE_WITHOUT_EVIDENCE / E_EVENT_SCOPE_MISMATCH
400 E_BAD_* / E_USAGE / E_BAD_TASK / E_BAD_STATUS / E_BAD_RECOVERY_OPTION
413 E_BODY_TOO_LARGE       500 其他（E_INTERNAL 等，不回显栈）
```

安全边界：

- 只 `listen("127.0.0.1")`；listen 后再次校验 `server.address()` 是 loopback，否则关闭。
- 每个连接校验 `socket.remoteAddress` ∈ {`127.0.0.1`,`::1`,`::ffff:127.0.0.1`}。
- 校验 `Host` 头只接受 loopback/localhost（防 DNS rebinding）；异常 Host → 403。
- 写请求（POST）额外校验：`Origin` 必须是同源 loopback 或缺失，`Sec-Fetch-Site` 不得为 cross-site，`Content-Type` 必须是 `application/json`；否则 403/415，且不调用 store。真实浏览器攻击与 socket 集成仍属未执行边界；本机程序调用不受影响。
- **不设 Bearer token**：本地单用户工具的信任边界是 loopback + OS 账户；同一 OS 用户下的进程可以读取并写入控制面状态。这不是远程/多用户安全边界，也不把控制面暴露到非 loopback。
- 请求体上限 64 KiB，事件 payload 上限 32 KiB；非法 JSON → 400；未知路由 → 404。
- 无 CORS、无第三方静态资源、无 TLS（仅 loopback，本地进程间调用）。
- `GET /` 与 `GET /ui` 返回自包含 HTML 控制面板（无数据）；页面自动读取 `/v1/health`、`/v1/tasks`，单击任务读取 `/v1/tasks/:id`；页面的「新建任务」「状态转换」「获取/续期/释放租约」「恢复 stale」按钮调用上述 POST 端点；CSP 禁止外部脚本/样式、`frame-ancestors 'none'`；无 token、无第三方资源。

### 4.4 Web UI（`src/control/ui.ts`）

- 同源自包含页面，`GET /` 与 `/ui` 均返回；无前端框架/构建链/CORS，只有一段内联 classic script（测试用 `new Function` 校验可解析）。
- 布局：桌面双列（任务列表 + 详情）、窄屏单列；视觉 token 固定（字号 12/13/14/16/20/28，间距 8/12/16/24）。
- 任务列表：按标题/ID/状态过滤、状态 pill、优先级；加载时读取 health + tasks，点击任务行即读取详情。
- 详情：状态/优先级/版本/时间/分支/来源/外部链接/工作树/幂等键等字段；任务操作区包含状态转换、lease 控件；下方为描述、验收标准、证据、运行记录、事件。
- 写交互：任务操作区只列出当前状态允许的目标转换（前端镜像 `TRANSITIONS`，仅用于可用性），可填备注/证据/阻塞原因；提交带 `expectedVersion`。成功刷新详情并 toast；服务端 400/409 回显在 `#status-error`（如 `E_DONE_WITHOUT_EVIDENCE`、`E_TASK_VERSION_CONFLICT`），不会静默纠正。
- lease：无租约时输入 owner（默认 `local-ui`）与可选 TTL 后 acquire；持有后显示 renew/release。
- 新建任务：模态框表单（标题/描述/验收标准每行一条/优先级/来源），前端校验标题必填，Esc/背景点击/取消关闭；成功后自动选中新任务。
- 恢复 stale：页头「恢复 stale」按钮调用 `POST /v1/recover`，toast 报告过期租约/中断运行/中断任务数量后刷新列表。
- 反馈与安全：所有动态值用 `textContent` 写入（防 XSS）；错误以内联提示 + toast（最多同时 3 条，success 4s / error 6s 自动消失）；无 token 输入、无外部请求。

## 5. 任务状态机（与 P0 一致）

```text
imported    → ready | blocked | failed
ready       → running | blocked | failed | cancelled
running     → review | blocked | failed | cancelled | interrupted
review      → done | running | blocked | failed | cancelled
blocked     → ready | running | failed | cancelled
failed      → ready | running
interrupted → ready | running | failed
done / cancelled → 终态
```

- `createTask` 禁止 `status: done`；`imported` 等非默认状态可用于导入路径。
- 非法转换 `E_BAD_TRANSITION`；`done` 无 evidence `E_DONE_WITHOUT_EVIDENCE`。
- `blockedReason` 在进入 `blocked` 时写入（未提供则 `"blocked"`），离开 `blocked` 时清空。

## 6. Lease 语义（30s / 10s 可配置）

- **单任务单 lease**：`leases.task_id` 是主键；有效租约存在时任何再 acquire 都返回 `E_LEASE_HELD`（同 owner 也拒绝）。
- **acquire 会驱动状态机**：任务不是 `running` 时先走合法转换到 `running`（`imported`/`done`/`cancelled` 会得到 `E_BAD_TRANSITION`），再写 lease 与 `lease.acquired` 事件。
- **过期 lease = 恢复事件，不是自动重跑**：
  - `acquireLease`/`renewLease` 发现 `expires_at <= now` 时，先**提交**“过期副作用”（任务 `running → interrupted`、绑定 run → `interrupted`、`lease.expired` 事件、删除 lease），然后才抛 `E_LEASE_EXPIRED`。副作用放在事务内提交后再抛错，避免回滚吞掉恢复记录。
  - 调用方必须显式调用 `recoverStale()` / 确认后再重新 acquire；控制面不会自动创建 lease 或新 run。
- **renew** 检查 owner；成功刷新 `heartbeat_at`/`expires_at`（`now + ttl`）。
- **release** 检查可选 owner；只删 lease 与写 `lease.released`，**不改任务状态**（完成/失败由调用方显式 `updateTaskStatus`）。
- `heartbeatMs` 是提示值：本实现不内建定时器、不自动续租；Worker 应每个 heartbeat 周期调用 renew。
- lease 过期不依赖进程序号/pid；只要调用方（控制面）还健在就能扫描。控制面进程本身崩溃时，下次启动调用 `recoverStale()` 即可。

## 7. 恢复语义（`recoverStale`）

顺序：

1. `expireLeases(now)`：所有过期 lease → 任务 `running → interrupted`；lease 绑定的 active run → `interrupted`；删 lease；写事件。
2. 扫描 `runs.status in ('starting','running')` 且 `started_at <= now - staleRunAfterMs`（默认 `0`）：
   - 该任务若有**未过期 lease**，跳过（活 Worker 的心跳保护该 run）。
   - 否则 run → `interrupted`（写 `ended_at` + `run.finished{reason:"stale_run"}`）。
   - 若该任务仍是 `running` 且已无其他 active run，任务 → `interrupted`。
3. 有变更时写一条全局 `control.recovered` 事件（汇总 task/run id）。
4. 返回 `RecoveryReport`；再次调用应为空报告（幂等）。

限制：没有 run 的 `running` 任务、以及从未 acquire 过 lease 的 `running` 任务不会被扫描改动；`staleRunAfterMs = 0` 意味着“无活 lease 的 active run 即视为孤儿”，若外部 runner 不 acquire lease 直接 `recordRun`，需要传入更大的窗口。恢复**绝不**创建 run/lease，也绝不把任务标成 `done`。

## 8. 单写者

- `.sage-kit/control/writer.lock` 内容 `{"pid":<pid>,"owner":"<random>","startedAt":"<iso>"}`。
- 第二个写者 open 时：owner pid 仍存活 → `E_WRITER_LOCKED`；pid 已死或锁内容损坏 → 视为 stale，删除后接管（崩溃恢复路径）。
- `close()` 只删除 owner 匹配的锁；`readOnly` open 不创建/不检查锁（只读诊断用）。
- 这把锁只解决“本机同 project root 的进程级单写者”；SQLite `busy_timeout=5000` 只作为二道防线。跨机器/多进程并发写不在范围（D-007）。

## 9. 错误码索引

| 领域 | 错误码 |
|---|---|
| open/config | `E_BAD_CONFIG` `E_WRITER_LOCK` `E_WRITER_LOCKED` `E_DB_PRAGMA` `E_DB_MIGRATION` `E_DB_SCHEMA_NEWER` `E_CONTROL_DB_OPEN` `E_CONTROL_DB_NOT_FOUND` `E_CONTROL_DB_NOT_INITIALIZED` `E_CONTROL_CLOSED` `E_CONTROL_READ_ONLY` |
| task | `E_BAD_TASK` `E_BAD_TASK_ID` `E_BAD_STATUS` `E_TASK_EXISTS` `E_TASK_NOT_FOUND` `E_BAD_TRANSITION` `E_DONE_WITHOUT_EVIDENCE` `E_TASK_VERSION_CONFLICT` |
| run | `E_BAD_RUN` `E_BAD_RUN_ID` `E_BAD_RUN_STATUS` `E_BAD_RUN_COMMAND` `E_RUN_EXISTS` `E_RUN_NOT_FOUND` `E_RUN_TASK_MISMATCH` `E_RUN_ALREADY_FINISHED` |
| event | `E_BAD_EVENT` `E_BAD_EVENT_DATA` `E_EVENT_TOO_LARGE` `E_EVENT_SCOPE_MISMATCH` |
| lease | `E_BAD_LEASE_OWNER` `E_BAD_LEASE_TTL` `E_LEASE_HELD` `E_LEASE_NOT_HELD` `E_LEASE_OWNER_MISMATCH` `E_LEASE_EXPIRED` |
| recovery/db | `E_BAD_RECOVERY_OPTION` `E_BAD_TIME` `E_BAD_PAGINATION` `E_BAD_DB_ROW` |
| HTTP | `E_BAD_HOST` `E_BAD_PORT` `E_NON_LOOPBACK` `E_BAD_JSON` `E_BAD_REQUEST` `E_BODY_TOO_LARGE` `E_METHOD_NOT_ALLOWED` `E_NOT_FOUND` `E_LISTEN_FAILED` `E_INTERNAL` |

## 10. 设计决定（schema/API）

- **A. 复用 P0 状态机**：`TRANSITIONS` 在 `src/core/tasks.ts` 未导出，故在 `src/control/schema.ts` 镜像同一张表并在测试里覆盖同一边界。风险：P0 改表时需同步；`src/control/**` 之外的 owner 改动 `core/tasks.ts` 时请同步通知。
- **B. 过期副作用先提交再抛错**：`acquireLease`/`renewLease` 的过期处理返回 outcome，事务提交后才抛 `E_LEASE_EXPIRED`，保证“标记 interrupted”不会因回滚丢失。
- **C. 事件分 scope 递增**：run 事件用 run 内 `seq`，任务事件用 task 内 `seq`（`run_id IS NULL`），两者皆空用全局 `seq`；partial unique index 保证唯一。lease 事件是 task-scope，绑定的 run id 放在 payload。
- **D. `evidence_json` 扩展**：为了让控制面复用 P0 的 `done` 证据不变量；纯加法列，列名/语义见 §3。
- **E. 文件锁而非 SQLite exclusive lock**：`locking_mode=EXCLUSIVE` 会让第二个进程等 5s 才报 “database is locked”，错误不可读；writer.lock 能立即给出 `E_WRITER_LOCKED` 并支持死进程接管。
- **F. `recoverStale` 以 lease 而非 pid 判定存活**：schema 无 pid 列（§6.2），活 Worker 的租约心跳就是存活证明；无 lease 的 active run 默认视为孤儿（`staleRunAfterMs=0`）。
- **G. 同步 store + 同步 handler**：`node:sqlite` 是同步 API；本地单用户、请求量极小，HTTP handler 直接调同步方法，不做线程池/队列抽象（D-015）。
- **H. `createControlServer` 为 async**：返回时已完成 listen，调用方可直接 `server.url` 发请求；端口 0 便于测试与并行实例。
- **I. 本地单用户不设 token**：控制面只绑定 `127.0.0.1` 并校验 loopback Host；信任边界是 OS 用户账户，不把“本机进程也要 token”当作必要复杂度。远程/多用户访问不在范围（D-007），若未来需要，另立鉴权契约。
- **J. 无鉴权内省**：health/tasks/task-detail 都可在 loopback 读取；它们不包含密钥，事件 payload 已经过 `redactRecord`。控制面仍不暴露到非 loopback。
- **K. 写操作只经 loopback UI/API（D-022 修订）**：任务创建、状态转换、lease、恢复全部通过本节 HTTP 端点完成，复用 `ControlStore` 的写方法与 P0 状态机；不新增前端框架、CORS、远程访问或 token。服务端仍是唯一权威：`expectedVersion` 乐观并发、状态机/证据校验都在 store 内，UI 只是薄客户端。
- **L. UI 镜像状态机仅为可用性**：`src/control/ui.ts` 内置 `TRANSITIONS` 副本用于过滤可选目标状态和显示提示；最终校验在服务端，非法/过期请求回显 400/409，不静默纠正。
- **M. HTTP 写端点是薄封装**：handler 只做 body 解析、参数上限校验和错误码映射，然后调用 store；不在 HTTP 层复制业务规则，避免出现第二套状态机/租约逻辑。

## 11. 明确非目标与集成注意

- CLI 已接线：`sage-kit control serve`、`control status`、`control recover`；`src/cli.ts` 使用动态 import，避免拖慢默认 CLI 启动（D-002/D-004）。`control serve` 现在只接受 `--port`/`--recover`/`--json`，启动后直接打印 UI URL；不再生成或打印 token。
- `package.json` 的 `test` 已由 Lead 加入 `tests/control.test.mjs` 与 `tests/feedback.test.mjs`、`tests/rsi.test.mjs`。
- 模式切换/迁移（`state export/import/migrate`）、备份恢复、`config.json` 的 `mode` 字段：**范围外**；文件模式是默认，控制面不提供迁移/备份，避免双写和额外状态。
- `runs` 的 pid/监督、自动心跳、run 结束时自动 `task review/failed` 迁移、lease 自动续租：**范围外**；Worker/CLI 显式调用对应方法，控制面不托管进程。
- HTTP 已提供 9 条路由 / 10 个操作（含任务创建、状态转换、lease renew、events 查询、recover）；events 分页 cursor、run/event 独立分页、rate limit、CORS/TLS 属于范围外。
- 面板不创建/监督 run（无 run 写端点），运行记录由外部 worker 调 store；UI 只读展示 runs/events——这是本地单用户控制面的边界，不是缺功能。
- `node:sqlite`：Windows Node v24.22.0 直接可用；WSL Node v22.22.1 也可用但会打印 ExperimentalWarning。`package.json` engines 为 `>=22.20`（`node:sqlite` 下限）；核心 P0 路径不会因控制面 import 失败而崩溃（保持 lazy import）。
- 已知边界：锁文件的 pid 可能被系统复用（极端情况下误判“存活”），可手动删除死锁文件；`STRICT` 表需要 SQLite ≥3.37（Node 22.22/24 内置版本已满足）；`recoverStale` 无 pid 校验，外部 runner 若不走 lease 需要传 `staleRunAfterMs`；无多进程读池/backup/artifacts。
- 写操作信任边界：无 CSRF token；对写请求校验 `Origin`（只接受同源 loopback 或缺失）、`Sec-Fetch-Site`（拒绝 cross-site）和 JSON `Content-Type`（非 JSON 返回 415），并只绑定 loopback + OS 账户（D-022）——同机同用户进程可写控制面状态；`POST /v1/tasks` 未强制幂等键，重试可能创建重复任务（UI 按钮忙态缓解）；`POST /v1/recover` 的 `staleRunAfterMs` 仅 API 参数，UI 固定使用默认值 0。

## 12. 文件清单（本 slice）

```text
src/control/index.ts     # 公共导出
src/control/schema.ts    # 路径、PRAGMA、迁移、schema、行解码
src/control/store.ts     # ControlStore/openControl：任务、run、事件、恢复、单写者
src/control/lease.ts     # lease 规则（acquire/renew/release/expire）+ 过期副作用
src/control/server.ts    # 127.0.0.1 JSON API（10 端点，读写）+ UI 路由
src/control/ui.ts        # 自包含本地控制面板（无 token、单击详情、新建/状态转换/lease/恢复）
tests/control.test.mjs   # 39 个测试（schema/任务/run/事件/lease/恢复/HTTP/UI）
docs/m2-control.md       # 本文
docs/decisions.md        # D-022（本地可写面板修订）
```
