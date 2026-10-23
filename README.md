# SAGE-Kit

**状态：P0 + M1 反馈同步 + M2 控制面 foundation + M3 RSI skeleton 已实现；未发布到 npm registry、未发布 release。** P0 自动化覆盖 78/78（含 P0、M1、M2、M3 测试），A13 已做真实 DSH headless + mock/真实模型和 Linux Web 部分验证，但浏览器 GUI、hook 自动注入、真实 `stop` 生命周期仍未验收。M1 的 GitHub/Gitea 真实 API 未验证（测试为 localhost fixture）；M2 仅 foundation（无 UI/提案/评估实体/备份导出）；M3 仅手动 skeleton（无定时器、无自动批准/合并/发布）。

SAGE-Kit 是一个面向**单用户、本地开发**的 Agent 开发工具包：它提供一份可安装的 Skill、一个本地文件模式的任务/证据 CLI、只读反馈同步、可选的 SQLite 控制面 foundation，以及受控的“反馈 → 提案 → 评估 → 人工批准”RSI skeleton。

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
   - M1 实现说明：[`docs/m1-feedback.md`](docs/m1-feedback.md)
   - M2 foundation：[`docs/m2-control.md`](docs/m2-control.md)
   - M3 skeleton：[`docs/m3-rsi.md`](docs/m3-rsi.md)
5. [`docs/hooks-and-host-adapters.md`](docs/hooks-and-host-adapters.md) — 宿主适配、三类 hook、失败降级。
6. [`docs/security.md`](docs/security.md) — 威胁模型、密钥、提示注入、沙箱、供应链；P0 实际安全行为见 §2。
7. [`docs/p0-acceptance.md`](docs/p0-acceptance.md) — P0 范围、命令、验收场景与自动化测试要求。
8. [`docs/platform-support.md`](docs/platform-support.md) — Windows/Linux/WSL 支持边界与主测试环境。
9. [`docs/skill-contract.md`](docs/skill-contract.md) — Skill 的触发、工作流、停止条件与质量门槛。
10. [`docs/decisions.md`](docs/decisions.md) — 设计基线决策（ADR 摘要）。
11. [`docs/references.md`](docs/references.md) — 参考项目、可借鉴点与不采用的边界。
12. [`SECURITY.md`](SECURITY.md) — 安全报告方式、支持范围与响应边界。
13. [`reports/p0/README.md`](reports/p0/README.md) — P0 本地证据汇总（自动化测试、DSH/Codex/Claude 文件适配、mock 模型 E2E、Linux Web）。
14. [`reports/milestones/m0-m3.md`](reports/milestones/m0-m3.md) — M0–M3 本轮交付、验证和未完成边界。

## 一句话边界

- **做**：本地单用户、单仓库、多任务并发、可恢复执行；P0 用文件模式实现任务/运行/事件/worktree。
- **做（目标）**：反馈驱动的受控改进、本地控制面、独立评估、人工批准发布。
- **不做**：多机、团队、多租户、实时协作、RBAC、远程共享 API、自动合并、无人值守递归自改。

## 当前阶段

- P0 本地文件模式已实现：`init`、`detect`、`doctor`、`task`、`worktree`、`run`、`brief`、`hook`、`uninstall`、`version`。
- M1 已实现：`feedback sync/list/show`；本地 JSONL、GitHub/Gitea 只读同步；fingerprint 去重、cursor 保留、不可信数据标记，brief 注入最新 1 条反馈。真实 GitHub/Gitea 未验证。
- M2 foundation 已实现：`control serve/status/recover`；SQLite WAL、task/run/event/lease、单写者、localhost token API；无 UI、无提案/评估实体、无备份导出（M2b）。
- M3 skeleton 已实现：`rsi create/list/run-once/request-approval/rollback-point/approve/reject`；固定命令评估、受保护资产检查、一次性人工 approval token、回滚点记录；无定时器、无自动批准/合并/发布（M3b）。
- 文件适配器：DSH（项目 `.dsh/skills/sage-kit` + `AGENTS.md`，固定版本源码已核对）、Codex（`.agents/skills` + `AGENTS.md`）、Claude Code（`.claude/skills` + `CLAUDE.md`）；全局作用域安装到宿主全局目录，说明块默认跳过。P0 不安装宿主原生 hook。
- 自动化测试：`npm test`（本机 Windows Node v24.22.0、WSL2 Ubuntu Node v22.22.1；主测试/CI 仍建议 Linux）；当前 **79 项 / 79 通过 / 0 失败**（Windows Node 24.22.0 与 WSL2 Ubuntu Node 22.22.1 各跑一遍），覆盖 P0、M1、M2、M3。覆盖矩阵与已知缺口见 [`docs/p0-acceptance.md`](docs/p0-acceptance.md)、[`docs/m1-feedback.md`](docs/m1-feedback.md)、[`docs/m2-control.md`](docs/m2-control.md)、[`docs/m3-rsi.md`](docs/m3-rsi.md)。
- A13 部分证据：真实 DSH 0.2.1-rc.2 headless + mock 模型验证了项目 Skill 发现/加载；**真实 DeepSeek 模型 headless** 调用 `skill` → 真实 `bash` → SAGE-Kit `task create`/`task list`，任务 JSON 由独立命令复核；Linux DSH Web 启动、token/cookie/SPA 检查通过。**浏览器 GUI 交互、hook 自动注入、真实 `stop` 生命周期 `NOT_EXECUTED`**，因此 A13 未完整通过。证据见 [`reports/p0/dsh-real-model-e2e.md`](reports/p0/dsh-real-model-e2e.md)、[`reports/p0/dsh-e2e-model.md`](reports/p0/dsh-e2e-model.md)、[`reports/p0/dsh-real-host.md`](reports/p0/dsh-real-host.md)、[`reports/p0/dsh-linux-web.md`](reports/p0/dsh-linux-web.md)。
- `NOT_IMPLEMENTED`：控制面 UI、M2b 备份/导出、M3 定时/自动循环、Bundle 导入/导出、宿主 hook 自动安装、真实 GitHub/Gitea API 验证。
- 文档中“目标设计（`TARGET`）”与“已实现（`P0`）”分开标注；实现偏差先改 ADR/文档，再改代码。

## 许可证

MIT。第三方代码/依赖的来源、许可证和版本在实现时单独记录；核心 P0 无运行时依赖。
