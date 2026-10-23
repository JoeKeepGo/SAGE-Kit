# 平台支持

SAGE-Kit 的目标宿主是 **DSH 运行时**，不是桌面应用。CLI 和 Skill 本身是 Node.js/文件系统工具，必须同时支持 Windows 与 Linux。

## 支持矩阵

| 平台 | 角色 | 状态 |
|---|---|---|
| Linux / WSL2 | 主测试、DSH Web/headless、CI 首选 | 已验证（10/10 P0、真实 DSH Skill 加载） |
| Windows 10/11 | 开发工作站、DSH 桌面/headless 宿主 | 必须可用；不要求作为测试执行环境 |
| macOS | CLI/Skill 理论可用 | 未验证，不作为 P0 承诺 |

## Windows 兼容约束

- 使用 `node:path`，不拼接 `/` 或依赖 POSIX 路径分隔符。
- 不调用 `bash`、`sh -c`、`chmod`；外部命令通过 `spawn` 直接执行。
- `worktree` 需要 Git for Windows；路径由 Node 处理，含空格的路径必须可用。
- Skill 安装模式默认 `copy`；`symlink` 在 Windows 使用 junction，失败时回退 copy。
- 文件适配器路径：
  - DSH：`.dsh/skills/sage-kit`（项目）或 `%USERPROFILE%\.dsh\skills\sage-kit`（全局）
  - Codex：`.agents/skills/sage-kit`
  - Claude Code：`.claude/skills/sage-kit`
- Hook 通过 stdin/stdout 交换 JSON，不依赖 Unix pipe 文件；宿主是否自动调用由宿主决定。
- 不承诺桌面专属能力（原生目录选择、Electron IPC、桌面通知等）在 Web/Linux 上可用。

## 证据边界

- Linux/WSL：`/home/kayann/sage-kit-linux-dsh` 持久环境；`refresh-and-test.sh` 通过 10/10，并完成真实 DSH headless 的 `skill` 工具调用。
- Windows：此前做过 CLI 与真实 DSH headless 的兼容冒烟；按当前约定不在 Windows 上继续跑测试套件。发布前用 `scripts/windows-smoke.ps1` 做一次人工安装/Skill 发现冒烟。
- “支持 Windows”指 CLI 与 Skill 的文件/命令路径可用，不等于所有桌面交互或宿主 hook 自动安装可用。

## 为什么以 Linux 为主

DSH 的 Web/headless 运行时可以通过公开 npm 包 `@deepseek-ai/dsh` 在 Linux 上运行；后续服务端、Worker 和自动化测试都不应依赖 Windows 桌面应用。Windows 只作为开发和本地调试平台。
