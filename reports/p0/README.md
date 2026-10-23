# P0 证据（本地文件模式）

日期：2026-10-24（本地）
运行环境：主测试环境 WSL2 Ubuntu 26.04.1 LTS（Node v22.22.1、npm 9.2.0、git 2.53.0）；开发机 Windows（Node v24.22.0、npm 11.19.1，未作为测试套件执行环境）
包版本：0.1.0
状态：P0 文件模式实现；A13 已做真实 DSH headless + **mock 模型**和 Linux Web 启动的部分验证，真实模型、浏览器 GUI 与 hook 自动注入未执行。

## 自动化测试

命令（在 WSL 持久环境 `/home/kayann/sage-kit-linux-dsh/src` 同步源码后）：

```text
npm run build
npm test
```

结果：`tests 19 / pass 19 / fail 0`（2026-10-24，WSL2 Ubuntu 26.04、Node v22.22.1）。测试数量/覆盖矩阵以 `docs/p0-acceptance.md` 为准；本文件记录运行结果。

覆盖（19 项，与 `docs/p0-acceptance.md` 同步）：

- A1 help/version；A1b `npm pack` 产物在隔离空 npm cache 下用 `npm install --offline --ignore-scripts` 安装到临时项目，运行已安装 CLI 的 `version`/`doctor --json`/`init`，断言无运行时依赖、tarball 不含 `tests/`、`reports/`、`work/`、`src/`、`node_modules/`、`scripts/`。
- A2/A3 init 幂等/uninstall 不破坏用户文件；A2b Codex/Claude 文件适配器；A2c 重复 `init` 时记录实际安装的 skill mode（copy/symlink）。
- A4 doctor 正常/损坏配置；A4b 缺 Skill 报错；A4c global scope 下 `HOME` 解析（fake/codex/claude）；A4d Node `>=22` 单一策略。
- A5 生命周期/证据/任务文件；A7 brief 字节预算；A7b 非 ASCII 截断（无 U+FFFD、字节不超限）。
- A8/A9/A10 hook 契约（session.start/command.after/stop）、非法 JSON、未知事件、`command.after` 脱敏、`stop --strict`；A8b `hook --timeout` 对停滞 stdin 强制生效（退出 124 + 合法 `warn` JSON，fail-open 且不写事件）；A8c 非法 `--timeout` 用法错误。
- A6 worktree 创建/删除/脏拒绝；A11 模拟 stale run 恢复；A11b 真实 SIGKILL 启动 `run` 的 CLI 后 `doctor` 恢复为 `interrupted`；A12 路径穿越、参数不经 shell。

未覆盖 / 部分：

- 缺 Node <22 的真实二进制分支：A4d 覆盖 `checkNode` 的版本策略单元断言，但未在 <22 的实际 Node 上运行 CLI 入口退出（需要旧版 Node 二进制）。
- 真实宿主 hook 生命周期/自动注入：`NOT_EXECUTED`（DSH 0.2.1-rc.2 未发现可安装的原生第三方 hook 配置）。
- bundle 导入/导出：P0 没有该命令，属 M2（见 `docs/p0-acceptance.md` 范围）。
- Windows 测试套件：按约定不在 Windows 执行（见 `docs/platform-support.md`）；Windows 冒烟脚本本次 `NOT_EXECUTED`。
- 真实模型、浏览器 GUI：`NOT_EXECUTED`（见下）。

## DSH 适配器 smoke

在临时项目 `work/dsh-smoke`（非 git 仓库，初始化不要求 git）执行：

```text
node dist/cli.js init --host dsh --scope project
node dist/cli.js doctor --json
node dist/cli.js detect --json
node dist/cli.js uninstall
```

实际生成：

- `.dsh/skills/sage-kit/SKILL.md`
- `.sage-kit/config.json`（host=dsh, scope=project）
- 受管 `AGENTS.md` 块
- `SESSION_BRIEF.md`

`doctor` 返回 `ok: true`；`detect` 识别 dsh/codex/claude/fake（dsh 证据为 `C:\Users\KayAnn\.dsh`）。这是 **Windows 开发机上的文件布局 smoke**，不是宿主会话验收。原始产物在 `work/dsh-smoke/`（被 `.gitignore` 忽略），见“证据与仓库策略”。

## Codex / Claude

自动化测试在临时目录执行 `init --host codex` 与 `init --host claude`，验证：

- Codex：`.agents/skills/sage-kit/SKILL.md` + `AGENTS.md`
- Claude：`.claude/skills/sage-kit/SKILL.md` + `CLAUDE.md`

未验证：在真实 Codex/Claude 会话中发现 Skill、生效说明块。属于 A13，`NOT_EXECUTED`。

## 真实 DSH 宿主（mock 模型，Windows 隔离环境）

