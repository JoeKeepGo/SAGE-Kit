/**
 * Minimal read-only control panel served at `/` and `/ui`.
 *
 * The page itself is public (no data); every `/v1/*` request still requires the
 * Bearer token and is performed from the browser with the token typed by the
 * user. No write buttons are provided.
 */
export function renderControlUiHtml(): string {
  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAGE-Kit Control · 只读</title>
<style>
  :root { color-scheme: dark light; --bg:#0f1115; --panel:#171a21; --line:#2b303b; --text:#e8eaf0; --muted:#9aa3b2; --accent:#7dd3fc; --ok:#86efac; --warn:#fbbf24; --bad:#fca5a5; }
  * { box-sizing: border-box; }
  body { margin:0; font:14px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; background:var(--bg); color:var(--text); }
  header { padding:20px 24px; border-bottom:1px solid var(--line); display:flex; gap:16px; align-items:baseline; flex-wrap:wrap; }
  header h1 { font-size:18px; margin:0; letter-spacing:.02em; }
  header span { color:var(--muted); font-size:12px; }
  main { max-width:1100px; margin:0 auto; padding:20px 24px 48px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; margin-bottom:16px; }
  label { display:block; color:var(--muted); font-size:12px; margin-bottom:6px; }
  input { width:100%; padding:9px 10px; border-radius:8px; border:1px solid var(--line); background:#0b0d11; color:var(--text); font:inherit; }
  .row { display:flex; gap:10px; align-items:end; flex-wrap:wrap; }
  .row > div { flex:1 1 320px; }
  button { padding:9px 14px; border-radius:8px; border:1px solid #2563eb; background:#1d4ed8; color:white; font:inherit; cursor:pointer; }
  button.secondary { background:transparent; border-color:var(--line); color:var(--text); }
  button:disabled { opacity:.45; cursor:not-allowed; }
  .muted { color:var(--muted); }
  .error { color:var(--bad); white-space:pre-wrap; }
  .ok { color:var(--ok); }
  .stats { display:flex; gap:10px; flex-wrap:wrap; }
  .stat { border:1px solid var(--line); border-radius:8px; padding:8px 12px; min-width:120px; }
  .stat b { display:block; font-size:18px; }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { color:var(--muted); font-weight:500; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
  tbody tr { cursor:pointer; }
  tbody tr:hover { background:#1d212a; }
  .pill { display:inline-block; padding:1px 8px; border-radius:999px; border:1px solid var(--line); font-size:12px; }
  pre { margin:0; padding:12px; background:#0b0d11; border:1px solid var(--line); border-radius:8px; overflow:auto; max-height:320px; white-space:pre-wrap; }
  footer { color:var(--muted); font-size:12px; padding-top:8px; }
</style>
</head>
<body>
<header>
  <h1>SAGE-Kit Control</h1>
  <span>只读预览 · 任务/健康状态 · 不提供写入操作</span>
</header>
<main>
  <section class="card">
    <div class="row">
      <div>
        <label for="token">控制面 Bearer Token（只存 sessionStorage，不发往外部）</label>
        <input id="token" type="password" autocomplete="off" placeholder="粘贴 control serve 输出的 token">
      </div>
      <button id="load">连接并刷新</button>
      <button id="clear" class="secondary">清除 token</button>
    </div>
    <p id="status" class="muted" role="status">未连接。</p>
    <pre id="error" class="error" hidden></pre>
  </section>

  <section class="card">
    <div class="stats">
      <div class="stat"><span class="muted">service</span><b id="service">—</b></div>
      <div class="stat"><span class="muted">schema</span><b id="schema">—</b></div>
      <div class="stat"><span class="muted">tasks</span><b id="count">—</b></div>
    </div>
  </section>

  <section class="card">
    <table>
      <thead><tr><th>id</th><th>title</th><th>status</th><th>updated</th><th>branch</th></tr></thead>
      <tbody id="tasks"><tr><td colspan="5" class="muted">连接后显示 tasks。</td></tr></tbody>
    </table>
  </section>

  <section class="card">
    <div class="row"><div><label>选中任务详情（只读 JSON）</label></div><button id="detail" class="secondary" disabled>查看选中任务</button></div>
    <pre id="json" class="muted">点击一行任务后查看详情。</pre>
  </section>

  <footer>本页只读取 <code>/v1/health</code> 与 <code>/v1/tasks</code>。没有创建/修改/租约操作。</footer>
</main>
<script>
(function () {
  "use strict";
  var TOKEN_KEY = "sage-kit-control-token";
  var tokenInput = document.getElementById("token");
  var statusEl = document.getElementById("status");
  var errorEl = document.getElementById("error");
  var serviceEl = document.getElementById("service");
  var schemaEl = document.getElementById("schema");
  var countEl = document.getElementById("count");
  var tasksEl = document.getElementById("tasks");
  var jsonEl = document.getElementById("json");
  var detailButton = document.getElementById("detail");
  var selectedId = null;

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function readTokenFromHash() {
    if (!location.hash || location.hash.indexOf("#token=") !== 0) return "";
    var token = decodeURIComponent(location.hash.slice(7));
    history.replaceState(null, "", location.pathname);
    return token;
  }

  function showError(message) {
    errorEl.hidden = false;
    errorEl.textContent = String(message);
    statusEl.textContent = "连接失败。";
  }

  function clearError() {
    errorEl.hidden = true;
    errorEl.textContent = "";
  }

  async function api(path) {
    var token = tokenInput.value.trim();
    if (!token) throw new Error("请先填写 Bearer token。");
    var response = await fetch(path, { headers: { authorization: "Bearer " + token } });
    var data = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      var detail = data && data.error ? data.error.message : response.statusText;
      throw new Error("HTTP " + response.status + ": " + detail);
    }
    return data;
  }

  function renderTasks(tasks) {
    if (!tasks.length) {
      tasksEl.innerHTML = '<tr><td colspan="5" class="muted">没有 task。</td></tr>';
      return;
    }
    tasksEl.innerHTML = tasks.map(function (task) {
      return '<tr data-id="' + esc(task.id) + '">' +
        '<td><code>' + esc(task.id) + '</code></td>' +
        '<td>' + esc(task.title) + '</td>' +
        '<td><span class="pill">' + esc(task.status) + '</span></td>' +
        '<td class="muted">' + esc(task.updatedAt) + '</td>' +
        '<td class="muted">' + esc(task.branch || "—") + '</td>' +
        '</tr>';
    }).join("");
    Array.prototype.forEach.call(tasksEl.querySelectorAll("tr[data-id]"), function (row) {
      row.addEventListener("click", function () {
        selectedId = row.getAttribute("data-id");
        Array.prototype.forEach.call(tasksEl.querySelectorAll("tr"), function (other) {
          other.style.background = other === row ? "#1d212a" : "";
        });
        detailButton.disabled = false;
        jsonEl.classList.remove("muted");
        jsonEl.textContent = "已选择 " + selectedId + "，点击“查看选中任务”。";
      });
    });
  }

  async function load() {
    clearError();
    var token = readTokenFromHash() || tokenInput.value.trim() || sessionStorage.getItem(TOKEN_KEY) || "";
    tokenInput.value = token;
    if (!token) {
      showError("需要 control serve 的 Bearer token。");
      return;
    }
    sessionStorage.setItem(TOKEN_KEY, token);
    statusEl.textContent = "读取中…";
    try {
      var results = await Promise.all([api("/v1/health"), api("/v1/tasks")]);
      var health = results[0];
      var tasks = results[1].tasks || [];
      serviceEl.textContent = health.service || "—";
      schemaEl.textContent = String(health.schemaVersion == null ? "—" : health.schemaVersion);
      countEl.textContent = String(tasks.length);
      statusEl.textContent = "已连接 · " + (health.now || "ok");
      renderTasks(tasks);
      selectedId = null;
      detailButton.disabled = true;
      jsonEl.classList.add("muted");
      jsonEl.textContent = "点击一行任务后查看详情。";
    } catch (error) {
      showError(error && error.message ? error.message : String(error));
    }
  }

  async function loadDetail() {
    if (!selectedId) return;
    clearError();
    try {
      var data = await api("/v1/tasks/" + encodeURIComponent(selectedId));
      jsonEl.classList.remove("muted");
      jsonEl.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      showError(error && error.message ? error.message : String(error));
    }
  }

  document.getElementById("load").addEventListener("click", load);
  document.getElementById("clear").addEventListener("click", function () {
    sessionStorage.removeItem(TOKEN_KEY);
    tokenInput.value = "";
    statusEl.textContent = "token 已清除。";
    clearError();
  });
  detailButton.addEventListener("click", loadDetail);
  tokenInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") load();
  });

  var fromHash = readTokenFromHash();
  if (fromHash) tokenInput.value = fromHash;
  if (tokenInput.value.trim() || sessionStorage.getItem(TOKEN_KEY)) load();
})();
</script>
</body>
</html>`;
}
