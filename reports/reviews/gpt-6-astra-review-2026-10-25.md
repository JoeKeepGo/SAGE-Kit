**总评：SAGE-Kit 已有真实可用的 CLI、文件任务流和 DSH 原生工具集成，但安全边界、状态归属与失败恢复仍存在可定位的缺陷；当前对外发布结论为 NO-GO。**

最优先处理三件事：

1. 阻止控制面接受跨站写请求，修正“loopback 等于同一 OS 用户”的安全假设。
2. 修复 RSI 的符号链接和路径别名绕过，避免候选修改受保护测试或写出临时工作区。
3. 修复安装资源的所有权记录，防止卸载删除安装时明确保留的用户目录。

以下 P0/P1/P2 表示**缺陷严重度**，与项目的 P0 里程碑不是同一概念。

本次严格按只读、离线方式进行，没有修改、创建或删除项目文件，没有安装依赖、访问网络或执行发布。审查对象是当前文件快照；`review-manifest.txt` 的 **242 条路径和字节数全部匹配**，但它不是内容哈希清单，且快照无 `.git`，因此无法独立证明全部内容对应 `3fa2c06`。

本轮实际执行了：

- Node 版本检查：`v24.22.0`。
- 现有 `dist/cli.js` 的 `version`、`--help`：正常，版本为 `0.1.0`。
- 3 项不会写文件的插件测试：全部通过。
- 52 个 `dist` JavaScript 文件的语法解析；字面量模块依赖图未发现循环。
- 若干直接加载现有代码、替换存储或网络依赖的**内存探针**。

没有执行全量 `npm test`、构建、打包、SQLite 打开或真实宿主会话。这些操作存在写入或联网副作用。下文将内存复现、静态事实与历史真实运行证据分别说明。

---

**问题清单中没有足够证据支持 P0 级事故判断，但以下 P1 足以阻塞发布。**

**F01 · P1 · 确定错误：控制面的跨站写入防护不成立。**

证据：[server.ts:263](D:/Projects/SAGE-Kit-review-copy/src/control/server.ts:263)、[server.ts:167](D:/Projects/SAGE-Kit-review-copy/src/control/server.ts:167)、[D-006](D:/Projects/SAGE-Kit-review-copy/docs/decisions.md:80)。

请求只检查连接地址和 Host，随后直接解析 JSON；没有 Origin 检查，也不要求 `Content-Type: application/json`。

本轮将以下输入直接送入实际路由函数，存储替换为内存对象：

```text
POST /v1/tasks
Host: 127.0.0.1:12345
Origin: http://untrusted.invalid
Content-Type: text/plain

{"title":"memory-only probe"}

结果：status=200，createTask 被调用。
```

冲突在于：文档把 loopback、Host 和无 CORS 当作足够的本地写入边界；实际上，**不允许跨站读取响应，不等于不允许跨站触发副作用**。

影响是：在允许网页访问 loopback 的浏览器环境中，恶意网页可能盲写任务、改变状态或触发恢复。浏览器自身的本地网络访问限制可能影响利用条件，但不能代替服务端防护；本轮未做浏览器端攻击复现。

最小修正：写端点检查精确同源 Origin，拒绝不支持的媒体类型，并明确无 Origin 的本地程序调用策略。无需因此引入 RBAC 或远程服务。

**F02 · P1 · 确定错误：RSI 的路径检查和受保护资产检查可以被符号链接绕过。**

证据：[candidate.ts:139](D:/Projects/SAGE-Kit-review-copy/src/rsi/candidate.ts:139)、[candidate.ts:167](D:/Projects/SAGE-Kit-review-copy/src/rsi/candidate.ts:167)、[validate.ts:144](D:/Projects/SAGE-Kit-review-copy/src/rsi/validate.ts:144)。

有三个具体问题：

- 应用候选前只做 `resolve()` 和字符串前缀检查；`writeFile()` 会跟随已有符号链接，父目录中的链接也没有检查。
- 受保护文件如果是符号链接，manifest 只记录链接目标字符串，不记录实际目标内容。
- `isProtectedPath()` 区分大小写，而 Windows 文件系统通常不区分。

