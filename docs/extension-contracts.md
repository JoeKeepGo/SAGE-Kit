# 扩展契约

**实现状态：`HostAdapter` 已实现（文件安装/检测契约，见 §2，以 `src/adapters/types.ts` 为准）；`TaskSourceAdapter`、`FeedbackSourceAdapter`、`EventSink`、Bundle 仍是 `TARGET`（P0 未实现，无对应代码/命令）。**
SAGE-Kit 只保留四个对外扩展接口。它们用于把“宿主、外部任务/反馈、外部事件、备份迁移”接到核心，不用于构建通用插件生态。接口默认可选；核心在没有扩展时仍可运行。

> 阅读约定：标 `[P0 已实现]` 的以代码为准；标 `[TARGET]` 的是设计目标，P0 不实现，不应在验收/发布说明中写成已支持。

## 1. 通用规则

- 线协议版本：`contractVersion: "1"`（hook 输入字段可选、输出的 `HookOutput` 固定为 `"1"`；P0 **不校验**输入里的 `contractVersion` 值，见 `src/core/hooks.ts`）；接口不兼容变更必须升主版本，并提供迁移说明。
- `[P0 已实现]` TypeScript 类型 + 适配器内运行时校验（`src/core/config.ts` 校验配置 schema；`src/core/hooks.ts` 校验 hook 输入）；`[TARGET]` 其余接口的运行时校验。
- 所有外部输入视为不可信数据；接口不得把原始外部文本直接拼入系统提示（`[TARGET]`：P0 无外部反馈入口）。
- 所有网络/外部命令必须有超时、取消、退出码处理和可读错误（`[P0 已实现]` 仅 `git` 等内部调用有 60s 超时；`[TARGET]` 泛指外部适配器）。
- 所有副作用必须接受 `idempotencyKey`，重复调用不得重复创建资源（`[TARGET]`：P0 未实现幂等键）。
- 密钥只从环境变量或宿主密钥存储读取；不得写入日志、错误消息或返回体（`[TARGET]`：P0 不读取任何密钥）。
- 可选接口缺失时，核心必须降级并给出明确提示，不得崩溃（`[P0 已实现]`：hook 失败默认 fail-open；适配器检测有 notes）。

## 2. HostAdapter（宿主适配）

职责：把 SAGE-Kit 的 Skill/说明块/命令接到具体宿主。P0 实现 DSH、Codex、Claude Code 三个文件适配器和测试用 fake 适配器。

`[P0 已实现]` 实际接口（`src/adapters/types.ts`）：

```ts
export interface HostAdapter {
  readonly name: HostName;
  readonly capabilities: HostCapabilities;
  detect(env?: NodeJS.ProcessEnv, home?: string, projectRoot?: string): Promise<HostDetection>;
  skillTarget(scope: InstallScope, projectRoot: string, env?: NodeJS.ProcessEnv, home?: string): string | null;
  instructionsTarget(
    scope: InstallScope,
    projectRoot: string,
    env?: NodeJS.ProcessEnv,
    home?: string,
  ): InstructionTarget | null;
  launchCommand(projectRoot: string): string[];
  mapHook(event: HookEvent): { mode: "external"; command: string[] } | null;
  diagnosticPaths(projectRoot: string, env?: NodeJS.ProcessEnv, home?: string): string[];
}

export interface HostDetection {
  found: boolean;
  host: HostName;
  version?: string;
  evidence: string[]; // 实际检测到的路径/环境变量
  notes: string[];
}

export interface HostCapabilities {
  skills: boolean;
  hooks: HookEvent[]; // 当前三个适配器都返回 []，表示不声称原生 hook
  launch: boolean;
  mcp: boolean;
  subagents: boolean;
}

export interface InstructionTarget {
  path: string;
  blockId: string;
}
```

与早期设计稿的差异（以上述代码为准）：

