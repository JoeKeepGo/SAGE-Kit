# DSH plugin E2E（真实 DSH 0.2.1-rc.2：profile 安装、原生工具、`agent/pre-step` brief 注入）

日期：2026-10-24（Pacific/Auckland；主要操作 UTC 03:26–03:37）
执行：teammate `dsh-e2e`（task-16）
对象：`packages/dsh-plugin`（包名 `sage-kit-dsh`）+ 根库 `sage-kit` 导出（工作树中未提交的 Lead 变更）
宿主：WSL2 内真实 DSH npm `0.2.1-rc.2`，隔离 `DSH_HOME`，不触碰 Windows/用户 `.dsh`

> 后续修复说明：本报告运行于 F-1 修复前的快照，注入消息 source 当时为 `{kind:"sage-kit",form:"brief"}`。F-1 已改为省略 `form`（`{kind:"sage-kit"}`）；工具与注入行为不变，最终打包/安装证据见 `reports/plugin/packaging.md` 的“最终修复后刷新”节，插件代码回归见 `tests/plugin.test.mjs`。

## 结论

| 验证项 | 结果 | 关键证据 |
| --- | --- | --- |
| `dsh plugin --profile ... add` 安装根库 + 插件（本地 tgz） | **PASS** | 两个 profile 均安装成功；插件被自动选为 bundle 层 |
| profile 层可见（`--dump-config`） | **PASS** | `# == sage-kit-dsh` + row `id/name: sage-kit-dsh` + config `autoBrief: true, maxBriefBytes: 2048` |
| 插件在真实 DSH headless 中加载（无 load error） | **PASS** | 启动退出 0、stderr 0 字节；请求 tools=30（含 5 个 sage 工具） |
| 原生工具 `sage_task_create/list/show/status`、`sage_brief` 可调用 | **PASS** | 确定性 mock 调满 5 个；真实模型调用其中 4 个 + `skill`；任务文件独立校验 |
| `agent/pre-step` 自动注入 brief（首次一次） | **PASS** | session 事件 `user/message`（当次快照 source `{kind:"sage-kit",form:"brief"}`；后续已改为省略 form），step 1 注入 1 次 |
| task 变化后注入更新 | **PASS** | 新建任务后注入新 brief；任务 running 后再次注入；3 个 brief 指纹互不相同 |
| 不变更时不重复注入 | **PASS** | 6 步仅 3 次注入（步骤 3/5/6 无新增；无重复 fingerprint） |
| 无 `.sage-kit` 项目 ⇒ 不注入 | **PASS** | 非初始化目录：注入 0 次、无 `.sage-kit` 目录产生、tools 仍注册 |
| 无项目时调用工具 | **PASS（可读错误）** | 3 次 `error`：`SAGE-Kit is not initialized for this project...`；turn 正常完成，不崩溃 |
| 真实模型端到端（非 mock） | **PASS** | `deepseek-official`/`deepseek-flash`，6 步，创建 `task-20261024033521-f06e62` 并置为 `running` |
| 隔离 `DSH_HOME`（在 DSH 安装目录祖先之外） | **PASS** | `/tmp/dsh-iso-home-…` 下 profile 仍加载、5 工具注册、无 stderr；peer 缺失不是加载阻塞 |
| `pnpm peers check` 报缺失 `@deepseek-ai/*` peer | **预期噪声（非阻塞）** | pnpm 层确实缺；DSH 0.2.1-rc.2 运行时由宿主解析（见 §7） |

一句话：**插件以真实 DSH bundle 形式安装进 fresh profile，真实 headless 会话中 5 个原生工具可被（mock 与真实模型）调用，`agent/pre-step` 自动 brief 注入按“首次一次 → 任务变化即更新 → 未变化不重复”工作，且在非 SAGE-Kit 项目不注入、不产生状态污染。** 唯一环境坑是 WSL 默认 `pnpm` 是 Windows scoop 二进制（panic: drive letter），需先装 Linux pnpm。

## 环境

- WSL2 Ubuntu 26.04.1（kernel `6.18.33.2-microsoft-standard-WSL2`），Node `v22.22.1`，npm `9.2.0`。
- 真实 DSH：`/home/kayann/sage-kit-linux-dsh/node_modules/.bin/dsh` → `0.2.1-rc.2`；隔离 `DSH_HOME=/home/kayann/sage-kit-linux-dsh/plugin-e2e/home`。
- Linux pnpm：WSL PATH 默认 `pnpm` 为 `/mnt/c/Users/.../scoop/apps/nodejs-lts/current/bin/pnpm`（Windows 二进制，`dsh plugin` 转发时 pnpm panic `current dir is an absolute path with drive letter`）。安装 Linux pnpm `12.15.0` 到隔离目录并前置 PATH：
  `npm install pnpm@12.15.0 --prefix /home/kayann/sage-kit-linux-dsh/plugin-e2e/tools`
