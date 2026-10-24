# 独立评审：DSH 原生插件 `sage-kit-dsh@0.1.0`

- 评审人：`review-p0`（task-19，只读评审）
- 日期：2026-10-24（Pacific/Auckland；工作树未提交快照，HEAD = `4295044`）
- 对象：`packages/dsh-plugin/`（`sage-kit-dsh@0.1.0`）+ 根库 `src/index.ts` 导出 + 根 `package.json`/CI + `reports/plugin/` 证据
- 方法：静态阅读 + DSH 0.2.1-rc.2 typings/运行时契约核对 + 独立重跑打包冒烟（隔离副本、隔离 `DSH_HOME`）+ 逐项抽查 E2E 证据 + 本文件为本次评审唯一写入
- 边界：未修改任何源码/文档/配置/证据；未 commit；未在 Windows 上运行；未复跑真实模型 E2E（抽查其已落盘证据）

## 0. 结论（给 Lead 的一句话）

**有条件可安装（Linux/WSL2 + DSH 0.2.1-rc.2 + pnpm >= 10）：功能证据成立，不建议以“已验证可用”对外表述前先修完 §2 的 F-1/F-2/F-3；Windows/macOS、DSH Web profile、`autoBrief:false` 等仍为 `NOT_EXECUTED`。**

> 修复回执（Lead，2026-10-24）：F-1 已改为 `source: { kind: "sage-kit" }`（省略非法 form）；F-2 已改为 `engines.dsh: ">=0.2.1-rc.2 <0.3.0-0"`；F-3 文档已对齐，并补 `tests/plugin.test.mjs` 与 `lib.js`。修复后重跑 `scripts/plugin-smoke.sh` 为 `PLUGIN SMOKE PASSED`（新 hash 见 `reports/plugin/packaging.md` 末节）；核心 `npm test` 103/103。真实模型 E2E 未在修复后重跑，仍以原快照为行为证据。

## 1. 独立复核结果（我实际执行/抽查的）

| 检查 | 结果 |
| --- | --- |
| 打包冒烟独立重跑：把工作树 rsync 到隔离目录（排除 `node_modules`/`dist`/`work`/`.git`），用 Linux node v22.22.1 + npm 9.2.0 + 隔离 `DSH_HOME` 跑 `scripts/plugin-smoke.sh` | **PASS**；插件层 `# == sage-kit-dsh` 出现，config 为 `autoBrief:true`/`maxBriefBytes:2048`；tarball sha256 分别为 root `161e454e…`、plugin `0616a2d5…`（与本报告快照不同属正常：README/文档在上次打包后又有编辑；脚本每次打印当次 hash，见 `scripts/plugin-smoke.sh` 摘要） |
| 插件模块可被 DSH 懒加载/配置 schema 解析：`dsh --profile <smoke> --dump-config-schema`（DSH_HOME 隔离） | exit 0、stderr 空、147,906 B schema 且含 `projectRoot`/`autoBrief`/`maxBriefBytes`（说明 `index.js` 的 `Config` 导出与模块解析在真实 DSH 组合中可用；`--dump-config` 本身不执行插件代码，此点与 `reports/plugin/packaging.md:114` 一致） |
| 根包 tarball 内容 | 124 项；含 `dist/cli.js`、`dist/index.js`、`dist/index.d.ts`、`skills/sage-kit/SKILL.md`、`README.md`、`SECURITY.md`、`AGENTS.md`、`LICENSE`；不含 `tests/reports/work/src/packages/scripts/.github` |
| 插件 tarball 内容 | 4 项：`index.js`、`package.json`、`README.md`、`cordis.patch.yml`；**无 LICENSE**（见 F-8） |
| E2E 证据抽查（`reports/plugin/evidence/`） | 真实模型会话：provider `deepseek-official`/`deepseek-flash`（`real-model/session.v4.jsonl`），工具调用 `skill → sage_task_create → sage_task_list → sage_task_status → sage_task_show`，3 次 brief 注入指纹互异、无重复；任务落盘 `real-model/created-task.json`；`dsh-stderr.log` 0 B。非初始化项目：0 注入、无 `.sage-kit` 产生、3 次工具调用返回可读 `not initialized` 错误（`noninit-tools/checks.txt`、`session-evidence.json`）。隔离 `DSH_HOME`：请求 `tools=30` 含 5 个 sage 工具（`isolated-home/001.json`）。场景 A/B：`scenario-a/session-evidence.json` 3 注入、`scenario-b` 0 注入 |
| 秘密扫描 | `reports/plugin/` 无真实密钥；`grep -E 'sk-[A-Za-z0-9]{16,}'` 命中的只是任务 id（`task-20261024…`）前缀误匹配；真实模型 key 未出现在任何证据中（报告只出现隔离 0600 文件路径，`dsh-plugin-e2e.md:102`/`:161`） |
| CI 工作流 | `python yaml.safe_load` 解析通过；jobs = `linux`、`plugin-smoke`；无 release/publish/tag 步骤；`plugin-smoke` 用固定 `DSH_VERSION=0.2.1-rc.2`/`PNPM_VERSION=10.34.8`（`.github/workflows/ci.yml:111-144`） |
| 核心/插件分离 | `src/` 无 `@deepseek-ai/*` 依赖；根 `package.json` 无 `dependencies`（仅 devDeps，`package.json:30-39`）；根 `files` 不含 `packages/`（`package.json:22-29`）；插件只调用 `src/index.ts` 暴露的核心 API（`packages/dsh-plugin/index.js:8-14`、`:111-221`），无自己的数据库/状态文件，未触碰控制面 |
| DSH 契约核对 | `ContextFormed` 合法 form 无 `brief`（`node_modules/@deepseek-ai/dsh-llm/lib/types/message.d.ts:75-93`）；`engines.dsh` 校验使用 `semver.satisfies(..., { includePrerelease: true })`（`node_modules/@deepseek-ai/dsh-app-boot/lib/index.js:277`） |

