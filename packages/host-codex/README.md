# SAGE-Kit Codex 宿主插件（薄包，草案）

**状态：文件级草案，未发布；根 npm `files` 已包含此目录，当前修复的 tarball 安装验证为 `NOT_EXECUTED`。真实 Codex CLI 的插件安装/卸载已用隔离 `CODEX_HOME` 验证（见下）；真实会话中的 hook 信任与注入激活为 `NOT_EXECUTED`。**

这个目录不是核心产品面：核心仍是 `sage-kit` CLI 与 `skills/sage-kit/SKILL.md`，任务是唯一权威状态源（`.sage-kit/`）。本插件只做两件事：

- 让 Codex 会话加载**规范 Skill 的安装副本**；
- 在 `SessionStart` 注入由 `sage-kit brief --json --require-initialized` 生成的、有界（默认 ≤2 KB、≤2 s）的会话摘要。

插件**没有自己的状态**，不启动服务，不联网，不调用模型；brief 读取失败或超时一律降级为静默（`{}`，退出码 0）。

## 1. 布局

```
packages/host-codex/
├── .codex-plugin/plugin.json   # Codex 插件清单模板（不含 version；安装时注入）
├── hooks/hooks.json            # SessionStart → hooks/session-start.cjs
├── hooks/session-start.cjs      # 宿主 hook 桥：stdin JSON → sage-kit brief → additionalContext
└── README.md
```

`skills/sage-kit/` 不放在本目录：Codex 要求 Skill 路径位于插件根内，因此由 `installCodexHostBundle()`
在安装时把规范 Skill（`skills/sage-kit`）复制进暂存插件目录，避免出现第二份手写 Skill。

## 2. 安装（当前草案路径）

在已运行 `sage-kit init` 的目标项目内执行：

1. 暂存：`sage-kit host install --host codex`（库 API：`installCodexHostBundle({ projectRoot })`）生成
   `.sage-kit/hosts/codex/`（含 `plugins/sage-kit` 与 Skill 副本）与归属标记
   `.sage-kit-host-bundle.json`。
2. 注册（宿主自己的命令，SAGE-Kit 不改 `~/.codex/config.toml`）：

   ```bash
   codex plugin marketplace add <项目>/.sage-kit/hosts/codex
   codex plugin add sage-kit@sage-kit
   ```

3. 卸载：`codex plugin remove sage-kit@sage-kit`，再
   `sage-kit host uninstall --host codex --project-root <项目>` 只删除归属标记中已成功创建的文件；核心卸载移除配置后仍可执行。
4. 幂等：重复暂存会覆盖自有文件并清理旧文件；无归属标记的目录默认拒绝覆盖（`E_HOST_BUNDLE_UNOWNED`）。

## 3. 验证证据与边界

已验证（`node --test tests/host-adapters.test.mjs`，本机 Codex CLI 0.164.0）：

- 隔离 `CODEX_HOME` 下 `plugin marketplace add` → `plugin add sage-kit@sage-kit` → `plugin list` →
  `plugin remove` 往返成功，真实 `~/.codex/config.toml` 未被修改；
- 暂存清单可被 Codex 解析，插件版本取自根 `package.json`；
- 暂存/重复暂存/卸载幂等，用户文件不会被删除；桥在未初始化项目静默、超时/坏输出降级、输出字节上限生效。

`NOT_EXECUTED`：

- 真实 Codex 会话中 `/hooks` 信任 + `SessionStart` 实际注入（需要交互式会话，CI 不可用）；
- 当前修复快照的 npm tarball 安装/暂存；根 `files` 已包含本目录，历史打包结果不能证明当前代码。

## 4. 安全

- `hooks/session-start.cjs` 只调用 `sage-kit brief`（只读），仅检查 `.sage-kit/config.json` 是否存在，不修改状态、不联网、不落盘；
- 宿主输入只取 `cwd`；不执行输入中的任何文本或命令；
- 只输出 JSON `hookSpecificOutput.additionalContext`，失败一律输出 `{}`；
- 未初始化项目（无 `.sage-kit/config.json`）直接静默，不注入通用提示。
