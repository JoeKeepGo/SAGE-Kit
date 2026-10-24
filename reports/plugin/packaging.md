# DSH 插件打包冒烟（plugin packaging smoke）

日期：2026-10-24（本地）
运行环境：WSL2 Ubuntu 26.04.1 LTS（Node v22.22.1、npm 9.2.0、pnpm 10.34.8、git 2.53.0）；开发机 Windows 不作为执行环境。
宿主：`@deepseek-ai/dsh` 0.2.1-rc.2（本次为**一次性 npm 安装到临时目录**，不是持久测试环境；与 CI 的安装方式一致）。
代码状态：工作区快照（包含 Lead 尚未提交的 `packages/dsh-plugin/`、`src/index.ts` 与根 `package.json` 的 exports）。以下 tarball hash 对应本快照；提交后应重跑脚本刷新。
状态：脚本与 CI 接线**已实现并在 WSL 实测通过**（`PLUGIN SMOKE PASSED`）。真实 DSH 启动、插件代码加载与模型调用**未执行**（`NOT_EXECUTED`，由 task-16 覆盖）；GitHub Hosted Runner 上的该 job **未执行**（本环境无 runner/act）。

## 交付物

- `scripts/plugin-smoke.sh`（新增；可重复执行，失败时保留 work 目录与日志）
- `.github/workflows/ci.yml` 新增 Linux job `plugin-smoke`
- 本报告

## 冒烟内容

`scripts/plugin-smoke.sh` 从全新构建开始验证：

1. 预检：`node >=22`、`npm`、DSH CLI（`DSH_BIN` 或 PATH 上的 `dsh`）、`pnpm >=10`（`PNPM_BIN` 或 PATH 上的 `pnpm`）。WSL 下若解析到 `/mnt/c` 的 Windows `dsh`/`pnpm` 会立即失败并给出修复提示；脚本把已验证的 pnpm 目录前置到 PATH，因为 `dsh plugin` 内部用 `execa('pnpm')` 从 PATH 查找 pnpm。
2. `npm run build`（缺少 `node_modules/typescript` 时先 `npm ci`），断言 `dist/index.js`、`dist/cli.js` 存在。
3. `npm pack` 根包 → 断言 tarball 含 `package.json`、`dist/cli.js`、`dist/index.js`、`skills/sage-kit/SKILL.md`，且不含 `tests/`、`reports/`、`work/`、`src/`、`node_modules/`、`scripts/`、`.github/`、`.git/`、`.sage-kit/`、`packages/`。
4. 在 `packages/dsh-plugin` 执行 `npm pack` → 断言含 `package.json`、`index.js`、`cordis.patch.yml`（值取自 manifest 的 `dsh.bundle.patch`）；断言 manifest 声明 `dsh.bundle.patch`、`engines.dsh`，且对 `sage-kit` 有 dependency/peer（否则插件拿不到核心库）。
5. 全新 `DSH_HOME` + 全新 profile，按 Lead 验证过的顺序分两次安装：`dsh plugin --profile <name> add <sage-kit.tgz>`，再 `dsh plugin --profile <name> add <sage-kit-dsh.tgz>`（每次都用绝对 tarball 路径）。
6. 校验 profile：`package.json` 的 `dependencies` 同时含 `sage-kit` 与 `sage-kit-dsh`，`dsh.profile.bundles` 含 `sage-kit-dsh`；`node_modules` 中 `sage-kit/dist/index.js` 与 `sage-kit-dsh/index.js` 存在；用 tarball 内 CLI 运行 `version`，与包版本一致。
7. `dsh --profile <name> --dump-config` 退出 0，且输出含 `# == sage-kit-dsh`、`- id: sage-kit-dsh`、`name: sage-kit-dsh`；脚本打印该合成的层片段。
8. 可选：`--with-tests` / `SAGE_SMOKE_TESTS=1` 追加 `npm test`。

## 实测命令

```bash
# WSL2 Linux；一次性工具链（与 CI 相同的安装方式）
npm install --prefix /tmp/pnpm-env --no-audit --no-fund pnpm@10.34.8
npm install --prefix /tmp/dsh-env --no-audit --no-fund @deepseek-ai/dsh@0.2.1-rc.2

cd /mnt/d/Projects/SAGE-Kit
npm ci
DSH_BIN=/tmp/dsh-env/node_modules/.bin/dsh \
PNPM_BIN=/tmp/pnpm-env/node_modules/.bin/pnpm \
bash scripts/plugin-smoke.sh
```

结果节选（完整 stdout 在运行 work 目录 `logs/` 中；脚本预检会打印 `node/npm/dsh/pnpm/repo/work`）：

