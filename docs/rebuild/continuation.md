# R1 本地持续执行约定

依据 [SPEC](SPEC.md)；本文件先定义实现与验收，不替代目标项目规范。
治理 Skill 无新增必装依赖。可选 `adapters/continuation.mjs` 使用 Node >=22 内置模块，
通过模块导出供宿主调用；无 CLI、模型调用、服务器、自动安装或发布。

## 接入与权威

`openContinuation({ root, planPath, statePath })` 返回 `inspect/begin/finish`。
root 为项目目录；planPath、statePath 是项目内显式相对路径，无固定项目目录布局。
plan 由已授权控制者从现行项目计划映射，不能由外部反馈授权；state 仅存执行观察。
项目规范及计划摘要 SHA-256 绑定该轮执行；任何变化停止进一步准入，要求控制者
核对差异、旧执行副作用与新授权后创建新的 state 路径。不得自动删记录重新开始。

plan JSON：`version:1`、`goal`、`authority:[相对文件路径]`、`constraints:[文本]`、
`maxAttempts`、`expiresAt`、`revoked:boolean`、`steps:[...]`。
每 step 有 `id`、`objective`、`dependsOn:[id]`、`scope:[相对路径]`、`checks:[检查名]`、
`requiresReview:boolean`、`admitted:boolean`、`humanGate:boolean`。
所有 step 明确指定这些字段；Light 可 `requiresReview:false`，checks 按项目要求选择。
拒绝重复/不存在的依赖及循环，拒绝不安全相对路径、symlink 路径与损坏状态。

## 三个操作

- `inspect()`：只读当前规范摘要与约束，返回 `action`、`step`（如有）和 `context`。
  `context` 包含完整 goal/constraints、权威引用/摘要及当前 step 的范围/必要检查。
  输入大小有界；超限报错，不静默截断治理条件。宿主可在开始/恢复/压缩后调用。
- `begin(stepId, attemptId)`：必须匹配 inspect 选出的下一项；先原子保存 intent，
  再返回 step 给宿主执行。attemptId 为宿主生成的幂等键，重复调用不启动第二次操作；
  返回 `replayed:true` 时宿主不得重执行。模块自身从不执行 step 的 shell/模型操作。
- `finish(attemptId, result)`：宿主提交 `outcome:passed|failed|not_executed`、
  `checks:[{id,passed:boolean,evidence:相对文件路径}]`，需要评审时附 `review` 文件路径。
  passed 必须覆盖当前 step 的全部必要 checks 且均 passed，并提供所需评审引用；
  evidence/review 文件必须存在，按内容摘要保存。重复同一结果返回原记录；不同结果拒绝。
  failed/not_executed 不意味着通过，也不表示产品被接受。

`action`：`continue`、`reconcile`（已有未结束 intent，先核对是否执行过）、
`human_gate`、`budget_exhausted`、`revoked`、`expired`、`authority_changed`、
`evidence_changed`、`reassess`（同一 step 两次失败）、`blocked`（无可执行依赖）、
`complete_pending_acceptance`。终止/阻塞时不生成新执行；独立已准入 step 可先推进。
恢复后的 finish 是控制者核对事实后的显式记录；模块不能从 PID/会话消失推断未执行。
已通过 evidence 被更改/删除时停止下游准入，避免继续使用失效证明。

## 持久化与信任边界

同一 state 使用独占创建锁文件，空锁/损坏锁也拒绝接管；不自动偷锁。写入用
临时文件 + fsync + rename，锁覆盖完整读改写。崩溃遗留锁由人/控制者先确认无活跃
写入者再清理；正常中断测试在 begin 返回后杀宿主，此时不持写锁。
文件完整性不等于抗同用户篡改，不承诺 TOCTOU 隔离、断电或 Windows 全进程树恢复。
scope 是提供给宿主的约束；模块不检查任意 shell 的实际写入路径，也不是安全沙箱。
checks 与 review 是宿主提交的可追溯证据引用，摘要防止事后换证据，不证明内容真实
或评审者独立；真实验证、独立评审和人类验收仍由项目治理承担。

## 实现前验收

1. 三个依赖步骤，真实本地命令写出结果/检查文件，经 finish 后继续，不逐项审批。
2. 失败后修复一次可继续；同一步两次失败转 reassess；Light 不强制 review。
3. begin 后进程真实 SIGKILL，重新打开只返回 reconcile，不重复外部副作用；
   核对遗留结果并 finish 后才可继续。
4. 未准入、人类门、撤销、预算/到期、规范变更、证据变更均不返回 continue。
5. 重复 begin/finish 幂等；冲突结果拒绝；空锁不接管；损坏状态不当作新项目。
6. 两种不同文件布局映射同一约定；无网络/模型调用，不修改原规范文件。

这些是本地组件/fixture 验收，不证明 DSH、Codex、Claude 的实际 hook 接入。

## 资源边界与验收

单次 inspect/begin/finish 的输入读取上限为 **8 MiB、128 个不同文件**；路径最多
32 段；保持计划 64 KiB、单个规范/证据 1 MiB、状态 4 MiB 的现有上限。
上限是当前工程预算，不是已测性能承诺。读取器按文件实际大小分配有界缓冲，
读入期间增长则拒绝，不先读完整个大文件再判断。单次调用相同文件只读/哈希一次；
不同调用重新核验内容，不用 mtime 缓存掩盖规范或证据变化。

inspect 返回 `io: {filesRead, bytesRead}` 表示本次实际输入内容读取量，不是操作系统物理
磁盘 IO（不含 metadata、锁文件和持久化）。不为统计写日志。预算超限抛出
`E_READ_BUDGET`，不得自动紧循环重试；先缩小本轮规范/任务范围或评估新的资源预算。
已有证据变更仍为 evidence_changed；资源错误单独报告，不能混成证据损坏。
幂等重放保持 state 文件内容及 mtime 不变；inspect 不创建状态文件、不启动子进程。

新增验收：大量重复证据引用不增加实际内容读取次数；多个合法大文件的总量超限
被明确拒绝；文件数超限不继续；同大小/mtime 内容变更仍被发现；幂等调用不重写
state；以代表性 fixture 测量多次 inspect 的 wall/CPU 时间和逻辑读量。将来 DSH
接入必须另外测试事件频率、注入去重、长会话及 RSI 预算，当前组件测量不能代替。

写入前同样检查序列化 state 不超过 4 MiB；超限抛出 `E_STATE_BUDGET`，原文件保持
不变，未完成 intent 仍待核对。控制者核对已执行副作用并归档本轮后才能开新轮；
不能通过无限追加记录产生“写成功但恢复时读不回”的状态，也不能自动清空历史。

## 本次重建的 RSI 用法

以进度文档记录观察、假设、修复/候选、针对性测试、独立评审和采用边界。
用户已授权的普通 bug 修复可继续；治理策略/Skill 的自我修改只提出候选，不自动采用。
本轮使用模型执行的受控改进流程；归档 RSI 程序尚未移植，不能称为已经运行 R3。
