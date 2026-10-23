# M3 RSI 骨架（提案 / 评估 / 人工批准 / 回滚点）

**状态：M3 skeleton 已实现并已验证（`IMPLEMENTED` / `VERIFIED`）；自主循环、定时调度、自动批准/合并/发布、控制面集成未实现（`NOT_IMPLEMENTED`）。**
本文只描述 `src/rsi/**` 这一个可选层。它不改变 P0 文件模式，不写 `.sage-kit/state/` 以外的业务状态，不接 CLI（CLI 接线由 Lead 负责，见 §12），不新增依赖、不联网、不调用模型。设计基线：`docs/feedback-and-rsi.md` §5–§9/§12、`docs/decisions.md` D-011（RSI 最高 L2、人工批准）、D-012（Builder/Evaluator 分离、评估资产受保护）、D-017（日志/状态脱敏）、D-018（不得把设计写成已实现）、D-005（单一权威写入源）。

验证环境与证据（2026-10-24，Windows，Node v24.22.0，`npm run build` 通过）：

```text
# 类型检查
npm run build                     # tsc -p tsconfig.json

# 本模块测试
node --test tests/rsi.test.mjs
# tests 12, suites 3, pass 12, fail 0, cancelled 0, skipped 0
```

测试覆盖：fixture 提案的创建/重载/损坏检测、失败候选被阻断且不自动重试、通过候选必须显式批准且需要 token/回滚点、审批挑战过期、受保护测试文件拒绝、diff/文件数与超时预算、单候选锁与 stale 锁接管、`runOnce` 只手动执行且一次一个候选、静态检查无网络/模型 SDK/默认定时器。

## 1. 范围与实现状态

| 能力 | 状态 | 说明 |
|---|---|---|
| 提案类型、校验、文件模式 store（`.sage-kit/rsi/`） | `IMPLEMENTED` | 原子写、损坏记录报错、不返回半条数据 |
| 固定评估命令 + 隔离临时副本 | `IMPLEMENTED` | 命令由 evaluator wiring 提供，spawn 无 shell；源工作区只读 |
| pass/fail 判定、退出码、超时、日志摘要 | `IMPLEMENTED` | 日志脱敏 + 每流 16 KiB 截断；200k 字符内存上限 |
| 受保护评估资产双重检查 | `IMPLEMENTED` | 评估前按路径拒绝；运行前后 sha256 manifest 对比 |
| diff 预算（默认 500 行 / 20 文件，可配置） | `IMPLEMENTED` | 超预算在跑测试前失败并记录 |
| 一次性人工 approval token | `IMPLEMENTED` | 32 hex，仅存 sha256，`timingSafeEqual`，默认 24h TTL |
| 显式人工决定（`decidedBy`）与拒绝记录 | `IMPLEMENTED` | 匿名批准被拒绝；拒绝同样落 `approvals/` |
| 回滚点记录 | `IMPLEMENTED` | 记录 `git checkout <baseCommit>` 指引；**不执行**回滚 |
| 手动 `runOnce`，一次一个候选 | `IMPLEMENTED` | 无默认定时器；可到 `awaiting_approval`，不会自动批准 |
| 单候选评估锁（PID stale 接管） | `IMPLEMENTED` | 同机同 project root；崩溃留下的死锁可接管 |
| `npm test` 接线 / `src/cli.ts` 子命令 | `IMPLEMENTED`（Lead） | `rsi create/list/run-once/request-approval/rollback-point/approve/reject`；lazy import |
| 定时同步/定时评估、自动批准、自动合并/发布、重写 `SKILL.md` | `NOT_IMPLEMENTED`（按 D-011 不实现） | 最高 L2；人工批准后由人执行发布 |
| Builder 生成候选、反馈同步/分类、M1 反馈源接入 | `NOT_IMPLEMENTED`（M3b 及 M1 接线） | 本 slice 接收已给好的 `CandidateFile[]` |
| SQLite 控制面集成、真实 `git worktree`、依赖安装、holdout/隐藏套件、基线对照、重复 ≥3 次评估 | `NOT_IMPLEMENTED`（M3b） | 见 §8、§12 |
| 网络请求 / 模型调用 | **不实现**（设计禁止） | 仅 Node 内置能力；静态测试断言无 `fetch`/网络模块/模型 SDK |

