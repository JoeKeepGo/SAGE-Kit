# DSH 真实模型端到端验证（Linux/WSL headless）

日期：2026-10-24（本地，Pacific/Auckland）；UTC 运行时间 2026-10-23T16:07Z  
宿主：WSL2 Ubuntu 26.04.1 LTS；Node v22.22.1  
DSH：`@deepseek-ai/dsh@0.2.1-rc.2`（Linux npm 安装，真实 headless profile）  
SAGE-Kit：0.1.0（测试项目安装自本地 `sage-kit-0.1.0.tgz`）  
模型：**真实 DeepSeek 模型**（不是 mock）；API key 仅从隔离环境变量读取

## 结论摘要

| 事项 | 状态 | 说明 |
|---|---|---|
| 真实模型 headless 会话 | **PASS** | DSH 正常完成一次真实模型 turn |
| Skill 发现/加载 | **PASS** | 模型调用 `skill`，返回项目 `.dsh/skills/sage-kit` 内容 |
| 真实模型 → `bash` 工具 → SAGE-Kit CLI | **PASS** | 模型自行创建任务并列出 |
| 任务落盘与独立校验 | **PASS** | 任务 JSON 存在，`task list`/`task show` 由独立命令复核 |
| GUI 浏览器交互 | **NOT_EXECUTED** | 未打开浏览器操作 |
| hook 自动注入 `session.start` | **NOT_EXECUTED / NOT_AVAILABLE** | DSH 0.2.1-rc.2 未发现可安装的原生第三方 hook 配置 |
| Windows 真实宿主 | **NOT_EXECUTED** | 按策略 Windows 不作为测试执行环境 |

**结论边界**：本次证明真实模型能在 DSH headless 中发现并加载 SAGE-Kit Skill，并调用真实 `bash` 工具执行 SAGE-Kit CLI、创建可被独立校验的任务；不证明 GUI 行为、hook 生命周期或 Windows 宿主。

## 1. 凭据配置（不记录密钥）

- 密钥存放在隔离 WSL 环境 `/home/kayann/sage-kit-linux-dsh/.real-model-key`，权限 `0600`；启动脚本同样 `0700`。
- 密钥只通过启动环境变量 `DEEPSEEK_API_KEY` 注入，不写入仓库、报告、事件日志或最终答案。
- 启动脚本读取密钥后 `exec dsh --profile headless --json ...`；命令输出只包含 DSH 事件流。
- 未将隔离密钥复制到 Windows DSH GUI 凭据库；GUI 凭据与 headless 隔离环境分离。

## 2. 真实模型运行

工作目录：`/home/kayann/sage-kit-linux-dsh/project`（非 git 的 scratch 项目，`.sage-kit/` 已初始化）

执行：

```bash
/home/kayann/sage-kit-linux-dsh/run-real-dsh.sh \
  "You are in a scratch project initialized with SAGE-Kit. Use the sage-kit skill, then use the bash tool to run the SAGE-Kit CLI and create exactly one tracked task titled 'Real model DSH E2E' ..."
```

实际事件流（`work/dsh-linux/real-e2e/run-01/events.jsonl`，30 行，4 个 tool_call）关键序列：

```text
{"type":"tool_call","tool":"skill","input":{"name":"sage-kit"}}
{"type":"tool_result","status":"completed","result":"<skill_content name=\"sage-kit\">...Base directory .../.dsh/skills/sage-kit..."}
{"type":"tool_call","tool":"bash","input":{"command":"node node_modules/sage-kit/dist/cli.js task create --title 'Real model DSH E2E' --acceptance 'Task JSON exists and task list shows it'"}}
{"type":"tool_result","status":"completed","result":"Created task-20261023160745-26c829: Real model DSH E2E\n"}
{"type":"tool_call","tool":"bash","input":{"command":"node node_modules/sage-kit/dist/cli.js task list --json"}}
{"type":"tool_result","status":"completed","result":"... task-20261023160745-26c829 ... status ready ..."}
{"type":"tool_call","tool":"bash","input":{"command":"test -f .sage-kit/state/tasks/task-20261023160745-26c829.json && echo \"task JSON exists\""}}
{"type":"tool_result","status":"completed","result":"task JSON exists\n"}
{"type":"final","text":"Created exactly one task. Task ID: task-20261023160745-26c829 ... Appears in list: Yes ..."}
```

DSH 退出码 0，stderr 为空。

## 3. 独立校验（不经模型）

```bash
cd /home/kayann/sage-kit-linux-dsh/project
node node_modules/sage-kit/dist/cli.js task list --json
node node_modules/sage-kit/dist/cli.js task show task-20261023160745-26c829 --json
test -f .sage-kit/state/tasks/task-20261023160745-26c829.json
sha256sum .sage-kit/state/tasks/task-20261023160745-26c829.json work/dsh-linux/real-e2e/run-01/events.jsonl
```

结果：

- `task list`：仅 1 个任务，`id=task-20261023160745-26c829`，`status=ready`，title/acceptance 与 prompt 一致。
- `task show`：合法 JSON，任务文件存在。
- 证据哈希（本地 scratch）：
  - task JSON：`fa3693ef6a24a5af18d538f07732ae1bbc16510eeb0fc8d696721f3123f098e2`
  - DSH 事件流：`096065afa46bd1508fd5820f2d6416291d5934498c58687459c8ed3b599268f6`

## 4. 与 mock E2E 的区别

- `reports/p0/dsh-e2e-model.md`：使用本地 mock 模型，固定触发 `skill`→`bash`，用于证明宿主装配和工具链；**不证明模型判断**。
- 本报告：真实 DeepSeek 模型自主选择 `skill` 和 `bash`，完成创建/列出/文件校验；**证明真实模型路径可用**。
- 两者都不证明 GUI、hook 自动注入或 Windows。

## 5. 未执行 / 后续

1. **GUI 浏览器交互**：未在 DSH Web 中打开浏览器会话；HTTP 面已在 `reports/p0/dsh-linux-web.md` 复检。
2. **hook 自动注入 / `session.start`**：DSH 当前未发现可安装原生 hook；`sage-kit hook` 可由用户/宿主显式调用，未验证宿主自动注入。
3. **真实模型下的完整 `running → review → done --evidence` 生命周期**：本次只验证 create/list/show；状态机由自动化测试覆盖，未让真实模型走完 done。
4. **Windows 真实宿主**：未执行。
5. **密钥清理**：隔离环境的 `.real-model-key` 保留供后续复测；不提交仓库。若不再需要，删除该文件即可。

## 6. 证据文件（`work/dsh-linux/real-e2e/`，被 `.gitignore` 忽略）

- `run-01/events.jsonl`：真实模型事件流（30 行）。
- `run-01/stderr.log`：空。
- 任务文件：测试项目 `.sage-kit/state/tasks/task-20261023160745-26c829.json`。
- 隔离凭据：`/home/kayann/sage-kit-linux-dsh/.real-model-key`（0600，不在仓库内）。

报告与证据中不含任何密钥或 token。
