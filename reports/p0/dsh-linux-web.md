# Linux 上的真实 DSH Web 部署验证

日期：2026-10-24  
环境：WSL2 Ubuntu 26.04.1 LTS；Node v22.22.1；npm 9.2.0；DSH npm 包 `@deepseek-ai/dsh@0.2.1-rc.2`  
隔离目录：`/home/kayann/sage-kit-linux-dsh`

## 安装方式

没有使用桌面应用，而是在 Linux 文件系统中直接安装公开的 npm 包：

```bash
mkdir -p /home/kayann/sage-kit-linux-dsh/{home,project,npm-cache}
export DSH_HOME=/home/kayann/sage-kit-linux-dsh/home
export npm_config_cache=/home/kayann/sage-kit-linux-dsh/npm-cache
cd /home/kayann/sage-kit-linux-dsh
npm init -y
npm install --no-audit --no-fund @deepseek-ai/dsh@0.2.1-rc.2
./node_modules/.bin/dsh --version
```

结果：`0.2.1-rc.2`，共安装 618 个包。随后在 `project/` 中安装 SAGE-Kit 并执行：

```bash
./node_modules/.bin/sage-kit init --host dsh --scope project
```

生成了 `.dsh/skills/sage-kit/SKILL.md`、`.sage-kit/config.json` 和受管 `AGENTS.md`。

## Web 启动

```bash
cd /home/kayann/sage-kit-linux-dsh/project
export DSH_HOME=/home/kayann/sage-kit-linux-dsh/home
../node_modules/.bin/dsh web --no-open --host 127.0.0.1 --port 18766
```

实际启动日志：

```text
dsh web: http://127.0.0.1:18766/?token=<process-token>
```

验证：

- 无 token 访问 `/`：HTTP 401；
- 带 token 访问：HTTP 303，设置 `dsh-auth-*` cookie；
- 跟随重定向：HTTP 200，返回约 37,512 字节的 SPA HTML；
- 页面包含 boot/module loader 脚本，不是静态占位页。

## Linux 上的 Skill 加载

用同一 Linux DSH 安装运行 headless，并用本地 mock Messages 端点触发一次 `skill` 工具调用。实际事件：

```text
{"type":"tool_call","tool":"skill","input":{"name":"sage-kit"}}
{"type":"tool_result","status":"completed","result":"<skill_content name=\"sage-kit\">..."}
{"type":"final","text":"READY"}
```

这证明 Linux 上的 DSH 运行时同样能发现项目 `.dsh/skills/sage-kit`，并加载完整的 SAGE-Kit Skill。

持久环境的一键回归脚本 `refresh-and-test.sh` 已跑通当前源码：Linux 构建成功、`npm test` 10/10、项目安装最新 tgz、DSH headless 再次返回 `skill` 工具结果。

## 结论

**DSH Web 可以部署在 Linux 上，不需要桌面应用或 Electron。** `@deepseek-ai/dsh` 是公开 npm 包，`dsh web` 用 Node 启动浏览器 UI；`dsh-base` 在 Linux 上使用 bash 工具栈。

## 生产化注意事项

1. **版本锁定**：当前是 `0.2.1-rc.2`，生产应锁定精确版本并保留 npm lockfile。
2. **不要直接暴露**：默认只适合单用户/本机；对外服务必须加 TLS、反向代理、访问控制，不能只依赖启动 token。
3. **单用户语义**：Web surface 仍是单用户 GUI，不是多租户服务；不要把它直接当成多玩家共享服务。
4. **进程管理**：用 systemd/容器托管，不要依赖交互式终端后台进程；DSH 需要一个持续运行的 Node 进程。
5. **浏览器验收**：本次验证了 HTTP/SPA、token/cookie 和 headless Skill 加载；真实浏览器交互、真实模型和 GUI 端到端仍未验收。

## 复现脚本

在 WSL 中：

```bash
/home/kayann/sage-kit-linux-dsh/start-web.sh   # 启动 Web GUI
/home/kayann/sage-kit-linux-dsh/run-headless.sh # Linux headless + mock Skill 调用
```