## 2. 文件布局与写入边界

```text
<project-root>/.sage-kit/rsi/
  proposals/<id>.json          # 提案 + 状态机字段
  evaluations/<id>.json        # 一次评估的完整证据
  approvals/<id>.json          # approved/rejected 记录
  rollback-points/<id>.json    # 回滚点
  evaluation.lock              # 单候选评估锁；JSON {pid, owner, startedAt}
```

- 路径由 `rsiPaths(projectRoot)` 给出；`openRsi()` 只计算路径，写方法按需创建目录（0700）。本 repo 的 `.gitignore` 忽略 `.sage-kit/`，所以状态不会进提交。
- 本模块**只**写 `.sage-kit/rsi/` 和 OS 临时目录；不读写 `.sage-kit/state/**`、`.sage-kit/control/**`、`SKILL.md`、`package.json`、git 历史。候选文件**只**写入临时副本，绝不写源工作区。
- 评估副本：`createEvaluationWorkspace()` 用 `fs.cp` 复制项目到 `os.tmpdir()/sage-kit-rsi-eval-*`，默认排除 `.git`、`.sage-kit`、`.dsh`、`node_modules`、`dist`、`work`、`coverage`、`reports`；无论成功失败，`finally` 中删除副本（`workspace.removed` 记录结果）。
- 单写者：文件模式仍是唯一权威写入源（D-005）；本模块不打开控制面 SQLite，也不要求控制面已启用。

## 3. 提案与状态机

提案记录（`Proposal`，schemaVersion 1）主要字段：

```json
{
  "schemaVersion": 1,
  "id": "prop-20260101000000-a1b2c3",
  "createdAt": "2026-01-01T00:00:00.000Z",
  "updatedAt": "2026-01-01T00:00:00.000Z",
  "feedbackRefs": [{ "id": "issue-1", "url": "https://...", "untrustedData": true }],
  "baseVersion": "0.1.0",
  "baseCommit": "0123456789abcdef0123456789abcdef01234567",
  "hypothesis": "改什么、为什么、预期影响",
  "scope": ["src/rsi/evaluate.ts"],
  "risks": ["回归风险"],
  "validationPlan": "运行的套件/指标/阈值",
  "rollbackPlan": "如何回滚",
  "candidate": { "builder": "builder-a", "summary": "改了什么", "files": [{ "path": "src/a.ts", "content": "..." }] },
  "status": "proposed",
  "attempts": 0,
  "evaluationId": "...",
  "approvalId": "...",
  "rollbackPointId": "...",
  "approvalChallenge": { "tokenHash": "<sha256 hex>", "createdAt": "...", "expiresAt": "..." }
}
```

约束：

- `feedbackRefs` 只存 id/URL/标题，统一加 `untrustedData: true`；URL 仅允许 http(s)。外部正文不进入提案、不执行（§4.3、D-011）。
- `baseCommit` 为 7–64 位小写十六进制；`baseVersion` 为 semver 风格标识；`candidate.files` 为非空数组，路径必须是项目相对 POSIX 路径，拒绝绝对路径、`..`、`.git/`、`.sage-kit/` 和重复路径。
- `content: null` 表示删除文件；候选不会携带可执行命令。

状态机（本 skeleton 只走这些边）：

```text
proposed        → evaluating → failed | awaiting_approval
proposed        → rejected（人工直接拒绝，无需先评估）
awaiting_approval → approved（approve）| rejected（rejectProposal）
failed / approved / rejected → 终态（不自动重试、不自动迁移）
```