- SAGE-Kit 构建：工作树 rsync 到 `/home/kayann/sage-kit-linux-dsh/plugin-e2e/build`，`npm install` + `npm run build`；`sage-kit version` → `0.1.0`。
- 打包产物（`<根>/pkg`；E2E 主证据用“earlier snapshot”，README 落地后已重新打包并在 fresh profile 复验“refreshed snapshot”）：
  - earlier snapshot（2026-10-24T03:26Z，E2E 主体运行使用）：`sage-kit-0.1.0.tgz` sha256 `312fe82ca00807cc918dd467485ba5cc76198edd7833b6c1501db50a482008a1`（199,580 B）；`sage-kit-dsh-0.1.0.tgz` sha256 `9a99b8e2d02bd3eda2f88461dde11a270da533a48e5530b74a66df53b4004fc0`（3,389 B，3 文件：`index.js`、`cordis.patch.yml`、`package.json`；此时 `README.md` 尚未落地）
  - refreshed snapshot（2026-10-24T03:44Z，当前工作树含 `packages/dsh-plugin/README.md` 14,048 B；root tarball 因 `docs/` 变更略增）：`sage-kit-0.1.0.tgz` sha256 `281be36c2f7971bebb10accdd5c694e6a6b717bc2551f2564d290a22bd90fb2b`（203,017 B）；`sage-kit-dsh-0.1.0.tgz` sha256 `651e8de0da9fdb288ea75e418d18a96487a32646b7c6d2d68b38b1436ec8e3a0`（9,593 B，4 文件：`index.js`、`package.json`、`README.md`、`cordis.patch.yml`）。在全新 profile `sage-kit-plugin-refreshed` 上重装并复跑确定性场景：5 个工具全成功、任务落盘、stderr 0 B（见 `evidence/profile/refresh-verify-*.txt`）。`reports/plugin/packaging.md` 的 8,065 B 是其 smoke 在 README 版本/打包时刻不同的另一快照，三者不矛盾，以各自 sha256 为准。
- 模型：确定性 mock（Anthropic Messages 风格本地 double，非模型）；真实模型为 DSH `deepseek-official` provider 的 `deepseek-flash`（session `request/header` 可见）。

## Profile 安装与 bundle 层

安装流程（两种顺序均验证）：

```bash
export DSH_HOME=/home/kayann/sage-kit-linux-dsh/plugin-e2e/home
export PATH=/home/kayann/sage-kit-linux-dsh/plugin-e2e/tools/node_modules/.bin:/home/kayann/sage-kit-linux-dsh/node_modules/.bin:$PATH

# 1) 从 headless 模板物化自定义 profile（base+headless bundles）
dsh --profile sage-kit-plugin --from-default-profile headless --dump-config >/dev/null

# 2) 安装（一次加两个 / 先根后插件均可）
dsh plugin --profile sage-kit-plugin add pkg/sage-kit-0.1.0.tgz pkg/sage-kit-dsh-0.1.0.tgz
# 或
dsh plugin --profile sage-kit-plugin add pkg/sage-kit-0.1.0.tgz
dsh plugin --profile sage-kit-plugin add pkg/sage-kit-dsh-0.1.0.tgz
```

观察：
- 根包 `sage-kit` 被识别为普通依赖（日志 `dsh: warning: sage-kit declares no dsh.bundle — installed as a plain dependency, not a profile layer`），不改变 bundles；
- 插件 `sage-kit-dsh` 声明 `dsh.bundle.patch`，pnpm 安装成功后被**自动追加**到 profile 的 `dsh.profile.bundles`：
  `["@deepseek-ai/dsh-base","@deepseek-ai/dsh-headless","sage-kit-dsh"]`；
- `--dump-config` 组合结果出现 `# == sage-kit-dsh` 层与 row（config 默认值正确）：

```yaml
# == sage-kit-dsh
- id: sage-kit-dsh
  name: sage-kit-dsh
  config:
    autoBrief: true
    maxBriefBytes: 2048
```

