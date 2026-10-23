# 安全与威胁模型

**实现状态：P0 文件模式、M1 只读反馈、M2 loopback 控制面、M3 评估闭环均已实现；多用户/远程/自动发布不实现。**
本文的 `[P0]` 小节以当前代码与测试为准；M1–M3 的实现安全边界见 `docs/m1-feedback.md`、`docs/m2-control.md`、`docs/m3-rsi.md`。标 `[TARGET]` 且未实现的控制仍不得当作已实现能力。安全目标仍是**防止本机上的代码/数据被不可信输入或错误自动化破坏**，不是防御多租户或远程攻击者。

## 1. 资产

`[P0]` 实际存在的本地资产：

- 本机代码与未提交改动、git 历史、worktree。
- `.sage-kit/` 下的任务/运行/事件文件、`SESSION_BRIEF.md`、`config.json`。
- 用户的 Agent 会话与提示内容（SAGE-Kit 之外的宿主负责）。
- 本机其他项目/文件（SAGE-Kit 不应越界访问）。

`[TARGET]` 未来资产：模型 API key、提案/评估/发布记录。M1 从环境变量读取 GitHub/Gitea 只读 token；本地控制面不设 token（D-006）。P0 不读取、不保存任何密钥（没有密钥相关功能）。

## 2. P0 实际安全行为与限制

先读这一节；第 3–4 节的设计控制只有标注 `[P0]` 的部分已实现。

1. **P0 无网络、无服务** `[P0]`：P0 文件模式 CLI 启动不做网络请求，没有 HTTP server、没有监听端口、没有 `fetch` 调用；hook 不联网、不调用模型。M2 的控制面是显式 `control serve` 才启动的可选 loopback 服务，不随 P0 自动启动。
2. **无密钥处理** `[P0]`：P0 不读取 token/API key，没有密钥存储/凭据服务。反过来，P0 的脱敏也不是“统一脱敏”：
   - `[P0]` 事件 `data` 经 `redactRecord`：按键名（`password`/`token`/`secret`/`authorization`/`api_key` 等）、值模式（`password=...`、`sk-...`）替换，深度 ≤4、每层 ≤30 键、字符串截断 500 字符（`src/core/fs-utils.ts`、`src/core/events.ts`）。
   - `[P0]` run 的 `command` argv 经 `redactCommand`：敏感 flag 的下一个参数替换为 `<redacted>`，`bearer`/`sk-`/`ghp_` 前缀值替换（`src/core/runs.ts`）。
   - **未脱敏**：任务 JSON 的 `title/description/acceptance/evidence`、`task status --note`、CLI stderr 错误消息、`init/doctor` 输出路径。不要把密钥写进这些字段/参数。
3. **文件权限** `[P0]`：`atomicWrite` 用默认 `0o644`（受进程 umask 影响），事件文件以 `0o600` 打开，目录权限未强制 `0700`。本机多用户场景依赖操作系统/umask，不是强保证。
4. **路径** `[P0]`：任务 id 白名单 `[a-z0-9][a-z0-9-]{0,63}` 阻止穿越；worktree 路径用 `resolve()` 前缀检查限制在 `.sage-kit/worktrees` 下；`uninstall` 只删与适配器期望路径一致的 skill。**没有 realpath/符号链接解析**——symlink 逃逸不是 P0 已验证的防护面，配置/说明块路径按本地可信配置处理。
5. **命令执行** `[P0]`：`run` 用 `spawn(shell:false)` + 参数数组，不经过 shell；stdout/stderr `inherit` 直接给用户。**已知限制**：`run` 继承完整环境变量（可能含密钥），没有超时/取消；`git` 子进程有 60s 超时并设置 `GIT_TERMINAL_PROMPT=0`（`src/core/process.ts`）。
6. **Hook** `[P0]`：stdin 上限 64 KB，输入必须是 JSON 对象，事件限定 `session.start`/`command.after`/`stop`，`--event` 与输入不一致会被拒绝；默认 fail-open，`stop --strict` 才 block。`--timeout` 在 50–2000ms 内被校验并应用于整个 hook 路径（含等待 stdin），超时输出合法 `warn` JSON 并以退出码 124 结束（见 `docs/hooks-and-host-adapters.md` 的线协议/超时小节与 `src/core/hooks.ts`；超时自动化覆盖见 P0-A8）。hook 失败**不会**写失败事件（成功调用才追加事件），失败可观测性有限。
7. **安装/卸载** `[P0]`：`init` 只写适配器指定路径和受管说明块，保留用户已有内容（A2/A3 有测试）；`init` 不安装任何宿主/ git hook。`uninstall` 只删自己的 skill、受管块、`SESSION_BRIEF.md`、`config.json`；`--purge` 才删整个 `.sage-kit/`。
8. **Git 边界** `[P0]`：没有自动 push/merge/publish 命令；`worktree remove` 默认拒绝脏 worktree；不安装 git hook。

