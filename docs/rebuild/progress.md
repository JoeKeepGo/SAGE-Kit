# 重建进度与恢复入口

## 当前范围

2026-10-26：用户授权恢复 v2026.8.13.1 基线并开始重建。R0–R3 本地实现与检查完成；
持续开发、治理 hook 和 RSI 是核心目标。规范见 [SPEC](SPEC.md)，权威见
[决策](../decisions.md)。本记录只协调进度，不取代规范、Git 或测试结果。

## 恢复位置（2026-10-26 观察）

- 基线 tag：`v2026.8.13.1` → `6355ecebadba149ceea8d51c446e023eac05a4dd`。
- 历史保留分支：`workflow/archive-runtime-20261026` → `69db3da7e8752c7edbedcaac4adceeace527a905`。
- 重建分支：`workflow/rebuild-governed-rsi`；主分支未重置，未 push/发布。
- 原来未跟踪的 `dist/`、tgz 与报告日志已保留到本机
  `local/archive-runtime-20261026/`，不作为新版本可执行入口或证据。
  `node_modules/`、`work/` 保留原状且不随包交付。分支备份不包含这些本地文件。
- 恢复归档代码可切换上述保留分支；切换前先保存当前重建文档。
  不需要强推或重写主分支历史。

## 验证

2026-10-26，本机 WSL2，以恢复基线和本次新增文档为检查对象：

| 检查 | 结果与证明范围 |
|---|---|
| `git diff v2026.8.13.1 -- skills contracts docs/agent docs/templates docs/SAGE_CORE.md` | 无差异；原 Skill、契约及上述治理资源原样恢复 |
| `bash scripts/check-repository.sh` | PASS；原版静态仓库完整性 |
| `bash tests/test_skill_portable_references.sh` | PASS；10 resources、24 package files、Markdown closure |
| `bash tests/test_claude_hooks.sh` | 14 PASS / 0 FAIL；原版 exact-path advisory fixture，不是真实 Claude 会话 |
| 新文档相对链接 / `git diff --check` | 6 个链接有效；无空白错误 |
| 独立语义审查及针对性复核 | 唯一 P2 已修复：必需评审按项目与风险等级决定，Light 不被强制新增独立评审；R0 无剩余阻断发现 |

初次检查因系统没有 jq/plutil，完整性/引用检查无法执行，hook 出现 3 个 fixture
失败；从系统配置的 Ubuntu 包源下载 jq/libjq1/libonig5 并仅解包到本机
`local/rebuild-check-tools/` 后，使用下列前缀执行以上三条命令均通过：

```sh
PATH="$PWD/local/rebuild-check-tools/extracted/usr/bin:$PATH" \
LD_LIBRARY_PATH="$PWD/local/rebuild-check-tools/extracted/usr/lib/x86_64-linux-gnu" \
bash scripts/check-repository.sh
```

另外两条命令使用相同环境前缀。未修改系统安装，未新增项目运行依赖，未改动
原版 hook 来掩盖缺失工具。原版核验只能证明其声明范围。

R0 检查时，Windows/macOS、真实 DSH/Codex/Claude、新执行循环与 RSI 均未执行；
后续 R1 证据见下文，不能从 R0 检查推导。

## R1：用现有治理与受控改进流程推进（2026-10-26）

用户进一步授权借现有 SAGE-Kit 与 RSI 模式持续完成重建。普通实现/验证/修复继续，
治理策略自我修改仍只产候选，需人批准；不自动改已发布 Skill、合并或发布。
按 [R1 约定](continuation.md) 先写接口与反例，再实现 `adapters/continuation.mjs`。
它是宿主可选模块，无模型/命令执行器、数据库、网络、根 package 或额外依赖。
原 Skill、契约、治理核心与模板对基线仍无差异；静态检查仅明确允许这一可选适配器，
保留禁止核心强制依赖与可执行入口的规则，CI 增加独立 Node 22 测试 job。

### 当前证据

- WSL2 Node 22.22.1：`node --test --experimental-test-isolation=none tests/continuation.test.mjs`
  **35 PASS / 0 FAIL / 0 SKIP**。覆盖两种文件布局、真实三步命令、失败修复、两失败
  复核、真实 SIGKILL 后结果核对、准入/人工关口/预算/规范变化/证据变化及损坏记录。
- 原静态完整性、portable references、Claude advisory hook 检查全部通过（hook 14/14）。
- 独立审查发现 1 个 P1 并已修复、针对性静态复核通过；最终测试由控制者在当前
  受限环境执行。没有把旧运行时 206 项结果复用作新版本证明。