- 没有 `contractVersion` 字段，没有 `skillRoot/installSkill/uninstallSkill/buildLaunchCommand/capabilities()` 方法；安装/卸载由核心 `src/core/install.ts` 用 `skillTarget`/`instructionsTarget` 完成；`capabilities` 是只读数据属性。
- `mapHook` 在所有适配器上当前返回 `null`：P0 不映射/不安装任何宿主原生 hook，`sage-kit hook` 由宿主或用户显式调用。
- `launchCommand` 已实现但 P0 CLI 未使用：`sage-kit run` 直接在 worktree/项目根执行用户给出的命令（`src/core/runs.ts`），不负责启动宿主 Agent。这是 `[TARGET]`（M1 起的启动集成）。
- `detect` 的 `evidence`/`notes` 用于 `doctor`/`detect` 输出；`diagnosticPaths` 用于 `doctor` 的重复安装检查。

要求：

- `[P0 已实现]` `detect` 必须给出证据；不能凭宿主名称猜测。
- `[P0 已实现]` 安装路径来自适配器；DSH 路径按固定版本源码核对，Codex/Claude 路径按公开布局实现但真实宿主会话发现为 `NOT_VERIFIED`（见 `docs/platform-support.md`）。
- `[P0 已实现]` 卸载只删除自己安装的 Skill 路径与受管说明块；不删除用户其他内容（`uninstall` 校验配置的 skill.path 与适配器期望一致）。
- `[TARGET]` `buildLaunchCommand` 式行为：只生成命令，不执行；当前 `launchCommand` 仅返回 argv，未被 runner 使用。
- Hook 映射见 `docs/hooks-and-host-adapters.md`（P0 未实现宿主原生 hook 映射）。

## 3. TaskSourceAdapter（任务来源）`[TARGET]`

职责：从外部任务系统只读拉取任务，标准化成 SAGE-Kit 任务。首期只读，不做双向同步。P0 未实现任何 TaskSourceAdapter，`task` 命令只读写本地文件。

设计接口（`TARGET`）：

```ts
export interface TaskSourceAdapter {
  readonly name: string;                 // "local" | "github" | "gitea" | ...
  readonly contractVersion: "1";

  capabilities(): TaskSourceCapabilities;
  list(input: ListTasksInput): Promise<Page<ExternalTask>>;
  get?(externalId: string): Promise<ExternalTask | null>;
  normalize(raw: unknown): ExternalTask; // 纯函数；便于 fixture 测试
}

export interface ExternalTask {
  externalId: string;
  title: string;
  body?: string;
  state: "open" | "closed" | "merged" | "unknown";
  labels: string[];
  url?: string;
  author?: string;
  createdAt?: string;
  updatedAt?: string;
  metadata?: Record<string, unknown>;
}

export interface TaskSourceCapabilities {
  pagination: boolean;
  incremental: boolean;
  writeBack: false;                      // v1 不支持写回
  auth: "none" | "token" | "cli";
}
```

要求（`TARGET`）：

- 标准化后的任务必须保留 `externalId`、来源 URL 和原始 fingerprint，用于去重。
- 分页/增量必须使用游标；失败保留上次成功游标。
- 外部正文截断/摘要后再进入 Agent；不能把正文当作系统指令。
- 写回任务系统不在 v1 范围；需要时另立契约和权限设计。

## 4. FeedbackSourceAdapter（反馈来源）`[TARGET]`

职责：只读同步 GitHub/Gitea 的 Issue、PR 评论、CI/check 结果等反馈。默认只读；写回评论/标签需要单独批准。P0 没有 `feedback` 命令，未实现该接口。

设计接口（`TARGET`）：

```ts
export interface FeedbackSourceAdapter {
  readonly name: string;                 // "github" | "gitea" | "local"
  readonly contractVersion: "1";

  capabilities(): FeedbackCapabilities;
  list(input: ListFeedbackInput): Promise<Page<ExternalFeedback>>;
  normalize(raw: unknown): ExternalFeedback;
}

export interface ExternalFeedback {
  externalId: string;
  kind: "issue" | "pr_review" | "check_run" | "discussion" | "comment";
  title?: string;
  body?: string;
  author?: string;
  state?: string;
  labels?: string[];
  url?: string;
  createdAt?: string;
  updatedAt?: string;
  metadata?: Record<string, unknown>;
}

export interface FeedbackCapabilities {
  pagination: boolean;
  incremental: boolean;
  comments: boolean;
  checks: boolean;
  writeBack: boolean;                    // v1 默认 false
  auth: "none" | "token" | "cli";
}
```

