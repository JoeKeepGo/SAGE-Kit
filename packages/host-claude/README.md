# SAGE-Kit Claude Code 宿主插件（薄包，草案）

**状态：文件级草案，未发布；根 npm `files` 已包含此目录，当前修复的 tarball 安装验证为 `NOT_EXECUTED`；本机没有 Claude Code CLI，真实安装/激活为 `NOT_EXECUTED`。**

核心仍是 `sage-kit` CLI 与 `skills/sage-kit/SKILL.md`；任务是唯一权威状态源（`.sage-kit/`）。本插件只做两件事：

- 让 Claude Code 会话加载**规范 Skill 的安装副本**；
- 在 `SessionStart` 注入由 `sage-kit brief --json --require-initialized` 生成的、有界（默认 ≤2 KB、≤2 s）的会话摘要。

插件**没有自己的状态**，不启动服务，不联网，不调用模型；hook 失败、超时或未初始化一律静默（`{}`，退出码 0）。

## 1. 布局

```
packages/host-claude/
├── .claude-plugin/plugin.json  # Claude Code 插件清单模板（不含 version；安装时注入）
├── hooks/hooks.json            # SessionStart → hooks/session-start.cjs
├── hooks/session-start.cjs      # 宿主 hook 桥，与 Codex 版逐字节一致
└── README.md
```

`skills/sage-kit/` 不放在本目录：由 `installClaudeHostBundle()` 在安装时从规范 Skill 复制进暂存插件目录，
避免出现第二份手写 Skill。

## 2. 安装（当前草案路径）

1. 暂存：`sage-kit host install --host claude`（库 API：`installClaudeHostBundle({ projectRoot })`）生成
   `.sage-kit/hosts/claude/`（含 `plugins/sage-kit`、Skill 副本、`.claude-plugin/marketplace.json`）
   与归属标记 `.sage-kit-host-bundle.json`。
2. 注册（Claude Code 自己的命令，SAGE-Kit 不改 `~/.claude` 配置）：

   ```
   /plugin marketplace add <项目>/.sage-kit/hosts/claude
   /plugin install sage-kit@sage-kit
   ```

3. 卸载：先 `/plugin uninstall sage-kit@sage-kit`，再
   `sage-kit host uninstall --host claude --project-root <项目>` 只删除归属标记中已成功创建的文件；核心卸载移除配置后仍可执行。
4. 幂等：重复暂存覆盖自有文件并清理旧文件；无归属标记目录默认拒绝覆盖（`E_HOST_BUNDLE_UNOWNED`）。

## 3. 验证证据与边界

已验证（`node --test tests/host-adapters.test.mjs`，无 Claude Code CLI）：

- 暂存清单/`marketplace.json`/hook 配置均为合法 JSON，且 manifest 版本取自根 `package.json`；
- 暂存 Skill 与规范 `skills/sage-kit/SKILL.md` 逐字节一致；
- 暂存/重复暂存/卸载幂等，用户文件不会被删除；
- hook 桥与 Codex 版逐字节一致，并在未初始化/超时/坏输出/大输出下按上限静默降级。

`NOT_EXECUTED`：

- 真实 Claude Code `/plugin install`、hook 信任与 `SessionStart` 注入（本机无 Claude Code CLI）；
- 当前修复快照的 npm tarball 安装/暂存；根 `files` 已包含本目录，历史打包结果不能证明当前代码。

## 4. 安全

- `hooks/session-start.cjs` 只调用 `sage-kit brief`（只读），仅检查 `.sage-kit/config.json` 是否存在，不修改状态、不联网、不落盘；
- 宿主输入只取 `cwd`；不执行输入中的任何文本或命令；
- 只输出 JSON `hookSpecificOutput.additionalContext`，失败一律输出 `{}`；
- 未初始化项目（无 `.sage-kit/config.json`）直接静默，不注入通用提示。
