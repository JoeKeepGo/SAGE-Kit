# SAGE-Kit

**状态：P0 本地文件模式已实现。P0-A1–A12 有自动化覆盖（A11 为模拟中断，部分边界未覆盖）；真实 DSH 0.2.1-rc.2 headless 和 Linux Web 部署已验证 Skill 发现/加载，真实模型/GUI 和 hook 自动注入未验；控制面、反馈同步和 RSI 未实现。**

SAGE-Kit 是一个面向**单用户、本地开发**的 Agent 开发工具包：它提供一份可安装的 Skill、一个可选的本地控制面，以及一个受控的“反馈 → 提案 → 评估 → 发布”改进闭环。

它不是团队协作平台，也不是多租户服务；团队任务系统只通过稳定接口接入。

## P0 快速开始

```bash
npm install
npm run build
# 在一个 git 仓库中安装到项目
node dist/cli.js init --host dsh --scope project
node dist/cli.js doctor --json
node dist/cli.js task create --title "First task" --acceptance "tests pass"
node dist/cli.js task list
```

安装到目标仓库后可用 `sage-kit`（或 `npx sage-kit`，若已发布/全局安装）；本仓库开发时用 `node dist/cli.js`。

主测试环境是 WSL/Linux（见 `docs/platform-support.md`）；Windows 不作为测试套件执行环境，但发布前必须用 `scripts/windows-smoke.ps1` 做兼容冒烟。

`init` 会写入 `.sage-kit/config.json`、宿主 Skill 目录和受管的 `AGENTS.md` 块（Codex/Claude 分别用 `.agents/skills`/`AGENTS.md`、`.claude/skills`/`CLAUDE.md`）。P0 不自动安装宿主 hooks；`hook` 命令可由宿主显式调用。

## 文档索引

按顺序阅读：

1. [`docs/architecture.md`](docs/architecture.md) — 目标架构、分层、状态归属、运行模式、路线图。
2. [`docs/state-and-durability.md`](docs/state-and-durability.md) — 文件模式/控制面模式、数据模型、恢复、并发与备份。
3. [`docs/extension-contracts.md`](docs/extension-contracts.md) — 四个扩展接口：宿主、任务源、反馈源、事件出口；Bundle 是导入/导出格式。
4. [`docs/feedback-and-rsi.md`](docs/feedback-and-rsi.md) — GitHub/Gitea 反馈、提案、独立评估、发布与回滚、L0–L2 自我改进。
5. [`docs/hooks-and-host-adapters.md`](docs/hooks-and-host-adapters.md) — 宿主适配、三类 hook、失败降级。
6. [`docs/security.md`](docs/security.md) — 威胁模型、密钥、提示注入、沙箱、供应链。
7. [`docs/p0-acceptance.md`](docs/p0-acceptance.md) — P0 范围、命令、验收场景与自动化测试要求。
8. [`docs/platform-support.md`](docs/platform-support.md) — Windows/Linux/WSL 支持边界与主测试环境。
9. [`docs/skill-contract.md`](docs/skill-contract.md) — Skill 的触发、工作流、停止条件与质量门槛。
10. [`docs/decisions.md`](docs/decisions.md) — 设计基线决策（ADR 摘要）。
11. [`docs/references.md`](docs/references.md) — 参考项目、可借鉴点与不采用的边界。
12. [`SECURITY.md`](SECURITY.md) — 安全报告方式、支持范围与响应边界。

## 一句话边界

- **做**：本地单用户、单仓库、多任务并发、可恢复执行、反馈驱动的受控改进。
- **不做**：多机、团队、多租户、实时协作、RBAC、远程共享 API、自动合并、无人值守递归自改。

## 当前阶段

- P0 本地文件模式已实现：`init`、`doctor`、`task`、`worktree`、`run`、`brief`、`hook`、`uninstall`。
- 文件适配器：DSH（优先，已按固定版本源码核对 Skill/AGENTS 路径）、Codex（`.agents/skills` + `AGENTS.md`）、Claude Code（`.claude/skills` + `CLAUDE.md`）；OpenCode 为 M1。
- 自动化测试：`npm test`；证据场景见 `docs/p0-acceptance.md` 和 [`reports/p0/README.md`](reports/p0/README.md)。
- 未执行：真实 DSH/Codex/Claude 会话验收；控制面、SQLite、反馈同步、提案/评估/RSI。
- 文档中的“目标设计”与“已实现”分开标注；实现偏差先改 ADR/文档，再改代码。

## 许可证

MIT。第三方代码/依赖的来源、许可证和版本在实现时单独记录；不为参考项目增加运行依赖。