可构造的受保护测试绕过：

```text
tests/check.test.mjs -> ../fixtures/check.mjs
候选修改 fixtures/check.mjs
```

`fixtures/check.mjs` 不命中默认保护目录，而 `tests/check.test.mjs` 的链接字符串没有变化。内存文件系统探针得到：

```text
candidateAllowed: true
targetReads: 0
detectedChanges: []
```

另外，直接调用现有校验函数得到：

```text
isProtectedPath("TESTS/check.mjs", DEFAULT_PROTECTED_PATHS) === false
```

冲突对象是 D-012“候选不能修改评估资产”，以及 M3“候选只写临时 worktree”的承诺。真实链接的文件系统破坏测试本轮未执行，但缺失的检查和绕过路径可以静态确定。

最小修正：候选落盘前检查目标及全部父路径的链接解析结果；受保护资产按实际文件归属保护，或明确拒绝评估资产中的符号链接；Windows 路径比较采用一致的大小写规则。修复必须发生在执行测试之前，不能仅靠执行后的 hash 检查。

**F03 · P1 · 确定错误：卸载会删除安装时保留的既有 Skill 目录。**

证据：[install.ts:125](D:/Projects/SAGE-Kit-review-copy/src/core/install.ts:125)、[install.ts:208](D:/Projects/SAGE-Kit-review-copy/src/core/install.ts:208)、[install.ts:258](D:/Projects/SAGE-Kit-review-copy/src/core/install.ts:258)。

已有目标目录且没有 `--force` 时，安装器明确保留目录，并返回空的安装文件列表；但随后仍把目标路径记入配置。卸载只检查路径是否等于适配器预期路径，然后递归删除整个目录，不检查所有权。

内存探针结果：

```text
filesOwnedAfterInstall: []
keptDuringInstall: true
skillDirectoryDeletedByUninstall: true
```

这与“保留用户文件”的安装语义冲突。影响包括用户自己维护的同名 Skill，以及多个项目共享的全局安装。

最小修正：记录“本次创建／接管／仅借用”的所有权；仅借用的目录不得删除。已拥有目录中的用户新增文件也应保留，或明确提示存在冲突。

**F04 · P1 · 确定错误：`run` 在注册进程事件监听器之前等待文件写入，可能漏掉启动失败或退出事件。**

证据：[runs.ts:87](D:/Projects/SAGE-Kit-review-copy/src/core/runs.ts:87)、[runs.ts:119](D:/Projects/SAGE-Kit-review-copy/src/core/runs.ts:119)。

顺序是：

```text
任务改为 running
→ spawn
→ await 写 run 文件
→ await 写事件
→ 注册 error / close 监听器
```

不存在的可执行文件可以在监听器注册前发出 `error`。本轮使用实际 `spawn`，将持久化替换成延迟的内存写入，得到：

```text
uncaughtError: ENOENT
settled: false
transitions: ["running"]
persistedStatuses: ["running"]
```

实际 CLI 默认会因未处理错误退出；任务可能已经是 `running`，而 run 记录还未可靠建立。`doctor` 主要扫描 run 记录，因此也不能保证修复这个窗口。

最小修正：`spawn` 后立即注册完整的事件处理，再做异步持久化；统一处理启动失败、正常退出、信号和存储失败，保证只完成一次，并建立可恢复的启动中记录。

**F05 · P1 · 确定错误：任务状态先写入，备注后校验，导致“报错但已提交”。**

证据：[tasks.ts:171](D:/Projects/SAGE-Kit-review-copy/src/core/tasks.ts:171)。

`updateTaskStatus()` 先保存新状态，再在构造事件时执行 `cleanText(options.note, ..., 2000)`。

本轮输入 2,001 字符备注，实际代码的内存执行结果：

```text
error: E_BAD_TASK
status: running
memoryWrites: 1
events: 0
```

影响同时覆盖 CLI 和插件：调用者看到失败后重试，却会遇到已改变的状态；事件审计也缺失。这不是只能由断电触发的跨文件事务问题，而是普通非法输入即可触发。

