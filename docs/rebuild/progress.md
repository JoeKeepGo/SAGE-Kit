# 重建进度与恢复入口

## 当前范围

2026-10-26：用户授权恢复 v2026.8.13.1 基线并开始重建。R0 基线恢复与方案检查完成；
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

Windows/macOS、真实 DSH/Codex/Claude、新执行循环与 RSI：`NOT_EXECUTED`。

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

## R2 准备与下一步

只读探针已确认本机已有 DSH 0.2.1-rc.2：
`/home/kayann/sage-kit-linux-dsh/node_modules/@deepseek-ai/dsh/lib/bin.js --version`
返回 `0.2.1-rc.2`，执行使用仓库内隔离 `DSH_HOME`。读取已安装源码确认
`dsh-agent/lib/types/runtime-types.d.ts` 有 `agent/pre-step`，
`dsh-compaction/lib/types/types.d.ts` 有压缩 session events；类型声明不是接线证明。
尚未启动用户 profile、调用模型或注册新插件。

下一项：在隔离目录把 R1 语义接入真实 DSH 插件，验证治理上下文注入、实际工具及
异常降级/门禁；先完成本地组件装配，再跑固定模型 fixture 与可用的真实会话。
Codex/Claude 对应接入与 R3 仍待实现，不把 R1 本地支持扩大成整体完成。
