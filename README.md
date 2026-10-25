# SAGE-Kit

**状态：0.2.0-alpha.1 内部 alpha；P0 + M1 反馈同步 + M2 本地可写控制面 + M3 评估闭环已实现；未发布到 npm registry。** 本次工作树自动化 206 项：205 通过、0 失败、1 跳过（Windows Node 24.22.0）（含 P0、M1、M2、M3、库 API、DSH 插件、RSI 门禁与 Codex/Claude 宿主包回归测试）；P0-A13 已在真实 DSH 0.2.1-rc.2 + 真实 DeepSeek 模型上通过 GUI、真实 stop、卸载/重装验证；DSH 不提供 `sage-kit hook` 的自动注入，记录为宿主能力边界（手动 `hook` 与 AGENTS 指令路径可用；可选原生插件走 DSH 插件机制，见下）。M1 已用真实 `api.github.com` 与 WSL2 隔离 Gitea 1.27.3 完成只读同步验证；M2 控制面板支持任务创建、状态转换、lease 与恢复（仅 loopback，无 token）；M3 支持真实 git worktree 评估、基线对比、重复评估、导出与人工批准（无定时器/自动批准/合并/发布）。

SAGE-Kit 是一个面向**单用户、本地开发**的 Agent 开发工具包：它提供一份可安装的 Skill、一个本地文件模式的任务/证据 CLI、只读反馈同步、可选的 SQLite 控制面（含本地控制面板），以及受控的“反馈 → 提案 → 评估 → 人工批准”RSI 闭环。

它不是团队协作平台，也不是多租户服务；团队任务系统只通过稳定接口接入（设计目标）。

另有**可选 DSH 原生插件** [`packages/dsh-plugin`](packages/dsh-plugin/README.md)（包名 `sage-kit-dsh`）：在 DSH 中提供原生任务工具与 `agent/pre-step` 自动 brief，并支持 `off`/`brief`/`strict` 三档模式；`strict` 对所有未终态、显式带 `rsiProposalId` 的任务检查已批准 + 评估通过 + 人工批准三重证据，未通过则拒绝该轮。它是宿主适配包，独立安装、版本受 `engines.dsh` 约束，不是核心 CLI/Skill 的替代，也不进入核心安装依赖。插件已在真实 DSH 0.2.1-rc.2 headless 通过 E2E（profile 安装、5 个原生工具、真实模型调用、brief 首次/更新/去重、无 `.sage-kit` 不注入，见 [`reports/plugin/dsh-plugin-e2e.md`](reports/plugin/dsh-plugin-e2e.md)）；独立评审结论为**有条件可安装**（[`reports/plugin/review.md`](reports/plugin/review.md)）；评审的 F-1/F-2 已修复（消息 source 不再声明非法 form；`engines.dsh` 上界改为 `<0.3.0-0`），F-3 文档已对齐。另在一个隔离的零依赖小项目 `tiny-notes` 上用真实模型跑通了“插件 brief → 任务 running/review/done → 测试证据”的完整会话（[`reports/plugin/sandbox-tiny-notes.md`](reports/plugin/sandbox-tiny-notes.md)）。Web GUI、Windows/macOS 与配置分支等边界未执行（`NOT_EXECUTED`），不要据此对外称全平台“已验证可用”。

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

本包**尚未发布到 npm registry**，`npx sage-kit` 不会从 registry 拉到它。使用方式：本仓库开发时用 `node dist/cli.js`；或 `npm pack` 得到 `sage-kit-0.2.0-alpha.1.tgz` 后 `npm install ./sage-kit-0.2.0-alpha.1.tgz`（或全局安装该 tarball）再用 `sage-kit`。

仓库原有 `sage-kit-0.2.0-alpha.1.tgz` 与当前源码不一致，不能作为本次修复证据；本次没有更新该 tarball。自动化中的临时打包/离线安装冒烟也不等于真实宿主激活验证。

主测试/CI 环境推荐 WSL/Linux（见 `docs/platform-support.md`）；本次工作树测试在 Windows Node 24.22.0 执行。P0 不是发布版本；若未来建立发布流程，发布前应用 `scripts/windows-smoke.ps1` 做一次人工安装/Skill 发现冒烟（当前 `NOT_EXECUTED`）。

需要一条命令跑通“构建 → 打包 → 隔离 DSH profile 安装 → 初始化 demo → 任务 create/brief/status/done”的自用闭环时，见 [`QUICKSTART.md`](QUICKSTART.md) 和可执行脚本 [`scripts/quickstart-dsh.sh`](scripts/quickstart-dsh.sh)（WSL2/Linux + 真实 DSH 0.2.1-rc.2 已验证；Windows/macOS 未验证）。