最小修正：所有输入校验和规范化必须先于第一次写入；增加“非法备注后任务与事件完全不变”的回归断言。

**F06 · P1 · 确定错误：CLI 与插件使用不同的项目根发现规则，在标准 worktree 中会操作不同状态。**

证据：[paths.ts:17](D:/Projects/SAGE-Kit-review-copy/src/core/paths.ts:17)、[lib.js:34](D:/Projects/SAGE-Kit-review-copy/packages/dsh-plugin/lib.js:34)、[index.js:47](D:/Projects/SAGE-Kit-review-copy/packages/dsh-plugin/index.js:47)。

CLI 找最近的 `.git`；插件找最近的 `.sage-kit/config.json`，不在 `.git` 边界停止。

对于项目自己的 worktree 布局：

```text
project/.sage-kit/config.json
project/.sage-kit/worktrees/task-demo/.git
```

从 worktree 中调用时，虚拟目录探针返回：

```text
CLI root:    project/.sage-kit/worktrees/task-demo
Plugin root: project
same: false
```

因此，“调用同一个库”不保证“操作同一份状态”。CLI 可能看不到插件任务，或创建另一套状态。嵌套独立仓库还可能被插件错误关联到父项目。

最小修正：共享一个明确的根解析函数，规定任务 worktree 如何映射到状态所属仓库；遇到无关的嵌套 Git 仓库应停止向上发现，而不是继续借用父项目配置。

**F07 · P1 · 确定错误：GitHub review comments 超过分页上限后，后续评论永久不可达。**

证据：[github.ts:243](D:/Projects/SAGE-Kit-review-copy/src/feedback/adapters/github.ts:243)、[sync.ts:115](D:/Projects/SAGE-Kit-review-copy/src/feedback/sync.ts:115)。

review comments 每次都从第一页按时间升序取，最多 10 页；cursor 仅用于本地过滤，没有保存分页续点。

本轮用注入的 `fetchImpl` 提供 1,001 条评论，没有发起网络请求：

```text
第一次：1000 条
第二次：1 条重复边界记录
cursorAdvanced: false
everRequestedPage11: false
item1001Seen: false
```

文档说明“每次最多 1,000 条”，但实际效果不是分批同步，而是第 1,001 条及后续内容无法到达。

最小修正：使用经接口版本确认的服务端增量参数，或保存分页续点；达到上限时明确返回未完成状态。验收应证明多次有限同步最终能够覆盖全部记录。

**F08 · P1 · 确定错误：RSI 中断后没有提案恢复路径，“逐 run 落盘”也与实现不符。**

证据：[evaluate.ts:427](D:/Projects/SAGE-Kit-review-copy/src/rsi/evaluate.ts:427)、[evaluate.ts:499](D:/Projects/SAGE-Kit-review-copy/src/rsi/evaluate.ts:499)、[run.ts:28](D:/Projects/SAGE-Kit-review-copy/src/rsi/run.ts:28)、[approve.ts:271](D:/Projects/SAGE-Kit-review-copy/src/rsi/approve.ts:271)。

提案先变为 `evaluating`，所有 baseline/candidate run 结果累积在内存，最后才保存 evaluation 和提案终态。

如果此间进程崩溃：

- stale lock 可以被接管；
- 提案仍为 `evaluating`；
- `runOnce()` 只选 `proposed`；
- 直接评估也只接受 `proposed`；
- `rejectProposal()` 拒绝 `evaluating`。

清理锁并没有恢复业务状态。正常写入 evaluation 后、写提案终态前的失败，也会留下类似不一致。

最小修正：增加显式恢复操作，根据持久化的尝试和 run 记录把孤儿评估标记为中断／失败；不得自动重跑。逐 run 证据应真实持久化，而不是仅写进最终 JSON 的数组。

---

**以下 P2 涉及接口可用性、契约冲突和发布证据。**

