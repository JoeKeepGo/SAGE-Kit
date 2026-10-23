# DSH 模型驱动端到端验证（Linux/WSL，确定性 mock 模型）

日期：2026-10-24（本地，Pacific/Auckland）；UTC 运行时间 2026-10-23T15:12:39Z–15:13:54Z  
宿主：WSL2 `6.18.33.2-microsoft-standard-WSL2` / Ubuntu 26.04.1 LTS  
运行时：Node v22.22.1、npm 9.2.0  
DSH：真实 npm 包 `@deepseek-ai/dsh@0.2.1-rc.2`（`/home/kayann/sage-kit-linux-dsh/node_modules`，`dsh --version` = `0.2.1-rc.2`）  
SAGE-Kit：0.1.0，测试项目安装自 `pkg/sage-kit-0.1.0.tgz`，sha256 `ae040089d7123e6a5bc2d8b5a3302e86610c3512c424f09af9263146cda744ab`  
环境：隔离 `DSH_HOME=/home/kayann/sage-kit-linux-dsh/home`；测试仓库 `/home/kayann/sage-kit-linux-dsh/project`（非 git 仓库，DAG 校验不依赖 git）  
模型：本地 Anthropic Messages mock 端点（**不是真实模型**，无外网模型调用）

## 结论摘要

| 事项 | 状态 | 说明 |
| --- | --- | --- |
| 真实模型 E2E | **NOT_EXECUTED** | 隔离 WSL 环境无真实 `DEEPSEEK_API_KEY`/模型账号凭据，见 §1 |
| 宿主装配 + Skill 发现/加载 | **PASS（mock 模型）** | 真实 DSH headless + 真实 SAGE-Kit CLI，mock 模型触发 `skill` |
| Skill → bash 工具 → SAGE-Kit CLI 创建任务/列表 | **PASS（mock 模型）** | 24/24 独立检查通过，见 §2.4 |
| Linux DSH Web HTTP 面 | **PASS（复检）** | 401/303/200、SPA 37,512 B；服务已停止，无残留监听 |
| 真实模型行为、GUI 浏览器交互、hook 自动注入 | **NOT_EXECUTED** | 见 §5 |

**证据分级（必须分开表述）**：

- 本节 E2E 证明的是 **DSH 宿主 wiring**：Skill 能被发现并加载、模型可见 `bash` 工具、bash 工具真实执行、SAGE-Kit CLI 落盘可被独立校验。
- 它 **不证明** 真实模型会正确选择/使用这些工具，也不证明 GUI 或 hook 生命周期。

## 1. 真实模型凭据核查（未打印任何密钥）

核查范围是隔离 WSL 环境（`DSH_HOME=/home/kayann/sage-kit-linux-dsh/home`、项目 cwd、`$HOME`）：

- 环境变量 `DEEPSEEK_API_KEY`、`ANTHROPIC_API_KEY`、`OPENAI_API_KEY`、`DSH_API_KEY` 均为 unset（只检查是否存在/长度，不输出值）。
- `<cwd>/.env`、`<DSH_HOME>/.env`、`$HOME/.env` 均不存在（headless 的 API-key 回退链为空）。
- 隔离 `$DSH_HOME/.credentials.yaml` 只含 `client-connection/browser-session`（Web 启动 token），**没有模型凭据**。
- 无凭据直接跑真实 provider 的失败证据（`work/dsh-linux/no-credential-check.log`）：

```text
{"type":"status","phase":"turn_end","turn":1,"reason":{"kind":"error",
 "error":{"message":"llm-deepseek: no API key for provider route \"deepseek-official\";
 store DEEPSEEK_API_KEY through the credentials service (the web Models page writes it),
 or export DEEPSEEK_API_KEY in the launching environment","code":"MISSING_CREDENTIAL"}}}
dsh: MISSING_CREDENTIAL: llm-deepseek: no API key ... 
exit_code=1
```

边界说明：Windows 桌面 DSH 的凭据存储（`C:\Users\KayAnn\.dsh\.credentials.yaml`）中存在
`deepseek-account-platform/device`、`deepseek-account-platform/default` 记录，但它 **不在隔离 WSL 环境内**；
且 headless profile 明确禁用托管凭据/授权/账号消费端（`@deepseek-ai/dsh-headless/cordis.patch.yml`：
`- id: credentials / authorization / deepseek-account`，均 `disabled: true`），
所以该账号凭据不能直接被 headless 路径使用。未提取、未复制、未打印任何凭据内容；真实模型运行因此记为 NOT_EXECUTED。