- `pnpm peers check` 报缺 `@deepseek-ai/cordis|dsh-llm|dsh-tools|schemastery`（见 §7，运行时由 DSH 解析，不阻塞）。
- pnpm 12 还提示 `Agent skills awaiting approval: sage-kit@file:...`（根包携带 `skills/` 目录触发 pnpm 的 agent-skill 检测，仅提示、不影响安装/加载）。

## 确定性 E2E（mock model double）

mock 只在本地模拟 Messages 流：按“已经用过的工具”推进 `create → list → status(running) → show → sage_brief`，不是模型、不测试模型质量（`work/plugin-e2e/prep/mock-plugin-model.mjs`）。

**场景 A：已初始化项目 + 预置一个 ready 任务**（`project-b`）
- `dsh --profile sage-kit-plugin --json "<prompt>"`，`DEEPSEEK_BASE_URL` 指向 mock，exit 0、stderr 0 B；
- 事件流：6 步、turn completed；5 个 tool_call 全部成功：`sage_task_create`、`sage_task_list`、`sage_task_status`、`sage_task_show`、`sage_brief`；
- 任务落盘并独立校验：新建任务 `task-20261024033340-61f5e0` → `running`；`task list` 可见 2 个任务；
- 注入（session `user/message`，source `{kind:"sage-kit",form:"brief"}`）：
  1. step 1：`task-20261024033326-3acee4:ready`（预置任务）
  2. create 之后：`task-20261024033340-61f5e0:ready`（任务变化 → 更新）
  3. status→running 之后：`task-20261024033340-61f5e0:running`（状态变化 → 更新）
  - 6 步共 **3 次**注入，指纹互不相同、无重复注入；步骤 3/5/6 brief 未变，故无新增；
- mock 请求体可见注入内容：brief 包在 `<sage-kit-brief>…</sage-kit-brief>`，作为 user 文本出现在模型上下文中（`evidence/scenario-a/001.json`、`003.json`、`005.json`）；session-title 请求（tools=0）不带注入。

**场景 B：无 `.sage-kit` 的目录**（`noninit`，text mock）
- 注入 0 次（请求与 session 事件均为 0）；未创建 `.sage-kit`；无 tool_call；
- 主请求 tools=30 且包含 5 个 sage 工具（插件注册与项目是否初始化无关）。

**场景 C：无项目时仍调用插件工具**（`noninit2`，plugin mock）
- 3 次工具结果为 `error`：`SAGE-Kit is not initialized for this project. Run \`sage-kit init --host dsh --scope project\` (or \`npx sage-kit init ...\`) first.`；
- turn 仍 completed、stderr 0 B、无注入、无 `.sage-kit` 产生 —— 符合“失败不污染/不阻塞 turn”。

另：首轮 mock 传入 `status: "in_progress"` 时工具返回可读校验错误：`invalid arguments: "status" must be one of ["imported","ready","running","review","done","blocked","failed","cancelled","interrupted"]`（defineTool schema 生效）。

## 真实模型 headless（非 mock）

- 项目 `project-c`（初始化 + 预置 ready 任务）；真实 `DEEPSEEK_API_KEY` 从隔离 0600 文件读入环境变量，不打印。
- 模型/适配器（session `request/header`）：`deepseek-official` / `deepseek-flash`，`reasoningEffort: high`，`maxTokens: 256000`。
- 6 步、turn completed；工具调用顺序：`skill{sage-kit}` → `sage_task_create` → `sage_task_list` → `sage_task_status(running)` → `sage_task_show`。
- 创建任务 `task-20261024033521-f06e62`（标题 `DSH plugin real-model task`，状态 `running`，acceptance 与模型请求一致）；模型最终答复包含任务 id 与 `task list` 输出；`task list` 共 2 个任务（预置 + 新建）。
- 注入：同一 session 3 次（`…33516-eb64fd:ready` → `…33521-f06e62:ready` → `…33521-f06e62:running`），指纹唯一、无重复；step 3/5/6 未重复注入。
- stderr 0 B、exit 0；模型行为中未出现 bash 改文件（按提示 “Do not edit any files”）。

## 隔离 DSH_HOME / peer 解析（回答“fresh profile outside DSH ancestor”）