| 编号、性质 | 证据与冲突 | 实际影响及最小修正 |
|---|---|---|
| **F09 · 设计取舍未与权威 ADR 对齐** | [config.ts:48](D:/Projects/SAGE-Kit-review-copy/src/core/config.ts:48) 只接受文件模式；[cli.ts:624](D:/Projects/SAGE-Kit-review-copy/src/cli.ts:624) 独立打开控制面；D-005 要求所有写操作知道当前模式 | 文件任务与数据库任务可以同时存在、互不可见。没有发现某个普通操作同时复制写入两边，但也没有实现“互斥的两种运行模式”。应选择：落实模式检查，或通过新 ADR 明确两套独立任务域，并在 UI/CLI 中显示归属。 |
| **F10 · 确定错误** | [cli.ts:564](D:/Projects/SAGE-Kit-review-copy/src/cli.ts:564) 的 `control status` 使用默认可写打开；[store.ts:340](D:/Projects/SAGE-Kit-review-copy/src/control/store.ts:340) 获取写锁 | 服务运行时，另一个进程执行状态查询会撞写锁；新目录查询还会创建数据库。改为真正只读查询，数据库不存在时报告未初始化。注意当前构造器即使 `readOnly` 也先调用 `ensureControlPaths()`。 |
| **F11 · 确定的幂等契约缺口** | [server.ts:315](D:/Projects/SAGE-Kit-review-copy/src/control/server.ts:315) 不传 `idempotencyKey`，而 [store.ts:426](D:/Projects/SAGE-Kit-review-copy/src/control/store.ts:426) 已支持；AGENTS 要求副作用幂等 | HTTP 响应丢失后重试可创建重复任务。UI 按钮忙态不能解决这个问题。让 API 接收幂等键，UI 在同一次创建的重试中复用它。 |
| **F12 · 确定错误** | [package.json:12](D:/Projects/SAGE-Kit-review-copy/package.json:12) 只导出根入口和 package.json；[M2 文档:97](D:/Projects/SAGE-Kit-review-copy/docs/m2-control.md:97)、[M3 文档](D:/Projects/SAGE-Kit-review-copy/docs/m3-rsi.md) 宣传包内 `dist` 子路径 API | 本轮实际导入 `sage-kit/dist/control/index.js`、`sage-kit/dist/rsi/index.js` 均返回 `ERR_PACKAGE_PATH_NOT_EXPORTED`。提供明确的受支持子路径，或撤回它们是外部公共 API 的表述。 |
| **F13 · 确定错误** | [server.ts:356](D:/Projects/SAGE-Kit-review-copy/src/control/server.ts:356) 仅转发 `taskId/limit`，M2 文档还声明 `runId/type` | `/v1/events?runId=run-a&type=run.finished` 的内存探针实际转发 `{}`，过滤被静默忽略。应实现过滤，或拒绝不支持的参数并同步契约。 |
| **F14 · 确定的文档冲突／证据不足** | [README:28](D:/Projects/SAGE-Kit-review-copy/README.md:28) 和平台文档称 Windows 不执行套件，AGENTS 又称 Windows 103 项通过；[architecture.md:262](D:/Projects/SAGE-Kit-review-copy/docs/architecture.md:262) 仍写 `better-sqlite3`，实现使用 `node:sqlite`；[M2 文档:325](D:/Projects/SAGE-Kit-review-copy/docs/m2-control.md:325) 错写 engines 为 `>=22.20` | 影响用户选环境、安装和判断支持范围。用带版本、日期和产物引用的支持矩阵替换互相冲突的现状段落；历史报告保留，但标明适用快照。 |
| **F15 · 确定的 schema 缺陷** | [插件 index.js:71](D:/Projects/SAGE-Kit-review-copy/packages/dsh-plugin/index.js:71)、[index.js:137](D:/Projects/SAGE-Kit-review-copy/packages/dsh-plugin/index.js:137)：`sage_task_show` 的 `id` 没有 `required:true` | 无参调用可以越过 schema 的必填检查，进入核心读取路径并产生误导错误。把必需字段写进 schema，并验证缺参在执行前被拒绝。 |

其中 F09 是权威契约冲突，F11 是明确的幂等要求缺口，不宜仅作为普通文案问题留待发布后处理。

---

**架构基本分层合理，但“同一个库”“不同目录”“单一权威”三个概念目前混在了一起。**