```text
==> installing root tarball into fresh DSH profile 'sage-kit-smoke'
dsh plugin add sage-kit: OK

==> installing plugin tarball into profile 'sage-kit-smoke'
dsh plugin add sage-kit-dsh: OK

==> checking the installed profile manifest
profile dependencies: sage-kit, sage-kit-dsh
profile bundles: @deepseek-ai/dsh-base, sage-kit-dsh

==> asserting the sage-kit layer in the composed profile config
--- composed layer (from dump-config) ---
# == sage-kit-dsh
- id: sage-kit-dsh
  name: sage-kit-dsh
  config:
    autoBrief: true
    maxBriefBytes: 2048

==> summary
dsh             0.2.1-rc.2 (/tmp/dsh-env/node_modules/.bin/dsh)
pnpm            10.34.8 (/tmp/pnpm-env/node_modules/.bin/pnpm)
plugin engine   >=0.2.1-rc.2 <0.3.0

PLUGIN SMOKE PASSED
```

### Tarball SHA-256（本工作区快照，2026-10-24）

```text
49db8e616b3cf9b99dc6adb59dc9224275ff5d205bb8f406e2f7e711eec09a2e  sage-kit-0.1.0.tgz       (202596 bytes)
0616a2d5d23fcca5fbf01816f23eab74d48d6a88ce792c301e661df8ef3ae4c3  sage-kit-dsh-0.1.0.tgz   (8065 bytes)
```

另以最终脚本版本跑过 `bash scripts/plugin-smoke.sh --with-tests`：分两次 `dsh plugin add`（均 OK）与 `--dump-config` 层断言通过后，`npm test` 为 `tests 99 / pass 99 / fail 0`（WSL2，Node v22.22.1；包含本工作区当时的 api/plugin 相关测试）。

插件 tarball 内容：`package/index.js`、`package/package.json`、`package/README.md`、`package/cordis.patch.yml`（README 由 Lead 在本次验证前补入）。

### 失败模式验证（脚本可读地报错，不会静默通过）

| 场景 | 实测结果 |
| --- | --- |
| pnpm 9.15.9（`PNPM_BIN` 指向） | 退出 1：`plugin-smoke: ERROR: pnpm >=10 required (found 9.15.9): DSH profiles configure pnpm in pnpm-workspace.yaml, which pnpm 9 ignores; ...` |
| PATH 上没有 dsh | 退出 1：`dsh not found: set DSH_BIN or put dsh on PATH (CI installs @deepseek-ai/dsh@0.2.1-rc.2)` |
| `PNPM_BIN` 指向 WSL 的 Windows pnpm（`/mnt/c/...`） | 退出 1：明确提示改用 Linux pnpm 并设置 `PNPM_BIN` |
| pnpm 9 实际执行 `dsh plugin add` | 不加 `-w` 先报 `ERR_PNPM_ADDING_TO_ROOT`；加 `-w` 仍因 pnpm 9 不识别 profile 的 `autoInstallPeers: false` 而请求未发布内部包，报 `ERR_PNPM_FETCH_404 .../@deepseek-ai%2Fdsh-type-meta` |

## CI 接线

`.github/workflows/ci.yml` 新增独立 job `plugin-smoke`（`ubuntu-latest`、`timeout-minutes: 20`）：

- job 级 env：`DSH_VERSION=0.2.1-rc.2`、`PNPM_VERSION=10.34.8`。
- 步骤：`checkout` → `setup-node 22 (cache npm)` → `npm ci` → **Install pinned DSH CLI and pnpm**（用 `npm install --prefix "$RUNNER_TEMP/..."` 装 `pnpm@$PNPM_VERSION` 与 `@deepseek-ai/dsh@$DSH_VERSION`，写入 `GITHUB_PATH`，`id: install-toolchain`、`continue-on-error: true`）→ 成功则执行 `bash scripts/plugin-smoke.sh`。
- 显式跳过：toolchain 安装失败时执行单独的 skip 步骤并输出 `::warning::`，说明插件冒烟未运行、`linux` job 仍覆盖 build/test/根 tarball；不会静默绿掉（warning annotation 可见）。
- 主 `linux` job（build、npm test、根 tarball packaging gate）不变；工作流仍只有 Linux runner，无 release/publish/tag 步骤。
- 本环境没有 GitHub Hosted Runner，未实际触发该 job（`NOT_EXECUTED`）；job 内的安装命令与冒烟脚本已在 WSL2 以同版本 pnpm/DSH 全流程执行通过。