- `attempts` 在进入 `evaluating` 时 +1；本 skeleton 每个提案最多评估一次，失败后保持 `failed`，再次 `runOnce` 不会重试（§9 预算：失败不自动无限重试，等待人工）。
- 只有 `proposed` 能进入评估；非 `proposed` 调 `evaluateCandidate()` 抛 `E_RSI_BAD_TRANSITION`。
- 只有 `awaiting_approval` 且评估 `passed` 能请求/执行批准；批准成功后才写 `approved`。

## 4. 公共 API（`src/rsi/index.ts`）

```ts
import {
  openRsi, rsiPaths, ensureRsiPaths,
  evaluateCandidate, runOnce, acquireEvaluationLock,
  requestApproval, approve, rejectProposal, createRollbackPoint,
  runFixedCommand, createEvaluationWorkspace,
  DEFAULT_RSI_LIMITS, DEFAULT_PROTECTED_PATHS, DEFAULT_APPROVAL_TTL_MS,
  RSI_SCHEMA_VERSION, RSI_PROPOSAL_STATUSES,
} from "<pkg>/dist/rsi/index.js";
```

```ts
const store = openRsi(projectRoot, { clock?: () => Date }); // clock 用于确定性测试

// 提案（evaluator/approval 状态机内部也使用 saveProposal）
store.createProposal({ baseVersion, baseCommit, hypothesis, scope, risks,
                       validationPlan, rollbackPlan, candidate, feedbackRefs?, note?, id? });
store.getProposal(id);                       // E_RSI_NOT_FOUND / E_RSI_STORE_CORRUPT
store.listProposals({ status? });            // createdAt/id 升序（runOnce 取最早 proposed）
store.saveProposal(proposal);

// 评估证据
store.getEvaluation(id);                     // E_RSI_NOT_FOUND / E_RSI_STORE_CORRUPT
store.listEvaluations({ proposalId? });      // startedAt/id 升序
store.saveEvaluation(evaluation);

// 审批记录 / 回滚点
store.getApproval(id); store.listApprovals({ proposalId? }); store.saveApproval(approval);
store.getRollbackPoint(id); store.listRollbackPoints(); store.saveRollbackPoint(point);

// 手动跑一个候选；没有 proposed 提案时返回 { outcome: "idle", evaluated: 0 }
await runOnce({
  projectRoot,                 // 或传 store
  testCommand: ["node", "--test", "tests/check.test.mjs"], // evaluator 固定套件
  limits?: { maxCandidateFiles, maxChangedLines, maxLogBytes, evaluationTimeoutMs },
  protectedPaths?: string[],   // 默认 DEFAULT_PROTECTED_PATHS
  copyExclude?: string[],      // 临时副本额外排除的顶层目录
});
// → { outcome: "idle"|"passed"|"failed", evaluated: 0|1,
//     proposalId?, evaluationId?, status?, reasonCode? }

// 单候选评估（runOnce 内部也用它；直接调用时需自己保证人工触发）
await evaluateCandidate({ projectRoot, proposalId, testCommand, limits?, protectedPaths?, copyExclude? });

// 人工审批闸门
const challenge = await requestApproval({ projectRoot, proposalId, approvalTtlMs? });
// challenge = { proposalId, approvalToken: "<32 hex, 只出现一次>", expiresAt }
const point = await createRollbackPoint({ projectRoot, baseCommit, baseVersion, artifactPath?, note? });
// point.rollbackCommand === `git checkout ${baseCommit}`（仅指引，不执行）
await approve({ projectRoot, proposalId, approvalToken: challenge.approvalToken,
                decidedBy: "human-name", rollbackPointId: point.id, note? });
await rejectProposal({ projectRoot, proposalId, decidedBy: "human-name", reason: "..." });

// 手动评估锁（测试/高级用；runOnce 自动 acquire/release）
const lock = await acquireEvaluationLock(store);
await lock.release();

// 固定命令执行器（可脱离 RSI 复用；超时 SIGTERM→2s 后 SIGKILL）
await runFixedCommand(["node", "--version"], cwd, { timeoutMs: 10_000 });
```

