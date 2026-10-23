# P0 验收

**状态：P0 文件模式已实现；A13 已做真实 DSH headless + mock 和 Linux Web 启动的部分验证，真实模型/浏览器 GUI 与 hook 自动注入未执行。**  
P0 是第一个实现里程碑。它只验证“本地、无控制面”的最小闭环；未通过前不开始控制面 UI、反馈自动同步或 RSI。

当前自动化覆盖（`npm test`）：A1 help/version；A2/A3 init/幂等/uninstall；A2b Codex/Claude 文件适配器；A4 正常/损坏配置；A5 生命周期/证据；A6 worktree；A7 brief；A8/A9/A10 hook/脱敏/strict；A11 **模拟** stale run 恢复；A12 路径穿越、参数不经 shell。未覆盖：缺 Node/Skill 的 doctor、hook 超时、真实 SIGKILL、bundle 导入导出。`npm pack` 后安装已手工验证（见 `reports/p0/README.md`），未纳入 CI。A13 已做真实 DSH headless + mock 和 Linux Web 启动的部分验证（Skill 发现/加载），真实模型、浏览器 GUI 和 hook 自动注入未执行。

## 1. P0 范围

包含：

- 一个 npm 包、CLI 入口、Skill 目录。
- `init` / `doctor` / `task` / `worktree` / `run` / `brief` / `hook` / `uninstall` 的最小实现。
- 文件模式状态（`.sage-kit/`），无 SQLite/控制面。
- 一个 worktree 内的任务执行包装（可用 fake host/命令测试，不要求真实模型）。
- `session.start` / `command.after` / `stop` 三个 hook 的文件模式实现。
- 基本安全与错误处理。

明确不包含：

- 本地控制面/UI、SQLite、任务队列、lease（M2）。
- GitHub/Gitea 反馈同步（M1）。
- 提案、评估、发布、RSI（M2/M3）。
- 多用户/团队/远程 API/多机。
- 真实模型质量评估；P0 只验证管道和状态正确性。

## 2. 测试环境

- Node.js `>=22`，ESM。
- 临时目录作为 `HOME`/仓库，不写用户真实配置。
- `FakeHostAdapter`：模拟宿主检测、Skill 安装路径、hook 调用；不启动真实 Agent。
- 可用本地脚本模拟“Agent 执行”（例如 echo/写文件），不调用模型。
- 测试必须在无网络环境下通过；需要网络的真实宿主安装是单独人工验收项。

## 3. 验收场景

目标：P0-A1 至 P0-A12 每条有自动化覆盖（允许明确标注“部分”）；P0-A13 是发布前的人工补充，不替代自动化。当前实际覆盖见文首矩阵。

### P0-A1 包与 CLI 可加载

- 操作：`node dist/cli.js --help`；`npm pack` 后安装到临时项目。
- 预期：帮助可用；无运行时依赖缺失；启动不访问网络；Node <22 给出明确错误。
- 证据：命令输出、exit code、依赖树。
- 自动化：部分（help/version；`npm pack` 安装为手工验证）。

### P0-A2 初始化

- 操作：在临时 git 仓库执行 `sage-kit init --host fake --scope project`。
- 预期：生成 `.sage-kit/config.json`；安装/链接 Skill 到适配器指定目录；不覆盖已有文件；输出下一步。
- 证据：目录树、config 内容、文件清单。
- 自动化：是。

### P0-A2b 文件适配器（Codex / Claude）

- 操作：在临时项目分别执行 `sage-kit init --host codex`、`sage-kit init --host claude`。
- 预期：Codex 写入 `.agents/skills/sage-kit/SKILL.md` + `AGENTS.md` 受管块；Claude 写入 `.claude/skills/sage-kit/SKILL.md` + `CLAUDE.md` 受管块；不覆盖用户原有内容。
- 证据：文件内容、受管块 marker、重复 init 幂等。
- 自动化：是（文件安装；真实会话发现 Skill 属 A13）。

### P0-A3 幂等初始化与卸载

- 操作：重复 `init`；再 `uninstall`。
- 预期：重复 init 不重复写/不破坏用户改动；卸载只删除 SAGE-Kit 文件；用户文件和其他 Skill 保留。
- 证据：前后目录 diff。
- 自动化：是。

### P0-A4 doctor

- 操作：正常仓库、缺 Node、缺 Skill、配置损坏分别执行 `sage-kit doctor`。
- 预期：正常返回 0 和摘要；异常返回非 0 和可读修复建议；不崩溃。
- 证据：各场景输出/exit code。
- 自动化：部分（正常/损坏配置；缺 Node/Skill 未覆盖）。

### P0-A5 任务生命周期（文件模式）

- 操作：`task create` → `list` → `status running` → `status review` → `status done`（带证据）。
- 预期：任务文件原子写入；非法转换被拒绝；done 必须有验收证据；列表可读。
- 证据：任务 JSON、事件行、错误消息。
- 自动化：是。

### P0-A6 worktree 隔离

