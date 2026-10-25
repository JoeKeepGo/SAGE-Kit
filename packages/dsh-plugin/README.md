# sage-kit-dsh（可选 DSH 原生插件）

**状态：实现已落地（0.2.0-alpha.1，未发布到 npm registry）；真实 DSH 0.2.1-rc.2 headless E2E 已通过（[`reports/plugin/dsh-plugin-e2e.md`](../../reports/plugin/dsh-plugin-e2e.md)：profile 安装、5 个原生工具、真实模型调用、`agent/pre-step` brief 首次/更新/去重、无 `.sage-kit` 不注入、隔离 `DSH_HOME`）。独立评审结论为**有条件可安装**（Linux/WSL2 + DSH 0.2.1-rc.2 + pnpm >=10；见 [`reports/plugin/review.md`](../../reports/plugin/review.md)）；F-1/F-2 已修复，F-3 文档已对齐。Web GUI、Windows/macOS、配置分支与故障降级等边界仍未执行（见 §8），不要据此对外称全平台“已验证可用”。**

这是 SAGE-Kit 的 **DSH 宿主适配包**，不是核心产品面，也不是 CLI/Skill 的替代品：

- 核心仍然是 `sage-kit` CLI 与 `skills/sage-kit/SKILL.md`；任务是**唯一权威状态源**（文件模式 `.sage-kit/`），由核心库 `src/index.ts` 读写。
- 本插件只做两类事：在 DSH 中注册原生任务工具；在 DSH `agent/pre-step` 注入当前任务 brief。
- 插件**没有自己的数据库/状态文件**，不启动任何服务，不使用控制面（M2）、不做评估/发布（M3），**不自动合并、不自动发布、不重写 SKILL.md**。
- 插件是 DSH 专有的可选适配器；不改变 SAGE-Kit 对 Codex/Claude/OpenCode 的适配方式，也不进入核心安装依赖（D-023）。

## 1. 要求

| 项 | 要求 |
|---|---|
| DSH | `>=0.2.1-rc.2 <0.3.0-0`（`package.json` 的 `engines.dsh`，由 DSH 插件管理器校验） |
| pnpm | **>=10**（DSH profile 用 `pnpm-workspace.yaml` 配置 `nodeLinker: hoisted`、`autoInstallPeers: false`；pnpm 9 会报错或错误地尝试安装宿主 peer） |
| Node.js | >=22（核心 `sage-kit` 的要求；DSH 运行时自身版本另行满足） |
| SAGE-Kit 核心 | `sage-kit@^0.2.0-alpha.1`（peer dependency，需安装到同一个 DSH profile） |
| 项目状态 | 项目中已执行 `sage-kit init --host dsh --scope project`（存在 `.sage-kit/config.json`） |
| 平台 | 证据目标为 Linux/WSL2；Windows/macOS 上的 DSH 插件运行未验证（`NOT_EXECUTED`） |

插件 `peerDependencies` 中的 DSH 运行时包（`@deepseek-ai/cordis`、`@deepseek-ai/dsh-llm`、`@deepseek-ai/dsh-tools`、`@deepseek-ai/schemastery`）由 DSH 安装/运行时提供，插件不随包携带这些依赖；DSH profile 明确 `autoInstallPeers: false`，因此安装时 pnpm 报 missing peer 是**预期**行为（见 §2 安装告警）。

## 2. 安装与启用

插件经 DSH 的 profile/插件机制安装，**不通过** `sage-kit init` 安装。以下安装流程已在 WSL2 以 DSH 0.2.1-rc.2 实测通过：打包冒烟（[`reports/plugin/packaging.md`](../../reports/plugin/packaging.md)，`PLUGIN SMOKE PASSED`）与真实 headless E2E（[`reports/plugin/dsh-plugin-e2e.md`](../../reports/plugin/dsh-plugin-e2e.md)，profile 安装 + 5 工具 + 自动 brief 均 PASS）。