## 2. Findings（按优先级）

严重度：High = 阻塞发布/会造成错误结论；Medium = 应在上线/定稿前修；Low = 建议修。

### F-1（Medium）`createUserMessage` 的 `source.form: "brief"` 不是 DSH 0.2.1-rc.2 的合法上下文形式
- 证据：`packages/dsh-plugin/index.js:250` 写入 `source: { kind: "sage-kit", form: "brief" }`；而 `@deepseek-ai/dsh-llm` 的 `ContextFormed` 只允许 `instructions`、`catalog`、`snapshot`、`notice`（必须带 `summary`）、`relay`、`recall` 或省略 `form`（`node_modules/@deepseek-ai/dsh-llm/lib/types/message.d.ts:75-93`）。
- 现状：运行时接受（session 事件里保存了 `{"kind":"sage-kit","form":"brief"}`，`reports/plugin/evidence/real-model/session.v4.jsonl`），但这是**未声明扩展点**：`form` 是带必填字段的 discriminated union，使用非法值等于绕过“producer 声明的 form 必须自带展示所需字段”的契约；一旦 DSH 升级后校验或按 form 渲染上下文，行为可能变化。
- 建议：省略 `form`（合法默认），或改用合法形式并补齐字段（若作为“注入说明”可用 `form:"instructions"`；若只是提示则用 `form:"notice"` + 一行 `summary`）。改后重跑 E2E 刷新 session 证据。

### F-2（Medium）`engines.dsh` 上界 `<0.3.0` 在 DSH 的校验语义下会接受 0.3.0 预发布版本
- 证据：`packages/dsh-plugin/package.json:13-15` 为 `">=0.2.1-rc.2 <0.3.0"`；DSH 的引擎校验用 `semver.satisfies(runtimeVersion, range, { includePrerelease: true })`（`node_modules/@deepseek-ai/dsh-app-boot/lib/index.js:277`）。实测该选项下 `0.3.0-rc.1` 满足此 range（`0.3.0` 不满足）。
- 影响：插件声明只面向 0.2.x，但 DSH 0.3.0-rc.* 会放行安装/启动；breaking 变更可能表现为运行时加载失败，而不是插件管理器拒绝。
- 建议：改为 `">=0.2.1-rc.2 <0.3.0-0"`（或 `<=0.2.9` 风格），并在 README 的版本约束行同步（`packages/dsh-plugin/README.md:16`）。

