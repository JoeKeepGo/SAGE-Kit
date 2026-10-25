# M3 RSI（提案 / 真实 git worktree 评估 / 基线对照 / 人工批准 / 回滚点）

**状态：M3 评估闭环已实现并验证（`IMPLEMENTED` / `VERIFIED`）：真实 git worktree、基线对比、有界重复、导出、可选控制面记录与 CLI 接线；自主循环、定时调度、自动批准/合并/发布按 D-011 不实现。**

本文只描述 `src/rsi/**` 这一个可选层。它不改变 P0 文件模式，不写 `.sage-kit/state/` 以外的业务状态，不新增依赖、不联网、不调用模型、不 fetch。设计基线：`docs/feedback-and-rsi.md` §5–§9/§12、`docs/decisions.md` D-011（RSI 最高 L2、人工批准）、D-012（Builder/Evaluator 分离、评估资产受保护）、D-017（日志/状态脱敏）、D-018（不得把设计写成已实现）、D-005（单一权威写入源）。

历史模块验证环境为 2026-10-24 Windows Node v24.22.0；本次修复全量结果来自 2026-10-26 同 Node 版本的工作树；下列计数分别注明历史模块与本次全量范围。

```text
# 类型检查
npm run build                     # tsc -p tsconfig.json，通过

# 本模块测试（27 项，含真实 git 仓库 E2E）
node --test tests/rsi.test.mjs
# tests 27, suites 5, pass 27, fail 0, cancelled 0, skipped 0
# duration_ms ≈ 31s（每个评估用例创建/清理真实 git worktree 并 spawn node --test）

# 本次修复全仓测试（含 N02/S16/R08/R10–R14）
npm test
# 2026-10-26 Windows Node 24.22.0, working tree
# tests 206, suites 25, pass 205, fail 0, cancelled 0, skipped 1
```

测试覆盖：提案存储/重载/损坏检测；非 git 仓库与未知 `baseCommit` 不消耗尝试次数；失败候选被阻断且不自动重试；通过候选有基线证据、仍必须显式人工批准（token、`decidedBy`、回滚点、一次性）；未提交改动不被评估、主工作树不被触碰；`repeats=3` 逐次记录；超界 repeats、受保护测试、diff 预算超限在跑测试前失败；超时被杀并清理 worktree；`runOnce` 一次一个候选；拒绝不写代码；证据 JSON 导出；可选控制面记录幂等（task/run/event）；静态检查无网络/模型 SDK/默认定时器。

## 1. 范围与实现状态

| 能力 | 状态 | 说明 |
|---|---|---|
| 提案类型、校验、文件模式 store（`.sage-kit/rsi/`） | `IMPLEMENTED` | schema v2；原子写、损坏记录报错、不返回半条数据 |
| 真实 `git worktree` 隔离评估 | `IMPLEMENTED` | 从提案 `baseCommit` 建 detached worktree；不动主工作树/索引；每个 run 独立 worktree；finally 清理 |
| 固定评估命令 + 超时 + 日志摘要 | `IMPLEMENTED` | 命令由 evaluator wiring 提供，spawn 无 shell；SIGTERM→2s→SIGKILL；日志脱敏 + 每流 16 KiB 截断 |
| 基线对照（base commit 跑同一命令） | `IMPLEMENTED` | 默认各 1 次；候选不得弱于基线（通过 run 数比较） |
| 有界重复评估 `repeats` | `IMPLEMENTED` | 默认 1，上限 `limits.maxRepeats`（默认 5）；逐 run 落盘；失败不自动重试 |
| 受保护评估资产双重检查 | `IMPLEMENTED` | 评估前按路径拒绝；运行前后 sha256 manifest 对比 |
| diff 预算（默认 500 行 / 20 文件，可配置） | `IMPLEMENTED` | 超预算在跑测试前失败并记录 |
| 一次性人工 approval token | `IMPLEMENTED` | 32 hex，仅存 sha256，`timingSafeEqual`，默认 24h TTL |
| 显式人工决定（`decidedBy`）与拒绝记录 | `IMPLEMENTED` | 匿名批准被拒绝；拒绝同样落 `approvals/` |
| 回滚点记录 | `IMPLEMENTED` | 记录 `git checkout <baseCommit>` 指引；**不执行**回滚 |
| 手动 `runOnce`，一次一个候选 | `IMPLEMENTED` | 无默认定时器；可到 `awaiting_approval`，不会自动批准 |
| 单候选评估锁（PID stale 接管） | `IMPLEMENTED` | 同机同 project root；`evaluation.lock` 的 PID 锁由 `.mutex` 串行化接管；`.mutex` 自身不自动回收，死 PID/无 owner 时 fail closed（`E_RSI_LOCK_STALE`），需人工确认无评估进程后删除 |
| 证据 JSON 导出 | `IMPLEMENTED` | `.sage-kit/rsi/exports/<evaluation-id>.json`；也可指定项目内路径 |
| 可选控制面记录（task/run/event） | `IMPLEMENTED`（显式调用） | `recordEvaluationInControl()`；不自动、不双写；见 §10 |
| CLI 接线（List/Create/Run-once/Approval/Reject/Export/Record-control） | `IMPLEMENTED`（Lead） | `run-once` 支持 `--repeats`、`--export [--out]`；独立 `rsi export` 与 `rsi record-control` |
| 定时同步/定时评估、自动批准、自动合并/发布、重写 `SKILL.md` | `NOT_IMPLEMENTED`（按 D-011 不实现） | 最高 L2；人工批准后由人执行发布 |
| Builder 生成候选、反馈同步/分类、M1 反馈源接入 | `NOT_IMPLEMENTED`（M3b 及 M1 接线） | 本 slice 接收已给好的 `CandidateFile[]` |
| 依赖安装、holdout/隐藏套件、多套件编排、控制面迁移 | 设计范围外（不阻塞 M3 闭环） | 固定命令可由 wiring 自行组合；见 §12 |
| 网络请求 / 模型调用 / git fetch | **不实现**（设计禁止） | 仅 Node 内置能力；静态测试断言无 `fetch`/网络模块/模型 SDK |