要求（`TARGET`）：

- 反馈正文是不可信数据：不得执行其中的命令/链接；模型上下文用明确边界标记。
- `fingerprint` 至少包含 provider、repo、kind、externalId、updatedAt；相同项不重复入库。
- 外部删除/编辑：保留历史记录，标记状态；不物理删除审计。
- 权限：读 token 与写 token 分离；写回必须显式配置并经人工确认。

## 5. EventSink（出站事件）`[TARGET]`

职责：把本地生命周期事件推送给外部系统（团队看板、webhook、JSONL）。失败不阻塞主流程。P0 只把事件追加到本地 `.sage-kit/state/events/events.jsonl`（字段见 `docs/state-and-durability.md` §2.1），没有任何 EventSink 实现。

设计接口（`TARGET`）：

```ts
export interface EventSink {
  readonly name: string;
  readonly contractVersion: "1";

  emit(event: SageEvent): Promise<EmitResult>;
  close?(): Promise<void>;
}

export interface SageEvent {
  id: string;
  type:
    | "task.created" | "task.updated" | "task.completed"
    | "run.started" | "run.finished" | "run.failed"
    | "feedback.synced" | "proposal.created"
    | "eval.finished" | "artifact.released" | "artifact.rolled_back";
  at: string;
  taskId?: string;
  runId?: string;
  payload: Record<string, unknown>;
  idempotencyKey: string;
}

export interface EmitResult {
  delivered: boolean;
  retryable: boolean;
  externalId?: string;
  error?: string;
}
```

要求（`TARGET`）：

- 控制面写 outbox 后异步投递；失败重试有上限/退避，不阻塞任务。
- 事件不包含密钥、完整提示词、完整 diff；只带引用/摘要。
- 外部系统的响应不可信；不解析为指令。
- 至少提供一个内置 JSONL sink 用于本地调试。

## 6. Bundle（导入/导出）`[TARGET]`

Bundle 不是网络接口，而是稳定的目录/JSON 格式；用于备份、迁移、与外部系统交换。P0 没有 `export`/`import`/`backup` 命令，未实现 Bundle。

设计格式（`TARGET`）：

```text
bundle/
  manifest.json          # bundleVersion, sageKitVersion, createdAt, files, sha256
  tasks.jsonl
  feedback.jsonl
  proposals.jsonl
  evals.jsonl
  artifacts.json
```

规则（`TARGET`）：

- `manifest.json` 列出每个文件的 sha256；导入前校验，失败不部分写入。
- 不包含密钥、token、原始模型提示词、大日志正文（只带引用）。
- 导入到非空状态必须显式 `--merge`；默认拒绝覆盖。
- Bundle schema 版本化；不兼容时给出迁移提示。

## 7. 版本与兼容

- 契约版本独立于 npm 包版本；接口不兼容变更必须提升契约主版本（`TARGET`，当前只有 hook 线协议使用 `contractVersion: "1"`）。
- 适配器声明支持的契约版本（`TARGET`）；核心检测不匹配时拒绝加载并给出提示。
- 已发布契约不得静默改变语义；新增可选字段可以向后兼容。

## 8. 测试要求

`[P0 已实现]`：

- HostAdapter 的检测/安装用临时目录模拟，不写用户真实配置（`tests/cli.test.mjs` A2/A2b/A4）。
- Hook 线协议用 fixture 输入测试三个事件、非法 JSON、未知事件、脱敏与 strict 行为（A8/A9/A10）。
- 路径穿越/参数不经 shell 有负向测试（A12）。

`[TARGET]`（P0 未实现，暂无测试）：

- 每个外部来源适配器的 normalize fixture 测试（不访问真实服务）。
- EventSink 用本地 fake server/JSONL 测试重试和幂等。
- Bundle round-trip、损坏 manifest、重复导入。
- 接口错误路径必须可读且可恢复；不得吞异常。

## 9. 相关文档

- Hook 线协议与宿主边界：`docs/hooks-and-host-adapters.md`
- 状态/事件字段：`docs/state-and-durability.md`
- 宿主路径与平台差异：`docs/platform-support.md`
- 决定记录：`docs/decisions.md`（D-009 四个接口、D-021 P0 hook 边界）