- 本机证据：`local/rebuild-r1/{continuation-test,baseline}.log`、`review.txt`。
  自用 `plan.json/state.json` 实际记录 R1 验证 intent → 带检查/评审证据 finish →
  自动选择已授权的 R2 只读探针；它们不是项目规范的第二权威，且不随包提交。
- 当前受限环境对子进程管道输出有限制：最初 `node --test` 仅有文件级失败；直接
  执行可定位到等待 stdout 就绪超时。改用真实副作用文件判断就绪，仍真实 SIGKILL，
  本地采用无测试文件进程隔离运行；CI 保留标准 `node --test`。本次未在此环境验证
  标准隔离运行模式、Windows/macOS 或真实宿主自动开发。

### RSI 观察与本轮修正

| 观察 | 假设/处理 | 证据与采用边界 |
|---|---|---|
| 初版 context 未带当前步骤的 scope/checks，两个布局测试失败 | 只恢复总目标不足以抵御范围遗忘；把 step 约束加入上下文 | 保留测试后修复通过；属于已授权实现修正，无治理策略自改 |
| 评审发现 passed 记录的 digest 列表被清空后可漏检证据 | 恢复不能只验证字段类型，要复核结果与证据集合 | 共用结果检查；补缺失/额外digest、缺check/review四个回归；复核关闭 P1 |
| sandbox 子进程 stdout 不可观察 | 用持久副作用确认执行后再杀进程，减少测试对管道的依赖 | 不降低中断验收，不skip；当前环境35项通过 |

这是模型执行的受控观察—修正—验证—独立复核流程，不是宣称 R3 自动 RSI 程序
已完成，亦未衡量普遍开发收益。长期策略候选（如将证据一致性检查推广到其它适配器）
需在对应范围独立评估，不自动修改原 Skill 或所有项目规则。

## R1 资源约束修正（2026-10-26）

依据用户反馈与决策 R-006，按事件调用的可选模块增加每次总读取 8 MiB/128 文件、
路径深度 32 的边界；同次引用去重，跨次仍按内容核验；幂等 begin/finish 不重写
state。状态写入超过 4 MiB 在替换文件前拒绝，避免成功写入后无法恢复。无 CLI、
轮询、全仓扫描、计数日志或额外依赖；RSI 不放入同步 hook。

- 当前环境允许标准测试隔离：`node --test tests/continuation.test.mjs` **44 PASS /
  0 FAIL / 0 SKIP**，包括原 35 项及新增读取/写入预算、去重、变更识别、幂等与测量。
  关闭了上述 R1 记录中“标准隔离模式未验证”的局部缺口，Windows/macOS 原生仍未测。
- 独立针对性静态审查及写入边界复核无阻断发现；测试由控制者执行。
- 原 Skill、契约、治理文档/模板对 v2026.8.13.1 仍无差异；`git diff --check` 通过。
  其输入未变，沿用 R1 的静态完整性/引用/原 hook 证据，未重复跑无关检查。
- 证据：`local/rebuild-resource/{continuation-tests,mounted-measurement,baseline,diff}.log`、
  `review.txt`。使用新的本地 plan/state 记录本轮 intent/结果；旧 R1 plan 所引用决策与
  协议已改变，其 fingerprint 不再代表当前轮，保留旧记录而不改写历史。

测量环境：WSL2 6.18.33.2、Node v22.22.1、x64；20 个已完成步骤共享一个 1 MiB
证据文件。准备工作及一次预热不计入；以下均为 **10 次 inspect 的总量**：

| fixture 位置 | wall | 进程 CPU（user + system） | 每次逻辑内容读取 |
|---|---|---|---|
| Linux `/tmp` | 32.734 ms | 29.383 + 6.916 ms | 4 文件 / 1,064,689 bytes |
| 本仓库 `local/rebuild-resource/tmp`（`/mnt/d`） | 282.254 ms | 37.489 + 23.572 ms | 4 文件 / 1,064,689 bytes |

D 盘位置使用同一测试的名称筛选单独运行，1 PASS。以上是单次本机样本，不设易波动
时延阈值，不是物理磁盘 IO、旧 CLI 对照或真实长会话收益。A14 组件边界已验证；
DSH 实际事件频率、同步 hook 超时、长会话和 RSI 预算仍须在接入阶段测量。