### F-3（Medium）文档仍把已落盘的 E2E 写成 `NOT_EXECUTED`，且“fake-context 已验证”缺少可提交证据
- 证据：`README.md:9`、`:43`、`:67`、`:82` 仍写“真实 DSH 会话 … 仍待 E2E 证据（通过前标 `NOT_EXECUTED`）”；`packages/dsh-plugin/README.md:3`、`:27`、`:135-137` 同样未更新（真实 DSH 会话已由 `reports/plugin/dsh-plugin-e2e.md` 覆盖）。同时 `README.md:9`/`:82` 与 `packages/dsh-plugin/README.md:133` 声称“fake-context 静态验证已通过”，但 `reports/plugin/` 下没有对应报告，README 自己写明“正式报告待补入”——按 `AGENTS.md`，没有可复现证据不应写“已验证”。
- 影响：提交后文档与证据自相矛盾（E2E 已过却标未执行；fake-ctx 声称通过却无产物），评审/用户会被误导。
- 建议（属 task-18/Lead 定稿）：E2E 行改为引用 `reports/plugin/dsh-plugin-e2e.md`；fake-ctx 要么把 harness（可提交的 fake ctx 测试/脚本）与输出落到 `reports/plugin/fake-ctx.md`（或 `tests/plugin.test.mjs`），要么降级为“未执行/仅 Lead 本地验证，无仓库证据”。

### F-4（Medium）E2E 复现命令依赖 gitignored 的 `work/plugin-e2e/` 脚本，提交后的证据不可复现
- 证据：`reports/plugin/dsh-plugin-e2e.md:159`（`bash "$REPO/work/plugin-e2e/prep/run-scenarios.sh"`）、`:164`（`assemble-evidence.sh`）、`:184`（“原始脚本与未压缩日志在 gitignored 的 work/plugin-e2e/”）；`work/` 被根 `.gitignore` 忽略，提交树中不存在这些脚本。
- 影响：证据从“可重放”降为“可阅读”；维护者无法按报告重跑 mock 场景与证据汇总。
- 建议：把 mock model double、场景 runner、证据汇总脚本收进 `reports/plugin/scripts/`（或 `tests/plugin-e2e/`）；报告引用提交内路径，原始日志继续放 `work/`。

### F-5（Low-Medium）`reports/plugin/packaging.md` 与最终版 `scripts/plugin-smoke.sh` 不一致
- 证据：`packaging.md:23` 写“按 Lead 验证过的顺序**分两次安装**”，`:45-49` 的输出片段也是两步（“installing root tarball…”/“installing plugin tarball…”）；但最终脚本 `scripts/plugin-smoke.sh:268-275` 是**一次 `dsh plugin add` 传入两个 tarball**（我本次重跑输出为“installing both tarballs into fresh DSH profile”）。另外 `packaging.md:6` 的 tarball hash 与当前工作树已不一致（报告已注明需提交后重跑，可接受）。
- 影响：报告与交付脚本行为不符，外部复现时对不上输出。
- 建议：按最终脚本措辞改写（或保留“两种顺序均验证”的说明，但明确脚本只用一次 add），并在提交前重跑刷新 hash。

### F-6（Low）两份报告对插件 tarball 清单的描述不一致（快照时差）
- 证据：`reports/plugin/dsh-plugin-e2e.md:36` 写插件 tgz 3 个文件（`index.js`、`cordis.patch.yml`、`package.json`），该值来自 16:26 的打包快照；当前 `packages/dsh-plugin/package.json:7-11` 的 `files` 已含 `README.md`，我独立打包得到 4 个文件（含 `README.md`）；`packaging.md:81` 也写含 README。
- 影响：只影响文档准确性（同一提交里两份报告口径不一）。
- 建议：在 e2e 报告该处加“快照早于 README 加入；最终包为 4 文件”的注记，或重跑打包刷新。