## 3. 信任边界

```text
[可信] 用户显式操作、SAGE-Kit 自身代码、已校验的本地配置
   │
   ├─ [不可信] 外部 Issue/PR/网页/CI 日志/第三方 bundle（M1 只读接入，正文始终作为数据）
   ├─ [不可信] 被修改的仓库内容、依赖、git hook
   ├─ [受限] 宿主 Agent 生成的命令/代码改动
   └─ [本机] M2 loopback 控制面（默认不启动；无 token，信任同机同用户）
```

规则：跨边界的文本一律当数据；跨边界的执行一律要校验/确认。M1 的反馈正文只作为 `UNTRUSTED DATA` 展示/带入 brief，不执行其中指令；仍不能把 SAGE-Kit 当作已具备对抗恶意提示注入的完整隔离。

## 4. 威胁与控制

### 4.1 提示注入 / 不可信数据

威胁：Issue/PR 评论、网页、CI 日志中包含“忽略之前指令、执行命令、上传密钥”等文本，被 Agent 当指令执行。

- `[P0]` 无外部反馈同步/网页抓取；brief 只由本地任务文件生成，大小受 `--max-bytes`（默认 2048，上限 8192）约束，超限截断。
- `[P0 限制]` 没有“不可信数据边界标记”机制；若用户把外部正文粘进 `--title/--description/--acceptance`，它会被当作普通任务文本进入 brief。不要这样做；外部文本应先人工消毒。
- `[TARGET]` 外部文本进入上下文前加明确边界和警告；不执行反馈中的命令/链接；记录来源/URL；不把完整外部正文塞进系统提示。

### 4.2 命令执行

威胁：路径/参数注入、shell 注入、危险命令、无限运行、环境变量泄漏。

- `[P0]` `run` 使用 `spawn` + 参数数组，`shell:false`；任务 id 白名单阻止路径注入；A12 覆盖“参数中的 `; touch …` 不会被执行”。
- `[P0 限制]` `run` 执行的命令继承完整环境变量、无超时/无取消；这是给用户直接运行命令的入口，不提供沙箱。
- `[P0]` `git` 调用有 60 秒超时；hook 不执行外部命令、不联网。
- `[TARGET]` 所有外部命令统一的超时/取消/cwd 限制/最小环境变量；高风险操作显式确认；输出脱敏。

### 4.3 文件与路径

威胁：路径穿越、符号链接逃逸、覆盖用户文件、worktree 边界逃逸。

- `[P0]` 任务 id 校验；worktree 路径 `resolve()` 前缀约束；用户已有 `AGENTS.md`/`CLAUDE.md` 内容在安装/卸载时保留；写文件用临时文件 + rename。
- `[P0 限制]` 没有 `realpath` 解析；没有 bundle 导入；没有 `0600`/`0700` 强制权限。
- `[TARGET]` `realpath` 后校验允许根；bundle 拒绝绝对路径/`..`/symlink；状态文件 `0600`、目录 `0700`；删除/覆盖前确认。

### 4.4 密钥与隐私

威胁：token/key 进入日志、提示词、错误消息、提交、UI。

- `[P0]` 不读取任何密钥；事件 data 与 run argv 尽力脱敏（§2.1）。
- `[P0 限制]` 脱敏不覆盖任务文本、CLI 错误、`run` 子进程输出；`run` 继承环境变量。
- `[TARGET]` 统一脱敏；密钥只从环境/密钥存储读取；模型上下文不含密钥；M1 只读 token 与未来写 token 分离；本地控制面不设 token（D-006）。

### 4.5 本地控制面（M2 foundation 已实现）

M2 的控制面是显式 `control serve` 才启动的可选 loopback 服务：

- 只绑定 `127.0.0.1`，不绑定 `0.0.0.0`；校验 `socket.remoteAddress` 与 `Host` 只接受 loopback（防 DNS rebinding）；不提供远程访问。
- **不设本地 token**（D-006）：信任边界是 OS 用户账户；同一 OS 用户下的进程可读取控制面状态。token 不能有效防御本地同用户进程，因此不作为必要控制。
- UI 使用严格 CSP（无外部脚本/样式、`frame-ancestors 'none'`）；不渲染不可信 HTML；控制面进程以当前用户运行；本地面板允许任务/状态/lease/恢复写操作，但仅限 loopback，且无自动合并/发布。
- 控制面不随 P0 文件模式自动启动。