默认值：`DEFAULT_RSI_LIMITS = { maxCandidateFiles: 20, maxChangedLines: 500, maxLogBytes: 16_384, evaluationTimeoutMs: 120_000 }`；`DEFAULT_PROTECTED_PATHS = ["tests","test","eval","holdout",".github","package.json","package-lock.json"]`；`DEFAULT_APPROVAL_TTL_MS = 24h`。

## 5. 评估流程（Builder / Evaluator 分离）

`evaluateCandidate()` 的顺序：

1. 校验输入（proposal id、固定命令、limits、protectedPaths）并获取全局评估锁；提案必须仍是 `proposed`。
2. `assessCandidate()` 在**源工作区只读基线**上计算候选 diff 统计：受保护路径命中、文件数、变更行数（前后缀裁剪的确定性近似，不做 LCS）。命中受保护资产或超预算时，**不创建副本、不跑测试**，直接写 `outcome: "failed"` 的评估并把提案置 `failed`。
3. 计算源工作区受保护资产的 sha256 manifest。
4. 复制项目到 OS 临时目录（排除重目录），在副本中应用候选文件；任何写错误记为 `E_RSI_CANDIDATE_APPLY_FAILED`。
5. 在副本中运行 evaluator wiring 提供的**固定命令**（不来自提案/候选），`shell: false`，硬超时；子进程环境会剥离宿主测试运行器变量（见 §10 G）。
6. 运行后重新计算副本的受保护 manifest 并与基线对比：测试套件若篡改测试/阈值/发布配置，同样判 `failed`（D-012）。
7. 记录 `Evaluation`（outcome/reasonCode/exitCode/signal/timedOut/durationMs/diff/protectedAssets/日志摘要/workspace），删除副本，移动提案状态：`passed → awaiting_approval`，否则 `failed`。

评估记录（`Evaluation`）关键字段：`command`（实际执行的固定命令，审计用）、`ranTests`（预检失败为 false）、`diff`（files/changedLines/limits）、`protectedAssets`（paths/ok/changed）、`workspace`（temp-copy/tempDir/removed）、`log`（stdout/stderr/truncated，已脱敏）。失败原因码：

| reasonCode | 含义 |
|---|---|
| `E_RSI_PROTECTED_ASSET` | 候选路径命中受保护资产（预检，未运行） |
| `E_RSI_DIFF_TOO_LARGE` | 文件数或变更行数超预算（预检，未运行） |
| `E_RSI_CANDIDATE_APPLY_FAILED` | 候选写入副本失败 |
| `E_RSI_EVALUATION_FAILED` | 固定命令未能启动（通用兜底） |
| `E_RSI_EVAL_SPAWN_FAILED` | spawn 失败（如命令不存在） |
| `E_RSI_EVAL_TIMEOUT` | 固定命令超时被杀 |
| `E_RSI_TESTS_FAILED` | 命令退出码非 0 |
| `E_RSI_PROTECTED_ASSET_CHANGED` | 运行后受保护资产 manifest 变化 |
| `E_RSI_PROTECTED_ASSET_UNVERIFIED` | 运行后 manifest 计算失败 |

闭合条件（通过 = 无 reasonCode）：命令实际运行、退出码 0、未超时、受保护资产运行前后一致。skeleton **不做** p0/regression/holdout 多套件、基线对照、多次重复；这些由 evaluator wiring 的固定命令自行组合（§12）。

## 6. 人工批准与回滚点

- `requestApproval()` 只为 `awaiting_approval`（评估 `passed`）的提案创建挑战；返回唯一一次明文 token（`randomBytes(16).toString("hex")`）。提案里只保存 `sha256(token)`，不保存明文。
- `approve()` 必须同时满足：挑战未过期（默认 24h）、token 以 `timingSafeEqual` 匹配、`decidedBy` 为非空显式身份、存在**匹配提案 `baseCommit` 和 `baseVersion`** 的回滚点。成功后写 `Approval{decision:"approved", decidedBy, evaluationId, rollbackPointId, rollbackCommand}`，提案 `status="approved"`，并清除挑战（一次性）。
- `rejectProposal()` 记录 `decision:"rejected"`、`decidedBy`、`reason`，不需要回滚点；同样进入终态。
- `createRollbackPoint()` 只记录数据：`baseVersion`、`baseCommit`、可选 artifact 的 sha256、`rollbackCommand`（`git checkout <baseCommit>`）。skeleton **从不执行** git/回滚/发布/合并，也不改 `SKILL.md`、`package.json`、版本号（D-011）。
- 边界：模块无法在技术上证明调用者是“真人”；`decidedBy` 是可审计的声明，CLI/UI 接线必须保证只在人工动作后调用 `approve()`/`rejectProposal()`（§12）。
- `approved` 之后没有任何自动动作：发布、合并、改 Skill 版本都要人另做；本模块只保留证据和回滚点。

