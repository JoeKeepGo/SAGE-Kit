# M1 真实 Gitea 反馈同步验证（WSL2 隔离实例）

- 任务：task-11（M1 真实 GitHub + WSL 隔离 Gitea 联调）
- 日期：2026-10-23 UTC（本地 2026-10-24，Pacific/Auckland）
- Gitea：**1.27.3**（官方 `linux-amd64`，sha256 校验一致），SQLite，仅监听 `127.0.0.1:3000`
- 工作目录：`/home/kayann/sage-kit-gitea`（WSL2 内，仓库外、隔离）
- 适配器宿主：WSL2 Ubuntu 26.04.1 LTS / Node v22.22.1；跨宿主另用 Windows / Node v24.22.0
- 被测代码：`/mnt/d/Projects/SAGE-Kit/dist/cli.js`（`src/feedback/**` 自提交 `5690d73` 起未改动）
- 原始输出：`reports/m1/evidence/gitea/`

## 结论摘要

| 事项 | 状态 | 说明 |
|---|---|---|
| 隔离 Gitea 实例启动 | **PASS** | 1.27.3，SQLite，`127.0.0.1:3000`，二进制 sha256 与官方一致 |
| 真实 API 创建用户/仓库/issue | **PASS** | `m1test/m1-feedback-test`，共 57 条 issue |
| 真实 `feedback sync --source gitea` | **PASS** | `fetched=57, added=57`（首次全量） |
| 分页（>50 条） | **PASS** | 过滤后 56 条分 2 页，`1.16s`，`X-Total-Count` 生效 |
| `since` 增量 | **PASS** | 新 issue 后 `fetched=2, added=1`；包含边界语义 |
| 幂等重跑 | **PASS** | `fetched=1, added=0, duplicates=1` |
| 本地时区时间戳归一 | **PASS** | Gitea 返回 `+13:00`，入库/cursor 为 UTC `.000Z` |
| issue 更新（close）→ 新版本 | **PASS** | `total=58, unique=57`，最新 `state=closed` |
| Windows 宿主跨 WSL 同步 | **PASS** | Windows `dist/cli.js` 经 localhost 转发 `fetched=57, added=57` |
| token 不输出/不落盘 | **PASS** | token 仅 `0600` 文件 → env；报告/证据已扫描 |
| 实例清理 | **PASS** | kill 后 2s 退出，端口 3000 关闭，无 `gitea web` 进程 |
| Gitea PR review comments | **NOT_IMPLEMENTED** | M1 按契约不同步（`comments=false`） |
| Gitea 公共实例/HTTPS | **NOT_VERIFIED** | 仅验证本机 loopback + 1.27.3 |

## 1. 隔离与凭据边界

- 全部状态在 WSL `/home/kayann/sage-kit-gitea`（`data/`、`custom/`、`log/`、SQLite、仓库裸库），不接触 Windows 仓库目录；仓库内只保存证据副本。
- Gitea 配置：`HTTP_ADDR=127.0.0.1`、`HTTP_PORT=3000`、`DISABLE_SSH=true`、`OFFLINE_MODE=true`、`INSTALL_LOCK=true`、关闭注册/邮件/OpenID/cron；`SECRET_KEY`/`INTERNAL_TOKEN` 由 `gitea generate secret` 生成，报告中的配置副本已全部替换为 `<redacted>`（含自动生成的 `JWT_SECRET`）。
- token 用 `gitea admin user generate-access-token` 生成，只写入 `/home/kayann/sage-kit-gitea/token.txt`（`0600`），随后只在 shell 变量 `GITEA_TOKEN` 中使用；未 echo、未复制到仓库或报告。
- 测试用户密码随机生成，写入 `credentials.txt`（`0600`），未输出。

## 2. 下载与校验

```console
$ wsl -e bash -lc 'cd /home/kayann/sage-kit-gitea && curl -fsSL -o gitea.part https://dl.gitea.com/gitea/1.27.3/gitea-1.27.3-linux-amd64 && mv gitea.part gitea && chmod +x gitea'
$ ./gitea --version
gitea version 1.27.3 built with go1.26.7-X:jsonv2 : bindata
$ sha256sum gitea
4da93c2c10b6980c359bcb86d5573ebfd7770e2e151756534edee24c8c12d971  gitea
$ curl -fsSL https://dl.gitea.com/gitea/1.27.3/gitea-1.27.3-linux-amd64.sha256
4da93c2c10b6980c359bcb86d5573ebfd7770e2e151756534edee24c8c12d971  gitea-1.27.3-linux-amd64
# SHA256_OK（expected == actual）
```