## 2. 确定性 mock 模型 E2E（宿主装配证据）

### 2.1 被测对象与 mock 设计

- 测试仓库是已 `sage-kit init --host dsh --scope project` 的项目：`.dsh/skills/sage-kit/SKILL.md`、
  `AGENTS.md` 受管块、`.sage-kit/config.json` 均在位。
- mock 端点：`work/dsh-linux/mock-task-e2e.js`（本地 `http://127.0.0.1:18765/v1/messages` SSE）。
  它是**模型替身**，按请求体状态机决策，不参与任何真实模型推理：

```text
tools 存在 + 尚无 tool_result            -> tool_use skill {name:"sage-kit"}
tools 存在 + 已有 tool_result、无 bash   -> tool_use bash {command:"<SAGE-Kit CLI task create && task list>"}
tools 存在 + 已有 bash tool_use          -> 最终文本
tools 为空（会话标题请求）                -> 短文本
```

- 编排脚本：`work/dsh-linux/run-task-e2e.sh`；独立校验器：`work/dsh-linux/verify-e2e.mjs`。
  运行时 `DEEPSEEK_BASE_URL=http://127.0.0.1:18765`，`DEEPSEEK_API_KEY` 为占位符（非真实密钥）。

### 2.2 命令与运行事实

```bash
# WSL 内执行（工作目录 /home/kayann/sage-kit-linux-dsh/project）
RUN_ID=run-02 /mnt/d/Projects/SAGE-Kit/work/dsh-linux/run-task-e2e.sh
```

脚本内部的真实 DSH 调用（prompt 逐字）：

```bash
/home/kayann/sage-kit-linux-dsh/node_modules/.bin/dsh \
  --profile headless --json \
  "Use the SAGE-Kit skill in this repository to create one tracked task for this test run, then confirm that it appears in the task list."
```

运行事实（`work/dsh-linux/run-02/environment.txt`）：

```text
dsh_version=0.2.1-rc.2           dsh_package=0.2.1-rc.2
sage_kit_cli_version=0.1.0       project=/home/kayann/sage-kit-linux-dsh/project
dsh_home=/home/kayann/sage-kit-linux-dsh/home
permission_mode=<shipped-default:workspace-write+ask>
DSH exit code: 0                 dsh-stderr.log: 0 字节
mock 请求数: 4（3 次主请求带 25 个工具 + 1 次会话标题请求 tools=0）
```

mock 侧决策记录（`run-02/mock-server.log`）：

```text
POST /v1/messages request=001 bytes=60794 messages=1 tools=25 decision=tool:skill
POST /v1/messages request=002 bytes=36727 messages=1 tools=0  decision=text
POST /v1/messages request=003 bytes=39876 messages=3 tools=25 decision=tool:bash
POST /v1/messages request=004 bytes=42017 messages=5 tools=25 decision=text
```

### 2.3 真实 DSH 事件流（`run-02/dsh-events.jsonl`，节选）

```text
{"type":"tool_call","callId":"toolu_mock_001","tool":"skill","input":{"name":"sage-kit"}}
{"type":"tool_result","callId":"toolu_mock_001","status":"completed",
 "result":"<skill_content name=\"sage-kit\">...Base directory for this skill: /home/kayann/sage-kit-linux-dsh/project/.dsh/skills/sage-kit..."}

{"type":"tool_call","callId":"toolu_mock_003","tool":"bash",
 "input":{"description":"Create and list the SAGE-Kit task","command":"node /home/kayann/sage-kit-linux-dsh/project/node_modules/sage-kit/dist/cli.js task create --title \"DSH mock-model E2E: create a tracked task\" ... && node .../cli.js task list"}}
{"type":"tool_result","callId":"toolu_mock_003","status":"completed",
 "result":"Created task-20261023151241-22d6e3: DSH mock-model E2E: create a tracked task\nID                           STATUS    TITLE\ntask-20261023151241-22d6e3   ready     DSH mock-model E2E: create a tracked task\n"}

{"type":"final","text":"Created one SAGE-Kit task by running the SAGE-Kit CLI through the DSH bash tool, then confirmed it with `sage-kit task list`."}
```

要点：`skill` 的工具结果来自 **项目内** `.dsh/skills/sage-kit`；`bash` 工具真实执行且结果中无
`[sandbox: ...]` 拒绝标记（runtime context 记录的默认策略为 `workspace-write`），任务由 CLI 真实落盘。

### 2.4 独立、无模型的校验