## 7. 调度与并发

- **只有调用才运行**：没有定时器、守护进程、队列、默认调度（§9）。`runOnce()` 每次只取最早 `proposed` 的提案，评估一个候选后结束；它可以到达 `awaiting_approval`，但永远不会批准。
- 单候选：`evaluation.lock`（PID 锁文件）。同一 project root 同时只有一个评估；活跃 pid 持锁时抛 `E_RSI_EVALUATION_LOCKED`。锁内容损坏或 pid 已死视为崩溃残留，删除后接管；`release()` 校验 owner，避免误删别人的锁。
- 失败/超时不自动重试；`attempts` 保持 1，等待人工处理。

## 8. 与 M2 控制面的差距（不发明接口）

M2 已实现 `openControl()` 的 tasks/runs/events/leases（见 `docs/m2-control.md`），但**没有**提案/评估/审批/回滚点实体，也没有候选级 lease。M2 文档明确把“提案/评估/RSI”标为 M3/M2b 未实现。因此本 slice：

- 以 `.sage-kit/rsi/` 文件 store 作为 M3 状态的**唯一权威写入源**，不打开、不写入 `control.db`，不做双写；
- 不向 M2 的 `ControlStore` 增加方法，也不在 M3 侧 mock/复制 M2 的 lease 语义；并发控制用本模块的短命评估锁。

若后续要把 M3 状态迁到控制面（M2b/M3b），需要的 M2 接口增量（当前**不存在**，故本 slice 不依赖）：

1. schema v2 迁移新增表：`rsi_proposals`、`rsi_evaluations`、`rsi_approvals`、`rsi_rollback_points`（JSON 字段可存 TEXT，id/status/created_at/updated_at 建索引）；
2. store 方法：对应 §4 的 create/get/list/save（至少 proposal 与 evaluation 的读写、approval 与 rollback point 的写入/读取）；
3. 候选级租约或明确的“单候选评估”互斥 API（当前 `leases` 只按 `task_id`，没有 proposal 维度）；
4. 迁移/导出路径与只读打开语义（文件模式 → 控制面模式不双写，D-005）；
5. CLI 接线（`src/cli.ts`，Lead 已完成）与 `npm test` 纳入 `tests/rsi.test.mjs`（已完成）。

在这些接口与迁移完成前，M3 状态保持文件模式，API 不承诺与控制面共享。

## 9. 错误码索引

| 领域 | 错误码 |
|---|---|
| store | `E_RSI_STORE_CORRUPT` `E_RSI_NOT_FOUND` `E_RSI_PROPOSAL_EXISTS` `E_RSI_BAD_ID` `E_RSI_BAD_INPUT` |
| 提案/候选 | `E_RSI_BAD_PROPOSAL` `E_RSI_BAD_CANDIDATE` `E_RSI_UNSAFE_PATH` `E_RSI_BAD_LIMIT` `E_RSI_BAD_COMMAND` |
| 评估 | `E_RSI_BAD_TRANSITION` `E_RSI_EVALUATION_NOT_FOUND` `E_RSI_WORKSPACE_FAILED` |
| 锁 | `E_RSI_EVALUATION_LOCKED` `E_RSI_LOCK_FAILED` `E_RSI_LOCK_OWNER_MISMATCH` |
| 审批/回滚点 | `E_RSI_BAD_APPROVAL` `E_RSI_NOT_AWAITING_APPROVAL` `E_RSI_APPROVAL_NOT_REQUESTED` `E_RSI_APPROVAL_EXPIRED` `E_RSI_APPROVAL_TOKEN_INVALID` `E_RSI_ALREADY_DECIDED` `E_RSI_ROLLBACK_ARTIFACT_NOT_FOUND` `E_RSI_ROLLBACK_POINT_NOT_FOUND` `E_RSI_ROLLBACK_POINT_MISMATCH` |