实际组件与写入路径如下：

```text
宿主 Skill / AGENTS 指令
             │
             ▼
           CLI ────────────────┐
             │                 │
DSH 插件 → 根库 index.ts       │
             │                 │
             ▼                 ▼
      core 文件任务 API     control serve / UI / HTTP
             │                 │
             ▼                 ▼
 .sage-kit/state/**      .sage-kit/control/control.db
 task / run / event       task / run / event / lease

feedback sync → .sage-kit/feedback/**
                       │
                       └──→ core.buildBrief → CLI / DSH 注入

rsi create / run-once / approve
             │
             ▼
       .sage-kit/rsi/**
             │
             ├──→ 临时 Git worktree → 固定评估命令
             └──→ 显式 record-control → M2 摘要记录
```

值得保留的设计：

- 核心没有运行时第三方依赖；DSH 专有导入位于独立插件包。
- 控制面和 RSI 由 CLI 动态加载，默认文件任务路径不需要 SQLite。
- 插件直接复用任务和 brief 函数，没有复制任务状态机或另建数据库。
- RSI 的控制面记录是显式摘要投影；提案、审批的权威实体仍在文件层，这一点不能简单算作违规双写。
- 没有发现需要删除的通用事件总线、规则引擎或多租户抽象。

需要收紧的结构：

- 根库实际依赖 `core/brief → feedback/store`，说明 brief 已承担反馈组合职责；这是可接受的小耦合，但不能再描述为完全独立的 P0 核心。
- 状态转换表在 core、control、UI 中有副本。UI 副本用于交互可以接受，两个服务端副本应共享一个纯规则模块。
- 插件和 CLI 的根解析不同，是实际状态分叉；两套任务存储并行，则是尚未解决的产品归属问题。
- 文件模式无锁、无跨文件事务、无通用幂等键，文档已有诚实说明。这是边界，不应把它宣传为支持同一任务的并发写入。
- 原子替换只能保护单个文件；不能由此推导任务、run、事件、审批多文件更新整体原子。

没有必要为这些问题重建平台。共享根解析、纯状态规则、输入预校验、资源所有权和有限的恢复记录即可解决主要缺陷。

---

**安全判断：当前实现适合受信任用户操作本地项目，尚不构成处理恶意候选的隔离环境。**

已经实现的防护包括：

- 参数数组调用外部命令，主要路径使用 `shell:false`。
- 任务 ID 白名单；普通 `../` 路径输入会被拒绝。
- 控制面固定绑定 `127.0.0.1`，校验远端地址与 Host。
- HTTP 请求体大小限制、SQL 参数绑定、UI 动态文本使用 `textContent`，并提供 CSP 和禁止嵌入措施。
- 外部反馈压平、截断、标记为不可信数据；没有自动执行反馈文字的代码路径。
- 审批 token 随机生成、只保存 hash、检查期限并使用定时安全比较。
- 没有自动 merge、publish 或后台 RSI 调度路径。

仍需准确表达的边界：

1. **TCP loopback 不验证 OS 用户。** 当前服务不能区分同机不同账户的客户端。可以把这种访问明确列为接受风险，但不能声称代码实现了“同一账户边界”。
2. **Git worktree 是工作目录隔离，不是权限沙箱。** [process.ts:35](D:/Projects/SAGE-Kit-review-copy/src/rsi/process.ts:35) 继承完整 `process.env`，只剥离几个测试变量。被测试代码仍可能访问密钥、主仓库、用户目录和网络。静态检查 RSI 源码没有 `fetch`，不能证明被执行代码不会联网。
3. **固定命令不等于固定行为。** 固定测试命令会加载候选代码；执行后 hash 也不能阻止候选先修改文件、再恢复内容。D-012 当前是一组检查，不是对抗恶意代码的完整隔离。
4. **审批 token 证明持有挑战值，不证明真人批准。** `decidedBy` 是声明字符串，文档已经承认这一点。由于批准只写记录、没有执行发布，目前没有发现它自动触发代码应用。
5. **脱敏不是统一保证。** 事件和部分日志有启发式脱敏，但任务标题、验收、证据会进入 brief。插件 README“brief 不含 token/密钥”的绝对表述过强，应改为“不主动读取环境密钥”，并说明用户文本可能包含敏感内容。
6. **进程终止不覆盖完整进程树。** RSI 仅终止直接子进程；P0 `run` 甚至没有超时／取消。后者已有披露，但与 AGENTS“所有外部命令必须有超时”的字面规则仍冲突。