### F-7（Low）插件 README 安装第 1 步会真的启动 Web/headless app，而不是只创建 profile
- 证据：`packages/dsh-plugin/README.md:35-37` 用 `dsh --profile sage-kit --from-default-profile web`（注释写“创建专用 profile”）；DSH README 对该命令的定义是 “Replace a custom profile with a fresh copy of a shipped template, **then boot it**”（`node_modules/@deepseek-ai/dsh/README.md:12`）。E2E 用了正确的最小形式 `dsh --profile … --from-default-profile headless --dump-config`（`reports/plugin/dsh-plugin-e2e.md:48`、`:155`）。
- 影响：照抄安装步骤的用户会在安装插件前被 Web 服务器阻塞（需 Ctrl-C），或误以为命令只是建 profile；无 Web 需求时该步也不必要（`dsh plugin add` 会自动初始化 base-backed profile）。
- 建议：把该步改为可选说明，并给出 `--dump-config` 只物化不启动的命令（与 E2E 一致）；明确“无 Web/headless 需求可跳过第 1 步”。

### F-8（Low）插件 package 缺 LICENSE，且缺少 npm 发布元数据
- 证据：`packages/dsh-plugin/package.json:7-11` 的 `files` 无 LICENSE，包目录下也没有 LICENSE 文件；我独立打包的 tgz 无 LICENSE（根包 tarball 因为有仓库根 `LICENSE` 而被 npm 自动包含）。`package.json` 无 `repository`/`homepage`。
- 影响：发布到 npm/分发 tarball 时 MIT 声明只有 `license` 字段，无许可证文本；来源信息缺失（本地 tgz 安装不受影响）。
- 建议：在 `packages/dsh-plugin/` 增加 `LICENSE`（复制根 MIT）并加进 `files`；补 `repository`/`homepage`（发布前）。

### F-9（Low）插件逻辑没有仓库内自动化测试
- 证据：`tests/` 只有 `api/cli/control/feedback/rsi` 五个测试文件（`package.json:33` 的 `npm test` 列表）；插件去重、`clampBriefBytes`、`discoverRoot`、fail-open 等逻辑目前只由未提交的 fake-ctx harness 与 `work/` 下的 E2E 脚本覆盖。
- 影响：回归风险；`npm test` 不能防插件逻辑退化。
- 建议：提交一个 `tests/plugin.test.mjs`（用最小 fake ctx：`ctx.tools.register`/`ctx.on`/`ctx.get("workingDirectory")`），覆盖：已初始化项目注入 1 次+同内容去重、任务变化后指纹变化、非初始化项目不注入且不建目录、`autoBrief:false` 不注册、`maxBriefBytes` clamp（256/8192）、buildBrief 抛错时 fail-open。

### F-10（Low）`peerDependencies: "*"` 造成每次安装的 missing-peer 噪声；可评估 optional 标记
- 证据：`packages/dsh-plugin/package.json:16-22`；`reports/plugin/evidence/profile/peers-check.log` 展示 4 个 `@deepseek-ai/*` missing peer。运行时由 DSH 宿主解析、不阻塞（E2E `isolated-home` 已证），README 也已解释为预期（`packages/dsh-plugin/README.md:23`、`:58-64`）。
- 建议：给 4 个宿主包加 `peerDependenciesMeta.{...,"optional": true}`（`sage-kit` 仍为必选 peer），以消除误导性告警；同时保留 README 说明。非阻塞。

### F-11（Low）`sage_task_status` 的 `note` 未限制长度，会原样写入事件文件
- 证据：`packages/dsh-plugin/index.js:188`（note 参数无长度上限）、`:195`（直接传 core）；`src/core/tasks.ts:172-177` 把 `options.note` 直接放进 `task.status_changed` 事件（对比 evidence 走 `cleanText(...,1000)`，`tasks.ts:158-162`）。
- 影响：模型/用户可写超长 note 到 `.sage-kit/state/events/*.jsonl`（本地磁盘增长；无注入执行）。同类问题 CLI 也存在，非插件特有。
- 建议：core 对 note 做 `cleanText(..., 500/1000)`，或插件侧截断。