DSH 进程退出后，脚本用普通 shell 直接查 SAGE-Kit 状态（不经模型）：

```bash
node .../sage-kit/dist/cli.js task list --json
node .../sage-kit/dist/cli.js task show task-20261023151241-22d6e3 --json
node .../sage-kit/dist/cli.js brief --task task-20261023151241-22d6e3 --max-bytes 2048
```

任务文件 `.sage-kit/state/tasks/task-20261023151241-22d6e3.json`（跑前为空目录，跑后恰好 1 个新文件）：

```json
{
  "schemaVersion": 1,
  "id": "task-20261023151241-22d6e3",
  "title": "DSH mock-model E2E: create a tracked task",
  "status": "ready",
  "acceptance": ["A task JSON exists under .sage-kit/state/tasks and sage-kit task list shows the task."],
  "evidence": [],
  "createdAt": "2026-10-23T15:12:41.884Z"
}
```

`.sage-kit/state/events/events.jsonl`：

```json
{"ts":"2026-10-23T15:12:41.890Z","type":"task.created","taskId":"task-20261023151241-22d6e3","data":{"status":"ready","title":"DSH mock-model E2E: create a tracked task"}}
```

`verify-e2e.mjs` 对 `run-02/` 的 **24/24 检查全部 PASS**（`run-02/verdict.json`，`"ok": true`）：

```text
dsh_exit_zero, event_skill_tool_call, event_skill_tool_result_loaded,
skill_resolved_from_project_dir, event_bash_tool_call, event_bash_tool_result_completed,
final_answer_present, no_error_events, pre_task_list_ok_empty, post_task_list_shows_task,
post_task_title_matches, post_task_status_ready, new_task_file_created, task_file_valid_json,
task_file_title_matches, task_file_acceptance_recorded, task_show_ok, brief_renders_task,
state_event_task_created, mock_requests_captured, main_requests_visible, bash_tool_advertised,
skill_tool_advertised, bash_call_roundtrip_in_model_input
```

模型请求侧证据（`run-02/requests/001.json`、`004.json`）：

- 请求体含 25 个工具，`bash` 与 `skill` 均在 schema 列表中；`max_tokens=256000`、`stream=true`；
- 工作区说明（user message 的 `<system-reminder>`）含 `<!-- sage-kit:begin -->` 的 `AGENTS.md` 受管块
  （`npx sage-kit brief`、`npx sage-kit task ...`、证据要求）；
- Skill 目录 `<available_skills>` 中列出 `sage-kit`；
- runtime context 记录 `Current DSH file policy: workspace-write`；
- 请求 004 回放了 assistant 的 `tool_use:skill`、`tool_use:bash` 及其 `tool_result`，即真实工具往返进入模型上下文。

项目文件基线哈希（复现核对用）：

```text
c945ec0a... SKILL.md (.dsh/skills/sage-kit)
fcf31fcf... AGENTS.md
33c6b431... .sage-kit/config.json
710eb2dd... node_modules/sage-kit/dist/cli.js
```

### 2.5 第一次尝试（run-01）与修正

`run-01`（UTC 15:11Z）同一条 E2E 实际也成功（任务 `task-20261023151144-94d5da` 创建并列出），
但校验器当时错误地假设新任务状态是 `running`；实际 CLI 语义为新建即 `ready`。
已修正校验器断言（`post_task_status_ready`），清空测试项目任务状态后重跑得到干净的 `run-02`（24/24）。
`run-01/` 与 `run-02/` 原始证据都保留在 `work/dsh-linux/` 下，报告以 `run-02` 为准。

## 3. Linux DSH Web 复检（可选步骤）

```bash
/mnt/d/Projects/SAGE-Kit/work/dsh-linux/web-check.sh   # 端口 18766，隔离 DSH_HOME，项目 cwd
```

结果（`work/dsh-linux/web-check/result.txt`，token 值不落盘）：

```text
boot=OK                          url_token=present
no_token_status=401              token_first_status=303（Set-Cookie，location: ./）
authed_page_status=200           authed_page_bytes=37512
listening_before_stop=1          listening_after_stop=0
process_alive_after_stop=no      无残留监听/进程（1876x 端口已复查）
```

边界：这里只验证 Web 服务启动、token/303/cookie/SPA 加载；**浏览器内真实操作与 GUI 会话未执行**
（无显示器/无真实凭据）。Web profile 与 headless 共用同一 `$DSH_HOME`，但本次没有在 GUI 中加载 Skill。

## 4. 与既有报告的关系