已用本机真实 DSH 0.2.1-rc.2 在隔离 `DSH_HOME` 中跑通 headless：DSH 发现项目 `.dsh/skills/sage-kit/SKILL.md`，**mock 模型**触发 `skill` 工具后返回完整 SKILL 内容；项目 `AGENTS.md` 受管块也进入模型请求。详见 [`dsh-real-host.md`](dsh-real-host.md)。

这是真实 DSH 装配证据，不是真实模型质量证据；`session.start` 自动注入未验证。原始证据在 `work/dsh-isolated/`（ignored）。

## DSH 模型驱动 E2E（mock 模型，Linux/WSL）

在 Linux/WSL 持久环境中用真实 `@deepseek-ai/dsh@0.2.1-rc.2` headless + 本地确定性 **mock Messages 端点**（不是真实模型）跑通：

- DSH 发现并加载项目 `.dsh/skills/sage-kit`（`skill` 工具返回完整 SKILL 内容）；
- mock 模型按状态机触发 `bash` 工具，执行 SAGE-Kit CLI `task create` + `task list`，任务真实落盘；
- 独立（不经模型）校验：任务 JSON、`task list --json`/`show`/`brief`、`events.jsonl`，`verify-e2e.mjs` 24/24 检查通过；
- 同一 Linux DSH 的 Web 面复检：无 token 401、带 token 303→200、SPA 约 37,512 字节，服务停止后无残留监听。

详见 [`dsh-e2e-model.md`](dsh-e2e-model.md)。结论边界：证明 **DSH 宿主 wiring + 真实 CLI 落盘**，不证明真实模型会正确选择/使用工具，也不证明 GUI 或 hook 生命周期。

## Linux / DSH Web

已在 WSL2 Ubuntu 26.04 中用公开 npm 包 `@deepseek-ai/dsh@0.2.1-rc.2` 安装真实 DSH，不依赖桌面应用：

- `dsh web --no-open --host 127.0.0.1 --port 18766` 正常启动并输出带 token 的 URL；
- 无 token 返回 401；带 token 经 303 cookie 后返回约 37.5KB 的 SPA；
- 同一 Linux DSH headless 成功调用 `skill` 工具并加载项目 `.dsh/skills/sage-kit`。

详见 [`dsh-linux-web.md`](dsh-linux-web.md)。这证明 Web 面可作为 Linux 部署基础，但不等于真实模型、浏览器交互或多租户验收。

## WSL 持久环境

主测试环境是 `/home/kayann/sage-kit-linux-dsh`（Linux 源码副本、当前包测试仓库、隔离 `DSH_HOME`、DSH npm 安装；机器特定路径）。一键命令：

```bash
/home/kayann/sage-kit-linux-dsh/refresh-and-test.sh
```

该脚本同步当前源码、构建、跑当前 P0 测试套件（当前 19 项，结果见上）、安装最新 tgz，并跑真实 DSH headless 的 `skill` 工具验证。Windows 不作为测试执行环境；Windows 兼容性见 `docs/platform-support.md`。

## WSL 独立环境（首次验证）

已在 Ubuntu 26.04 WSL2（Node v22.22.1、npm 9.2.0、git 2.53.0）中做独立安装与测试，结果记录见 [`wsl-test.md`](wsl-test.md)。摘要：打包安装、fake 项目、三种宿主文件适配、全局 DSH（隔离 `DSH_HOME`）、空格路径均通过；**该报告记录的是早期 10 项测试版本**，当前套件已扩展到 19 项并以本报告结果为准。真实 DSH/Codex/Claude 会话仍未验证。

## 证据与仓库策略

- 原始证据大多在 `work/` 下（`work/dsh-smoke/`、`work/dsh-isolated/`、`work/dsh-linux/`、`work/pack-smoke/` 等）。`.gitignore` 忽略 `work/`，因此这些文件**不随仓库提交**，clean clone 找不到它们；报告中的 `work/...` 引用只用于说明本机复现位置。
- 需要长期保留的关键结果已转写进本报告和 `dsh-e2e-model.md`（命令、哈希、事件节选、校验项）；`work/dsh-linux/` 下有 mock 脚本与 `run-02/` 原始产物，可在那台 WSL 环境复现。
- `reports/p0/requests/` 也在 `.gitignore` 中（若生成请求体，不提交）。
- 历史测试记录（`wsl-test.md`、`dsh-linux-web.md`）中的 `10/10` 是当时版本；当前套件 19 项，统一以本报告与 `docs/p0-acceptance.md` 为准。
- 本次变更只新增/更新报告文件；未 commit/push/tag/发布，报告与证据不含任何密钥或 Web token。

## 证据边界

- 这些结果只证明本地文件布局、CLI 状态机、hook 契约、fake/host-file 适配路径、真实 DSH 的装配与 mock 模型驱动链路。
- 不证明真实模型行为/质量、真实宿主 hook 生命周期、并发控制面、SQLite/lease、反馈同步或 RSI。
- 上述未执行项在文档中保持 `NOT_EXECUTED`，不得写成已验收。
