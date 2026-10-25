# Changelog

## Unreleased

### 主要能力

- 可选 Codex/Claude 宿主包：`sage-kit host install|uninstall --host codex|claude` 把 marketplace + 薄插件 + 规范 Skill 副本暂存到 `.sage-kit/hosts/<host>/`；归属标记保证重复安装与安全卸载，根 npm 包带 `packages/host-*` 模板。
- DSH 插件新增 `off`/`brief`/`strict` 模式与只读 RSI 门禁；`sage_task_create` 支持 `rsiProposalId` 标记。
- 新增 `Task.rsiProposalId`、`checkRsiGate()` 与 `task create --rsi`；门禁要求 approved + evaluation passed + approval approved 三重证据。
- 新增 `QUICKSTART.md` / `scripts/quickstart-dsh.sh` 自用闭环。

### 修复与加固（2026-10-25 全量复核后）

- F01：控制面写请求校验 Origin、Sec-Fetch-Site 与 JSON Content-Type；非本地/跨站请求返回 403/415。
- F02：RSI candidate 路径检查拒绝 symlink、大小写变体与受保护路径；gate 校验记录与文件名身份一致、approval 与 evaluation 绑定。
- F03：安装/卸载只清理自己创建的文件，保留用户已有 skill、brief、状态目录和宿主包中的用户文件。
- F04：运行记录按 generation 排序；空命令、spawn 失败、终态持久化失败、review → interrupted 与同启动时刻/旧 PID 记录均收口。
- F06：Git 项目根解析区分普通仓库、linked worktree、submodule 与 separate-git-dir；strict init 在无法可靠解析时 fail closed；宿主包安装检查 symlink 逃逸，卸载不递归删除未归属内容。
- F07：GitHub review-comment 分页、最近页水位与同时间戳扫描有界，`since` 不丢页；失败保留旧 cursor。
- F08：RSI 单候选锁串行化 acquire；release 单次、无锁外 rename；旧 mutex 只在确认 owner 不可达时接管，stale/ownerless/损坏 mutex 明确失败。
- 第二轮复审 R01：run 记录先于 task running 持久化；崩溃后由本任务的 stale run 恢复，不把更早的成功 run 误归给中断尝试。
- 第二轮复审 R02：宿主包拒绝覆盖目标路径上不在上一 marker 中的已有文件（除非 force），避免用户文件被新模板吞并。
- 第二轮复审 R03：核心卸载按 config.skill.files 逐文件删除并剪空目录，保留用户自行加入 skill 目录的文件。
- 第二轮复审 R04：宿主包检查 `.sage-kit` / `.sage-kit/hosts` 祖先 symlink，先于任何写入/删除失败关闭。
- 第二轮复审 R05：GitHub review-comment 使用双扫描（since + 全量）按 externalId 合并，页面移动不会永久漏条目。
- 第三轮复审 N01：run 在 spawn 前先校验状态并持久化 startup intent；`imported` 任务在命令执行前拒绝。
- N02：issue 扫描记录完整性和跨页重复；未完成/位移时要求完整且无重复的全量对账，否则失败并保留旧 cursor。
- N03/S16：新恢复尝试覆盖所有允许启动状态；已有终态 run 不撤销显式 ready 重置；doctor 报告实际任务变化/错误；setup 失败有界确认子进程退出。spawn 后 PID 落盘前硬崩溃仍有未识别子进程窗口。
- R06/R07：受保护评估资产遇到 symlink 直接拒绝；candidate 删除只允许文件，不允许递归删除目录。
- R09/R10：quickstart 显式 `--project-root`，要求 realpath 并 canonicalize `.dsh` 保护根。
- 插件 strict 模式对任何标记任务先校验提案存在，不再对未初始化项目/空任务静默放行；task 列表严格模式在损坏记录上 fail closed。
- 文档修正 supervisor/cordis 引导文案、QUICKSTART 中的实际命令与 `SAGE_KIT_BIN` 解析。

### 验证

- 本次工作树：Windows Node 24.22.0 `npm test` 206 项，205 通过、0 失败、1 跳过；本次未重跑 WSL2。
- 现有 `reports/reviews/gpt-6-astra-final-review.md` 仍为 NO-GO；本次没有新外部评审。本次修复覆盖 N02/N05/N06/S16-01–03、N03 恢复残留及 R08/R10–R14 的小范围修改。N04 全历史 review 扫描容量、Windows 完整进程树终止及真实宿主激活仍有限制；原有 tarball 不能证明当前修复。
- 已知边界：F02 的 Windows symlink/junction 检测是尽力而为；死/无 owner 的 `.mutex` 需确认无评估进程后人工清理；F09–F15 按本地单用户威胁模型降级；DSH 插件只在 DSH 0.2.1-rc.2 Linux/WSL2 headless 路径验证，Web GUI、Windows/macOS 未验证；真实 Codex 会话 hook 激活与 Claude Code 安装仍为 `NOT_EXECUTED`。

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