### F-12（Low）相对路径 `projectRoot` 以 `process.cwd()` 解析，与文档“Absolute”不一致
- 证据：`packages/dsh-plugin/index.js:53-59`（相对值 `resolve(process.cwd(), value)`），而 `Config.projectRoot` 描述为 “Absolute SAGE-Kit project root”（`:20-22`）。
- 影响：DSH 服务进程的 cwd 与 session 工作目录不同时，相对配置会指向意外目录；绝对路径（文档推荐）不受影响。
- 建议：拒绝相对值并给出可读错误，或改为按 `directoryFor(ctx, agent)` 解析。

### F-13（Low）按 session+fingerprint 去重：上下文压缩后同一 brief 不会重新注入
- 证据：`packages/dsh-plugin/index.js:226-241` 用 `WeakMap<session, fingerprint>`；若长会话发生 compaction 丢掉早先注入的 brief，而任务内容未变，则 fingerprint 相同 → 不再注入（brief 从上下文中永久消失，直到任务变化/新会话）。
- 影响：长会话（触发 compaction）的边界行为；E2E 6 步未覆盖。
- 建议：在 README 限制中写明，或在 pre-step 检测“当前消息上下文不含 `<sage-kit-brief>`”时允许重注入（需谨慎避免重复）。

### F-14（Info）安装包内 README 的相对链接失效；根包 README 链接 `packages/` 同理
- 证据：`packages/dsh-plugin/README.md:27`、`:134` 链接 `../../reports/plugin/packaging.md`；根 `README.md` 链接 `packages/dsh-plugin/README.md`，而根包 tarball 不含 `packages/`。仅影响已安装包的阅读体验。

### F-15（Info）Lead 口述的 stop / uninstall / “0.0.0 拒绝”在 `reports/plugin/` 无对应证据
- 现状：Lead 消息称插件相关的 stop、uninstall、0.0.0 版本拒绝已验证；但我检查 `reports/plugin/` 仅有 `dsh-plugin-e2e.md`、`packaging.md` 与 `evidence/` 六个目录，未发现 stop/uninstall/engine-reject 的原始产物（`reports/p0/gui-e2e/15-host-uninstall-cycle.txt` 是宿主/P0 的卸载证据，不是插件卸载）。E2E 报告的 `NOT_EXECUTED` 清单（`dsh-plugin-e2e.md:116-125`）也未提这些项。
- 建议：若要在提交信息/文档中引用这三项，补最小证据文件（命令+输出）到 `reports/plugin/evidence/`；否则按“Lead 本机口述、仓库无证据”处理，不写入已验证声明。

## 3. 安全评审要点（未发现阻塞问题）

- **工具输入**：`defineTool` 声明 schema（`index.js:111-220`）；核心再做约束：id 正则 `[a-z0-9][a-z0-9-]{0,63}`（`src/core/fs-utils.ts:118-126`）、title ≤200/description ≤2000/acceptance ≤500×20（`src/core/tasks.ts:66-82`）。任务 id 经 `readTask` 校验后再拼路径，未发现路径穿越写入（`tasks.ts:107-119`、`:148-178`）。
- **状态写入面**：工具只通过核心 API 写 `.sage-kit/`；非初始化项目调用工具返回可读错误且不创建 `.sage-kit`（`noninit-tools/checks.txt`: `sage_kit_dir_created=no`）。插件无自身数据库、无控制面、无自动合并/发布。
- **注入面**：`agent/pre-step` 注入内容来自本地 task 状态（title/status/acceptance/evidence），以 `<sage-kit-brief>` 包裹，只读本地文件；失败 catch 后 warn + 返回原 decision，不阻断 turn（`index.js:256-265`）。未发现网络调用、shell 调用。
- **凭据**：真实模型 key 未进入证据/报告（仅隔离 0600 文件路径）；建议在 `packaging.md` 报告中也注明“key 不落盘到报告”。
- **残余风险**：F-11 无上限 note、F-12 相对 projectRoot、F-13 compaction 边界；均低。

## 4. 证据强度表（防止过度声明）