## 2. 文件布局与写入边界

```text
<project-root>/.sage-kit/rsi/
  proposals/<id>.json          # 提案 + 状态机字段
  evaluations/<id>.json        # 一次评估的完整证据（含 baseline/runs/comparison）
  approvals/<id>.json          # approved/rejected 记录
  rollback-points/<id>.json    # 回滚点
  exports/<evaluation-id>.json # 导出的证据摘要（显式导出时）
  evaluation.lock              # 单候选评估锁；JSON {pid, owner, startedAt}
```

- 路径由 `rsiPaths(projectRoot)` 给出；`openRsi()` 只计算路径，写方法按需创建目录（0700）。本 repo 的 `.gitignore` 忽略 `.sage-kit/`，所以状态不会进提交。
- 本模块**只**写 `.sage-kit/rsi/`；评估用的 worktree 建在 `os.tmpdir()/sage-kit-rsi-wt-*` 并清理。不写 `.sage-kit/state/**`、`.sage-kit/control/**`（除非显式调用 `recordEvaluationInControl()`，且只经 M2 公开 API）、`SKILL.md`、`package.json`、git 历史。候选文件**只**写入临时 worktree，绝不写源工作区。
- worktree：`createEvaluationWorktree()` 用 `git worktree add --detach <tmp>/worktree <baseCommit>` 创建；每个 baseline/candidate run 一个新 worktree，`cleanup()` 执行 `git worktree remove --force` + `git worktree prune`，失败则删除目录后 prune。主工作树的未提交改动**不进入**评估。
- 单写者：文件模式仍是 M3 状态的唯一权威写入源（D-005）；本模块默认不打开控制面 SQLite。控制面记录是显式、可选的适配器（§10），不是双写。

## 3. 提案与状态机

提案记录（`Proposal`，`schemaVersion: 2`）主要字段：