## 发现（供 Lead / task-18 文档参考）

1. **pnpm 10 是硬约束**：DSH profile 把包管理器设置放在 `pnpm-workspace.yaml`（`nodeLinker: hoisted`、`autoInstallPeers: false`）。pnpm 9 不识别这些设置，会尝试自动安装插件 peer，进而请求未发布的内部包：`ERR_PNPM_FETCH_404 https://registry.npmjs.org/@deepseek-ai%2Fdsh-type-meta`；同一命令在 pnpm 10.34.8 下成功。脚本已强制 `>=10` 并给出明确错误。建议在插件安装文档（task-18）写明 `pnpm >=10`。
2. 安装顺序与 Lead 手工验证的配方一致：新 `DSH_HOME` + 新 profile，先 `dsh plugin --profile <name> add <sage-kit.tgz>` 再 `add <sage-kit-dsh.tgz>`（绝对路径），每一步都断言退出 0。pnpm 10 下根 workspace 的 add 无需 `-w`（实测 exit 0）；pnpm 9 下不加会先报 `ERR_PNPM_ADDING_TO_ROOT`，加了也会因 peer 自动安装而 404（见上一条），这也是脚本要求 pnpm ≥10 的原因。
3. 安装时的告警是**预期**、不应判失败：
   - `WARN Issues with peer dependencies found ... missing peer @deepseek-ai/cordis / dsh-llm / dsh-tools / schemastery`：profile 明确 `autoInstallPeers: false`，这些 peer 由 DSH 宿主提供；
   - `dsh: warning: sage-kit declares no dsh.bundle — installed as a plain dependency, not a profile layer`：根包是插件的库依赖，不是 profile 层，符合设计。
4. 成本：一次性 `npm install @deepseek-ai/dsh@0.2.1-rc.2` 约 **2 分钟 / 618 包 / 863 MB**（WSL2）。因此拆成独立 job 并允许 toolchain 安装失败时显式跳过；若要改成强制门禁，去掉 `continue-on-error` 即可。未加 `actions/cache`（保持简单；如需缩短常态 CI 时间可后续加，key 按 DSH 版本固定）。
5. 插件 manifest 在本次最终快照完整：`package.json files` 中的 `README.md` 已存在并进入 tarball；此前中间快照曾缺失，现已无缺口。

## 未验证 / 剩余边界

- `--dump-config` 只证明 profile 合成出插件层，**不执行插件代码**：插件 `index.js` 真实加载、`sage_task_create/list/show/status` 工具注册与调用、`agent/pre-step` 自动 brief 注入是否触发一次/变更后更新、无 `.sage-kit` 项目不注入等，均未在本次冒烟覆盖 → 属 task-16（真实 DSH profile E2E）。
- 真实 DeepSeek 模型运行未执行（无凭据/不属本任务）。
- GitHub Actions 上的 `plugin-smoke` job 未实际运行（无 runner）；YAML 已用 PyYAML 解析校验、脚本已 `bash -n` 并通过 CMD 全流程。
- Windows 不作为测试目标（仓库既有策略）；脚本在 WSL 下会拒绝 Windows 版 pnpm/dsh。
- 报告中的两个 hash 对应**当前未提交工作区**（含 Lead 的插件与核心 exports 改动）；提交后重跑脚本刷新，脚本每次都会打印当次 sha256。

## 最终修复后刷新（F-1/F-2 + lib.js/license）

在修复评审 F-1（去掉非法 `source.form:"brief"`）、F-2（`engines.dsh` 上界 `<0.3.0-0`），并新增 `lib.js`、插件 `LICENSE`、`tests/plugin.test.mjs` 后，重新执行：

```text
bash scripts/plugin-smoke.sh --keep --workdir /tmp/sage-plugin-smoke-final
PLUGIN SMOKE PASSED
plugin engine   >=0.2.1-rc.2 <0.3.0-0
root tarball    sage-kit-0.1.0.tgz       sha256 6ba2df8426e99a6cd8a219e920320368f0a133f870a878f17d7bd79c51af1e8f
plugin tarball  sage-kit-dsh-0.1.0.tgz   sha256 628dcee8b9e19554253463807f58633f2f3016e74047d94a1e89bda0c4599084
```

最终核心测试为 `tests 103 / pass 103 / fail 0`（含 `tests/plugin.test.mjs` 4 项）。插件 tarball 现在包含 `package/index.js`、`package/lib.js`、`package/package.json`、`package/README.md`、`package/cordis.patch.yml`、`package/LICENSE`。本报告前面段落的 hash/99 项是历史快照，最终以本节为准。