## 3. 初始化（SQLite + 本地回环）

```bash
D=/home/kayann/sage-kit-gitea
cd "$D"
./gitea generate secret SECRET_KEY    # 写入 app.ini，报告副本已 redacted
./gitea generate secret INTERNAL_TOKEN
# app.ini（完整版见 reports/m1/evidence/gitea/wsl/app.ini.redacted）
./gitea migrate --work-path "$D" --config "$D/custom/conf/app.ini"
PW=$(openssl rand -hex 16)            # 密码不记录
echo "m1test:$PW" > credentials.txt && chmod 600 credentials.txt
./gitea admin user create --username m1test --password "$PW" --email m1test@example.local \
  --admin --must-change-password=false --work-path "$D" --config "$D/custom/conf/app.ini"
# New user 'm1test' has been successfully created!
./gitea admin user generate-access-token --username m1test --token-name sage-kit-m1 --scopes all \
  --work-path "$D" --config "$D/custom/conf/app.ini" > token.txt   # 0600，未输出
setsid nohup ./gitea web --work-path "$D" --config "$D/custom/conf/app.ini" \
  > "$D/log/console.log" 2>&1 < /dev/null &
# server_up_after=2s
$ curl -s http://127.0.0.1:3000/api/v1/version
{"version":"1.27.3"}
$ ss -ltn | grep 3000
LISTEN 0 4096 127.0.0.1:3000 0.0.0.0:*
```

## 4. 真实数据（API 创建）

```console
# 仓库
POST /api/v1/user/repos {"name":"m1-feedback-test", ...}
→ "full_name":"m1test/m1-feedback-test", "default_branch":"main"

# 测试 issue #1（后续 #2，再用循环创建 #3–#57，共 57 条）
POST /api/v1/repos/m1test/m1-feedback-test/issues
→ "html_url":"http://127.0.0.1:3000/m1test/m1-feedback-test/issues/1"
   "number":1
   "title":"[SAGE-Kit M1 real-API test] Gitea sync probe"
   "state":"open"
   "created_at":"2026-10-24T07:03:50+13:00"
   "updated_at":"2026-10-24T07:03:50+13:00"
```

注意时间戳是 Gitea 服务器**本地时区 RFC3339**（`+13:00`），不是 UTC。

`X-Total-Count` 实测存在，且随 `since` 过滤变化：

```console
$ curl -sSD - -o /dev/null -H "Authorization: token $GITEA_TOKEN" \
    "$API/repos/m1test/m1-feedback-test/issues?state=all&limit=1&page=1" | grep -i x-total-count
X-Total-Count: 57                                   # 未过滤

$ curl -sSD - -o /dev/null -G -H "Authorization: token $GITEA_TOKEN" \
    --data-urlencode "state=all" --data-urlencode "limit=50" --data-urlencode "page=1" \
    --data-urlencode "since=2026-10-23T18:04:43.000Z" \
    "$API/repos/m1test/m1-feedback-test/issues" | grep -i x-total-count
X-Total-Count: 56                                   # since 过滤后
```

`since` 行为探测（真实 1.27.3）：

| `since` 值 | HTTP | 返回条数 |
|---|---|---|
| `2030-01-01T00:00:00.000Z`（未来） | 200 | 0 |
| `2000-01-01T00:00:00.000Z`（过去） | 200 | 1 |
| `2026-10-23T18:03:50.000Z`（= item updatedAt，UTC） | 200 | 1（包含边界） |
| `2026-10-23T18:03:50.000Z` 未 URL 编码地传 `+13:00` 形式 | 422 | 参数里的 `+` 被当成空格；适配器用 `URLSearchParams` 编码，无此问题 |

## 5. 适配器真实同步（WSL）