```json
{
  "schemaVersion": 2,
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
- `baseCommit` 为 7–64 位小写十六进制，且必须在本地 git 仓库中可解析（不 fetch、不凭空创建）；`baseVersion` 为 semver 风格标识；`candidate.files` 为非空数组，路径必须是项目相对 POSIX 路径，拒绝绝对路径、`..`、`.git/`、`.sage-kit/` 和重复路径。
- `content: null` 表示删除文件；候选不会携带可执行命令。
- schema 从 1 升到 2（新增 `runs/baseline/comparison/repeats/baseCommit` 等证据字段）。**没有迁移**：skeleton 时期写下的 v1 记录在读取时按 `E_RSI_STORE_CORRUPT` 处理；由于 `.sage-kit/` 不入库，只有本地残留需要手动删除 `.sage-kit/rsi/`。

状态机（本 skeleton 只走这些边）：

```text
proposed        → evaluating → failed | awaiting_approval
proposed        → rejected（人工直接拒绝，无需先评估）
awaiting_approval → approved（approve）| rejected（rejectProposal）
failed / approved / rejected → 终态（不自动重试、不自动迁移）
```

- `attempts` 只在通过输入校验、git 前置检查与候选预检、真正进入评估时 +1；非 git 仓库、未知 commit 等基础设施错误在 `proposed` 状态直接抛出，不消耗尝试次数，可修复后重试。
- 每个提案最多评估一次；失败后保持 `failed`，再次 `runOnce` 不会重试（§9 预算：失败不自动无限重试，等待人工）。
- 只有 `proposed` 能进入评估；非 `proposed` 调 `evaluateCandidate()` 抛 `E_RSI_BAD_TRANSITION`。
- 只有 `awaiting_approval` 且评估 `passed` 能请求/执行批准；批准成功后才写 `approved`。

## 4. 公共 API（`src/rsi/index.ts`）

```ts
import {
  openRsi, rsiPaths, ensureRsiPaths,
  evaluateCandidate, runOnce, acquireEvaluationLock,
  requestApproval, approve, rejectProposal, createRollbackPoint,
  runFixedCommand,
  createEvaluationWorktree, resolveGitRepository, resolveBaseCommit, runGitCommand,
  exportEvaluationSummary, recordEvaluationInControl,
  DEFAULT_RSI_LIMITS, DEFAULT_PROTECTED_PATHS, DEFAULT_APPROVAL_TTL_MS,
  DEFAULT_REPEATS, RSI_SCHEMA_VERSION, RSI_PROPOSAL_STATUSES,
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
  projectRoot,                 // 或传 store；必须是 git 仓库根
  testCommand: ["node", "--test", "tests/check.test.mjs"], // evaluator 固定套件
  repeats?: 1,                 // 默认 1；上限 limits.maxRepeats（默认 5）
  limits?: { maxCandidateFiles, maxChangedLines, maxLogBytes, evaluationTimeoutMs, maxRepeats },
  protectedPaths?: string[],   // 默认 DEFAULT_PROTECTED_PATHS
});
// → { outcome: "idle"|"passed"|"failed", evaluated: 0|1,
//     proposalId?, evaluationId?, status?, reasonCode? }

// 单候选评估（runOnce 内部也用它；直接调用时需自己保证人工触发）
await evaluateCandidate({ projectRoot, proposalId, testCommand, repeats?, limits?, protectedPaths? });

// 人工审批闸门
const challenge = await requestApproval({ projectRoot, proposalId, approvalTtlMs? });
// challenge = { proposalId, approvalToken: "<32 hex, 只出现一次>", expiresAt }
const point = await createRollbackPoint({ projectRoot, baseCommit, baseVersion, artifactPath?, note? });
// point.rollbackCommand === `git checkout ${baseCommit}`（仅指引，不执行）
await approve({ projectRoot, proposalId, approvalToken: challenge.approvalToken,
                decidedBy: "human-name", rollbackPointId: point.id, note? });
await rejectProposal({ projectRoot, proposalId, decidedBy: "human-name", reason: "..." });

// 证据导出（显式；默认写 .sage-kit/rsi/exports/<evaluation-id>.json）
const exported = await exportEvaluationSummary({ projectRoot, evaluationId, outFile?, write? });
// exported = { summary: { proposal, evaluation, approvals, rollbackPoint? }, filePath? }

// 可选控制面记录（显式；不自动调用，见 §10）
const control = openControl(projectRoot);   // M2 API，由调用方持有/关闭
recordEvaluationInControl({ store: control, proposal, evaluation });

// 手动评估锁（测试/高级用；runOnce 自动 acquire/release）
const lock = await acquireEvaluationLock(store);
await lock.release();