`init` 会写入 `.sage-kit/config.json`、宿主 Skill 目录、项目根的 `SESSION_BRIEF.md`，并默认写入受管的 `AGENTS.md` 块（Codex/Claude 分别用 `.agents/skills`/`AGENTS.md`、`.claude/skills`/`CLAUDE.md`）。说明块行为：`--scope project`（默认）默认写入，`--no-instructions` 跳过；`--scope global` 默认**跳过**，需 `--instructions` 才写。P0 不自动安装宿主 hooks；`hook` 命令可由宿主显式调用。

### 可选：DSH 原生插件

DSH 0.2.1-rc.2 用户可额外安装可选原生插件，获得原生任务工具与自动 brief（不替代 Skill/CLI，也没有控制面）：

```bash
npm run build && npm pack                             # sage-kit-0.2.0-alpha.1.tgz
(cd packages/dsh-plugin && npm pack)                  # packages/dsh-plugin/sage-kit-dsh-0.2.0-alpha.1.tgz
dsh plugin --profile <name> add -w ./sage-kit-0.2.0-alpha.1.tgz ./packages/dsh-plugin/sage-kit-dsh-0.2.0-alpha.1.tgz
dsh --profile <name> --dump-config
```

需要 pnpm >=10；安装时需要 DSH 0.2.1-rc.2。安装告警（宿主 peer 缺失、core 不是 profile 层）是预期行为。精确命令、配置、工具清单、自动 brief 行为、`engines.dsh` 版本约束与限制详见 [`packages/dsh-plugin/README.md`](packages/dsh-plugin/README.md)；打包/组合验证见 [`reports/plugin/packaging.md`](reports/plugin/packaging.md)，真实 headless E2E 已通过（[`reports/plugin/dsh-plugin-e2e.md`](reports/plugin/dsh-plugin-e2e.md)；Web GUI 未跑，标 `NOT_EXECUTED`）。

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
15. （可选）[`packages/dsh-plugin/README.md`](packages/dsh-plugin/README.md) — DSH 原生插件：安装、配置、工具、自动 brief、版本约束与限制。
    - 插件证据：[`reports/plugin/packaging.md`](reports/plugin/packaging.md)（打包/组合冒烟已通过）、[`reports/plugin/dsh-plugin-e2e.md`](reports/plugin/dsh-plugin-e2e.md)（真实 DSH 0.2.1-rc.2 headless E2E 已通过）与 [`reports/plugin/review.md`](reports/plugin/review.md)（独立评审：有条件可安装）；Web GUI 等边界未执行前标 `NOT_EXECUTED`。

> 宿主升级状态：[`docs/host-plugin-upgrade.md`](docs/host-plugin-upgrade.md) — DSH 插件 `off/brief/strict` + 只读 RSI 门禁、Codex/Claude 宿主包、quickstart 已实现；仍未验证的宿主激活矩阵标 `NOT_EXECUTED`，本文不是架构基线。

## 一句话边界

- **做**：本地单用户、单仓库、多任务并发、可恢复执行；P0 用文件模式实现任务/运行/事件/worktree；可选 DSH 原生插件（独立包）提供宿主原生工具与自动 brief，核心 CLI/Skill 仍是权威源。
- **做（目标）**：反馈驱动的受控改进、本地控制面、独立评估、人工批准发布。
- **不做**：多机、团队、多租户、实时协作、RBAC、远程共享 API、自动合并、无人值守递归自改。

## 当前阶段