本次没有找到可确认的全局 prototype pollution 或普通 shell 参数拼接注入；这不抵消已确认的跨站写入和路径别名问题。

DSH 插件增加了 agent 可直接调用的任务写工具，但没有增加独立的 OS 权限。是否符合宿主只读模式或工具审批策略，当前快照缺少对应宿主策略测试，不能接受“完全没有扩大未授权写入面”的强结论。

---

**DSH 插件的真实集成证据成立，但范围比“插件全面验证通过”窄。**

我核对了原始 `session.v4.jsonl`，而不只看报告结论：

- 早期 mock 场景确实有五个原生 `sage_*` 工具调用，以及三条 brief 注入。
- 早期真实模型场景有 `skill` 和四个原生任务工具调用，不是仅靠 `bash → CLI` 间接完成。
- 修复后 `final-postfix/scenario-a` 有五个原生工具调用，以及两条 `source:{kind:"sage-kit"}` brief。不能把早期场景的“三条注入”直接套到这次复跑。
- `final-postfix/summary.json` 的 `injectedCount:0` 来自旧解析规则；报告已注明这一限制。原始 session 证明不是零注入，但汇总脚本需要修正。
- tiny-notes 保存了 `done` 任务、三条 `dsh-plugin` evidence、四条 brief 和 4/4 测试输出，支持一次真实任务完成闭环。

对应证据：[插件原始会话](D:/Projects/SAGE-Kit-review-copy/reports/plugin/evidence/real-model/session.v4.jsonl)、[修复后会话](D:/Projects/SAGE-Kit-review-copy/reports/plugin/evidence/final-postfix/scenario-a/session.v4.jsonl)、[tiny-notes 最终任务](D:/Projects/SAGE-Kit-review-copy/reports/plugin/evidence/sandbox-tiny-notes/task-done.json)。

代码还支持以下判断：

- 自动 brief 在 `next()` 返回后组合消息；遇到拒绝决定不注入。
- 去重缓存按 session 对象隔离，指纹来自最终 brief 内容。
- brief 构建异常会记录警告并返回原决定。
- `autoBrief:false` 有实现分支。
- 插件不调用网络或 shell。

但以下仍不能升级为 `VERIFIED`：

- 多 session 并发状态写入安全。
- compaction 后重新注入；当前仅按指纹去重，文档已承认可能丢失 brief。
- 宿主只读／审批策略下的写工具行为。
- 完整故障降级、配置损坏、慢文件读取的时限。
- Windows/macOS 和 DSH Web 插件路径。
- 插件卸载、版本拒绝等没有对应完整产物的场景。

尤其是自动 brief 每个 step 都重新构建、读取任务和反馈，然后才比较指纹；没有自己的时间预算。**输出字节数有限，不等于执行成本有限。**

---

**测试与证据矩阵如下。`IMPLEMENTED` 表示代码存在；`VERIFIED` 必须限定验证对象与环境；历史通过不等于本轮重新通过。**