- 操作：为任务创建 worktree；在 worktree 写文件；尝试清理脏 worktree。
- 预期：主工作区不受影响；分支命名正确；脏 worktree 拒绝自动删除；任务记录路径。
- 证据：`git worktree list`、git status、清理错误。
- 自动化：是。

### P0-A7 Session brief

- 操作：`sage-kit brief --task <id>`；以及 `session.start` hook 调用。
- 预期：输出包含任务/验收/下一步；≤ 2KB；不含密钥/完整反馈正文；无任务时给最小 brief。
- 证据：brief 文件、hook stdout、大小检查。
- 自动化：是。

### P0-A8 Hook 契约与降级

- 操作：合法输入、非法 JSON、超时、未知事件分别调用 `hook`。
- 预期：合法输出符合 schema；非法/超时 fail-open（strict 除外）；不写网络；退出码符合契约。
- 证据：fixture 输出、耗时、exit code。
- 自动化：部分（契约/非法 JSON；超时未覆盖）。

### P0-A9 command.after 记录

- 操作：通过 hook 或 `run` 包装执行一个本地命令，发送 `command.after`。
- 预期：事件记录命令摘要、退出码、耗时；不记录完整敏感输出；失败不阻断。
- 证据：事件文件行、脱敏检查。
- 自动化：是。

### P0-A10 stop 证据检查

- 操作：任务无验收证据时 `stop`；有证据时 `stop`；分别默认/`--strict`。
- 预期：无证据默认 warn；strict 返回 block/非零；有证据通过；不误报。
- 证据：stdout/exit code。
- 自动化：是。

### P0-A11 崩溃/中断恢复

- 操作：启动一个 fake run，在写入 run 记录后 kill 进程；重新执行 `doctor`/`task list`。
- 预期：状态文件可解析；任务标 `interrupted` 或保持已知状态；不会误标 done；可手动重试。
- 证据：kill 前后状态、恢复输出。
- 自动化：部分（构造 stale run 记录；未真实 SIGKILL 子进程）。

### P0-A12 安全基线

- 操作：路径穿越/符号链接输入；含 token 的日志；shell 元字符参数；bundle 路径（若 P0 有导出）。
- 预期：拒绝越界写；日志脱敏；参数不经 shell 拼接；无密钥泄漏。
- 证据：负向测试、扫描结果。
- 自动化：部分（路径穿越、参数不拼接；bundle 未实现）。

### P0-A13 真实宿主安装（人工）

- 操作：优先选 DSH（Taluvia 主开发宿主），其次 Claude Code 或 Codex；在临时项目执行 `init`，启动一次会话。
- 预期：Skill 可被发现；`session.start` 能由宿主调用并注入 brief（若该宿主支持 hook）；`stop` 可运行；卸载干净。
- 证据：截图/命令输出/宿主日志；记录宿主版本。
- 自动化：否（发布前人工验收，不阻塞 CI）。2026-10-24 补充：真实 DSH 0.2.1-rc.2 headless + mock 模型已验证 Skill 发现与 `skill` 工具加载；真实模型、GUI 会话和 hook 自动注入未验证。证据见 `reports/p0/dsh-real-host.md`。

## 4. 通过标准

- P0 目标：P0-A1 至 P0-A12 自动化全部通过；P0-A13 至少一个宿主通过。当前 A1–A12 已有自动化覆盖（见上方“当前自动化覆盖”），但部分场景是模拟/部分覆盖，不能据此声称 P0 完整验收。
- 无 P0 范围外的功能被误纳入（控制面/反馈/RSI 未实现是预期）。
- 所有失败有可读错误；无静默吞异常。
- 文档中的命令、路径、字段与实际一致。
- `npm pack` 产物不包含测试 fixture、密钥、临时文件。
- 测试不依赖网络/真实模型；可在干净环境重复。

## 5. 证据格式

测试输出保存到 `reports/p0/`（不提交大文件）：

```json
{
  "runId": "p0-YYYYMMDD-HHMMSS",
  "node": "v22.x",
  "os": "linux/darwin/win32",
  "commit": "<sha>",
  "scenarios": [
    { "id": "P0-A1", "status": "PASS", "evidence": "reports/p0/A1.txt" }
  ],
  "knownFailures": []
}
```

没有证据的能力保持 `NOT_IMPLEMENTED` / `NOT_EXECUTED`；不得用“应该可以”代替验收。

## 6. 运行方式（目标）

```bash
npm ci
npm test              # 单元/契约测试
npm run test:p0       # P0 验收（无网络）
npm run test:security # 负向/脱敏测试
```

命令在实现时落地；本文件是验收合同，不是已实现证明。

## 7. 后续里程碑准入

P0 全部通过后：

- M1 才开始接 GitHub/Gitea 只读反馈。
- M2 才开始控制面/SQLite/UI/提案/评估/发布。
- M3 才谈 L2 半自动 RSI。

任何“先做 UI/自动改进再补 P0”的提议默认拒绝，除非有明确证据表明 P0 阻塞且风险可控。
