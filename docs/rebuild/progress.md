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

## 下一步

进入 R1：选择最小项目 fixture，先定义授权、任务依赖、
上下文刷新和恢复记录的具体例子及反例，再实现最小适配支持。涉及可选代码交付时
同步收窄原版绝对“无运行时”检查，保留无强制依赖的治理包；不能先移植整个旧 CLI。