- P0 本地文件模式已实现：`init`、`detect`、`doctor`、`task`、`worktree`、`run`、`brief`、`hook`、`uninstall`、`version`。
- M1 已实现：`feedback sync/list/show`；本地 JSONL、GitHub/Gitea 只读同步；fingerprint 去重、cursor 保留、不可信数据标记，brief 注入最新 1 条反馈。已通过真实 `api.github.com` 与 WSL2 自建 Gitea 1.27.3 验证；残余真实边界见 `docs/m1-feedback.md`。
- M2 已实现：`control serve/status/recover`；SQLite WAL、task/run/event/lease、单写者、loopback API（无 token）；`control serve` 提供本地控制面板（`/ui`：任务列表/详情、新建任务、状态转换、lease acquire/renew/release、恢复；单击任务直接出详情）。
- M3 已实现：`rsi create/list/run-once/request-approval/rollback-point/approve/reject`；真实 git worktree 候选评估、基线对比、重复评估、受保护资产/预算检查、导出、一次性人工 approval token、回滚点；无定时器、无自动批准/合并/发布（按 L2 设计）。
- 文件适配器：DSH（项目 `.dsh/skills/sage-kit` + `AGENTS.md`，固定版本源码已核对）、Codex（`.agents/skills` + `AGENTS.md`）、Claude Code（`.claude/skills` + `CLAUDE.md`）；全局作用域安装到宿主全局目录，说明块默认跳过。P0 不安装宿主原生 hook。
- 可选宿主包：`sage-kit host install|uninstall --host codex|claude` 把 marketplace + 薄插件 + 规范 Skill 副本暂存到 `.sage-kit/hosts/<host>/`；归属标记保证重复安装幂等、卸载只删自有文件。宿主注册仍由宿主 CLI 完成（`codex plugin marketplace add ...` / `/plugin marketplace add ...`）；真实 Codex CLI 0.164.0 已在隔离 `CODEX_HOME` 完成注册往返，真实会话 hook 激活与真实 Claude Code 安装仍为 `NOT_EXECUTED`。
- 可选 DSH 原生插件（0.2.0-alpha.1，未发布）：`sage-kit-dsh` 提供 `sage_task_create` / `sage_task_list` / `sage_task_show` / `sage_task_status` / `sage_brief` 原生工具，并在 DSH `agent/pre-step` 自动注入 brief；`mode` 支持 `off`/`brief`/`strict`，`strict` 只对 `rsiProposalId` 标记任务执行只读审批门禁；独立包、不进入核心安装依赖，版本由 `engines.dsh` 约束。已在真实 DSH 0.2.1-rc.2 headless 通过 E2E（profile 安装、5 工具、真实模型、brief 首次/更新/去重、无项目不注入；[`reports/plugin/dsh-plugin-e2e.md`](reports/plugin/dsh-plugin-e2e.md)）；独立评审为“有条件可安装”（[`reports/plugin/review.md`](reports/plugin/review.md)）；Web GUI 等边界 `NOT_EXECUTED`。
- 自动化测试：本次工作树执行 `npm run build` 与 `npm test`（2026-10-26，Windows Node 24.22.0）：**206 项 / 205 通过 / 0 失败 / 1 跳过**。跳过 Windows 非 detached 后代管道场景；escaped 后代有界返回测试通过。本次未重跑 WSL2、真实 DSH strict E2E 或真实 Codex/Claude 会话激活。原工作树写权限阻塞，副本结果不表示补丁已应用。
- 独立复核：现有 [`最终评审`](reports/reviews/gpt-6-astra-final-review.md) 为 **NO-GO**；本次没有新外部评审。针对性修复为 N02 增加完整性/跨页重复检查；恢复只让当前新恢复尝试校正启动状态，报告实际任务变化；安装区分 pending 与完成归属，不完整 Skill 重装明确失败，宿主卸载不再要求核心配置；R08/R10–R14 有对应回归。N04 的全历史 review 扫描容量限制仍未修复；spawn 到 PID 落盘之间的硬崩溃窗口、逃逸后代进程及真实宿主激活仍有文档边界，不能由单元测试推断全面关闭。
- A13 证据：真实 DSH 0.2.1-rc.2 + 真实 DeepSeek 模型已在 headless 与 Web GUI 中完成 `skill` → 真实 `bash` → `task create/list`；GUI 停止/重启后会话与任务恢复；卸载/重装循环通过；真实 `dsh web` 停止后进程/端口清理。DSH 本身不提供 hook 自动注入（`NOT_AVAILABLE`），手动 `sage-kit hook` 与 AGENTS 指令路径可用；按 A13“至少一个宿主通过”判定为 PASS。证据见 [`reports/p0/dsh-gui-e2e.md`](reports/p0/dsh-gui-e2e.md)、[`reports/p0/dsh-real-model-e2e.md`](reports/p0/dsh-real-model-e2e.md)。
- 设计上不实现：多用户/远程控制面、自动批准/合并/发布、无人值守定时 RSI、Bundle 导入/导出。M1 真实 API 的未覆盖边界（GitHub Link 分页/私有仓库/企业版/429、Gitea 公共实例/HTTPS）见 `docs/m1-feedback.md`；M2/M3 的模块级限制见各自专题文档。
- 文档中“目标设计（`TARGET`）”与“已实现（`P0`）”分开标注；实现偏差先改 ADR/文档，再改代码。

## 许可证

MIT。第三方代码/依赖的来源、许可证和版本在实现时单独记录；核心 P0 无运行时依赖。