```bash
# 0) 在 SAGE-Kit 仓库构建并打包两个包
npm run build
npm pack                                  # 产出 sage-kit-0.2.0-alpha.1.tgz
(cd packages/dsh-plugin && npm pack)      # 产出 packages/dsh-plugin/sage-kit-dsh-0.2.0-alpha.1.tgz

# 1) 准备 profile：从模板物化专用 profile（E2E 用 headless 模板验证；不要动 Desktop 保留 profile）
dsh --profile sage-kit --from-default-profile headless --dump-config >/dev/null
# 或 web 模板：--from-default-profile web（该路径的插件加载尚未执行，见 §8）

# 2) 先安装核心包，再安装插件包（同一 profile；-w 显式表示 workspace root）
dsh plugin --profile sage-kit add -w ./sage-kit-0.2.0-alpha.1.tgz ./packages/dsh-plugin/sage-kit-dsh-0.2.0-alpha.1.tgz

# 3) 检查 profile 组合结果：输出应包含 "# == sage-kit-dsh" 与 id/name: sage-kit-dsh，
#    且退出码为 0
dsh --profile sage-kit --dump-config

# 4) 启动（headless 已验证：dsh --profile sage-kit --json "<prompt>"；web 启动未验证）
dsh --profile sage-kit --json "<prompt>"
```

要点：

- `dsh plugin --profile <name> <pnpm 参数>` 会把参数转发给 profile 目录中的 pnpm；DSH 负责 profile 初始化、依赖安装与 profile 写锁。E2E 验证了两种顺序：一次 `add` 两个 tarball，或先根包后插件；也验证了 pnpm 12 下不加 `-w` 成功。pnpm 9 会失败（见下面安装告警）。
- 必须先装 `sage-kit` 再装插件：插件 `import * as sage from "sage-kit"`，peer dependency 需要从同一 profile 的 `node_modules` 解析。
- 安装成功后 profile `package.json` 的 `dependencies` 同时含 `sage-kit` 与 `sage-kit-dsh`，`dsh.profile.bundles` 含 `sage-kit-dsh`；`--dump-config` 只组合配置、不启动 app，适合安装后静态检查。
- 安装/启动时 DSH 会校验 `engines.dsh`；运行中的 DSH 版本不在范围内会被拒绝（可用 DSH 的精确版本豁免命令 `version-exemptions` / `allow-version` 显式放行，风险自担，见 §7）。
- 卸载：`dsh plugin --profile sage-kit remove sage-kit-dsh`（核心包按需保留/移除）。

### 安装告警（预期，不是失败）

- `WARN Issues with peer dependencies found ... missing peer @deepseek-ai/cordis / dsh-llm / dsh-tools / schemastery`：DSH profile 设置 `autoInstallPeers: false`，这些 peer 由 DSH 宿主运行时提供，属预期；不要为了消除告警把它们安装进 profile（E2E 已验证缺失这些 peer 不影响加载，见 [`reports/plugin/dsh-plugin-e2e.md`](../../reports/plugin/dsh-plugin-e2e.md) §隔离 DSH_HOME）。
- `dsh: warning: sage-kit declares no dsh.bundle — installed as a plain dependency, not a profile layer`：`sage-kit` 是插件的库依赖，不是 profile 层；只有 `sage-kit-dsh` 带 `dsh.bundle.patch`，属正确行为。
- pnpm 9 不是受支持环境：DSH profile 的 `pnpm-workspace.yaml` 设置会被 pnpm 9 忽略，导致对未发布内部包发起请求（如 `ERR_PNPM_FETCH_404 ... @deepseek-ai/dsh-type-meta`）或 `ERR_PNPM_ADDING_TO_ROOT`；请使用 pnpm >=10（打包冒烟用 10.34.8，E2E 用 12.15.0）。
- **WSL 注意**：默认 `pnpm` 可能是 Windows 二进制（scoop 等），`dsh plugin add` 会以 `current dir is an absolute path with drive letter` 之类错误失败；请安装 Linux pnpm 并前置到 PATH（E2E 报告复现命令中有示例）。
- pnpm 12 可能提示 `Agent skills awaiting approval: sage-kit@file:...`（根包携带 `skills/` 目录触发），仅提示、不影响安装/加载。

## 3. 配置

