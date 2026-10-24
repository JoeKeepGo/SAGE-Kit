# 隔离沙箱：tiny-notes + DSH 原生插件真实会话

日期：2026-10-24（Pacific/Auckland）
对象：DSH 0.2.1-rc.2 + `sage-kit-dsh@0.1.0` + 当前 SAGE-Kit HEAD `4bf44cf`
目的：用一个很小的独立仓库验证“真实 DSH 会话 → 插件工具 → 文件状态 → 测试 → 证据 → done”的完整路径，而不是只验证插件加载。

## 1. 隔离环境

- 测试项目：`work/sandbox/tiny-notes`（在 SAGE-Kit 仓库的 gitignored `work/` 下，独立 git 仓库；不进入 SAGE-Kit 提交）。
- 项目内容：零依赖 Node ESM notes CLI，`add/list/remove`，`node --test` 4 个测试；预置一个已知 bug：`removeNote` 删除的是目标后一条。
- 初始状态：`node --test` 1 个测试失败（`removes exactly the requested note`）。
- SAGE-Kit：用仓库 `dist/cli.js init --host dsh --scope project` 初始化；创建任务 `task-20261024063224-b0061b`（ready）。
- DSH：独立 `DSH_HOME=/tmp/sage-sandbox-home`，profile `sandbox` 从 `headless` 模板物化；用本地 tarball 安装 `sage-kit` + `sage-kit-dsh`，不触碰用户 `.dsh`。
- 模型：真实 DeepSeek（使用隔离 WSL 环境中的 0600 key 文件，仅通过环境变量注入；未写入项目/报告）。

## 2. 真实会话结果

`dsh --profile sandbox --json "<prompt>"` 退出 0、stderr 0 B。模型按插件 brief 工作，调用顺序包括：

1. `sage_task_list` / `sage_task_show` 确认 ready 任务；
2. `sage_task_status` → `running`；
3. 读取 `src/store.js`，把 `notes.splice(index + 1, 1)` 改为 `notes.splice(index, 1)`；
4. `node --test`：**4/4 通过**；
5. `git diff` 确认唯一代码改动；
6. `sage_task_status` → `review`；
7. `sage_task_status` → `done`，带 3 条 evidence（source 均为 `dsh-plugin`）。

任务最终状态：`done`，evidence 含代码改动、完整测试输出、diff 确认。项目内未 commit/push。

## 3. 插件注入证据

session 中实际出现 4 条 `<sage-kit-brief>` user 消息，对应任务状态：

```text
1. ready
2. running
3. review
4. done
```

说明 `agent/pre-step` 在任务变化后更新 brief；同一状态未重复注入（4 个不同状态，4 条）。证据：`reports/plugin/evidence/sandbox-tiny-notes/session-briefs.jsonl`、`brief-injections.txt`。

## 4. 发现

1. **插件路径工作正常**：模型先尝试 `npx sage-kit brief`，因包未发布到 npm 返回 E404；随后按插件能力改用 `sage_task_*` 工具并完成全部状态/证据操作。没有手动编辑 `.sage-kit`。
2. **可改进点**：`sage-kit init` 写入的 AGENTS 受管块仍写“先运行 `npx sage-kit brief`”；在未发布/未本地安装核心包的 DSH 插件场景会先产生一次 E404。建议后续把受管说明改成“宿主提供 SAGE-Kit 插件工具时优先 `sage_brief`/`sage_task_*`；否则使用已安装 CLI”，并在 SKILL 中同样说明。本轮只记录，不修改产品行为。
3. 沙箱项目未纳入版本控制，避免把测试 fixture 混入产品仓库；证据已复制到 `reports/plugin/evidence/sandbox-tiny-notes/`。

## 5. 证据清单

- `reports/plugin/evidence/sandbox-tiny-notes/task-done.json`：最终任务与 3 条 evidence。
- `test-output.txt`：4/4 测试输出。
- `store.diff`：唯一代码改动。
- `dsh-run.jsonl`：DSH 事件流（含工具调用、测试输出、最终消息）。
- `session-briefs.jsonl`：4 条注入 brief 的 session 记录。
- `brief-injections.txt`：注入状态序列。
- `dsh-run.err`：空（stderr 0 B）。

## 6. 边界

- 这是单次真实模型会话，不是统计/基准；模型可能因随机性走不同工具路径。
- 未测试 DSH Web GUI、Windows/macOS、`autoBrief:false`、配置错误降级。
- 未发布 npm/release；沙箱不是产品功能承诺。