`reasonCode` 是评估记录里的失败分类（§5），与抛出的 `SageError.code` 分开：预检失败/测试失败属于“候选没通过”，是正常结果，不抛异常。

## 10. 设计决定

**A. 文件模式 store，而不是 SQLite。** M2 没有提案/评估实体（§8），强行扩展会发明未定契约并制造双写风险；文件模式与 P0 的状态目录一致，原子写 + 单写者，便于审计和测试。代价是迁移到控制面时要做一次导出/映射。

**B. 临时副本，而不是 `git worktree`。** skeleton 不依赖 git、不复制 `node_modules/.git`、可离线、清理确定；代价是不能评估需要真实分支/依赖安装/构建缓存的候选（M3b）。副本包含源工作区当前未提交内容，因此**评估的是调用时的现场**，不是某个提交。

**C. 固定命令属于 evaluator wiring。** 提案/候选只能提供文件内容，不能提供命令、阈值或测试路径；命令数组经校验后以 `shell: false` 直接 spawn，参数不经过 shell。评估器可在同一命令中串起 `p0`/`regression` 套件（§12）。

**D. 批准是显式动作。** 需要一次性挑战 token + 显式 `decidedBy` + 匹配基线的回滚点；三者缺一不可，“没有反对”不构成批准（D-011）。token 只存 hash，成功批准后清除挑战。

**E. 受保护资产双重检查。** 预检按路径拒绝候选对 `tests/` 等的修改；运行前后再对资产做 sha256 manifest 对比，防止测试套件在评估过程中改写测试/阈值/发布配置（D-012）。manifest 用相对路径，符号链接记录目标而不是内容。

**F. 日志脱敏与截断。** 命令输出在内存中最多保留尾部 200k 字符，落盘前按 `password|passwd|token|secret|authorization|api-key =/：` 与 `sk-*` 模式替换为 `[REDACTED]`，每个流最多 16 KiB（D-017）。这是**启发式**，不是完整的密钥识别（§11）。

**G. 剥离宿主测试运行器环境。** 测试里发现：当 evaluator 本身跑在 `node --test` 下时，继承的 `NODE_TEST_CONTEXT` 会让嵌套的 `node --test` 误判自己是 runner 子进程，直接退出 0 而不执行 fixture 套件，导致错误地“通过”。`fixedCommandEnvironment()` 因此剥离 `NODE_TEST_CONTEXT`/`NODE_TEST_REPORTER`/`NODE_V8_COVERAGE` 并设置 `GIT_TERMINAL_PROMPT=0`；固定命令在干净、离线友好的环境中运行。其他宿主环境变量的潜在影响未穷举（§11）。

**H. 失败不重试。** `runOnce` 不循环、不重跑；`attempts` 只递增一次。连续失败要人工处理（§9 预算）。

**I. 无网络、无模型。** 模块只 import Node 内置能力；静态测试禁止 `fetch(`、网络模块、`setInterval(` 和模型 SDK 名称。网络/模型如果出现在 evaluator 的固定命令里，那是调用方 wiring 的责任，不是本模块能力。

**J. Windows 信号边界。** 超时先 `SIGTERM`，2s 后 `SIGKILL`；Windows 上只杀直接子进程，不保证杀整棵进程树（§11）。

## 11. 已知限制与残余风险

