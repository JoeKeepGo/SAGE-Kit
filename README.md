# SAGE-Kit

**状态：P0 本地文件模式已实现，未发布到 npm registry。** P0-A1–A12 有自动化覆盖（缺 Node <22 分支未覆盖；A11 含模拟 stale run 与真实 SIGKILL 恢复；A8 覆盖 hook 超时；bundle 导入/导出不在 P0 范围）；A13 已做真实 DSH headless + **mock 模型**和 Linux Web 启动的部分验证（Skill 发现/加载），真实模型、浏览器 GUI 和 hook 自动注入未执行。控制面、SQLite、反馈同步、提案/评估/RSI 未实现（M1–M3 目标）。

SAGE-Kit 是一个面向**单用户、本地开发**的 Agent 开发工具包：它提供一份可安装的 Skill、一个本地文件模式的任务/证据 CLI，以及（设计目标）本地控制面和受控的“反馈 → 提案 → 评估 → 发布”改进闭环。P0 只实现本地文件模式，`docs/` 中标 `TARGET` 的能力均未实现。

它不是团队协作平台，也不是多租户服务；团队任务系统只通过稳定接口接入（设计目标）。

## P0 快速开始

```bash
npm install
npm run build
# 在一个 git 仓库中安装到项目
node dist/cli.js init --host dsh --scope project
node dist/cli.js doctor --json
node dist/cli.js task create --title "First task" --acceptance "tests pass"
node dist/cli.js task status <id> running
node dist/cli.js task status <id> review
node dist/cli.js task status <id> done --evidence "tests pass"
node dist/cli.js task list
```

本包**尚未发布到 npm registry**，`npx sage-kit` 不会从 registry 拉到它。使用方式：本仓库开发时用 `node dist/cli.js`；或 `npm pack` 得到 `sage-kit-0.1.0.tgz` 后 `npm install ./sage-kit-0.1.0.tgz`（或全局安装该 tarball）再用 `sage-kit`。

主测试环境是 WSL/Linux（见 `docs/platform-support.md`）；Windows 不作为测试套件执行环境。P0 不是发布版本；若未来建立发布流程，发布前应用 `scripts/windows-smoke.ps1` 做一次人工安装/Skill 发现冒烟（当前 `NOT_EXECUTED`）。

`init` 会写入 `.sage-kit/config.json`、宿主 Skill 目录、项目根的 `SESSION_BRIEF.md`，并默认写入受管的 `AGENTS.md` 块（Codex/Claude 分别用 `.agents/skills`/`AGENTS.md`、`.claude/skills`/`CLAUDE.md`）。说明块行为：`--scope project`（默认）默认写入，`--no-instructions` 跳过；`--scope global` 默认**跳过**，需 `--instructions` 才写。P0 不自动安装宿主 hooks；`hook` 命令可由宿主显式调用。

## 文档索引

按顺序阅读：

1. [`docs/architecture.md`](docs/architecture.md) — 目标架构、分层、状态归属、运行模式、路线图。
2. [`docs/state-and-durability.md`](docs/state-and-durability.md) — 文件模式/控制面模式、数据模型、恢复、并发与备份。
3. [`docs/extension-contracts.md`](docs/extension-contracts.md) — 四个扩展接口：宿主、任务源、反馈源、事件出口；Bundle 是导入/导出格式。
4. [`docs/feedback-and-rsi.md`](docs/feedback-and-rsi.md) — GitHub/Gitea 反馈、提案、独立评估、发布与回滚、L0–L2 自我改进。
5. [`docs/hooks-and-host-adapters.md`](docs/hooks-and-host-adapters.md) — 宿主适配、三类 hook、失败降级。
6. [`docs/security.md`](docs/security.md) — 威胁模型、密钥、提示注入、沙箱、供应链；P0 实际安全行为见 §2。
7. [`docs/p0-acceptance.md`](docs/p0-acceptance.md) — P0 范围、命令、验收场景与自动化测试要求。
8. [`docs/platform-support.md`](docs/platform-support.md) — Windows/Linux/WSL 支持边界与主测试环境。
9. [`docs/skill-contract.md`](docs/skill-contract.md) — Skill 的触发、工作流、停止条件与质量门槛。
10. [`docs/decisions.md`](docs/decisions.md) — 设计基线决策（ADR 摘要）。
11. [`docs/references.md`](docs/references.md) — 参考项目、可借鉴点与不采用的边界。
12. [`SECURITY.md`](SECURITY.md) — 安全报告方式、支持范围与响应边界。
13. [`reports/p0/README.md`](reports/p0/README.md) — P0 本地证据汇总（自动化测试、DSH/Codex/Claude 文件适配、mock 模型 E2E、Linux Web）。

## 一句话边界

- **做**：本地单用户、单仓库、多任务并发、可恢复执行；P0 用文件模式实现任务/运行/事件/worktree。
- **做（目标）**：反馈驱动的受控改进、本地控制面、独立评估、人工批准发布。
- **不做**：多机、团队、多租户、实时协作、RBAC、远程共享 API、自动合并、无人值守递归自改。

## 当前阶段

- P0 本地文件模式已实现：`init`、`detect`、`doctor`、`task`、`worktree`、`run`、`brief`、`hook`、`uninstall`、`version`。
- 文件适配器：DSH（项目 `.dsh/skills/sage-kit` + `AGENTS.md`，固定版本源码已核对）、Codex（`.agents/skills` + `AGENTS.md`）、Claude Code（`.claude/skills` + `CLAUDE.md`）；全局作用域安装到宿主全局目录，说明块默认跳过。P0 不安装宿主原生 hook；OpenCode 为 M1 目标。
- 自动化测试：`npm test`（主测试环境 Linux/WSL）；当前 **19 项 / 19 通过 / 0 失败**（WSL2 Ubuntu 26.04、Node v22.22.1，2026-10-24），覆盖矩阵与已知缺口见 [`docs/p0-acceptance.md`](docs/p0-acceptance.md) 和 [`reports/p0/README.md`](reports/p0/README.md)。已知缺口：缺 Node <22 的运行时集成测试（A4d 只覆盖版本策略单元断言）；真实宿主 hook 自动注入无实现。
- A13 部分证据：真实 DSH 0.2.1-rc.2 headless + mock 模型验证了项目 Skill 发现/加载，mock 模型触发 `skill` 与 `bash` 工具后由 CLI 创建任务；Linux DSH Web 启动、token/cookie/SPA 检查通过。**真实模型、浏览器 GUI 交互、hook 自动注入 `NOT_EXECUTED`**。证据见 [`reports/p0/dsh-e2e-model.md`](reports/p0/dsh-e2e-model.md)、[`reports/p0/dsh-real-host.md`](reports/p0/dsh-real-host.md)、[`reports/p0/dsh-linux-web.md`](reports/p0/dsh-linux-web.md)。
- `NOT_IMPLEMENTED`：控制面/UI、SQLite、lease、反馈同步、提案/评估/RSI、Bundle 导入/导出、宿主 hook 自动安装。
- 文档中“目标设计（`TARGET`）”与“已实现（`P0`）”分开标注；实现偏差先改 ADR/文档，再改代码。

## 许可证

MIT。第三方代码/依赖的来源、许可证和版本在实现时单独记录；核心 P0 无运行时依赖。