| 能力 | 证据 | 评级 |
| --- | --- | --- |
| 两个 tarball 安装进 fresh profile、bundle 自动追加、`--dump-config` 含插件层 | `packaging.md` + 我的独立重跑 PASS | 强 |
| 真实 DSH headless 加载插件（无 load error，tools=30 含 5 工具） | `dsh-plugin-e2e.md:14`、`evidence/isolated-home/001.json` | 强（Linux/WSL2、DSH 0.2.1-rc.2） |
| 5 个工具可被调用（mock 全调用 + 真实模型调用其中 4 个 + skill） | `dsh-plugin-e2e.md:15`、`scenario-a/session-evidence.json`、`real-model/session-evidence.json` | 强 |
| 自动 brief 首次一次 / 变化更新 / 未变化不重复 | `scenario-a`、`real-model`（3 注入、指纹互异）；`dsh-plugin-e2e.md:16-18` | 强 |
| 非初始化项目不注入、无 `.sage-kit` 污染、工具可读报错、turn 不崩 | `noninit-tools/*` | 强 |
| 真实模型端到端（deepseek-official/deepseek-flash） | `real-model/*`（session request/header、created-task.json） | 中-强（1 次任务，无稳定性统计） |
| 隔离 `DSH_HOME`（DSH 安装目录之外） | `isolated-home/001.json`（tools=30） | 强（0.2.1-rc.2） |
| `autoBrief:false` / 显式 `projectRoot` / `maxBriefBytes` 截断 / 损坏 config 降级 | 无 | **NOT_EXECUTED** |
| Web profile（`dsh web`）内插件行为 | 无（仅 headless） | **NOT_EXECUTED** |
| 多 session 并发去重 | 无 | **NOT_EXECUTED** |
| Windows/macOS 宿主 | 无 | **NOT_EXECUTED** |
| CI `plugin-smoke` job 在 GitHub Hosted Runner 实跑 | 仅 YAML+WSL 等价执行 | **NOT_EXECUTED** |
| 插件版本不兼容拒绝（0.0.0 等） | 仓库内无产物（见 F-15） | **无证据** |
| 插件 uninstall / stop | 仓库内无插件层产物（见 F-15） | **无证据** |

## 5. 建议优先级（Top 5）

1. **修 F-1 + F-2（代码/清单，分钟级）**：`source.form` 改合法值；`engines.dsh` 上界改 `<0.3.0-0`；重跑打包冒烟 + 一条 E2E 刷新证据与 hash。
2. **文档定稿（task-18）**：更新根 README + 插件 README 的 E2E 状态；处理 fake-ctx 证据（提交 harness 报告或降级表述）；对齐测试计数（`README.md:3` 的 93/93 vs `packaging.md:79` 的 99/99 以最终 `npm test` 输出为准）。
3. **证据可复现（task-16）**：把 `work/plugin-e2e/prep/*.sh`、mock model double 收进 `reports/plugin/scripts/`，报告引用提交内路径（F-4）。
4. **补最小自动化回归**：提交 `tests/plugin.test.mjs`（fake ctx，覆盖去重/clamp/非初始化/fail-open），并纳入 `npm test`（F-9）；顺带修 `packaging.md` 与脚本不一致（F-5）、e2e tarball 清单注记（F-6）。
5. **发布前清理**：插件包 LICENSE/repository（F-8）、README 安装步骤 `--dump-config` 形式（F-7）、peer optional 标记（F-10）、README 安装链接（F-14）；CI 的 `plugin-smoke` job 在真实 runner 上跑一次或明确记录 `NOT_EXECUTED`。

## 6. 结论复核（供 Lead 定稿话术）

- 可以说：**在 Linux/WSL2 + DSH 0.2.1-rc.2（headless）+ pnpm ≥ 10 下，插件安装、加载、5 个原生工具、`agent/pre-step` brief 注入（首次/更新/去重）与非初始化项目不污染，已有仓库内可查看的安装/工具/注入/真实模型证据；核心 CLI/Skill 仍是唯一权威状态源。**
- 不可以说（截至本评审）：Windows/macOS 可用、Web profile 已验证、`autoBrief:false`/`projectRoot`/截断/损坏配置降级已验证、多 session 并发安全、CI 已在 GitHub runner 实跑、插件 uninstall/stop/版本拒绝已验证、或“fake-context 已验证”目前无提交证据。
- 上述 §2 F-1/F-2 修掉、§5 第 1–2 项完成前，建议保持插件 README 的“未发布/未验证”口径，不对外称“已验证可用”。