- **进程树**：超时只保证终止直接子进程；Windows 上孙进程可能存活（无 job object/taskkill /T）。评估命令应尽量短、可用 `--test` 自带超时。
- **评估深度**：没有真实 `git worktree`、依赖安装、构建缓存、holdout 隐藏套件、基线对照、重复 3 次/固定随机种子；当前只有一条调用方固定命令。`p0`/`regression`/`security` 套件的组合与阈值校准仍是 wiring 责任。
- **候选大小**：`maxChangedLines`/`maxCandidateFiles` 限制 diff，但 `candidate.files[].content` 的字节大小没有上限；超大候选会在评估前占用内存/临时磁盘。需要在 Builder/CLI 侧限制（M3b）。
- **批准真人性**：`decidedBy` 只是审计字符串，模块无法验证“真人”；必须由 CLI/UI 保证只在人工动作后调用。
- **锁**：PID 可能被系统复用（极端情况下误判存活）；仅覆盖同机同 project root，跨机器/多进程并发不在范围。
- **日志脱敏**：正则启发式，裸 base64 密钥、非键值形式的凭据可能漏脱敏；日志只应视为“尽力而为”，不要把密钥写进命令输出。
- **评估现场**：评估的是源工作区的当前副本（含未提交改动），不是某个干净提交；结果需结合 `baseCommit` 与 diff 一起审阅。
- **与 M2 脱节**：不共享控制面的任务/run/event 记录；同一 repo 同时跑 M2 worker 与 RSI 评估时，两套状态互不感知（§8）。
- **多候选**：单候选锁是进程级文件锁；`runOnce` 串行，不提供队列、优先级、取消。

## 12. 集成注意（给 Lead，不在本 slice 内）

- `src/cli.ts` 未改动。建议接线（命令名由 Lead 定）：`sage-kit rsi propose --file <proposal.json>`、`rsi evaluate --proposal <id> --suite <fixed-command>`、`rsi approve --proposal <id> --token <一次性 token> --by <name> --rollback-point <id>`、`rsi rollback-point --commit <sha> --version <v>`、`rsi reject ...`。所有命令都应 lazy import `dist/rsi/index.js`，不拖慢默认 CLI 启动。
- `package.json` 未改动；`npm test` 需要加入 `tests/rsi.test.mjs`（Lead 负责）。本 slice 验证命令见文首。
- 文档：`docs/architecture.md`/roadmap 的状态更新由文档所有者完成；不要把本 skeleton 写成“自动改进循环”或“已实现发布”。合并后建议在 `docs/feedback-and-rsi.md` §12 标注 M3 现状。
- 不要为 RSI 启用控制面模式或双写；文件模式 store 与 `.sage-kit/state/` 的既有边界一致。
- 发布前展示证据：提案、evaluation JSON（含 command/log/diff）、approval 记录、rollback point；`approved` 不触发任何自动动作。

## 13. 文件清单（本 slice）

```text
src/rsi/index.ts      # 公共导出
src/rsi/types.ts      # 类型、默认限额、受保护路径、状态枚举
src/rsi/paths.ts      # .sage-kit/rsi/ 布局、id 生成
src/rsi/validate.ts   # 提案/候选/命令/limits/protectedPaths 校验
src/rsi/candidate.ts  # diff 统计、受保护 manifest、候选应用
src/rsi/store.ts      # 文件模式 store（原子写、损坏检测）
src/rsi/lock.ts       # 单候选评估锁（PID stale 接管）
src/rsi/workspace.ts  # 隔离临时副本（复制/清理）
src/rsi/process.ts    # 固定命令执行（超时、日志捕获、环境剥离）
src/rsi/evaluate.ts   # Evaluator 主流程 + 失败分类
src/rsi/run.ts        # 手动 runOnce（一次一个候选）
src/rsi/approve.ts    # 一次性人工批准、拒绝、回滚点
tests/rsi.test.mjs    # 12 个测试（store/评估/审批/预算/锁/隔离/静态边界）
docs/m3-rsi.md        # 本文
```

本模块没有新增错误类型文件；错误与全仓一致使用 `src/core/errors.ts` 的 `SageError`（`code` + `exitCode`）。`package.json`、`src/cli.ts`、`src/control/**`、其他文档均未由本 slice 修改。