- 新建 `DSH_HOME=/tmp/dsh-iso-home-1792812850`（`/tmp` 下无任何 `node_modules`、无 DSH 安装祖先），从 headless 模板物化 profile，`dsh plugin add` 两个 tgz，`--dump-config` 仍出现插件层；
- profile `node_modules` 只有 `sage-kit`、`sage-kit-dsh`（pnpm 未安装任何 `@deepseek-ai/*` peer）；
- headless 仍启动成功：tools=30，包含 5 个 sage 工具，stderr 0 B；
- 结论：在 DSH 0.2.1-rc.2 上，插件 bundle 里 `peerDependencies: @deepseek-ai/*` 的缺失**不影响加载**——DSH 运行时从安装自身解析这些包；`pnpm peers check` 的告警是预期噪声（打包层面仍建议注明“peer 由 DSH 提供”，见 §9）。

## 已知边界 / NOT_EXECUTED

1. **仅 headless**：`dsh web` 中的插件加载/工具/brief 注入未跑（GUI 会话成本高，headless 已覆盖相同的 loader 与 agent/pre-step 路径）；未做 Web 截图。
2. **配置分支未覆盖**：`autoBrief:false`、显式 `projectRoot`、`maxBriefBytes` 截断（256..8192 clamp）行为未逐一执行。
3. **失败降级路径未覆盖**：损坏的 `.sage-kit/config.json`、brief 构建抛错时的 `ctx.logger.warn` 降级未注入故障验证。
4. **工具边界**：`sage_task_status` 标记 done 时无 evidence 的拒绝、非法 id、schema 数组/字符串边界只验证了 enum 一例。
5. **多会话并发**：per-session WeakMap 去重只在单 session 验证；跨 session 同 profile 的并发未测。
6. **安装形态**：只测本地 tgz；`file:` 目录 link、registry 版本、`--patch` overlay、DSH 其他版本（<0.2.1-rc.2 或 0.3.x）未测。
7. **Windows 宿主**：未以 Windows 为测试目标（按要求）。
8. **模型质量**：真实模型仅 1 次任务，不做模型能力/稳定性统计。

## 与 Lead 独立证据交叉核对

Lead 在另一套隔离环境（`DSH_HOME=/home/kayann/sage-kit-linux-dsh/home-plugin-test2`，profile `sage-kit-plugin`，Linux pnpm，mock model `MOCK_SKILL_CALL=0` 与自定义 tool-call mock，另加 fake-ctx 单测）得到：插件加载、请求 tools 含 5 个 sage 工具、`messages[0]` 出现 `<sage-kit-brief>`、`tool_call sage_task_create` 成功落盘、第二次相同 pre-step dedupe、`autoBrief:false` 不注册 listener。本轮独立复现结果：

| Lead 证据 | 本轮独立证据 | 一致性 |
| --- | --- | --- |
| profile 加载插件、tools 含 5 个 sage 工具 | §7 隔离 `DSH_HOME=/tmp/dsh-iso-home-1792812850`：tools=30 含 `sage_brief, sage_task_create, sage_task_list, sage_task_show, sage_task_status`，stderr 0 B | 一致 |
| mock 下 `<sage-kit-brief>` 出现在模型请求 | §4 场景 A：注入以 user 文本进入请求（`evidence/scenario-a/001.json` 等），session 落 `source {kind:"sage-kit",form:"brief"}` | 一致 |
| `tool_call sage_task_create` 成功、任务落盘 | §4 场景 A 5 个工具全成功；§5 真实模型同样调用 create/list/status/show | 一致 |
| 第二次相同 pre-step dedupe | §4/§5：6 步仅 3 次注入、指纹互异，未变化步骤 3/5/6 无新增 | 一致（E2E 层面；未重复 fake-ctx 单测） |
| `autoBrief:false` 不注册 listener | 未执行（见 NOT_EXECUTED 第 2 条） | 未复现 |
| Linux pnpm（WSL 默认 pnpm 为 Windows scoop，会 panic） | §2：确认并改用 Linux pnpm 12.15.0 | 一致 |

## 复现命令（Linux/WSL）