// 固定命令执行器（可脱离 RSI 复用；有界进程树终止，见 §11 L）
await runFixedCommand(["node", "--version"], cwd, { timeoutMs: 10_000 });
```

如果 acquire 已创建 `evaluation.lock` 而随后 acquisition mutex 清理失败，会先释放刚获得的锁再抛错；回滚也失败时以 `AggregateError` 保留两个错误，不丢弃仍需人工处理的锁错误。

默认值：`DEFAULT_RSI_LIMITS = { maxCandidateFiles: 20, maxChangedLines: 500, maxLogBytes: 16_384, evaluationTimeoutMs: 120_000, maxRepeats: 5 }`；`DEFAULT_REPEATS = 1`；`DEFAULT_PROTECTED_PATHS = ["tests","test","eval","holdout",".github","package.json","package-lock.json"]`；`DEFAULT_APPROVAL_TTL_MS = 24h`；git plumbing 单命令预算 `DEFAULT_GIT_TIMEOUT_MS = 60s`。

## 5. 评估流程（Builder / Evaluator 分离，真实 git worktree）

`evaluateCandidate()` 的顺序：

1. 校验输入（proposal id、固定命令、limits、protectedPaths、repeats 上界）并获取全局评估锁；提案必须仍是 `proposed`。
2. **git 前置检查**：`git rev-parse --show-toplevel` 必须是 `projectRoot` 本身（`E_RSI_NOT_GIT_REPO` / `E_RSI_GIT_ROOT_MISMATCH` / `E_RSI_GIT_UNAVAILABLE`）；`baseCommit` 必须能解析为本地 commit（`E_RSI_BAD_BASE_COMMIT`）。不做 fetch/pull。
3. **预检**：在 base commit 的全新 worktree 上调用 `assessCandidate()`，计算候选文件数/变更行数、受保护路径命中，并生成受保护资产基线 manifest。预检 worktree 用完即删。命中受保护资产或超预算时，**不跑基线、不跑测试**：写 `ranTests: false` 的失败评估，提案置 `failed`。
4. 标记 `evaluating`（`attempts += 1`）。
5. **基线**：对 base commit 跑 `repeats` 次固定命令；每次一个全新 worktree（不应用候选）。
6. **候选**：跑 `repeats` 次固定命令；每次一个全新 worktree，应用候选文件，跑同一命令，运行后重新计算受保护 manifest 与基线对比。
7. 汇总 run 结果，计算 `comparison`，持久化 `Evaluation`，清理所有 worktree，移动提案状态：`passed → awaiting_approval`，否则 `failed`。

评估记录（`Evaluation`）关键字段：

```text
schemaVersion, id, proposalId, attempt, startedAt, finishedAt,
baseCommit, repeats, command,
outcome, reasonCode?, reasonMessage?,
ranTests, exitCode, signal, timedOut, durationMs,
diff: { files, changedLines, limits: { maxFiles, maxChangedLines } },
protectedAssets: { paths, ok, changed },
log: { stdout, stderr, truncated },            # 候选首个 run；已脱敏/截断
runs: [EvaluationRun],                          # 候选 runs（kind: "candidate"）
baseline: { runs, passedRuns, failedRuns, outcome: "passed"|"failed"|"not_run" },
comparison: { candidateRuns, baselineRuns, candidatePassedRuns,
              baselinePassedRuns, noWeakerThanBaseline }