受控改进记录：读取预算测试通过后，审查持久化路径发现写入/读取上限不对称；
先补“超限 finish 保留原记录且仍 reconcile”反例，再补写前检查，复测及针对性
复核通过。这是已授权实现修正，未自动改变任何项目目标、验收或已发布 Skill。

## R2 准备与下一步

只读探针已确认本机已有 DSH 0.2.1-rc.2：
`/home/kayann/sage-kit-linux-dsh/node_modules/@deepseek-ai/dsh/lib/bin.js --version`
返回 `0.2.1-rc.2`，执行使用仓库内隔离 `DSH_HOME`。读取已安装源码确认
`dsh-agent/lib/types/runtime-types.d.ts` 有 `agent/pre-step`，
`dsh-compaction/lib/types/types.d.ts` 有压缩 session events；类型声明不是接线证明。
尚未启动用户 profile、调用模型或注册新插件。

随后在 `local/rebuild-dsh/` 建立隔离 Cordis Context，仅加载已安装的真实
agents/session/projections/llm/system-prompt/tools/loop 服务，使用本地确定性模型替身：
`timeout 15s node local/rebuild-dsh/component-probe.mjs` 退出 0。两次请求收到治理
注入及一次真实 `probe_echo` 结果，session 记录 `turn/end: completed`，无 agent/error；
进程正常退出。完整记录在 `component-probe-result.json`，启动修正在
`component-probe-notes.md`。没有加载默认 profile、provider、凭据或 HTTP 服务，
无网络/真实模型调用。证明可在宿主内接入而无需逐工具启动 CLI；尚未接入 R1
适配器，不是完整 headless、插件安装、压缩恢复或长会话资源验收。

该探针之后的 R2 实现与证据见下文。

## R2：DSH 原生接入与本地安装验收（2026-10-26）

用户明确授权进入 R2。依据 [DSH 约定](dsh.md)，新增可选私有包
`adapters/`：在真实 `agent/pre-step`、`tools/pre-execute` 与 tools registry 中接入
治理提醒、准入、结果和恢复，不另建模型循环。普通模型步骤只读有限规范/状态，
首次/新 turn/实际 surface replacement/记录变化才完整核对历史证据；begin 始终
完整准入。工具失败或取消立即清除本会话执行许可，同批后续工具不能沿用。

原 Skill、契约、治理核心和模板保持基线；核心不依赖该包。包内只有现有宿主 peers，
无 CLI、安装脚本、后台轮询或同步 RSI。bundle 初装禁用，必须配置项目映射后启用；
测试确实启用并执行，未使用“发现禁用 entry”代替交付。默认用户 profile 未改动。

### 最终候选证据

- WSL2、Node v22.22.1、DSH **0.2.1-rc.2**，最终安装包：
  `node --test tests/continuation.test.mjs tests/dsh*.test.mjs`，**68 PASS / 0 FAIL /
  0 SKIP**（底层 49、原生闭环 9、故障 8、真实中断 1、原生 profile 1）。
- 实际三步本地任务、检查/必需评审引用、人工关口、规范变更、重放拒绝、同批失败
  拦截、超时/取消、上下文上限、实际 surface replacement 均有对应反例/正例。
  子进程在真实工具副作用发生后、finish 前被 SIGKILL，重建宿主核对后继续，
  副作用最终仅 `first\nsecond\n`，未重复执行已发生的动作。
- 原生 DSH CLI/profile loader 从本地 tgz 装包、启用 bundle、完整投影 schema，
  启动隔离 fixture application：4 次模型替身请求、1 次实际写入、3 个成功工具
  结果、持久状态 passed、turn completed。不是 stock headless 或真实模型质量验收。
- 工件：`local/rebuild-dsh/sage-kit-dsh-plugin-0.0.0-rebuild-r2.tgz`，SHA-256：
  `ca6a8278b491fa2a15ca3d4f490143dbeb74ae306bd7b322f7913c8f23386366`。
  测试显式指定该 tgz 与其 `installed-final/` 安装入口，禁用安装脚本及联网安装；
  宿主使用本机已有版本，没有调用 provider 或读取凭据。
- 独立审查发现并修复 1 个 P1：显式治理工具读入失败后，同批后续工具可沿用旧
  owner。补真实 DSH 多工具批次回归后通过；独立针对性静态复核无剩余阻断。
  审查者没有运行最终套件，最终执行证据由控制者提供。
- 仓库静态完整性 PASS；portable references 10 resources / 24 package files 与
  Markdown closure PASS；原 Claude advisory hook fixture 14/14（不是真实 Claude
  会话）。基线资源差异为空；源码、tgz 和安装目录的 6 个包文件逐字节一致。
  受影响文档链接与空白检查通过。Windows/macOS 原生及远程 CI 尚未执行。
