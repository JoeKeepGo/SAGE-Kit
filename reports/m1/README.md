# M1 真实集成证据（task-11）

本目录是 task-11（M1 真实 GitHub + WSL2 隔离 Gitea 联调）的运行证据与报告，来源于一次性的真实环境执行（不进入 `npm test`，测试仍全离线）。

## 验收对照

| 验收项 | 结果 | 证据 |
|---|---|---|
| 真实 GitHub sync 至少取到 1 条真实 issue（非 fixture） | **PASS** | issue #26；`fetched=26, added=26` → `github-real.md`、`evidence/github/sync-1.json` |
| 真实 Gitea（WSL2 隔离）sync 至少取到 1 条真实 issue | **PASS** | 57 条真实 issue；`fetched=57, added=57` → `gitea-real.md`、`evidence/gitea/wsl/sync-1.json` 与 `host-sync-1.json` |
| 真实 API 兼容性检查/修复 | **PASS（未发现需要改代码的 bug）** | 认证头/分页/`since`/base URL/`X-Total-Count`/issue-PR 归一均按实现工作；实测行为见两份报告 §8–§9 |
| 落盘、幂等、失败保留 cursor | **PASS** | 两份报告的同步/重跑输出；失败路径仍由 `tests/feedback.test.mjs` fixture 覆盖 |
| 测试不回归 | **PASS** | `npm test` 81/81 通过；`tests/feedback.test.mjs` 13/13 |
| 文档状态更新 | **PASS（本 agent 范围内）** | `docs/m1-feedback.md` §3/§5/§8/§9 更新；其他 owner 的文档见下方“遗留” |
| 不提交/不发布 | **PASS** | 未 commit/push/release；改动留在工作区 |

## 最终构建复核（集成后重跑）

并行 agent 的 control WIP 曾使全仓 build 短暂失败；其修复后，用**最终构建**对两个真实源各重跑一次，确认证据不是旧 dist 的偶然结果：

```console
$ npm run build
> tsc -p tsconfig.json
# exit 0

$ node --test tests/feedback.test.mjs
ℹ tests 13  ℹ pass 13  ℹ fail 0

$ npm test
ℹ tests 81  ℹ suites 15  ℹ pass 81  ℹ fail 0   # 2026-10-24 07:09 本地
```

- GitHub（同一临时项目）：`fetched=1, added=0, duplicates=1, total=27, unique=26`，cursor 不变 → `evidence/github/sync-4-final-build.json`。
- Gitea（重启隔离实例后，Windows 宿主 `dist/cli.js`）：`fetched=1, added=0, duplicates=1, total=57, unique=57` → `evidence/gitea/host-sync-3-final-build.json`；复核后实例再次停止（`PORT_3000_CLOSED`，无 `gitea web` 进程）→ `evidence/gitea/final-build-check.txt`。
- 最终 `dist/feedback/` 产物 sha256：`evidence/build-feedback-sha256.txt`。

## 环境

| 项 | GitHub 验证 | Gitea 验证 |
|---|---|---|
| 宿主 | Windows 10.0.26300.9711，Node v24.22.0，`gh` 2.102.1 | WSL2 Ubuntu 26.04.1 LTS，Node v22.22.1；另用 Windows Node v24.22.0 跨宿主 |
| 服务端 | `api.github.com`（公开仓库 `JoeKeepGo/SAGE-Kit`） | Gitea 1.27.3（官方 linux-amd64，sha256 校验一致），SQLite，`127.0.0.1:3000` |
| 认证 | `GITHUB_TOKEN=$(gh auth token)`（`gho_`），仅 env | `GITEA_TOKEN`（CLI 生成，`0600` 文件 → env），仅 env |
| 反馈数据 | 25 条既有 issue/PR + 1 条标注测试 issue（#26，已关闭） | 57 条真实 issue（#1–#57，其中 #1 已关闭并留验证评论） |
| 实例状态 | 测试 issue #26 保持关闭（公开仓库中的标注记录） | 实例已停止，保留在 WSL `/home/kayann/sage-kit-gitea`，不在仓库内 |

## 证据索引

```text
reports/m1/
├── README.md                      # 本文件
├── github-real.md                 # 真实 GitHub 报告（命令 + 输出 + 边界）
├── gitea-real.md                  # 真实 Gitea 报告（隔离实例、API、同步、清理）
└── evidence/
    ├── build-feedback-sha256.txt  # 最终 dist/feedback 产物哈希
    ├── github/                    # 真实 GitHub 原始输出
    │   ├── issue-create.txt
    │   ├── sync-1.json
    │   ├── show-issue-26.json
    │   ├── list-1.json
    │   ├── brief.txt
    │   ├── sync-2-idempotent.json
    │   ├── issue-close.txt
    │   ├── issue-view-closed.json
    │   ├── sync-3-after-close.json
    │   └── sync-4-final-build.json
    └── gitea/                     # 真实 Gitea 原始输出
        ├── wsl/                   # WSL 适配器运行证据（env、sync-1..5、show/list/brief、headers、redacted config）
        ├── host-sync-1.json       # Windows 宿主首次全量 57 条
        ├── host-sync-2-idempotent.json
        ├── host-sync-3-final-build.json
        ├── host-list.json
        ├── host-project-dir.txt
        └── final-build-check.txt
```

## 安全与凭据

- 两个源都只从环境变量读取 token；未 echo、未写入仓库、报告或任何证据文件。
- `reports/` 已扫描：无 `gho_` token、无 40-hex token 形态；Gitea `app.ini.redacted` 已把 `SECRET_KEY`/`INTERNAL_TOKEN`/`JWT_SECRET` 全部替换为 `<redacted>`。
- 远端正文作为不可信数据处理：`show`/`list` 带 `untrustedData: true`，brief 只注入截断摘要并加 `UNTRUSTED DATA` 边界。
- GitHub 测试 issue 正文明确声明“自动化验证、不会被当作指令”。

## 遗留（不在本 agent 所有权内）

- `docs/feedback-and-rsi.md` §172 与 `docs/architecture.md` §280 仍写“真实 GitHub/Gitea API 未验证”，需各自 owner 更新。
- GitHub 真实 `Link` 分页、非空 PR review comment、私有仓库/GitHub Enterprise、429 限流；Gitea 公共实例/HTTPS/其他版本仍未验证（详见两份报告“未验证”节）。
- 测试 issue #26 是公开仓库中的历史记录，保留关闭状态；如需彻底清理需仓库 owner 删除。