### 4.6 Git 与 worktree

威胁：git hook 注入、误 push、分支污染、worktree 残留、git 配置被改。

- `[P0]` 不自动 push/merge；不安装 git hook；不覆盖用户已有 hook；worktree 分支可预测（`sage-kit/<task-id>`）；清理前检查未提交改动（`--force` 例外）。
- `[TARGET]` 安装 hook 前展示并备份；保护受保护分支/文件；候选改进不能改评估/审批配置。

### 4.7 依赖与供应链

威胁：恶意 npm 包、许可证问题、体积膨胀、postinstall 脚本。

- `[P0]` 包无运行时依赖（`package.json` 无 `dependencies`；A1b 在隔离空 cache 下用 `npm install --offline --ignore-scripts` 验证可安装）；有 lockfile；CI 在 Linux 上 `npm ci` → build → test；无 postinstall 脚本。
- `[TARGET]` 新增依赖记录用途/许可证/体积/替代方案；CI 审查；定期 audit，高危漏洞阻断发布。

### 4.8 RSI 特有风险（`TARGET`，M3）

P0 无提案/评估/发布/RSI。目标控制：L2 上限；发布人工批准；Builder/Evaluator 分离；评估资产受保护；发布 artifact 不可变、可回滚。

### 4.9 Bundle 导入/导出（`TARGET`）

P0 无 `export`/`import`/`backup` 命令。目标控制：manifest schema/hash/大小校验；拒绝绝对路径/`..`/symlink；默认不覆盖非空状态；临时目录展开校验后原子替换。

## 5. 安全默认值（P0 实际）

| 项 | P0 实际 | 目标 |
|---|---|---|
| 控制面监听/鉴权 | M2 `control serve` 可选；loopback + Host 校验，无 token | 保持 loopback，不设 token |
| 外部反馈 | M1 只读同步（`GITHUB_TOKEN`/`GITEA_TOKEN`） | 保持只读 |
| GitHub/Gitea 权限 | M1 从环境变量读取只读 token，不落盘 | 最小只读；写权限显式配置 |
| 自动 push/merge/publish | 关闭（无这些命令） | 关闭 |
| Hook 网络/模型调用 | 禁止（代码无网络/模型路径） | 禁止 |
| 密钥来源 | P0 不读取密钥 | 环境变量/宿主密钥存储 |
| 日志/事件正文 | 事件 data、run argv 尽力脱敏；任务文本不脱敏 | 统一脱敏、截断 |
| 文件权限 | 事件 0600；任务/配置 0644（umask） | 状态 0600、目录 0700 |
| 候选发布 | 无发布流程 | 人工批准 |
| 保留策略 | 无自动清理 | 任务/提案长期；run 日志 90 天 |

## 6. 安全验收（P0/P1）

`[P0 自动化]`（`tests/cli.test.mjs`）：

- 路径穿越的任务 id 被拒绝；命令参数不经 shell（A12）。
- 事件 data 中形如 `token=secret-value` 的尾巴被脱敏，不落入 `events.jsonl`（A8/A9/A10）。
- hook 非法 JSON/未知事件 fail-open，`stop --strict` 返回 `block`（A8/A9/A10）。
- `uninstall` 保留用户已有说明内容（A2/A3）。
- 包无运行时依赖、离线可安装（A1b）。
- hook 超时：P0-A8 覆盖（`--timeout` 生效、超时输出 warn + 退出码 124）。

`NOT_IMPLEMENTED`（P0 不承诺）：

- 控制面远程鉴权/TLS（当前只允许 loopback，无远程入口）。
- `run` 的命令超时/取消（只有内部 `git` 有超时）。
- 密钥扫描测试；统一脱敏。
- symlink 逃逸防护（无 realpath 校验）。
- 外部反馈注入 fixture（无反馈入口）。
- P1/M2：bundle 校验、评估隔离、发布回滚、依赖 audit。

## 7. 限制

- 不防御拥有本机账户/root 权限的攻击者。
- 不防御宿主 Agent 自身被完全攻陷；SAGE-Kit 只能限制其工具面和数据流。
- P0 `run` 不提供沙箱：继承环境、无超时/无取消、stdout/stderr 直接输出。
- P0 脱敏是尽力而为，不覆盖任务文本/错误/子进程输出。
- 不提供加密存储；依赖操作系统磁盘加密/文件权限。
- 不承诺模型供应商的数据处理策略；密钥与数据边界需用户自行配置。
- 安全问题应按 `SECURITY.md` 报告；未修复前不公开细节。