- 本机原始记录：`local/rebuild-dsh/final-tests.log`、`mounted-measurement.log`、
  `package-pack.json`、`package-install-final.log`、`artifact-check.log`、`review.txt`、
  `{repository-integrity,portable-references,claude-advisory,baseline,diff,doc-links}.log`。本地
  `validation-plan.json/validation-state.json` 从最终验证开始记录 intent/结果，
  不倒填此前实现过程，不随包交付，也不替代项目权威。

### 资源观察

同一真实宿主 fixture：1 份 64 KiB 历史证明、25 次确定性模型请求。下表为该循环
总量（含宿主处理；不含 fixture 准备和随后单独的 surface replacement 检查）：

| fixture 位置 | wall | 进程 CPU（user + system） | 逻辑内容读取 | 治理注入 |
|---|---|---|---|---|
| Linux `/tmp` | 121.385 ms | 110.201 + 24.492 ms | 76 文件次 / 98,935 bytes | 4 |
| 本仓库 `local/rebuild-dsh/tmp`（`/mnt/d`） | 754.283 ms | 245.640 + 50.743 ms | 76 文件次 / 98,935 bytes | 4 |

测试另外断言普通 observe 每次 3 文件、低于 16 KiB，历史完整检查仅 1–2 次；
同 turn 真正替换 surface 后重新注入。单次本机样本，不是物理 IO、旧 CLI 对照、
故障文件系统硬实时保证或真实长任务的 CPU 上限。RSI 独立预算仍在 R3 验证。

### 受控改进与下一项

本轮沿用 SAGE-Kit 与 RSI 的观察—假设—反例—修复—复核流程：独立评审暴露
同批工具边界，先固定反例，再清理失效执行标记；未自动修改目标、验收或原 Skill。
这不等于 R3 自动 RSI 已实现。

下一项是 **R3：受控 RSI 闭环**。从真实失败/返工证据产生隔离候选，固定基线与
评估资产，双侧检查保护边界，批准绑定候选/评估，采用前有人工关口并可回滚。
真实模型长任务质量、更多压缩插件、Windows/macOS 原生和 Codex/Claude 接入
仍未验证；本地 R2 完成不代表整体用户验收、远程 CI 或发布完成。

## R3：受控 RSI 与真实缺陷自用评估（2026-10-26）

用户明确授权进入 R3。先按 [RSI 约定](rsi.md)划定 builder、evaluator 与采用权限，
从归档提取固定命令、隔离、路径和一次性批准思路；未搬回旧任务管理器。
新增可选 `rsi.mjs` 与 `rsi-process.mjs`，DSH 显式配置后提供六个原生工具。
失败/评审/返工引用形成不可变候选，基线和候选运行同一固定检查；两侧保护都须
通过。采用和回滚各自请求一次原生批准，绑定候选、评估、实际文件、规范和计划；
等待期间变化或过期拒绝，回滚不覆盖第三方改动。

原 Skill、契约、核心治理及模板仍与基线无差异。DSH 当前规范引用和开发 plan/state
另列为 RSI 禁写集合，不能因误配 targets 或批准而修改。RSI 不在同步 hook 内运行。
每次完整 API 操作共享 8 MiB/128 文件次读取预算；每候选最多三次评估，不自动重试。
短命 guardian 用 EOF/IPC 事件处理控制者退出，正常完成、超时、取消和控制者
SIGKILL 后都清理同组命令及后代，无后台轮询。

### 最终候选证据

- WSL2 6.18.33.2、Node v22.22.1、DSH **0.2.1-rc.2**；精确安装包入口执行：
  `node --test tests/continuation.test.mjs tests/dsh*.test.mjs tests/rsi*.test.mjs`。
  **125 项：124 PASS / 0 FAIL / 1 SKIP**；唯一 skip 是 Windows 专属拒绝路径测试，
  当前为 Linux。RSI 组件 29、进程生命周期 13 PASS/1 SKIP、DSH RSI 14，其余 R1/R2
  及扩展 profile 68。Windows 评估代码明确拒绝，未宣称平台验证通过。
- 实际 DSH CLI/profile loader 从最终 tgz 启用插件，9 次模型替身请求、7 个成功
  工具结果，先完成开发任务，再完成 RSI 比较、两次独立 allowed-once、实际采用和
  回滚还原；schema 完整。使用真实 approval 服务和测试 answerer，无真人同意声明。
