# P0 证据（本地文件模式）

日期：2026-10-24（本地）  
Node：v24.22.0 · npm：11.19.1 · 包版本：0.1.0  
状态：P0 文件模式实现；A13 已做真实 DSH headless + mock 的部分验证，真实模型/GUI 与 hook 自动注入未执行。

## 自动化测试

命令：

```text
npm run build
npm test
```

结果：`tests 10 / pass 10 / fail 0`（2026-10-24）。  
覆盖：A1、A2/A3、A2b（Codex/Claude 文件适配器）、A4、A5、A6、A7、A8/A9/A10、A11（模拟 stale run）、A12。

未覆盖 / 部分覆盖：

- A1：`npm pack` 后安装已手工验证（临时项目 `npm install <tgz>`，`npx sage-kit version` 输出 0.1.0）；CI 未覆盖打包安装。
- A4：未模拟缺 Node/缺 Skill；覆盖正常与损坏配置。
- A8：未覆盖 hook 超时。
- A11：用 stale run 记录模拟中断，未真实 SIGKILL 子进程。
- A12：未覆盖 bundle 导入/导出（P0 无 export 命令）。
- A13：真实模型/GUI 会话未执行；DSH headless + mock 已验证 Skill 发现/加载，未验证真实模型行为与 hook 自动注入。

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

`doctor` 返回 `ok: true`；`detect` 识别 dsh/codex/claude/fake（dsh 证据为 `C:\Users\KayAnn\.dsh`）。  
后续补充：已在隔离 `DSH_HOME` 中用真实 DSH 0.2.1-rc.2 headless + mock 验证 DSH 发现并加载该 Skill；DSH 没有可安装的原生 hook 配置，`session.start` 自动注入仍未验证。详见 [`dsh-real-host.md`](dsh-real-host.md)。

## Codex / Claude

自动化测试在临时目录执行 `init --host codex` 与 `init --host claude`，验证：

- Codex：`.agents/skills/sage-kit/SKILL.md` + `AGENTS.md`
- Claude：`.claude/skills/sage-kit/SKILL.md` + `CLAUDE.md`

未验证：在真实 Codex/Claude 会话中发现 Skill、生效说明块。属于 A13。

## 真实 DSH 宿主

已用本机真实 DSH 0.2.1-rc.2 在隔离 `DSH_HOME` 中跑通 headless：DSH 发现项目 `.dsh/skills/sage-kit/SKILL.md`，mock 模型触发 `skill` 工具后返回完整 SKILL 内容；项目 `AGENTS.md` 受管块也进入模型请求。详见 [`dsh-real-host.md`](dsh-real-host.md)。这是真实 DSH 装配证据，不是真实模型质量或 hook 自动注入证据。

## Linux / DSH Web

已在 WSL2 Ubuntu 26.04 中用公开 npm 包 `@deepseek-ai/dsh@0.2.1-rc.2` 安装真实 DSH，不依赖桌面应用：

- `dsh web --no-open --host 127.0.0.1 --port 18766` 正常启动并输出带 token 的 URL；
- 无 token 返回 401；带 token 经 303 cookie 后返回约 37.5KB 的 SPA；
- 同一 Linux DSH headless 成功调用 `skill` 工具并加载项目 `.dsh/skills/sage-kit`。

详见 [`dsh-linux-web.md`](dsh-linux-web.md)。这证明 Web 面可作为 Linux 部署基础，但不等于真实模型、浏览器交互或多租户验收。

## WSL 持久环境

主测试环境是 `/home/kayann/sage-kit-linux-dsh`（Linux 源码副本、当前包测试仓库、隔离 DSH_HOME、DSH npm 安装）。一键命令：

```bash
/home/kayann/sage-kit-linux-dsh/refresh-and-test.sh
```

该脚本同步当前源码、构建、跑 10/10 P0 测试、安装最新 tgz，并跑真实 DSH headless 的 `skill` 工具验证。Windows 不作为测试执行环境；Windows 兼容性见 `docs/platform-support.md`。

## WSL 独立环境（首次验证）

已在 Ubuntu 26.04 WSL2（Node v22.22.1、npm 9.2.0、git 2.53.0）中做独立安装与测试，结果记录见 [`wsl-test.md`](wsl-test.md)。摘要：打包安装、fake 项目、三种宿主文件适配、全局 DSH（隔离 `DSH_HOME`）、空格路径、完整 P0 套件 `10/10` 均通过；真实 DSH/Codex/Claude 会话仍未验证。

## 证据边界

- 这些结果只证明本地文件布局、CLI 状态机、hook 契约和 fake/host-file 适配路径。
- 不证明模型行为、真实宿主 hook 生命周期、并发控制面、SQLite/lease、反馈同步或 RSI。
- 上述未执行项在文档中保持 `NOT_EXECUTED`，不得写成已验收。
