# R4 项目规范映射

依据 [决策 R-002](../decisions.md)、[SPEC](SPEC.md) 与 [A02](acceptance.md)。
映射把项目现有文档和条目接到[持续执行约定](continuation.md)，不建立第二份产品
规范。本页及示例是 SAGE-Kit 的接入证据；目标项目的规范、权限和产品验收仍由
目标项目及其 owner 决定。

## 如何选择当前一轮

1. 明确项目 root、当前版本/决定入口、任务与验收入口、只读历史范围。选择当前
   任务涉及的规范文件和原始条目 ID；不要求导入全项目需求。
2. `authority` 使用原始相对文件路径；`objective` 保留任务、需求和验收的原始
   ID/章节引用。独立映射记录可保存引用及摘要；不得把摘要当作新规范。
3. `scope` 来自该轮明确允许的路径/操作；`checks` 对应原验收 ID 或具体必要检查。
   规范引用不是命令授权，`interfacePrerequisites` 中的 SPEC ID 也不是已完成任务，
   不能直接转换成 `dependsOn` 或推定依赖满足。真实任务依赖由当前计划明确映射。
4. `admitted`、`humanGate`、`requiresReview`、预算及到期时间来自当前授权与风险
   判断，不能从“已采用设计”或 `PLANNED_NOT_STARTED` 推导。模型不能自己解除
   阶段门。plan/state 使用项目选定位置；执行观察不写回规范任务的状态字段。
5. 文件摘要绑定当前轮；规范内容变化会使已有状态返回 `authority_changed`。
   控制者核对受影响要求与证据后开新轮，保留旧记录。当前实现绑定整份选定文件，
   不做章节级语义差异判断；因此应选有界的相关文件，而非每轮扫描全仓。

`scope` 只是宿主约束，不是文件系统沙箱；带通配符的原规划路径也不会自动展开
或执行。运行前仍需宿主核对实际操作。映射检查通过只表示引用及机械门禁可接通，
不证明技术栈构建通过、需求完整实现或产品验收通过。

## Taluvia 的有界只读映射

来源：用户指定的 `Taluvia_Space_Docset_v1.12.0`，于 2026-10-26 读取。
[捕获记录](../../examples/rebuild/taluvia-mapping.json) 保存 **14 个文件、475,320 字节**
的原始相对路径、完整 SHA-256、长度及章节/条目选择器，不复制产品规范正文。
覆盖一个 P0 任务及其相关入口；不是全 docset 审计，也不是 Taluvia 执行计划。

| 映射角色 | 原始引用 | 观察到的状态/意义 |
|---|---|---|
| 当前版本/决定 | `RELEASE.json` → `governance/decisions-1.12.md`；`D-12-01`、`D-12-02`、`D-12-04` | 1.12.0 设计基线；采用设计不等于运行 |
| 规范 | `specs/SPEC-00/SPEC.md` §“1.12 Cordis 模块组合与生命周期”；接口前提另含 `SPEC-01` | 产品实现/运行 `NOT_EXECUTED` |
| 需求 | `specs/SPEC-00/requirements.md#tv112-req-00-01`、`#tv112-req-00-02`；同 ID 的 `data/requirements-1.12.json` 条目 | `ADOPTED_1_12_DESIGN_NOT_IMPLEMENTED`；验证 `NOT_EXECUTED` |
| 任务 | `data/tasks.json` 的 `TV112-TASK-00-01` | 服务端 Cordis 组合根；P0；`PLANNED_NOT_STARTED` |
| 验收 | `data/acceptance.json` 的 `TV112-ACC-00-01`、`TV112-ACC-00-02` | 原任务 focusedAcceptanceTests；`NOT_EXECUTED`，evidence 为空 |
| 探针/阶段 | `implementation/dsh-runtime-spike.md` 的 `S16`；`implementation/plan.md` 的 P0 | 组合/角色裁剪/客户端等真实验证尚未执行 |
| 状态入口 | `governance/status.md`、`data/stages.json` | 任务计划未开始；产品验收未执行 |

任务到两个需求的关联是本次依据相同 SPEC、主题和验收建立的显式映射；没有把
它冒充源任务中已经存在的 requirementIds 字段。原 task 的 plannedPath、接口前提、
验收 ID 原样保留；不把其他 P0 任务删掉或声称这一条覆盖全部 P0。

发现并保留一处局部版本差异：`data/stages.json` 的 `docsetVersion` 和 `revision`
仍为 `1.11.0`，而 RELEASE 与当前决定指向 `1.12.0`。测试固定记录这一观察，
不静默修复、不把旧字段当成当前版本，也不据此推定执行准入。未来真正接入该项目
时，需按其现行权威核对受影响阶段含义；本次只读映射不依赖此差异解除阶段门。

测试将上述文件原始字节复制到一次性目录，再以原路径交给 `openContinuation`。
唯一准入步骤是 fixture 自身的引用检查；产品任务 `admitted:false`。检查结束后
仍为 `blocked`，不能开始 Taluvia 产品任务。单独修改临时副本的决定文件后得到
`authority_changed`。开始和结束均核对所选源文件摘要；不写原 docset，不启动
其工具、构建、集群、模型、DSH profile 或产品进程。临时记录随测试清理。

## 小型项目与复跑

另一个 fixture 是扁平的 CSV 工具项目：`brief.txt` 直接保存 `REQ-CSV-01` 与
`ACCEPT-CSV-01`，`todo.json` 指向 `export.py`；计划为根目录 `work-order.json`，
观察保存在 `.observed/round.json`。它无需采用 Taluvia 的 SPEC/data 目录。
引用检查通过后仍停在明确的人工门；缺少检查证据不能完成。未选择的临时笔记变化
不影响绑定；选中的规范变化使旧轮失效。这里只验证映射与治理行为，没有实现或
运行 Python 产品。

在仓库根目录运行：

```sh
SAGE_TALUVIA_DOCSET=/mnt/d/Projects/Taluvia.Space/deliverables/Taluvia_Space_Docset_v1.12.0 \
  node --test tests/project-mapping.test.mjs
```

路径可替换为同一版本的显式本地目录。源文件不匹配捕获记录时测试失败，需先核对
变化再更新映射，不能自动接受新摘要。没有环境变量时，Taluvia 项明确 skip，
只运行小项目 fixture，不能据此声称实时验证了 Taluvia。当前一次显式本地运行
两项通过、无 skip；更完整的阶段状态仍以[进度](progress.md)为准。

这些证据覆盖 A02 的两种结构、引用保持和有界源文件不变，以及相关规范变更门禁。
不覆盖真实 Taluvia 产品开发、全需求追溯审计、宿主 hook、RSI 收益或最终人工验收。