- 覆盖双侧资产篡改、固定评估入口误列 target、治理文件误配、内容/规范/评估篡改、
  批准等待变化与过期、第三方回滚冲突、实际文件写入后取消恢复、只读不写盘、
  跨阶段总读取超限、输出/次数/时间预算及后代进程清理。
- 工件 `local/rebuild-rsi/sage-kit-dsh-plugin-0.0.0-rebuild-r3.tgz`，SHA-256：
  `a58ab41761cf430260ee4ffda8506448d70769216203a5009462fc4fb628a6aa`。
  源码、tgz、`installed-final/` 的 8 个包文件逐字节一致；本地离线安装且禁用脚本，
  未修改默认 profile、读取凭据、调用 provider、发布或 push。
- 静态完整性 PASS；portable references 10 resources / 24 package files 与闭包 PASS；
  原 Claude advisory fixture 14/14；核心基线差异为空。受影响文档链接与空白检查通过。
  Windows/macOS 原生、远程 CI 及真实模型长期开发质量未验证。
- 独立审查共发现 2 个 P1、2 个 P2：跨层治理禁写集合缺失、锁内批准过期复查遗漏、
  预算分阶段重置，以及 guardian 正常退出清理空窗。均经针对性修复/回归与独立
  静态复核关闭，无剩余阻断。独立审查和最终测试由不同角色提供，未互相冒充。

### RSI 自用：修复本轮真正发现的问题

独立审查真实复现：暂停控制者 → 评估命令正常退出 → 杀控制者，同组孙进程仍能写出
`orphan effect`。保留缺陷源码及受保护的固定复现脚本，再用本轮 `openRSI` 建立候选
并比较修复（guardian 在报告结果后自行终止进程组，不把清理留给控制者）。

| 同一固定检查 | 退出码 | 保护检查 | 命令 wall |
|---|---|---|---|
| 真实缺陷基线 | 1，出现 orphan effect | 通过 | 1640.049 ms |
| 修复候选 | 0，无遗留副作用 | 通过 | 1637.758 ms |

该次完整 RSI 比较累计读取 **19 文件次 / 94,903 bytes**，结果为 human_approval。
无批准 adopt 实际被拒绝，隔离源快照仍保持缺陷版。工程 bug 修复按本轮已授权的
实现/纠错流程完成；没有把 RSI 的候选通过偷换为自动采用治理策略。
这证明对该实际故障的改进与门禁，不证明 RSI 对所有任务都有收益。

### 资源测量与恢复边界

另一个固定小 fixture（3 个评估输入、1 个规范、1 个候选目标）的一次基线/候选比较，
不含 fixture 准备；以下 CPU **仅为父测试进程**，不含评估子进程 CPU：

| fixture 位置 | wall | 父进程 CPU（user + system） | 全操作逻辑读取 |
|---|---|---|---|
| Linux `/tmp` | 361.198 ms | 12.575 + 14.826 ms | 25 文件次 / 3,336 bytes |
| 项目磁盘 `local/rebuild-rsi/tmp`（`/mnt/d`） | 588.545 ms | 72.838 + 23.236 ms | 25 文件次 / 3,320 bytes |

读取量含状态/失败日志中的运行元数据，两个样本大小略有不同。它不是物理 IO、
子进程 CPU 上限或旧 CLI 对照。RSI 的命令有独立时间/输出预算；临时目录不是
操作系统沙箱，主动逃离进程组的代码不在清理保证内。硬中断后可能留下锁和临时
目录，须确认写入者停止并清理明确归属资源，再记录中断，不自动偷锁或重跑。

原始证据位于 `local/rebuild-rsi/`：`final-tests.log`、`mounted-measurement.log`、
`self-evaluation.{json,log}`、`guardian-project/`、`review.txt`、`history-review.txt`、
`package-pack.json`、`package-install.log`、`artifact-check.log`、
`{repository-integrity,portable-references,claude-advisory,baseline,diff,doc-links}.log`。
最终验证另用 `validation-plan.json/validation-state.json` 记录 intent、检查和评审；
从验证开始记账，不倒填此前实现，不随产品包提交。

下一项是 **R4：Codex/Claude 适配及跨项目验证**。按真实宿主能力记录支持矩阵，
验证不同文档结构项目仍保持同一治理语义。真实模型长期收益与真人策略采用仍需
单列验证；R3 本地实现完成不代表整体用户验收、生产采用或发布完成。
