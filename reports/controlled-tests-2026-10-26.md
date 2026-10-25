# SAGE-Kit 受控测试报告（WSL2 + Windows）

日期：2026-10-26  
版本：`0.2.0-alpha.1`  
源码：`D:\Projects\SAGE-Kit`，分支 `main`，HEAD `a27a5ffcbecc9336f2fc0c429d797c4f125c8122`  
状态：测试时工作树未提交（`git status --porcelain` 共 48 项）；未 commit、未 push、未发布。

## 1. 测试范围

两端均执行仓库完整测试命令：

```text
npm test
```

该命令先执行 `tsc -p tsconfig.json`，再运行 `tests/` 下 12 个测试文件，覆盖：

- CLI 生命周期、安装/卸载、doctor、worktree、run/recovery、hook；
- GitHub/Gitea 反馈分页、游标、增量同步和不可信数据处理；
- control-plane SQLite/HTTP API、loopback 写入保护；
- RSI 提案、评估、批准、门禁、锁与恢复；
- DSH/Codex/Claude host bundle、插件模式、strict pre-step；
- quickstart shell 脚本和跨平台路径解析。

本轮是**受控测试**，不是产品验收，也不是真实 DSH/模型/在线 API 的联调。

## 2. 环境与隔离

| 项目 | Windows | WSL2 |
|---|---|---|
| OS / kernel | Windows 11 10.0.26300 | Linux 6.18.33.2-microsoft-standard-WSL2 |
| Node | v24.22.0 | v22.22.1 |
| npm | 11.19.1 | 9.2.0 |
| git | 2.56.0.windows.2 | 2.53.0 |
| 源码 | 当前工作树 `D:\Projects\SAGE-Kit` | 独立副本 `/home/kayann/sage-kit-controlled-20261026-021441/src` |
| 测试临时目录 | `%TEMP%\sage-kit-controlled-win-e87569f126e240b09231d8597c9fa364\tmp` | 独立副本内 `test-tmp` |
| npm cache | 独立 `npm-cache` | 独立 `npm-cache` |
| HOME / 用户目录 | 未切换；测试使用自身临时目录 | 独立 `home` 目录 |
| 真实 DSH profile | 未使用 | 未使用 |

WSL 副本通过 `rsync` 从当前工作树复制，排除了 `.git`、`node_modules`、`work`、`dist`、`.repair-validation`，随后执行 `npm ci`（新增 3 个包，耗时 834ms）。副本共 272 个源文件，清单文件：

```text
work/controlled-tests/2026-10-26/source-manifest.sha256
sha256 = 3c81614623b27b44fc5724cc5eeaf108f4ce6b4e803f5929ee59ec7122f9c92c
```

Windows 测试在同一工作树上运行，测试进程使用独立的 `SAGE_KIT_TEST_TMPDIR` 和 `npm_config_cache`；`SAGE_TEST_BASH` 指向 Git Bash。未启动真实 DSH、未访问真实 DSH profile。

## 3. 结果

| 环境 | tests | pass | fail | skipped | exit | duration |
|---|---:|---:|---:|---:|---:|---:|
| Windows | 206 | 205 | 0 | 1 | 0 | 43.84s |
| WSL2 | 206 | 206 | 0 | 0 | 0 | 23.92s |

两端均为 25 个 suite。

Windows 唯一 skip：

```text
R12: an exited command with inherited descendants cannot hold evaluation open
# Windows sandbox does not reproduce inherited pipes with a non-detached child
```

同一 R12 的 escaped-descendants 场景在 Windows 通过；WSL2 下 inherited 与 escaped 两个场景均通过。因此该 skip 是 Windows 进程/管道复现能力限制，不是代码失败。

## 4. 观察到的非失败输出

- 测试中出现 Node `DEP0190` 警告（既有测试使用 `child_process` 的 shell 参数），未导致失败。
- Git 在创建临时 worktree / submodule fixture 时输出默认分支提示和换行提示，属于测试夹具噪声。
- 测试结束后 WSL 隔离 `test-tmp` 为空；Windows 测试临时根目录保留在受控临时目录下，未写入 DSH profile。

## 5. 未覆盖的验证

以下项目**没有**被本轮测试证明：

1. 真实 DSH 0.2.1-rc.2/0.2.2-rc.1 的 plugin/hook 激活；quickstart 测试使用 stub，不启动真实 DSH。
2. 真实 Codex/Claude 会话中的 host bundle 注册与激活。
3. 在线 GitHub/Gitea API 与真实分页、限流、认证；当前使用本地 HTTP fixture。
4. 模型调用、真实任务生成、真实 RSI 模型判断和成本。
5. 浏览器中的 control panel 视觉/交互验收。
6. 生产负载、长时间运行、磁盘/CPU 资源回归；当前只有单元/集成超时断言，没有性能基准。
7. 所有 Windows 进程树硬终止场景；R12 的一个分支仍被 skip。
8. 从干净 commit 重建的复现性：本轮源码是带 48 项未提交改动的工作树，结果不能仅靠 HEAD 复现。

## 6. 结论

- Windows 与 WSL2 的完整测试套件均通过；没有出现环境特有的功能性失败。
- Windows 仅有一个与环境相关的 skip，且同名替代场景通过；WSL2 全部通过。
- 结论仅适用于当前工作树和当前测试套件；不能替代真实 DSH/宿主、在线适配器、模型和产品验收。
- 建议下一步：先提交/固定当前工作树，再分别做真实 DSH strict E2E、真实宿主激活矩阵和在线适配器测试；本轮不发布。

## 7. 附件（本机）

以下路径是测试时的本机证据；`work/` 已被 `.gitignore` 忽略，未纳入仓库：

```text
work/controlled-tests/2026-10-26/windows-test.log
work/controlled-tests/2026-10-26/windows-test-exit.log
work/controlled-tests/2026-10-26/wsl-test.log
work/controlled-tests/2026-10-26/wsl-npm-ci.log
work/controlled-tests/2026-10-26/source-manifest.sha256
```

WSL 隔离运行目录：`/home/kayann/sage-kit-controlled-20261026-021441`。
