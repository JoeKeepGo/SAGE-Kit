# 扩展契约

**状态：设计基线；HostAdapter 已实现（DSH/Codex/Claude/fake），其余接口未实现。**  
SAGE-Kit 只保留四个对外扩展接口。它们用于把“宿主、外部任务/反馈、外部事件、备份迁移”接到核心，不用于构建通用插件生态。接口默认可选；核心在没有扩展时仍可运行。

## 1. 通用规则

- 契约版本：`contractVersion: "1"`；不兼容变更必须升主版本，并提供迁移说明。
- 所有接口都是 TypeScript 类型 + 运行时校验；实现放在独立目录，不进入核心启动路径。
- 所有外部输入视为不可信数据；接口不得把原始外部文本直接拼入系统提示。
- 所有网络/外部命令必须有超时、取消、退出码处理和可读错误。
- 所有副作用必须接受 `idempotencyKey`，重复调用不得重复创建资源。
- 密钥只从环境变量或宿主密钥存储读取；不得写入日志、错误消息或返回体。
- 可选接口缺失时，核心必须降级并给出明确提示，不得崩溃。

## 2. HostAdapter（宿主适配）

职责：把 SAGE-Kit 的 Skill/命令/生命周期接到具体宿主。P0 至少实现一个。

```ts
export interface HostAdapter {
  readonly name: string;                 // "claude-code" | "codex" | "opencode" | "dsh" | ...
  readonly contractVersion: "1";

  detect(): Promise<HostDetection>;
  skillRoot(scope: "project" | "global"): Promise<string>;
  installSkill(input: InstallSkillInput): Promise<InstallResult>;
  uninstallSkill(input: UninstallSkillInput): Promise<UninstallResult>;
  buildLaunchCommand(input: LaunchInput): Promise<LaunchCommand>;
  mapHook?(event: HostHookEvent): HookMapping | null;
  capabilities(): HostCapabilities;
}

export interface HostDetection {
  found: boolean;
  version?: string;
  executable?: string;
  configDir?: string;
  evidence: string[];                    // 实际检测到的路径/命令/版本
}

export interface InstallSkillInput {
  sourceDir: string;                     // 包内 skills/sage-kit
  scope: "project" | "global";
  mode: "symlink" | "copy";
  force?: boolean;
}

export interface InstallResult {
  installedPath: string;
  mode: "symlink" | "copy";
  files: string[];
  warnings: string[];
}

export interface HostCapabilities {
  hooks: Array<"session.start" | "command.after" | "stop">;
  skills: boolean;
  subagents: boolean;
  headless: boolean;
  mcp: boolean;
}
```

要求：

- `detect` 必须给出证据；不能凭宿主名称猜测。
- 安装路径必须来自宿主公开文档或实际探测；不得硬编码未经验证的目录。
- 卸载只删除自己安装的文件；不删除用户数据/其他 Skill。
- `buildLaunchCommand` 只生成命令，不执行；执行由 CLI runner 负责。
- Hook 映射见 `docs/hooks-and-host-adapters.md`。

## 3. TaskSourceAdapter（任务来源）

职责：从外部任务系统只读拉取任务，标准化成 SAGE-Kit 任务。首期只读，不做双向同步。

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

要求：

- 标准化后的任务必须保留 `externalId`、来源 URL 和原始 fingerprint，用于去重。
- 分页/增量必须使用游标；失败保留上次成功游标。
- 外部正文截断/摘要后再进入 Agent；不能把正文当作系统指令。
- 写回任务系统不在 v1 范围；需要时另立契约和权限设计。

## 4. FeedbackSourceAdapter（反馈来源）

职责：只读同步 GitHub/Gitea 的 Issue、PR 评论、CI/check 结果等反馈。默认只读；写回评论/标签需要单独批准。

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

要求：

- 反馈正文是不可信数据：不得执行其中的命令/链接；模型上下文用明确边界标记。
- `fingerprint` 至少包含 provider、repo、kind、externalId、updatedAt；相同项不重复入库。
- 外部删除/编辑：保留历史记录，标记状态；不物理删除审计。
- 权限：读 token 与写 token 分离；写回必须显式配置并经人工确认。

## 5. EventSink（出站事件）

职责：把本地生命周期事件推送给外部系统（团队看板、webhook、JSONL）。失败不阻塞主流程。

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

要求：

- 控制面写 outbox 后异步投递；失败重试有上限/退避，不阻塞任务。
- 事件不包含密钥、完整提示词、完整 diff；只带引用/摘要。
- 外部系统的响应不可信；不解析为指令。
- 至少提供一个内置 JSONL sink 用于本地调试。

## 6. Bundle（导入/导出）

Bundle 不是网络接口，而是稳定的目录/JSON 格式；用于备份、迁移、与外部系统交换。

```text
bundle/
  manifest.json          # bundleVersion, sageKitVersion, createdAt, files, sha256
  tasks.jsonl
  feedback.jsonl
  proposals.jsonl
  evals.jsonl
  artifacts.json
```

规则：

- `manifest.json` 列出每个文件的 sha256；导入前校验，失败不部分写入。
- 不包含密钥、token、原始模型提示词、大日志正文（只带引用）。
- 导入到非空状态必须显式 `--merge`；默认拒绝覆盖。
- Bundle schema 版本化；不兼容时给出迁移提示。

## 7. 版本与兼容

- 契约版本独立于 npm 包版本；接口不兼容变更必须提升契约主版本。
- 适配器声明支持的契约版本；核心检测不匹配时拒绝加载并给出提示。
- 已发布契约不得静默改变语义；新增可选字段可以向后兼容。

## 8. 测试要求

- 每个适配器至少有 normalize 的 fixture 测试，不访问真实服务。
- HostAdapter 的检测/安装用临时目录模拟，不写用户真实配置。
- EventSink 用本地 fake server/JSONL 测试重试和幂等。
- Bundle 用 round-trip、损坏 manifest、重复导入测试。
- 接口错误路径必须可读且可恢复；不得吞异常。