插件在 DSH profile 中通过 bundle patch 启用，默认值来自 [`cordis.patch.yml`](cordis.patch.yml)：

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `projectRoot` | string（可选） | 自动发现 | SAGE-Kit 项目根绝对路径。设置时会校验 `<root>/.sage-kit/config.json` 存在；相对路径会被拒绝（报可读错误），不做隐式 cwd 解析。不设置时从 DSH 会话工作目录向上找最近的已初始化项目。 |
| `autoBrief` | boolean | `true` | 是否在 `agent/pre-step` 自动注入 brief。 |
| `maxBriefBytes` | number | `2048` | 自动注入 brief 的字节上限，自动收敛到 256–8192。 |

在 profile 的 `cordis.patch.yml`（或 home/profile 层）覆盖该条目即可改配置，示例：

```yaml
- id: sage-kit-dsh
  config:
    autoBrief: true
    maxBriefBytes: 4096
    projectRoot: /absolute/path/to/project
```

覆盖语法以 DSH 0.2.1-rc.2 的 patch 语义为准（本仓库尚未单独验证该覆盖示例）；如果 `projectRoot` 指向未初始化项目，插件会报错而不是静默使用错误目录。

## 4. 工具

插件向 DSH 注册 5 个工具，参数由 DSH 的 `defineTool` 在调用前校验；工具直接调用 `sage-kit` 核心库（不 shell out CLI），读写与 CLI 相同的文件模式状态。任务类工具返回格式化 JSON `{ "ok": true, "task" | "tasks": ... }`；`sage_brief` 返回核心 `BriefResult`（`{ "text", "taskId"?, "truncated" }`）。

| 工具 | 参数 | 行为 |
|---|---|---|
| `sage_task_create` | `title`（必填）、`description`（可选）、`acceptance`（string[]，可选） | 在 `.sage-kit/state/tasks/` 创建任务；失败返回工具错误。 |
| `sage_task_list` | `status`（可选，枚举 `TASK_STATUSES`） | 列出任务；可按状态过滤。 |
| `sage_task_show` | `id`（必填） | 读取单个任务 JSON。 |
| `sage_task_status` | `id`、`status`（必填）、`evidence`（string[]，可选）、`note`（可选） | 走核心状态机转换；`done` 需要至少一条 `evidence`（由核心校验），记录 `source: "dsh-plugin"`。 |
| `sage_brief` | `taskId`（可选）、`maxBytes`（可选，256–8192，默认 2048） | 返回核心 `buildBrief()` 的 brief（与 `sage-kit brief` 同源）。 |

没有任务或项目未初始化时，工具会返回明确错误信息（提示先运行 `sage-kit init --host dsh --scope project`），不会自动创建状态。

## 5. 自动 brief 行为

- **触发**：DSH `agent/pre-step` 事件（waterfall）。插件先调用 `next()` 取得决策；`reject` 决策不注入。
- **项目发现**：优先 `projectRoot` 配置；否则从 DSH 会话工作目录（无会话工作目录时用进程 cwd）向上找最近包含 `.sage-kit/config.json` 的目录。
- **未初始化**：找不到 `.sage-kit/config.json` 时**不注入**，不影响普通项目里的 DSH 使用。
- **内容**：调用核心 `buildBrief()`，与 `sage-kit brief`/宿主 hook 的 `session.start` 使用同一 brief 生成器（含当前任务、验收、证据、可选最新反馈标记）；受 `maxBriefBytes` 限制。
- **注入形式**：一条 user 消息，内容为 `<sage-kit-brief>\n...\n</sage-kit-brief>`，消息 `source` 为 `{ kind: "sage-kit" }`（省略 `form`，即 DSH 文档化的“未声明上下文”默认态；此前非法 `form:"brief"` 的 F-1 已修复）；插入到最后一个“已被消费”的消息之后（尽量贴近当前步）。
- **去重**：按 session 缓存 brief 文本的 sha256；同一 session 内容不变不重复注入；任务/证据变化导致 brief 变化时重新注入。
- **失败降级（fail-open）**：构建或注入抛异常时只记录 `logger.warn`，返回原决策，不阻断 turn；不写失败事件/状态。
- **边界**：不联网、不调用模型；brief 中可能包含任务 worktree 绝对路径，但核心 brief 不含 token/密钥；反馈内容按不可信数据展示。