| 范围／声称 | 实际证据 | 结论与缺口 |
|---|---|---|
| 全量 103 项测试 | 测试声明确为 CLI 23、feedback 13、control 38、RSI 19、API 6、plugin 4；报告记载 103/103 | 测试数量可复核；全量结果属于历史证据。本轮 `NOT_EXECUTED` |
| P0 A1–A12 | 测试代码使用真实临时文件、Git、离线 tarball 安装和真实 SIGKILL；另有模拟 stale run | 不是全 mock。但未覆盖 F03–F06 等失败路径；本轮未执行写入测试 |
| 构建及现有 dist | 52 个 JS 可解析，CLI help/version 正常 | 现有 JS 的这些性质 `VERIFIED`；TypeScript 构建及 src/dist 全量一致性 `NOT_EXECUTED` |
| 库与插件回归 | 6 个库 API 测试；4 个插件测试主要覆盖 lib、manifest、源码模式 | 本轮安全选择的 3 项通过；不能把它们当作 `apply()`、pre-step 和真实 DSH 的完整自动化回归 |
| M1 真实同步 | GitHub 公共仓库、WSL Gitea 1.27.3 的报告与产物；fixture 覆盖分页 | 有历史真实证据；GitHub真实非空 review comments 等仍未验证，且 F07 已有当前反证 |
| M2 store/API/UI | 38 项覆盖真实 SQLite、HTTP、状态、lease、恢复；UI检查以返回内容和脚本解析为主 | `IMPLEMENTED`，有历史集成证据；不能等同浏览器完整交互与跨站安全验证 |
| M3 评估 | 19 项包含真实 Git worktree、固定命令、基线、重复、超时、审批 | 正常受控候选路径有历史证据；恶意链接、权限隔离和评估中断恢复不足 |
| DSH 原生工具 | 原始 session 有原生 tool/call、tool/result、任务落盘及 brief | 指定 Linux/WSL2、DSH 0.2.1-rc.2 路径有真实历史证据，不只是 CLI 间接调用 |
| CI 与打包 | Linux 主 job 含干净打包和离线安装；插件 job 固定宿主版本 | 配置 `IMPLEMENTED`；没有 Windows CI。插件工具链安装失败允许跳过，绿色工作流不能证明插件门禁执行 |
| tiny-notes 产品闭环 | diff、4/4 输出、done 任务、session brief 产物 | 单次历史产品结果有证据；完整沙箱项目缺失，不能从本快照完整重建 |

具体缺失路径已经确认：

```text
.git
node_modules
work/sandbox/tiny-notes
work/plugin-e2e/prep/run-scenarios.sh
work/plugin-e2e/prep/mock-plugin-model.mjs
```

其中 `work/` 缺失符合快照说明，**不是产品实现缺陷**；但依赖这些文件的复现说明不能被当作自包含的发布验收流程。

本轮执行的无写入测试命令为：

```powershell
node --test --test-name-pattern='clamps|manifest|source does' tests/plugin.test.mjs
```

结果为 3/3。内存探针证明的是实际函数在受控依赖下的行为，不冒充真实浏览器、磁盘故障或宿主 E2E。

---

**M1/M2/M3 的实际闭环，需要按下面的边界理解。**

| 环节 | 当前实际行为 | 判断 |
|---|---|---|
| 外部反馈进入本地 | 同步、规范化、去重、存储，brief 带最新一条 | `IMPLEMENTED` |
| 反馈自动生成任务／提案 | 没有自动分类、建任务或候选生成链路 | `NOT_IMPLEMENTED`；M1 专题文档有说明 |
| M2 面板操作任务 | 可以创建、转状态、获取／续期／释放 lease、恢复 stale | `IMPLEMENTED`，不是只读面板 |
| M2 驱动执行 | 不启动／监督任务进程，不把 CLI 文件任务自动纳入数据库 | 明确设计边界 |
| M3 候选评估 | 用户提供候选 JSON 和固定命令，临时 worktree 中执行 | `IMPLEMENTED` |
| M3 批准后应用代码 | 只写审批记录，不把候选写回主工作区 | `NOT_IMPLEMENTED`，且没有自动动作 |
| 发布与回滚 | 发布由人另做；回滚点主要是记录和命令指引 | 自动发布／回滚不实现，符合当前范围 |

所以，“反馈 → 提案 → 评估 → 批准”并非一条已经自动接通的产品链路。用户仍需读取反馈、准备候选 JSON、选择命令、审阅结果、手动应用代码并发布。

**这些人工步骤不应全部被算作缺陷。** 自动合并、发布、调度本来就不在目标内；真正的问题是 README 的总体闭环措辞容易掩盖“反馈到提案尚需人工搬运”，以及 M2、文件任务、RSI 默认互不感知。

---

**我不接受现有文档或先前助手结论中的以下推导。**