- `reports/p0/dsh-real-host.md`：真实 DSH headless + mock 仅验证 `skill` 工具加载（Windows 隔离环境）。
- 本报告在 Linux/WSL 上把链路推进到 **bash 工具真实执行 + SAGE-Kit CLI 创建任务/列表 + 独立文件校验**。
- 两者都是 mock 模型证据，均不能替代真实模型验收；`reports/p0/dsh-linux-web.md` 的 Web 结论仍成立。

## 5. 明确 NOT_EXECUTED

1. **真实 DeepSeek 模型运行**：隔离环境无真实凭据（§1）；未用占位/伪造结果替代。
2. **真实模型下的 Skill 选择/使用质量**：mock 模型按固定状态机行动，不反映模型判断。
3. **GUI 浏览器交互**：未在浏览器中打开并操作 SAGE-Kit 会话。
4. **hook 自动注入 / `session.start`**：按既有核查（`dsh-real-host.md`），DSH 没有可安装的原生 hook 配置，`brief` 自动注入未验证；本次未执行 `sage-kit session start/stop` 宿主生命周期。
5. **真实 DSH 会话中的 `task status done --evidence` 完整闭环**：本次只到 create + list + show + brief；`done` 状态机无模型参与。
6. **卸载/清理验证**：未在测试项目执行 `sage-kit uninstall`（项目保留供复现）。
7. **Windows 作为测试目标**：按任务要求未在 Windows 执行测试。
8. **账号凭据（`deepseek-account-platform`）路径**：headless 禁用托管凭据，未尝试恢复/迁移该凭据。

## 6. 复现

```bash
# 清空测试项目任务状态（仅测试环境 scratch，非仓库文件）
cd /home/kayann/sage-kit-linux-dsh/project
rm -f .sage-kit/state/tasks/*.json .sage-kit/state/events/events.jsonl

# 确定性 E2E（自动起停 mock，退出码为 24 项检查的汇总）
/mnt/d/Projects/SAGE-Kit/work/dsh-linux/run-task-e2e.sh

# Web HTTP 面复检（自动停止服务）
/mnt/d/Projects/SAGE-Kit/work/dsh-linux/web-check.sh
```

说明：重复运行会各自创建一个新任务；`verify-e2e.mjs` 的 `pre_task_list_ok_empty` 与
`post_task_list_shows_task` 要求从空任务列表开始。

## 7. 证据文件清单（`work/dsh-linux/`，已被 `.gitignore:3 work/` 忽略）

| 文件 | 内容 |
| --- | --- |
| `mock-task-e2e.js` | 确定性 mock Messages 状态机（skill → bash → final） |
| `run-task-e2e.sh` | 起停 mock、跑真实 DSH headless、独立 CLI 校验 |
| `verify-e2e.mjs` | 24 项独立检查（事件流、任务文件、CLI 输出、mock 请求） |
| `run-02/` | 主证据：`environment.txt`、`dsh-events.jsonl`、`dsh-exit.txt`、`mock-server.log`、`requests/001–004.json`、`task-file.json`、`post-task-list.json`、`task-show.json`、`brief.txt`、`events-log.jsonl`、`verdict.json` |
| `run-01/` | 首次尝试证据（校验器断言修正前，任务同样创建成功） |
| `web-check/` | Web 复检：`result.txt`、`web.log`、SPA 页面、cookie/headers |
| `no-credential-check.log` | 真实凭据缺失的 `MISSING_CREDENTIAL` 失败证据 |

本次任务只新增本报告与 `work/dsh-linux/` 下的忽略产物；未修改 `src/`、`tests/`、`docs/`、README 或 git 历史，
未 commit / push / tag / 发布 GitHub release。报告与证据中不含任何密钥或 Web token。
（说明：核查时工作树中存在其他协作者的 `docs/p0-acceptance.md`、`tests/cli.test.mjs` 改动，与本报告无关。）

## 8. 对 P0-A13 的表述建议

可以写：**DSH 0.2.1-rc.2（Linux/WSL，headless）在 mock 模型驱动下完成了 Skill 发现/加载，并经真实 `bash`
工具调用 SAGE-Kit CLI 创建、列出了任务，任务 JSON 与状态事件由独立命令校验。**

不能写：本报告（mock 模型）证明真实模型会话或 GUI 已验收。真实模型 headless 的独立证据在 `reports/p0/dsh-real-model-e2e.md`（2026-10-24 追加）；GUI 与 hook 自动注入仍保持 `NOT_EXECUTED`。
