# 平台支持

SAGE-Kit 的目标宿主是 **DSH 运行时**（Web/headless 与桌面应用共用同一套 `DSH_HOME` 状态目录），不是只面向桌面应用。CLI 和 Skill 本身是 Node.js/文件系统工具，代码按 Windows 与 Linux 同时可用来写；**P0 的主测试环境是 Linux/WSL**。

## 支持矩阵

| 平台 | 角色 | P0 状态 |
|---|---|---|
| Linux / WSL2 | 主测试环境、DSH Web/headless、CI 首选 | 历史自动化与真实 DSH 证据见 `reports/p0/README.md`；本次修复未在 WSL2 重跑，不能把 Windows 副本测试结果推广到 Linux/WSL2 |
| Windows 10/11 | 开发工作站、DSH 桌面/headless 宿主 | 本次工作树在 Windows Node 24.22.0 执行：206 项，205 通过、0 失败、1 跳过；CI 仍优先 Linux，`scripts/windows-smoke.ps1` 的人工宿主冒烟未重跑 |
| macOS | CLI/Skill 理论可用 | `NOT_VERIFIED`，不作为 P0 承诺 |

## Node.js

- `>=22`（`package.json` 的 `engines`，D-014）；CLI 入口在 Node <22 时打印明确错误并以非 0 退出。
- 使用 ESM 与内置 `fs/promises`、`child_process`、`fetch`（P0 实际未使用 fetch），核心零运行时依赖。

## Windows 兼容约束

- 使用 `node:path`，不拼接 `/` 或依赖 POSIX 路径分隔符。
- 不调用 `bash`、`sh -c`、`chmod`；外部命令通过 `spawn`（参数数组、`shell:false`）执行。
- `worktree` 需要 Git for Windows；路径由 Node 处理，含空格的路径需在冒烟中覆盖。
- Skill 安装模式默认 `copy`；`--mode symlink` 在 Windows 创建目录 junction，创建失败时回退为 copy 并输出 warning。
- 文件适配器路径（`init` 实际写入）：
  - **DSH**：项目 `.dsh/skills/sage-kit`；全局 `$DSH_HOME/skills/sage-kit`。说明块：项目 `AGENTS.md`；全局 `$DSH_HOME/AGENTS.md`。
  - **Codex**：项目 `.agents/skills/sage-kit` + `AGENTS.md`；全局 `<home>/.agents/skills/sage-kit` + `<home>/.codex/AGENTS.md`。
  - **Claude Code**：项目 `.claude/skills/sage-kit` + `CLAUDE.md`；全局 `<home>/.claude/skills/sage-kit` + `<home>/.claude/CLAUDE.md`。
  - `fake` 适配器只用于测试（`.fake/skills/sage-kit`），不是真实宿主。
- 路径环境变量优先级（`src/adapters/*.ts`）：
  - `DSH_HOME`：`env.DSH_HOME` 优先；未设置时用 `<home>/.dsh`，其中 `<home>` 依次为 `HOME`、`USERPROFILE`，都没有时用 `.`（相对当前目录）。
  - Claude：检测/安装使用 `<home>/.claude`（`HOME`/`USERPROFILE`）。
  - Codex：**检测**使用 `CODEX_HOME`（未设置时 `<home>/.codex`），但**全局安装路径不使用 `CODEX_HOME`**，而是 `<home>/.agents/skills`、`<home>/.codex/AGENTS.md`。这是已知不一致，若要支持自定义 `CODEX_HOME` 需在适配器里补齐（未实现）。
- 作用域与说明块：`--scope project`（默认）默认写入受管说明块；`--no-instructions` 跳过；`--scope global` 默认**跳过**说明块，需显式 `--instructions` 才写。
- Hook 通过 stdin/stdout 交换 JSON，不依赖 Unix pipe 文件；`init` 不安装宿主 hook，宿主是否自动调用由宿主决定（DSH 0.2.1-rc.2 未发现可安装的原生第三方 hook 配置）。

## 证据边界

- Linux/WSL：主测试环境为 `/home/kayann/sage-kit-linux-dsh`（Linux 源码副本 + 测试项目 + 隔离 `DSH_HOME` + DSH npm 安装，机器特定路径）；其 `refresh-and-test.sh` 做同步/构建/测试/tgz 安装/DSH headless 验证。历史运行见 `reports/p0/wsl-test.md`、`reports/p0/dsh-linux-web.md`，最新自动化计数见 `reports/p0/README.md`。
- 真实 DSH 证据：`reports/p0/dsh-real-host.md`（Windows 隔离环境，mock 模型，Skill 加载）、`reports/p0/dsh-e2e-model.md`（Linux/WSL，mock 模型，Skill → bash → SAGE-Kit CLI 创建任务，24/24 独立检查）、`reports/p0/dsh-real-model-e2e.md`（Linux/WSL，**真实 DeepSeek 模型** headless，Skill → bash → 创建/列出/文件校验）。前两者是 mock 模型证据；后者是真实模型 headless 证据，但不含 GUI/hook。
- Windows：本次工作树运行 `npm test`（206 项，205 通过，1 跳过）及真实本地 Git worktree 测试；`scripts/windows-smoke.ps1` 的安装/宿主冒烟未执行，不计入自动化证据。
- “支持 Windows”指 CLI 与 Skill 的文件/命令路径可用，不等于所有桌面交互或宿主 hook 自动安装可用。

## 为什么以 Linux 为主

DSH 的 Web/headless 运行时可以通过公开 npm 包 `@deepseek-ai/dsh` 在 Linux 上运行；后续服务端、Worker 和自动化测试都不应依赖 Windows 桌面应用。Windows 只作为开发和本地调试平台。