## 6. 状态、安全与不做什么

- **单一权威源**：任务/运行/事件仍是 `.sage-kit/` 文件状态；插件通过核心库 API 读写，不复制、不双写，不启动控制面，也不连接 M2 SQLite。
- **只操作文件模式**：控制面模式（M2）下不要同时用本插件改任务；两者不双写是核心约束（D-005）。
- **无权限扩大**：插件不读取 token/密钥，不做网络请求，不执行 shell，不写 `.sage-kit/` 之外的文件（除 DSH profile 自身安装行为），不自动合并/发布/重写 Skill。
- **不替代 Skill/CLI**：插件让 DSH 有原生工具和自动 brief，但任务验收、证据规则、停止条件仍由 Skill/CLI 文档与核心状态机约束。

## 7. 版本与发布

- 插件版本 `0.2.0-alpha.1`，独立于核心；peer 依赖 `sage-kit@^0.2.0-alpha.1` 与 `engines.dsh: >=0.2.1-rc.2 <0.3.0-0`。
- MIT License；**未发布**到 npm registry / 未创建 release。安装使用仓库内 `npm pack` 的 tarball。
- 安装/管理 profile 需要 pnpm >=10（DSH profile 的 `pnpm-workspace.yaml` 设置需要 pnpm 10；pnpm 9 会报错或错误安装 peer）。
- DSH 版本升级超出 `engines.dsh` 范围时，安装/启动会被 DSH 插件管理器拒绝，需要更新插件版本或使用 DSH 的显式精确版本豁免（`dsh plugin ... version-exemptions` / `allow-version`；属 DSH 机制，风险自担）。
- **上界**：DSH 0.2.1-rc.2 的引擎校验使用 `semver.satisfies(..., { includePrerelease: true })`；因此上界用 `<0.3.0-0` 排除 `0.3.0-rc.*` 预发布版本（review F-2 已修复）。

## 8. 验证状态（诚实边界）

