# WSL 独立环境 P0 验证

日期：2026-10-24  
环境：Ubuntu 26.04.1 LTS（WSL2，cgroup v2，systemd）；Node v22.22.1；npm 9.2.0；git 2.53.0；无 Docker；未使用 sudo。

> 历史说明：本报告记录的是 2026-10-24 早期 **10 项测试**版本。P0 套件此后扩展到 **19 项**（A1b 打包安装、A2c、A4b/A4c/A4d、A7b、A8b/A8c、A11b 等）；最新通过结果与覆盖列表见 [`README.md`](README.md) 和 `docs/p0-acceptance.md`。本文中的 `10/10` 均指当时版本，不代表当前计数。

## 现行持久环境

主测试环境已固定为：`/home/kayann/sage-kit-linux-dsh`

- `/home/kayann/sage-kit-linux-dsh/src`：当前源码 Linux 副本
- `/home/kayann/sage-kit-linux-dsh/project`：安装当前包的测试仓库
- `/home/kayann/sage-kit-linux-dsh/home`：隔离 DSH_HOME
- `/home/kayann/sage-kit-linux-dsh/refresh-and-test.sh`：一键同步、构建、测试、刷新项目并跑 DSH headless

## 隔离方式（首次验证）

- 测试根目录：`/home/kayann/sage-kit-wsl-test-1792763904`
- 独立 `HOME`、`TMPDIR`、`npm_config_cache`、`DSH_HOME`
- 使用 `npm pack` 产物安装到临时项目，不依赖 Windows 工作区
- 测试结束后保留成功根目录供复核；失败/污染目录已删除

## 测试隔离修复

首次在 WSL 源码副本运行完整测试时出现 7 个失败。原因是 WSL 的 `/tmp/.git` 已存在，测试把仓库建在 `/tmp` 下，`findProjectRoot()` 向上找到了 `/tmp/.git`，多个测试共享了同一个项目根。

修复：测试临时目录改用 `~/.cache/sage-kit-tests`（或 `SAGE_KIT_TEST_TMPDIR`），不再依赖 `/tmp` 是否干净。修复后完整套件重新通过 10/10（当时版本）。

## 结果

1. **打包安装**：`npm install /mnt/d/Projects/SAGE-Kit/work/sage-kit-0.1.0.tgz` 成功；`sage-kit version` 输出 `0.1.0`。
2. **fake 项目**：`init --host fake --scope project`、`doctor --json`、任务生命周期（`running → review → done` + 证据）、`brief`、`session.start`、worktree 创建/强删、`uninstall` 均通过。
3. **文件适配器**：`init --host dsh`、`init --host codex`、`init --host claude` 分别生成：
   - `.dsh/skills/sage-kit/SKILL.md`
   - `.agents/skills/sage-kit/SKILL.md`
   - `.claude/skills/sage-kit/SKILL.md`
4. **完整 P0 套件**：在 WSL 内重新安装依赖、构建并运行 `npm test`，结果 `tests 10 / pass 10 / fail 0`（当时版本；当前套件 19 项，最新结果见 [`README.md`](README.md)）。
5. **全局 DSH + 空格路径**：在独立 `DSH_HOME` 下执行 `init --host dsh --scope global`，Skill 安装到 `$DSH_HOME/skills/sage-kit`；工程路径含空格时任务/卸载正常；删除 Skill 后 `doctor` 正确返回 `ok:false` 并指出 `skill` 检查失败。
6. **Windows 挂载路径**：通过 `/mnt/d/...` 读取包并安装，未依赖 `/mnt/c` 用户目录。

## 发现的环境问题

WSL 继承了 Windows 的 `DSH_HOME=/mnt/c/Users/KayAnn/.dsh`。第一次全局测试因此把 Skill 写入了真实 DSH 目录，而不是临时目录。已清理该测试产物；后续测试显式设置 `DSH_HOME` 到测试根目录。这不是代码缺陷，但说明**任何全局安装测试都必须隔离 DSH_HOME**。

## 未验证

- 当时未用 npm 安装 DSH；后续已用 `@deepseek-ai/dsh@0.2.1-rc.2` 在 WSL 内安装并验证 Web/headless，见 [`dsh-linux-web.md`](dsh-linux-web.md)；mock 模型驱动的 Skill → bash → CLI 任务链路见 [`dsh-e2e-model.md`](dsh-e2e-model.md)。
- 真实 Codex / Claude Code 会话中的 Skill 发现与 hook 注入（P0-A13）
- 真实模型行为、浏览器 GUI 交互、hook 自动注入（`NOT_EXECUTED`）
- 控制面、SQLite、lease、反馈同步、RSI（`NOT_IMPLEMENTED`）

## 结论

P0 文件模式在 Linux/WSL 下可安装、可构建、可运行，路径/空格/全局作用域的基本行为正确；不能据此声称真实宿主集成已验收。后续已在隔离 DSH_HOME 中用真实 DSH 0.2.1-rc.2 headless + mock 模型验证 Skill 发现/加载（见 `dsh-real-host.md`、`dsh-e2e-model.md`）；仍缺真实模型/GUI 和 hook 自动注入验收。当前套件为 19 项，见 [`README.md`](README.md)。