```bash
H=/home/kayann/sage-kit-linux-dsh; E2E=$H/plugin-e2e
REPO=/mnt/d/Projects/SAGE-Kit
# 0) Linux pnpm（WSL 必需，Windows pnpm 会 panic）
[ -x "$E2E/tools/node_modules/.bin/pnpm" ] || npm install pnpm@12.15.0 --prefix "$E2E/tools"
# 1) 构建 + 打包
rsync -a --delete --exclude node_modules --exclude dist --exclude work --exclude .git \
  "$REPO/" "$E2E/build/"
(cd "$E2E/build" && npm install --no-audit --no-fund && npm run build && npm pack --pack-destination "$E2E/pkg")
(cd "$E2E/build/packages/dsh-plugin" && npm pack --pack-destination "$E2E/pkg")
# 2) fresh profile + 安装
export DSH_HOME="$E2E/home"
export PATH="$E2E/tools/node_modules/.bin:$H/node_modules/.bin:$PATH"
dsh --profile sage-kit-plugin --from-default-profile headless --dump-config >/dev/null
dsh plugin --profile sage-kit-plugin add "$E2E/pkg/sage-kit-0.1.0.tgz" "$E2E/pkg/sage-kit-dsh-0.1.0.tgz"
dsh --profile sage-kit-plugin --dump-config | grep -A4 'sage-kit-dsh'
# 3) 确定性场景
bash "$REPO/work/plugin-e2e/prep/run-scenarios.sh"
# 4) 真实模型（key 在隔离 0600 文件；不打印）
cd "$E2E/project-c" && DEEPSEEK_API_KEY="$(cat "$H/.real-model-key")" \
  dsh --profile sage-kit-plugin --json "<prompt>" > events.jsonl 2> stderr.log
# 5) 证据汇总
bash "$REPO/work/plugin-e2e/prep/assemble-evidence.sh"
```

## 对实现/打包的观察（非阻塞，供 Lead 定稿）

1. **peerDependencies 策略**：`peerDependencies: @deepseek-ai/*: "*"` 在 0.2.1-rc.2 由 DSH 运行时解析，实测可加载；`pnpm peers check` 会报缺（用户可能误解）。建议在 `packages/dsh-plugin/README.md` 明确“这些 peer 由 DSH 宿主提供，不要手动安装”，或评估改为 `dependencies` + 版本 pin 的利弊。
2. **pnpm 版本探测**：WSL 下默认 pnpm 可能是 Windows 二进制，导致 `dsh plugin add` panic；文档可加一行“WSL 需 Linux pnpm”。（README 文档任务属 task-18。）
3. **pnpm 12 “Agent skills awaiting approval”**：根包 `skills/` 目录触发，仅提示；若担心用户困惑可在文档说明（不改变行为）。
4. **注入去重语义正确**：fingerprint 包含 status/evidence，任务状态变化即更新；session 持久化里表现为新增 `user/message`（source `sage-kit`），不会重复旧 brief。
5. **错误路径干净**：未初始化项目调用工具返回可读错误且不阻断 turn；未初始化项目不注入、不创建状态目录。

## 证据清单（`reports/plugin/evidence/`）

- `profile/`：`environment.txt`（版本/tarball sha256/内容）、`refresh-verify.txt`（README 落地后的 refreshed tarball 快照、新 sha256/size、fresh profile 复验摘要）、`refresh-verify-add.log`、`refresh-verify-events.jsonl`、`dump-config-refreshed.yml`、`add-both-tgz.log`、`add-root-tgz.log`、`add-plugin-tgz.log`、`separate-add-root.log`、`profile-package.json`、`dump-config-headless-template.yml`、`dump-config-with-plugin.yml`、`dump-config-excerpt.txt`、`peers-check.log`、`profile-node-modules.txt`
- `scenario-a/`：`checks.txt`、`dsh-events.jsonl`、`session-evidence.json`（3 注入 + 5 工具调用）、`injection.json`、`001.json`/`003.json`/`005.json`（模型请求可见 brief）、`post-task-list.txt`、`brief-after.txt`、`dsh-stderr.log`
- `scenario-b/`：`checks.txt`、`session-evidence.json`（0 注入）、`001.json`（tools=30）、`dsh-events.jsonl`、`dsh-stderr.log`
- `noninit-tools/`：`checks.txt`、`session-evidence.json`（3 error tool_result）、`dsh-events.jsonl`、`dsh-stderr.log`
- `real-model/`：`checks.txt`、`prompt.txt`、`dsh-events.jsonl`、`session-evidence.json`（3 注入、skill+4 工具）、`created-task.json`、`post-task-list.txt`、`pre-task-list.json`、`dsh-stderr.log`
- `isolated-home/`：`checks.txt`、`dsh-home.txt`、`001.json`（isolated 下 tools=30 含 5 sage 工具）、`session-evidence.json`、`dsh-events.jsonl`（exit 0、stderr 0）

（原始脚本与未压缩日志在 gitignored 的 `work/plugin-e2e/`；本报告未修改 src/docs/packages，未 commit。）