```bash
cd /home/kayann/sage-kit-gitea/project
export GITEA_API_URL='http://127.0.0.1:3000/api/v1'
export GITEA_TOKEN="$(grep -oE '[0-9a-f]{40}' /home/kayann/sage-kit-gitea/token.txt)"  # 不 echo
node /mnt/d/Projects/SAGE-Kit/dist/cli.js feedback sync --source gitea --repo m1test/m1-feedback-test --json
```

### 5.1 首次全量（1 条）

```json
{ "ok": true, "source": "gitea", "repo": "m1test/m1-feedback-test",
  "fetched": 1, "added": 1, "duplicates": 0, "total": 1, "unique": 1,
  "cursor": "2026-10-23T18:03:50.000Z",
  "cursorKey": "gitea:m1test/m1-feedback-test", "untrustedData": true }
```

源时间戳 `2026-10-24T07:03:50+13:00` → 入库/cursor `2026-10-23T18:03:50.000Z`（utc 归一正确）。`show gitea:m1test/m1-feedback-test:issue:1 --json` 返回 `state: open`、`author: m1test`、本地 URL；`brief` 注入 Gitea `UNTRUSTED DATA` 块。

### 5.2 幂等重跑

```json
{ "fetched": 1, "added": 0, "duplicates": 1, "total": 1, "unique": 1,
  "cursor": "2026-10-23T18:03:50.000Z", "untrustedData": true }
```

### 5.3 新 issue 后增量（since 包含边界）

issue #2 创建后：

```json
{ "fetched": 2, "added": 1, "duplicates": 1, "total": 2, "unique": 2,
  "cursor": "2026-10-23T18:04:43.000Z", "untrustedData": true }
```

取回 cursor 对应的旧条目 + 新条目；fingerprint 去重后只新增 1 条。

### 5.4 57 条分页（>50 → 2 页）

创建 #3–#57 后：

```json
{ "ok": true, "source": "gitea", "repo": "m1test/m1-feedback-test",
  "fetched": 56, "added": 55, "duplicates": 1, "total": 57, "unique": 57,
  "cursor": "2026-10-23T18:04:59.000Z", "untrustedData": true }
elapsed=1.16s
```

`fetched=56 > limit 50` 即真实翻页证据；`X-Total-Count`（过滤后 56）路径被实际使用。

### 5.5 关闭 issue #1 后 → 新版本

```console
$ curl ... -X POST "$API/repos/m1test/m1-feedback-test/issues/1/comments" -d '{"body":"Verified by SAGE-Kit M1 real-API run ..."}'
$ curl ... -X PATCH "$API/repos/m1test/m1-feedback-test/issues/1" -d '{"state":"closed"}'
"number":1, "state":"closed", "comments":1,
"updated_at":"2026-10-24T07:05:13+13:00", "closed_at":"2026-10-24T07:05:13+13:00"
```

重跑：

```json
{ "fetched": 15, "added": 1, "duplicates": 14, "total": 58, "unique": 57,
  "cursor": "2026-10-23T18:05:13.000Z", "untrustedData": true }
```

`fetched=15`：cursor 为前一秒水位，包含边界 + 同一秒内批量创建的 14 条会被重复取回，fingerprint 去重后只新增关闭 issue 的新版本。最新版本：

```console
$ node dist/cli.js feedback show gitea:m1test/m1-feedback-test:issue:1 --json
"fingerprint": "sha256:4f928eea19363901d653ad25198d07898502363b691b465f52b3d149d23bfb94",
"state": "closed",
"updatedAt": "2026-10-23T18:05:13.000Z"
$ node dist/cli.js feedback list --json   → count=57
```

## 6. 跨宿主：Windows `dist/cli.js` → WSL Gitea

WSL2 localhost 转发使 Windows 宿主可直接访问 `127.0.0.1:3000`：

```console
$ curl -s http://127.0.0.1:3000/api/v1/version
{"version":"1.27.3"}
```

Windows 侧隔离临时项目（`/tmp/sage-m1-gitea-host.AVrHVP`），token 经命令替换从 WSL `0600` 文件读入 env（未输出）：

