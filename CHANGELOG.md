# Changelog

## 0.2.0-alpha.1 — 2026-10-25

内部 alpha 版本，用于本地单用户试用与反馈，不是公开稳定版。

### 主要能力

- P0 文件模式：`init`、`detect`、`doctor`、`task`、`worktree`、`run`、`brief`、`hook`、`uninstall`、`version`。
- M1：GitHub/Gitea 只读反馈同步；Issue/PR 评论分页与 `since` 增量水位。
- M2：本地 SQLite 控制面、任务/运行/事件/lease、loopback HTTP API 与本地可写面板。
- M3：受控 RSI 提案、真实 git worktree 评估、基线/重复/预算、人工批准与回滚点；无定时器、无自动批准/合并/发布。
- 可选 DSH 原生插件 `sage-kit-dsh`：5 个原生任务工具与 `agent/pre-step` 自动 brief；独立包，不进入核心依赖。

### 修复与加固

- F03：安装/卸载只清理自己创建的文件，保留用户已有 skill、brief 和状态目录。
- F04：运行记录按不可变 `generation` 排序；空命令、spawn 失败、终态持久化失败和 `review → interrupted` 恢复均收口；旧 PID/同毫秒记录不再覆盖新运行。
- F06：Git 项目根解析增加 registry 身份校验；linked worktree、submodule、`--separate-git-dir` 和旧 registry 不再被静默误判；无法可靠解析时 fail closed。
- F07：GitHub review-comment 分页有界，`since` 水位不会因 `maxPages` 丢页或重复扫已见页。
- F08：RSI 单候选锁在正常/异常路径收口；读取失败不再误接管活锁，release 不再饥饿，重叠/重复 release 共享一次释放操作，stale/ownerless/损坏 mutex 明确失败。
- F01/F02：本地控制面变更请求增加 Origin/Content-Type 校验；RSI candidate 路径检查默认拒绝 symlink、大小写变体与保护路径。

### 验证

- 自动化：`npm test` **131/131**（Windows Node 24.22.0 与 WSL2 Ubuntu Node 22.22.1）。
- `npm run build` 通过；CI 含 clean-pack、tarball 内容检查和离线安装 smoke。
- 第 10、11 轮 GPT-6-Astra 复核：**GO**，范围为“纯本地单用户 + 已授权降级”；无剩余 P0/P1。
- 已知边界：F02 的 Windows symlink/junction 检测是尽力而为；死/无 owner 的 `.mutex` 需确认无评估进程后人工清理；F09–F15 按本地单用户威胁模型降级；DSH 插件只在 DSH 0.2.1-rc.2 Linux/WSL2 headless 路径验证，Web GUI、Windows/macOS 未验证。

### 未发布

- 未发布到 npm registry。
- 本版本作为 GitHub Pre-release 提供；不是 stable 版本。
