# 真实 DSH 宿主验证（隔离环境）

日期：2026-10-24  
DSH：0.2.1-rc.2（本机已安装的真实应用）  
环境：`D:\Projects\SAGE-Kit\work\dsh-isolated`  
模型：本地 mock Anthropic Messages 兼容端点（不是真实 DeepSeek 模型）

## 隔离内容

- `DSH_HOME=D:\Projects\SAGE-Kit\work\dsh-isolated\home`
- 测试仓库：`work\dsh-isolated\project`
- 未写入 `C:\Users\KayAnn\.dsh`；未改写桌面 GUI 配置
- `dsh.cmd` 只把 `DSH_HOME` 指到隔离目录，调用本机真实 DSH

## 执行

```powershell
cd D:\Projects\SAGE-Kit\work\dsh-isolated
.\run-dsh-test.ps1
```

DSH 以 `--profile headless --json` 运行，任务为 “Reply with the single word READY…”。mock 模型只在主请求中返回一次 `skill` 工具调用，随后返回最终文本。

## 证据

`DSH_EXIT=0`，事件流包含：

```text
{"type":"tool_call","tool":"skill","input":{"name":"sage-kit"}}
{"type":"tool_result","status":"completed","result":"<skill_content name=\"sage-kit\">..."}
{"type":"final","text":"READY"}
```

模型请求体（`requests/001.json`、`002.json`、`003.json`）确认：

- 工具列表包含 `skill`；DSH 实际执行 `skill` 后返回了完整的 `SKILL.md` 内容；
- 请求中的项目说明包含 `AGENTS.md` 的受管 `sage-kit` 块，包括 `npx sage-kit brief`、`task` 和证据要求；
- 技能目录来自项目 `.dsh/skills/sage-kit`，不是全局目录。

## 结论与边界

已验证真实 DSH 的 **Skill 发现、skill 工具加载、项目 AGENTS 说明加载、headless 会话/事件流/退出码**。这比 fake adapter 强，但仍不是完整 P0-A13：

- mock 模型不是真实模型，不证明模型会正确选择或使用该 Skill；
- DSH 当前没有可安装的原生 hook 配置，`session.start` 自动注入未验证；
- `sage-kit brief` 可由 CLI 或用户显式调用，不能声称 DSH 自动注入；
- 真实 DSH 桌面 GUI 会话仍可补一次人工验收；Linux Web 部署已另行验证，见 [`dsh-linux-web.md`](dsh-linux-web.md)。

复现环境说明见 [`work/dsh-isolated/README.md`](../../work/dsh-isolated/README.md)。