```

`EvaluationRun` 含 `index/kind/applied/ranTests/outcome/exitCode/signal/timedOut/durationMs/protectedAssets/log/worktree`；`worktree = { kind: "git-worktree", path, removed }`，`removed` 是清理结果，测试同时断言目录已不存在。`command` 是实际执行的固定命令（审计用），`ranTests` 在预检失败时为 `false`。

## 6. 判定规则与失败原因码

通过（`outcome: "passed"`）必须同时满足：

1. 候选预检通过（无受保护路径命中、在 diff/文件数预算内）；
2. 每个候选 run 都 `passed`（命令实际运行、退出码 0、未超时、运行后受保护资产未变）；
3. `candidatePassedRuns >= baselinePassedRuns`（**不弱于基线**）；
4. 所有 run 的受保护资产检查都没有 `ok: false`。

说明：

- 基线可以失败。若基线上固定套件本来就失败、候选把它修到通过，则 `baselinePassedRuns=0`、`candidatePassedRuns=N`，候选通过——这是“不比基线弱”的语义，不是“绝对质量提升”的证明；人类仍需审阅 diff 与证据。
- 基线与候选使用**同一条固定命令、同一个 base commit**；候选若让套件通过数少于基线，说明它更弱，判 `failed`。
- 每个 run 都是独立 worktree，重复次数用于暴露 flaky 行为；重复只增加证据，**不自动重试**：失败候选仍只记录一次评估、`attempts` 只 +1。
- 判定不抛异常：预检失败/测试失败是“候选没通过”，写入 `Evaluation` 后返回；只有输入/环境/锁等基础设施错误才抛 `SageError`。

失败原因码：

| reasonCode | 含义 |
|---|---|
| `E_RSI_PROTECTED_ASSET` | 候选路径命中受保护资产（预检，未运行） |
| `E_RSI_DIFF_TOO_LARGE` | 文件数或变更行数超预算（预检，未运行） |
| `E_RSI_WORKTREE_FAILED` | `git worktree add/remove` 失败 |
| `E_RSI_CANDIDATE_APPLY_FAILED` | 候选写入 worktree 失败 |
| `E_RSI_EVALUATION_FAILED` | 兜底：固定命令未能启动/内部意外 |
| `E_RSI_EVAL_SPAWN_FAILED` | spawn 失败（如命令不存在） |
| `E_RSI_EVAL_TIMEOUT` | 固定命令超时被杀 |
| `E_RSI_TESTS_FAILED` | 命令退出码非 0 |
| `E_RSI_PROTECTED_ASSET_CHANGED` | 运行后受保护资产 manifest 变化 |
| `E_RSI_PROTECTED_ASSET_UNVERIFIED` | 运行后 manifest 计算失败 |
| `E_RSI_WEAKER_THAN_BASELINE` | 兜底保留；当前判定先取首个失败 run 的 reasonCode，正常路径不会出现 |

## 7. 人工批准与回滚点

- `requestApproval()` 只为 `awaiting_approval`（评估 `passed`）的提案创建挑战；返回唯一一次明文 token（`randomBytes(16).toString("hex")`）。提案里只保存 `sha256(token)`，不保存明文。
- `approve()` 必须同时满足：挑战未过期（默认 24h）、token 以 `timingSafeEqual` 匹配、`decidedBy` 为非空显式身份、存在**匹配提案 `baseCommit` 和 `baseVersion`** 的回滚点。成功后写 `Approval{decision:"approved", decidedBy, evaluationId, rollbackPointId, rollbackCommand}`，提案 `status="approved"`，并清除挑战（一次性）。
- `rejectProposal()` 记录 `decision:"rejected"`、`decidedBy`、`reason`，不需要回滚点；同样进入终态。
- `createRollbackPoint()` 只记录数据：`baseVersion`、`baseCommit`、可选 artifact 的 sha256、`rollbackCommand`（`git checkout <baseCommit>`）。本模块**从不执行** git/回滚/发布/合并，也不改 `SKILL.md`、`package.json`、版本号（D-011）。
- 边界：模块无法在技术上证明调用者是“真人”；`decidedBy` 是可审计的声明，CLI/UI 接线必须保证只在人工动作后调用 `approve()`/`rejectProposal()`（§13）。
- `approved` 之后没有任何自动动作：发布、合并、改 Skill 版本都要人另做；本模块只保留证据和回滚点。

## 8. 调度与并发

- **只有调用才运行**：没有定时器、守护进程、队列、默认调度（§9）。`runOnce()` 每次只取最早 `proposed` 的提案，评估一个候选后结束；它可以到达 `awaiting_approval`，但永远不会批准。
- 单候选：`evaluation.lock`（PID 锁文件）。同一 project root 同时只有一个评估；活跃 pid 持锁时抛 `E_RSI_EVALUATION_LOCKED`。锁内容损坏或 pid 已死视为崩溃残留；`evaluation.lock` 的接管用原子 `rename`，若移动到的锁已被新 owner 替换则放回并失败，避免两个进程同时认为拿到锁。**读取锁文件失败（EPERM/EBUSY/EACCES 有界重试后仍失败）不能当作“损坏/空闲”而执行接管**：必须明确报 `E_RSI_LOCK_FAILED`，否则会抢走活 owner 的锁。`release()` 校验 owner 后直接 `unlink`，**不经过 `.mutex`**：它已经拥有该锁文件，只需删除；若让 release 与持续到来的 acquire 争同一把 mutex，正常同进程并发会出现 release 饥饿（5s 超时并留下 evaluation.lock）。同一 handle 的并发/重复 `release()` 共享同一次释放操作（不是各自独立 unlink），避免两个迟到的 unlink 误删后继 owner；完成后幂等。并发 acquire 看到活锁会拒绝，看到路径已删则可创建新锁，两者都安全。`.mutex` 只负责把 acquire 的“检查和发布”串行化；它**不会**自动移动或回收，因为移走公共路径会产生第三方进入的窗口。死 PID 或无 owner 的 `.mutex` 以 `E_RSI_LOCK_STALE` 失败，需确认没有评估进程运行后手工删除该目录；这牺牲自动崩溃恢复，换取跨进程互斥不被破坏。acquire 释放自己的 `.mutex` 时先删除 `owner` 再 `rmdir`，不 rename 公共路径；Windows 上 `EPERM/EBUSY` 会短重试，仍失败则抛 `E_RSI_LOCK_FAILED`，不再静默吞掉清理失败；owner JSON schema 损坏（空 owner/类型错误/数组）也明确报错，不与“另一个有效 owner”混淆。
- 恢复同一互斥：`recoverInterruptedEvaluations()` 也获取同一把锁，在锁内重新读取 proposal/evaluation 再写入；不能在“检查锁空闲”之后无锁写回，否则会覆盖另一个评估刚完成的成功证据。读取 evaluation 时只有 `E_RSI_NOT_FOUND` 才合成中断证据；权限/I/O/JSON 损坏错误直接向上抛出，绝不把已成功的证据改写成 failed。
- 有界重复：一次调用最多 `limits.maxRepeats`（默认 5）轮基线 + 同轮候选；没有“再跑一次直到通过”的逻辑。
- 失败/超时不自动重试；`attempts` 保持 1，等待人工处理。

## 9. 与 M2 控制面的关系（可选记录，不双写）

M2 已实现 `openControl()` 的 tasks/runs/events/leases（见 `docs/m2-control.md`），但**不复制**提案/评估/审批/回滚点实体，也没有候选级 lease；这些实体由 M3 文件 Store 实现。因此：

- `.sage-kit/rsi/` 文件 store 仍是 M3 状态的**唯一权威写入源**（D-005）；`evaluateCandidate()`/`runOnce()` 不会打开 `control.db`。
- 需要把证据登记到控制面时，调用方显式执行：

```ts
const control = openControl(projectRoot);
const record = recordEvaluationInControl({ store: control, proposal, evaluation });
// record = { taskId, runId, taskCreated, runCreated, eventId? }
control.close();
```

  适配器只通过 M2 公开 API 写：`review` 任务（`source: "rsi"`）、`rsi-evaluator` run（固定命令/退出码/失败码）、`rsi.evaluation` 事件（含 repeats/baseline/comparison 摘要）。id 由 `sha256(proposalId|evaluationId)` 前 16 位确定性生成，重复调用同一 evaluation 会复用 task/run/event，不重复写。
- 它**不是**迁移：M2 中不会出现完整的 `Proposal`/`Evaluation` 实体，也没有在控制面里做批准；批准仍是 §7 的文件模式 + 人工动作。文件模式已完成 M3 评估闭环，控制面只做可选证据记录，不需要迁移表或双写。
- 并发：同一 repo 同时跑 M2 worker 与 RSI 评估时，两套状态默认互不感知；只有显式记录后才在控制面留下 task/run/event。评估互斥靠 §8 的文件锁。

## 10. 证据导出

`exportEvaluationSummary()` 生成自包含 JSON：`{ schemaVersion, exportedAt, projectRoot, proposal, evaluation, approvals, rollbackPoint? }`。

- 默认写入 `.sage-kit/rsi/exports/<evaluation-id>.json`；`outFile` 可指定项目内相对/绝对路径。
- 路径必须在 `projectRoot` 内，否则 `E_RSI_UNSAFE_PATH`；`write: false` 只返回对象不落盘。
- 导出是只读视图，不改变状态，不触发合并/发布。

## 11. 设计决定

**A. 文件模式 store，而不是 SQLite。** M2 没有提案/评估实体（§9），强行扩展会发明未定契约并制造双写风险；文件模式与 P0 的状态目录一致，原子写 + 单写者，便于审计和测试。代价是迁移到控制面时要做一次导出/映射。

**B. 真实 `git worktree`，而不是临时副本。** 候选必须在干净、可复现的提交上评估：worktree 从提案 `baseCommit` 检出，主工作树的未提交改动、索引和未跟踪文件都不参与；结果为“该提交 + 候选”的确定证据。代价是评估需要本地 git 且 `baseCommit` 必须已在本地（不 fetch），因此 Fixed 命令/依赖安装等仍受仓库现状限制。

**C. 固定命令属于 evaluator wiring。** 提案/候选只能提供文件内容，不能提供命令、阈值或测试路径；命令数组经校验后以 `shell: false` 直接 spawn，参数不经过 shell。评估器可在同一命令中串起 `p0`/`regression` 套件。

**D. 批准是显式动作。** 需要一次性挑战 token + 显式 `decidedBy` + 匹配基线的回滚点；三者缺一不可，“没有反对”不构成批准（D-011）。token 只存 hash，成功批准后清除挑战。

**E. 受保护资产双重检查。** 预检按路径拒绝候选对 `tests/` 等的修改；运行前后再对资产做 sha256 manifest 对比，防止测试套件在评估过程中改写测试/阈值/发布配置（D-012）。manifest 用相对路径，符号链接记录目标而不是内容。

**F. 日志脱敏与截断。** 命令输出落盘前按 `password|passwd|token|secret|authorization|api-key =/：` 与 `sk-*` 模式替换为 `[REDACTED]`，每个流最多 16 KiB（D-017）。这是**启发式**，不是完整的密钥识别（§12）。

**G. 基线对照。** 只跑一次候选无法区分“命令本来就失败”和“候选把它弄失败”。因此基准也在 base commit 上跑同一命令 `repeats` 次，只有 `candidatePassedRuns >= baselinePassedRuns` 才通过；代价是一次评估最多 `2 × repeats` 个 worktree/命令。

**H. 有界重复。** 默认 1 次、上限 5 次；重复用于暴露 flaky 测试而不是自动重试。失败候选不会因重复而被“碰运气”通过（必须每个候选 run 都过）。

**I. 控制面记录是显式适配器。** 自动写 `control.db` 会形成双写（违反 D-005）并让 M3 依赖可选层；改为调用方显式 `recordEvaluationInControl()`，只写 task/run/event 摘要，确定性 id 保证幂等。

**J. 无网络、无模型、不 fetch。** 模块只 import Node 内置能力；静态测试禁止 `fetch(`、网络模块、`setInterval(` 和模型 SDK 名称。git 只做本地 `rev-parse`/`worktree add`/`remove`/`prune`，`GIT_TERMINAL_PROMPT=0`，不 fetch/pull。

**K. 剥离宿主测试运行器环境。** 当 evaluator 本身跑在 `node --test` 下时，继承的 `NODE_TEST_CONTEXT` 会让嵌套的 `node --test` 误判自己是 runner 子进程而直接退出 0。`fixedCommandEnvironment()` 因此剥离 `NODE_TEST_CONTEXT`/`NODE_TEST_REPORTER`/`NODE_V8_COVERAGE` 并设置 `GIT_TERMINAL_PROMPT=0`；其他宿主环境变量的潜在影响未穷举（§12）。

**L. 进程超时收尾。** POSIX 命令以独立进程组启动，超时向组发送 `SIGTERM`，2s 后发送 `SIGKILL`；Windows 仍只向直接子进程发送这两个信号。再等至多 2s 仍未收到 `close` 时关闭本地输出管道并返回超时失败，stderr 明确记录可能仍存活的后代，评估和锁释放不再无限等待（§12）。

## 12. 已知限制与残余风险

- **git 依赖**：评估要求 `projectRoot` 是 git 仓库根、`baseCommit` 已在本地；不 fetch，所以新提交需由用户先同步。浅克隆中缺失的 commit 会 `E_RSI_BAD_BASE_COMMIT`。
- **评估现场变化**：只评估 base commit + 候选；主工作树的未提交改动**不会**被评估（与 skeleton 的“临时副本”行为相反）。这是有意变化，需要用户先把改动提交或用候选表达。
- **worktree 清理**：正常/失败/超时路径都会清理；若进程被硬杀（SIGKILL/断电），OS 临时目录与 `.git/worktrees` 管理项可能残留，需要手动 `git worktree prune` 并删除 `sage-kit-rsi-wt-*`。清理失败只记录 `removed: false`，不抛异常（避免掩盖评估结果）。
- **进程树**：POSIX 另建会话/进程组的后代不在原进程组中；Windows 只终止直接子进程，完整进程树终止仍未实现。管道未关闭时会有界失败并报告未确认退出的后代，不能声称它们已被终止；没有持久化进程树身份或 Windows Job Object。真实 Windows 沙箱中的 `taskkill /T /F` 返回拒绝访问，不能据此声称支持进程树清理。
- **评估深度**：只有一条固定命令；没有 holdout/隐藏套件、依赖安装、构建缓存；基线对照与重复只能减少误判，不能证明正确性。`p0`/`regression`/`security` 的组合与阈值校准仍是 wiring 责任。
- **候选大小**：`maxChangedLines`/`maxCandidateFiles` 限制 diff，但 `candidate.files[].content` 的字节大小没有上限；超大候选会在写 worktree 时占用磁盘/内存，需在 Builder/CLI 侧限制。
- **批准真人性**：`decidedBy` 只是审计字符串，模块无法验证“真人”；必须由 CLI/UI 保证只在人工动作后调用。
- **锁**：PID 可能被系统复用（极端情况下误判存活）；同机同 project root 的跨进程 acquire/takeover 由 `.mutex` 目录串行化，但仅覆盖本机文件系统；跨机器/网络文件系统不在范围。
- **日志脱敏**：正则启发式，裸 base64 密钥、非键值形式的凭据可能漏脱敏；日志只应视为“尽力而为”。
- **基线语义**：`candidatePassedRuns >= baselinePassedRuns` 是“不更弱”，不是“更好”；基线与候选都失败时同样判失败，人类需看证据与 diff。
- **schema v2 无迁移**：skeleton 的 v1 记录会被当作损坏记录（`E_RSI_STORE_CORRUPT`）；`.sage-kit/` 被 gitignore，只有本地残留需要清理。
- **CLI 已补齐**：`rsi run-once --repeats <n> --export [--out <path>]`、`rsi export <evaluation-id>`、`rsi record-control <evaluation-id>`；默认仍 `repeats=1`，不改变既有行为。
- **控制面默认脱节（显式记录可桥接）**：不显式记录时 M2 看不到 RSI 评估；需要时用 `rsi record-control <evaluation-id>` 写一条控制面事件引用了文件评估，但评估实体仍在文件层，不做双写（§9）。

## 13. 集成状态与注意

- `src/cli.ts` 已接线：`rsi create/list/run-once/request-approval/rollback-point/approve/reject/export/record-control`，lazy import `dist/rsi/index.js`，`run-once --test-command <json-array>` 失败返回退出码 1。
- CLI 支持 `--repeats <n>`（库校验上界）、`--export [--out <path>]`、`rsi export` 与 `rsi record-control`；不要加“自动反复评估直到通过”的循环。
- `package.json` 的 `npm test` 已包含 `tests/rsi.test.mjs`（Lead 接线）；本 slice 验证命令见文首。
- 文档：`docs/architecture.md`、README 与里程碑报告已标注 M3 现状；不要把本模块写成“自动改进循环”或“已实现发布”。
- 不要为 RSI 启用控制面双写；文件模式 store 与 `.sage-kit/state/` 的既有边界一致。
- 发布前展示证据：提案、evaluation JSON（含 command/baseline/runs/comparison/diff/log）、approval 记录、rollback point；`approved` 不触发任何自动动作。

## 14. 文件清单（本 slice）

```text
src/rsi/index.ts         # 公共导出
src/rsi/types.ts         # 类型、默认限额、受保护路径、schema v2、状态枚举
src/rsi/paths.ts         # .sage-kit/rsi/ 布局（含 exports/）、id 生成
src/rsi/validate.ts      # 提案/候选/命令/limits/protectedPaths/repeats 校验
src/rsi/candidate.ts     # diff 统计、受保护 manifest、候选应用
src/rsi/store.ts         # 文件模式 store（原子写、损坏检测）
src/rsi/lock.ts          # 单候选评估锁（evaluation.lock 接管；.mutex stale 时 fail closed）
src/rsi/worktree.ts      # 真实 git worktree 创建/解析/清理（替代旧 workspace.ts）
src/rsi/process.ts       # 固定命令执行（超时、日志捕获、环境剥离）
src/rsi/evaluate.ts      # Evaluator 主流程：基线 + 候选 + 对照 + 失败分类
src/rsi/run.ts           # 手动 runOnce（一次一个候选）
src/rsi/approve.ts       # 一次性人工批准、拒绝、回滚点
src/rsi/export.ts        # 评估证据 JSON 导出
src/rsi/control-record.ts# 可选 M2 控制面记录适配器
tests/rsi.test.mjs       # 27 个测试（store/git worktree E2E/基线/重复/审批/预算/隔离/导出/控制面/恢复锁/释放公平性/静态边界）
docs/m3-rsi.md           # 本文
```

旧 `src/rsi/workspace.ts`（`fs.cp` 临时副本）已删除；它的职责由 `worktree.ts` + `evaluate.ts` 的 base-commit worktree 流程取代。本模块没有新增错误类型文件；错误与全仓一致使用 `src/core/errors.ts` 的 `SageError`（`code` + `exitCode`）。`package.json`、`src/cli.ts`、`src/control/**`、其他文档均未由本 slice 修改（工作树中这些文件的改动来自其他 owner）。