```console
$ export GITEA_API_URL='http://127.0.0.1:3000/api/v1'
$ export GITEA_TOKEN="$(wsl.exe -e bash -lc 'grep -oE "[0-9a-f]{40}" /home/kayann/sage-kit-gitea/token.txt | head -1')"
$ node dist/cli.js feedback sync --source gitea --repo m1test/m1-feedback-test --json
{ "fetched": 57, "added": 57, "duplicates": 0, "total": 57, "unique": 57,
  "cursor": "2026-10-23T18:05:13.000Z", "untrustedData": true }
$ node dist/cli.js feedback sync --source gitea --repo m1test/m1-feedback-test --json
{ "fetched": 1, "added": 0, "duplicates": 1, "total": 57, "unique": 57, "untrustedData": true }
$ node dist/cli.js feedback list --json → count=57
```

## 7. 清理与隔离确认

```console
$ kill "$(cat gitea.pid)"; # waited
stopped_after=2s
$ ss -ltn | grep ':3000' || echo PORT_3000_CLOSED
PORT_3000_CLOSED
$ pgrep -af '[g]itea web' || echo NO_GITEA_WEB_PROCESS
NO_GITEA_WEB_PROCESS
```

- 实例目录保留在 WSL `/home/kayann/sage-kit-gitea`（`gitea` 二进制、SQLite、token 文件 `0600`、`project/.sage-kit`），**不在仓库内**，未提交。
- 仓库内只有 `reports/m1/evidence/gitea/**` 证据副本；`app.ini.redacted` 已确认 `SECRET_KEY`/`INTERNAL_TOKEN`/`JWT_SECRET` 全部为 `<redacted>`；证据目录扫描无 40-hex token、无 `gho_`。
- 统计：`items.jsonl` 58 行 = 57 unique id + 1 个关闭后新版本；`items_sha256=6508b3b7...`（见 `evidence/gitea/wsl/store-summary.txt`）。

## 8. 实测 API 行为记录

| 假设/行为 | 真实结果（Gitea 1.27.3） |
|---|---|
| `Authorization: token <token>` | 接受 |
| `X-Total-Count` 响应头 | 存在且随 `since` 过滤变化（57 → 56） |
| `since`（RFC3339，含 `.000Z`） | 接受；包含边界（`updated_at >= since`） |
| `state=all&page&limit=50` | 接受；filtered 56 条分 2 页 |
| Gitea 时间戳时区 | 服务器本地时区（`+13:00`），适配器归一为 UTC |
| issue 更新语义 | `updated_at` 变化 → 新 fingerprint → 追加新版本 |
| 未编码的 `+` 时区偏移 | 422（query 中 `+` 被当空格）；适配器用 `URLSearchParams` 编码，无此问题 |
| 空评论 / review comments | M1 不请求 Gitea review comments（`comments=false`） |

## 9. 未验证 / 残余边界

- 仅验证 Gitea **1.27.3 + SQLite + 本机 loopback**；`gitea.com` 公共实例、其他版本、HTTPS/反向代理、负载下的行为未验证。
- Gitea PR 在 issue 列表中的 `pull_request` 字段未真实构造验证（测试仓库无 PR）；M1 只同步 issues。
- Gitea review comments / checks 不同步（M1 契约）。
- 限流、ETag、重试/退避未实现（与 M1 设计一致）。
- 跨宿主的 localhost 转发在本次 Windows/WSL 组合可用，但不代表所有 WSL 配置。

## 10. 证据文件

`reports/m1/evidence/gitea/`：

- `wsl/env.txt`、`wsl/version.json`、`wsl/repo-create.json`、`wsl/issue-create.json`、`wsl/issue-2-create.json`、`wsl/bulk-create.txt`
- `wsl/sync-1.json`、`wsl/sync-2-idempotent.json`、`wsl/sync-3-incremental.json`、`wsl/sync-4-pagination.json`、`wsl/sync-4-time.txt`、`wsl/sync-5-after-close.json`
- `wsl/show-issue-1.json`、`wsl/show-issue-1-closed.json`、`wsl/list-final.json`、`wsl/brief.txt`、`wsl/issues-headers.txt`、`wsl/issue-1-close.json`、`wsl/issue-1-comment.json`
- `wsl/store-summary.txt`、`wsl/app.ini.redacted`、`wsl/console.log`
- 跨宿主：`host-sync-1.json`、`host-sync-2-idempotent.json`、`host-list.json`、`host-project-dir.txt`