- “103/103，所以整体正确。”测试数量不能覆盖未经测试的异常窗口；本轮已经找到多个可复现反例。
- “只有 loopback、无 CORS，所以只有同机同用户能安全写。”地址检查既不认证 OS 用户，也不阻止所有跨站副作用。
- “worktree 隔离，所以恶意候选不会影响主工作区。”工作目录隔离没有撤销进程权限，且候选写入存在符号链接缺口。
- “插件和 CLI 使用同一个库，所以一定共享同一状态。”它们的根目录解析明确不同。
- “M2 不写 `.sage-kit/state`，所以完成了模式互斥。”这只能证明分开存储，不能证明当前模式有唯一权威。
- “RSI 已逐 run 持久化、可恢复。”当前 run 结果在内存累积，`evaluating` 没有正常恢复出口。
- “没有自动发布就是闭环未完成的缺陷。”我不接受这个反向推论；人工发布符合 D-011，不应为了补功能数量破坏边界。

先前插件评审中 F-1/F-2 的修复可以从当前代码和修复后 session 核实，我不把已修复问题重复列为开放缺陷。但其“安全未发现阻塞问题”的结论不足以覆盖本次发现的共享核心问题。

---

**发布就绪度：NO-GO；可以继续受控开发试用，不应把当前快照作为完成整体验收的发布候选。**

阻塞项是 F01–F08，以及 F09 的权威模式契约冲突。发布前还必须解决对外 API 导出、幂等入口和证据门禁的准确性。

已经具备的基础不应被忽略：两个包都有 MIT 许可证，存在安全策略、核心打包白名单、独立插件包、版本字段和较多真实集成产物。

仍缺少的发布交付内容包括：

- 明确的核心／插件版本兼容及升级策略。
- 变更日志和当前候选的发布说明。
- 状态 schema 升级、失败恢复和用户数据保留策略；当前 RSI v1 记录被当作损坏处理，不是迁移。
- 可实际使用的私密安全报告入口，而不仅是“联系维护者”。
- 与最终交付 tarball 绑定的验收记录。
- 对插件发布真正有效的必执行门禁；现有 `continue-on-error` 加 warning 只能说明跳过，不能证明通过。

**最小修复顺序与验收标准如下；本次没有实施这些修改。**

| 顺序 | 修复范围 | 可执行验收标准 |
|---|---|---|
| 1 | F01 控制面请求边界 | 恶意 Origin、`text/plain`、表单类型写入均被拒绝，任务／lease／事件完全不变；同源 UI 与明确支持的本地客户端仍可操作 |
| 2 | F02 RSI 路径与资产保护 | 外部目标 symlink、父目录链接、受保护测试别名和 Windows 大小写变体均在执行前拒绝；外部哨兵文件保持不变 |
| 3 | F03 安装资源所有权 | 预置用户 Skill → init 不覆盖 → uninstall；目录与内容逐字节不变；正常卸载仅删除自己拥有的资源 |
| 4 | F04、F05 执行与提交顺序 | 不存在的命令、极快退出、存储失败都产生一次明确终态；非法 note/evidence 不产生任何写入 |
| 5 | F06、F09 状态归属 | 在主仓库、任务 worktree、嵌套独立仓库中，从 CLI 与插件定位到预期相同状态；模式冲突明确拒绝或明确显示独立任务域 |
| 6 | F08 RSI 恢复 | 在标记 evaluating 后、单个 run 后、evaluation 保存后分别中断；恢复得到一致可审计状态，重复恢复幂等，且绝不自动重跑 |
| 7 | F07、F10–F13 接口完整性 | 多次有限同步取得第 1,001 条评论；服务运行中可查询状态；相同幂等键只建一个任务；导出的 API 可从安装包导入；事件过滤准确 |
| 8 | F14、F15 与最终交付验收 | 修正 schema 和现状文档；保存必要 E2E harness；按实际承诺平台验证最终 tarball，并把结果绑定到内容哈希 |

下一轮评审应先针对这些边界做回归，再对最终候选执行一次完整测试、打包安装及指定版本的 DSH 验收；无需新增插件系统、调度器或远程控制面。