| 项 | 状态 |
|---|---|
| 插件实现（工具/自动 brief/配置/版本约束） | 已存在（`index.js`、`cordis.patch.yml`、`package.json`） |
| 根包 `npm run build` / 测试 | 见仓库 `npm test` 与 `reports/`；核心 `npm test` 已含 `tests/plugin.test.mjs` 的 lib/manifest 回归测试 |
| 打包安装：两个 tarball 经 `dsh plugin --profile <name> add ...` 装入全新 profile；profile dependencies/bundles 正确；`dsh --dump-config` 退出 0 且含 `# == sage-kit-dsh` | 已通过（[`reports/plugin/packaging.md`](../../reports/plugin/packaging.md)，`PLUGIN SMOKE PASSED`；WSL2、DSH 0.2.1-rc.2、pnpm 10.34.8） |
| 真实 DSH 0.2.1-rc.2 headless 加载插件（无 load error，tools=30 含 5 个 sage 工具） | 已通过（[`reports/plugin/dsh-plugin-e2e.md`](../../reports/plugin/dsh-plugin-e2e.md)） |
| 原生工具在真实 DSH 会话中可调用 | 已通过：确定性 mock 调满 5 个；真实模型（`deepseek-flash`）6 步调用 `skill` + 4 个任务工具（同报告） |
| `agent/pre-step` 自动 brief：首次一次、任务变化后更新、不变更不重复、无 `.sage-kit` 不注入、隔离 `DSH_HOME` 可加载 | 已通过（同报告；3 个 brief 指纹、6 步 3 次注入、非初始化目录 0 注入） |
| 真实模型端到端（非 mock） | 已通过（`deepseek-official`/`deepseek-flash`，1 次任务；不做模型质量统计） |
| 真实小项目会话（隔离仓库 + 种子 bug + 测试 + 证据） | 已通过（[`reports/plugin/sandbox-tiny-notes.md`](../../reports/plugin/sandbox-tiny-notes.md)：4/4 测试、任务 ready→running→review→done、4 次 brief；发现未发布包的 `npx` E404 摩擦） |
| `--dump-config` 真正加载插件代码/执行插件逻辑 | 不能由 `--dump-config` 证明；插件加载与工具执行由上述 headless E2E 覆盖 |
| Lead 本地 fake-ctx 验证（加载/工具/注入去重） | 无仓库内可提交报告，**不作为验收依据**；评审 F-3 建议补 `reports/plugin/fake-ctx.md` 或降级表述 |
| DSH Web（GUI）中的插件加载/工具/brief 注入 | `NOT_EXECUTED`（E2E 仅 headless；loader 与 pre-step 路径相同，但未跑 GUI） |
| 配置分支：`autoBrief:false`、显式 `projectRoot`、`maxBriefBytes` 截断/clamp | `NOT_EXECUTED`（E2E 报告 §已知边界 2；评审 F-3/F-15 亦未提供） |
| 故障降级：损坏 `config.json`、brief 构建抛错时的 `logger.warn` 路径 | `NOT_EXECUTED`（E2E 报告 §已知边界 3） |
| 工具边界：无 evidence 标记 done、非法 id、schema 边界 | 部分（仅验证 status enum 一例）；其余 `NOT_EXECUTED` |
| 多会话并发去重 | `NOT_EXECUTED`（仅单 session 验证） |
| 插件逻辑的仓库内自动化测试（lib/clamp/discoverRoot/manifest） | 已新增 `tests/plugin.test.mjs`（11 项，含 standard/separate-git-dir/submodule linked worktree 与过期注册表）；工具/注入行为仍由 fake-ctx 与 E2E 覆盖，未做完整 fake-ctx 单测（评审 F-9 部分） |
| 注入消息 `source.form` 的 DSH 契约合法性 | 已修复（F-1）：省略 `form`，只保留 `source.kind`，符合 DSH 的未声明上下文默认态 |
| 长会话 compaction 后 brief 重注入 | 未覆盖；当前按 session+内容指纹去重，compaction 丢上下文后同样内容可能不再注入（评审 F-13） |
| 插件 README 相对链接（`../../docs`、`../../reports`） | 仅在仓库内有效；npm tarball 内这些链接失效（评审 F-14，Info） |
| CI `plugin-smoke` job 在 GitHub Hosted Runner 上运行 | `NOT_EXECUTED`（无 runner；脚本已在 WSL2 全流程通过） |
| Windows/macOS DSH 插件运行 | `NOT_EXECUTED` |
| 插件 stop / uninstall / 版本不兼容拒绝 | 仓库内无证据（评审 F-15；不写入已验证声明） |
| 独立评审 | [`reports/plugin/review.md`](../../reports/plugin/review.md)：**有条件可安装**；F-1（非法 form）/F-2（版本上界）已修复，F-3（文档状态）已对齐；平台与配置分支仍未全量验证 |

说明：E2E 报告中的插件 tarball 快照早于 README/lib 补入；当前插件包含 `index.js`、`lib.js`、`cordis.patch.yml`、`README.md`、`LICENSE`。**最终 tarball 内容与 SHA-256 以提交后重跑 [`scripts/plugin-smoke.sh`](../../scripts/plugin-smoke.sh) 的结果为准**；未执行项不写成已验证。

## 9. 文件结构

```text
packages/dsh-plugin/
  index.js            # DSH 插件：工具注册 + agent/pre-step 自动 brief
  lib.js              # 与 DSH 无关的纯 helper（clamp/discoverRoot/projectRoot）
  cordis.patch.yml    # DSH bundle patch（默认 autoBrief/maxBriefBytes）
  package.json        # 包元数据：engines.dsh、peerDependencies、dsh.bundle
  README.md           # 本文件
  LICENSE             # MIT（随包分发）
```

相关文档：[根 README](../../README.md)、[Hook 与宿主适配](../../docs/hooks-and-host-adapters.md)、[架构](../../docs/architecture.md)、[决策 D-023](../../docs/decisions.md)、[状态与持久化](../../docs/state-and-durability.md)。
