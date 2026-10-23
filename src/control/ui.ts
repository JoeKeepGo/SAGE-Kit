/**
 * Read-only control panel served at `GET /` and `GET /ui`.
 *
 * The panel is a single self-contained HTML document:
 * - no external assets (CSP `default-src 'none'` compatible),
 * - no authentication UI: the loopback server is the trust boundary, so the
 *   page auto-loads `/v1/health` and `/v1/tasks` on open,
 * - one click on a task row immediately loads `GET /v1/tasks/:id`,
 * - every rendered value goes through `textContent` (no `innerHTML` with data),
 * - all reads are GETs; there is no write path.
 *
 * The inline script is deliberately a classic (non-module) script so the HTML
 * can carry it inline under the server's CSP.
 */
export function renderControlUiHtml(): string {
  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>SAGE-Kit Control · 只读控制面板</title>
<style>
:root {
  --bg: #f6f7f9;
  --surface: #ffffff;
  --surface-2: #f1f3f6;
  --border: #e3e6ea;
  --border-strong: #d4d8de;
  --text: #16181d;
  --text-2: #4b5563;
  --text-3: #8b93a1;
  --accent: #2563eb;
  --accent-soft: #eff4ff;
  --accent-border: #c7d7fb;
  --blue: #1d4ed8;
  --blue-soft: #e8efff;
  --amber: #a16207;
  --amber-soft: #fff7e0;
  --green: #15803d;
  --green-soft: #e9f7ef;
  --orange: #c2410c;
  --orange-soft: #fff1e8;
  --violet: #6d28d9;
  --violet-soft: #f2edff;
  --red: #b91c1c;
  --red-soft: #fdecec;
  --red-border: #f3c1c1;
  --slate: #475569;
  --slate-soft: #eef1f5;
  --shadow: 0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06);
  --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  --fs-12: 12px;
  --fs-13: 13px;
  --fs-14: 14px;
  --fs-16: 16px;
  --fs-20: 20px;
  --fs-28: 28px;
  --sp-8: 8px;
  --sp-12: 12px;
  --sp-16: 16px;
  --sp-24: 24px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1216;
    --surface: #161a20;
    --surface-2: #1c222a;
    --border: #2a323d;
    --border-strong: #3a4452;
    --text: #e7ebf0;
    --text-2: #aeb8c4;
    --text-3: #7d8896;
    --accent: #6ea8ff;
    --accent-soft: #1b2a44;
    --accent-border: #2f4a75;
    --blue: #93b4ff;
    --blue-soft: #1a2540;
    --amber: #f0c674;
    --amber-soft: #2b2312;
    --green: #6ee7a8;
    --green-soft: #132a20;
    --orange: #f4a678;
    --orange-soft: #2e1d12;
    --violet: #c4a7ff;
    --violet-soft: #241b3a;
    --red: #ff9b9b;
    --red-soft: #331a1e;
    --red-border: #5a2a2f;
    --slate: #c3ccd8;
    --slate-soft: #252c36;
    --shadow: none;
  }
}
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: var(--fs-14);
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, p, dl, dt, dd, ul, ol, li, figure { margin: 0; padding: 0; }
ul, ol { list-style: none; }
button { font: inherit; color: inherit; }
code, pre { font-family: var(--font-mono); }
[hidden] { display: none !important; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  z-index: 100;
  padding: var(--sp-8) var(--sp-12);
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
}
.skip-link:focus { left: var(--sp-8); top: var(--sp-8); }

.app-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-16);
  padding: var(--sp-12) var(--sp-24);
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.brand { display: flex; align-items: center; gap: var(--sp-12); min-width: 0; }
.brand-mark {
  display: grid;
  place-items: center;
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--accent);
  color: #ffffff;
  font-size: var(--fs-13);
  font-weight: 700;
  letter-spacing: 0.04em;
}
.brand-text { min-width: 0; }
.brand-text h1 {
  font-size: var(--fs-28);
  line-height: 1.15;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.brand-sub { font-size: var(--fs-12); color: var(--text-3); }
.badge {
  flex: none;
  padding: 0 var(--sp-8);
  border: 1px solid var(--accent-border);
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: var(--fs-12);
  font-weight: 600;
  line-height: 22px;
}
.app-actions { display: flex; align-items: center; gap: var(--sp-12); }
.health {
  display: flex;
  align-items: center;
  gap: var(--sp-8);
  max-width: 380px;
  overflow: hidden;
  color: var(--text-3);
  font-size: var(--fs-12);
  white-space: nowrap;
  text-overflow: ellipsis;
}
.dot { flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--text-3); }
.dot-ok { background: var(--green); }
.dot-err { background: var(--red); }
.dot-idle { background: var(--text-3); }
.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-8);
  padding: var(--sp-8) var(--sp-12);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: var(--fs-13);
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.btn:hover { background: var(--surface-2); }
.btn:disabled { opacity: 0.6; cursor: default; }
.btn-primary { border-color: var(--accent-border); background: var(--accent-soft); color: var(--accent); }
.btn-primary:hover { background: var(--surface-2); }
.btn-small { padding: var(--sp-8) var(--sp-12); font-size: var(--fs-12); }
.btn-icon { font-size: var(--fs-14); line-height: 1; }
.btn.is-loading .btn-icon { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-16);
  margin: var(--sp-16) var(--sp-24) 0;
  padding: var(--sp-12) var(--sp-16);
  border: 1px solid var(--red-border);
  border-radius: 12px;
  background: var(--red-soft);
  color: var(--red);
  font-size: var(--fs-13);
}
.alert-text { overflow-wrap: anywhere; }

.app-main {
  display: grid;
  grid-template-columns: minmax(320px, 400px) minmax(0, 1fr);
  gap: var(--sp-16);
  align-items: start;
  max-width: 1440px;
  margin: 0 auto;
  padding: var(--sp-16) var(--sp-24) var(--sp-24);
}
.card {
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  box-shadow: var(--shadow);
}
.list-card {
  position: sticky;
  top: 76px;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 96px);
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-8);
  padding: var(--sp-12) var(--sp-16);
  border-bottom: 1px solid var(--border);
}
.card-title { font-size: var(--fs-16); font-weight: 600; letter-spacing: -0.01em; }
.card-sub { overflow: hidden; color: var(--text-3); font-size: var(--fs-12); font-weight: 500; white-space: nowrap; text-overflow: ellipsis; }
.list-toolbar { padding: var(--sp-12) var(--sp-12) var(--sp-8); }
.search { display: block; color: var(--text-3); font-size: var(--fs-12); }
.search-label { display: block; margin-bottom: var(--sp-8); font-weight: 600; letter-spacing: 0.02em; }
#task-filter {
  width: 100%;
  padding: var(--sp-8) var(--sp-12);
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: var(--fs-13);
}
#task-filter:focus { border-color: var(--accent); outline: 2px solid var(--accent-soft); }
.task-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-8);
  min-height: 200px;
  padding: var(--sp-8) var(--sp-8) var(--sp-12);
  overflow: auto;
}
.task-item {
  display: flex;
  flex-direction: column;
  gap: var(--sp-8);
  width: 100%;
  padding: var(--sp-12);
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease, border-color 0.12s ease;
}
.task-item:hover { background: var(--surface-2); }
.task-item.is-active { border-color: var(--accent-border); background: var(--accent-soft); }
.task-item-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--sp-8); }
.task-item-title {
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow-wrap: anywhere;
  font-size: var(--fs-14);
  font-weight: 600;
  line-height: 1.4;
}
.task-item-meta { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-8); min-width: 0; color: var(--text-3); font-size: var(--fs-12); }
.id-inline { color: var(--text-2); font-size: var(--fs-12); }
.dot-sep { color: var(--text-3); }
.priority-chip {
  flex: none;
  padding: 0 var(--sp-8);
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--text-2);
  font-size: var(--fs-12);
  line-height: 22px;
}
.pill {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: var(--sp-8);
  padding: 0 var(--sp-8);
  border-radius: 999px;
  background: var(--slate-soft);
  color: var(--slate);
  font-size: var(--fs-12);
  font-weight: 600;
  line-height: 22px;
  white-space: nowrap;
}
.pill-dot { flex: none; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.pill.s-imported { background: var(--slate-soft); color: var(--slate); }
.pill.s-ready { background: var(--blue-soft); color: var(--blue); }
.pill.s-running { background: var(--amber-soft); color: var(--amber); }
.pill.s-review { background: var(--violet-soft); color: var(--violet); }
.pill.s-done { background: var(--green-soft); color: var(--green); }
.pill.s-blocked { background: var(--orange-soft); color: var(--orange); }
.pill.s-failed { background: var(--red-soft); color: var(--red); }
.pill.s-cancelled { background: var(--slate-soft); color: var(--text-3); }
.pill.s-interrupted { background: var(--amber-soft); color: var(--orange); }
.pill.s-unknown { background: var(--slate-soft); color: var(--slate); }

.list-empty { display: flex; flex-direction: column; align-items: center; gap: var(--sp-8); padding: var(--sp-24) var(--sp-12); text-align: center; }
.list-empty-title { color: var(--text-2); font-size: var(--fs-13); font-weight: 600; }
.list-empty-text { color: var(--text-3); font-size: var(--fs-12); line-height: 1.6; }
.noscript { margin: var(--sp-24); padding: var(--sp-16); border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text-2); font-size: var(--fs-13); }

.detail-card { min-height: calc(100vh - 124px); }
.detail-scroll { padding: var(--sp-24); }
.detail-body { display: flex; flex-direction: column; }
.detail-head { padding-bottom: var(--sp-16); border-bottom: 1px solid var(--border); }
.detail-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--sp-16); }
.detail-title { overflow-wrap: anywhere; font-size: var(--fs-20); font-weight: 700; line-height: 1.3; letter-spacing: -0.01em; }
.detail-sub { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-12); margin-top: var(--sp-8); color: var(--text-3); font-size: var(--fs-13); }
.id-chip {
  padding: 0 var(--sp-8);
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--text-2);
  font-size: var(--fs-13);
  line-height: 22px;
  overflow-wrap: anywhere;
}
.sub-item { white-space: nowrap; }
.meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--sp-12) var(--sp-16);
  margin-top: var(--sp-16);
}
.meta-item { min-width: 0; }
.meta-label { margin-bottom: var(--sp-8); color: var(--text-3); font-size: var(--fs-12); }
.meta-value { overflow-wrap: anywhere; color: var(--text); font-size: var(--fs-13); font-weight: 500; }
.meta-value.mono { font-family: var(--font-mono); font-size: var(--fs-12); }
.meta-value.is-empty { color: var(--text-3); font-weight: 400; }
.meta-value.is-expired { color: var(--red); font-weight: 600; }

.detail-section { margin-top: var(--sp-24); padding-top: var(--sp-16); border-top: 1px solid var(--border); }
.detail-body > .detail-section:first-of-type { margin-top: var(--sp-16); padding-top: 0; border-top: 0; }
.section-head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--sp-8); margin-bottom: var(--sp-12); }
.section-title { color: var(--text-2); font-size: var(--fs-13); font-weight: 700; letter-spacing: 0.02em; }
.section-meta { color: var(--text-3); font-size: var(--fs-12); white-space: nowrap; }
.section-note { margin-top: var(--sp-8); color: var(--text-3); font-size: var(--fs-12); line-height: 1.6; }
.prose { overflow-wrap: anywhere; color: var(--text); font-size: var(--fs-14); line-height: 1.7; white-space: pre-wrap; }
.empty-box { padding: var(--sp-16); border: 1px dashed var(--border-strong); border-radius: 8px; background: var(--surface-2); }
.empty-text { color: var(--text-3); font-size: var(--fs-13); }
.callout { margin-top: var(--sp-16); padding: var(--sp-12) var(--sp-16); border: 1px solid var(--red-border); border-radius: 8px; background: var(--red-soft); }
.callout-title { margin-bottom: var(--sp-8); color: var(--red); font-size: var(--fs-12); font-weight: 700; letter-spacing: 0.02em; }
.callout-text { overflow-wrap: anywhere; color: var(--text); font-size: var(--fs-14); line-height: 1.6; white-space: pre-wrap; }

.acceptance { display: flex; flex-direction: column; gap: var(--sp-8); counter-reset: acc; }
.acceptance-item { position: relative; padding-left: var(--sp-24); overflow-wrap: anywhere; font-size: var(--fs-14); line-height: 1.6; }
.acceptance-item::before {
  counter-increment: acc;
  content: counter(acc);
  position: absolute;
  left: 0;
  top: 0;
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border: 1px solid var(--accent-border);
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: var(--fs-12);
  font-weight: 700;
  line-height: 1;
}

.timeline { position: relative; display: flex; flex-direction: column; gap: var(--sp-16); padding-left: var(--sp-24); }
.timeline::before { content: ""; position: absolute; left: 5px; top: var(--sp-8); bottom: var(--sp-8); width: 1px; background: var(--border); }
.timeline-item { position: relative; }
.timeline-dot { position: absolute; left: calc(var(--sp-24) * -1); top: 6px; width: 11px; height: 11px; border: 2px solid var(--accent); border-radius: 50%; background: var(--surface); }
.timeline-body { min-width: 0; }
.timeline-top { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: var(--sp-8); }
.timeline-note { overflow-wrap: anywhere; font-size: var(--fs-14); font-weight: 500; }
.timeline-time { color: var(--text-3); font-size: var(--fs-12); white-space: nowrap; }
.timeline-source {
  display: inline-block;
  max-width: 100%;
  margin-top: var(--sp-8);
  padding: 0 var(--sp-8);
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--text-3);
  font-size: var(--fs-12);
  line-height: 22px;
  overflow-wrap: anywhere;
}

.table-wrap { overflow: auto; border: 1px solid var(--border); border-radius: 8px; }
.data-table { width: 100%; min-width: 640px; border-collapse: collapse; font-size: var(--fs-13); }
.data-table th {
  padding: var(--sp-8) var(--sp-12);
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-3);
  font-size: var(--fs-12);
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
}
.data-table td { padding: var(--sp-8) var(--sp-12); border-bottom: 1px solid var(--border); color: var(--text-2); vertical-align: top; }
.data-table tbody tr:last-child td { border-bottom: 0; }
.data-table tbody tr:hover { background: var(--surface-2); }
.cell-mono { color: var(--text-2); font-family: var(--font-mono); font-size: var(--fs-12); overflow-wrap: anywhere; }
.cell-muted { color: var(--text-3); font-size: var(--fs-12); white-space: nowrap; }
.run-error-row td { background: var(--red-soft); color: var(--red); }

.event-list { display: flex; flex-direction: column; overflow: hidden; border: 1px solid var(--border); border-radius: 8px; }
.event-row { display: flex; flex-direction: column; gap: var(--sp-8); padding: var(--sp-12); border-bottom: 1px solid var(--border); }
.event-row:last-child { border-bottom: 0; }
.event-main { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--sp-8); }
.event-time { color: var(--text-3); font-size: var(--fs-12); }
.event-type { color: var(--text); font-size: var(--fs-13); font-weight: 600; }
.event-meta { color: var(--text-3); font-size: var(--fs-12); }
.event-data {
  max-height: 120px;
  margin: 0;
  padding: var(--sp-8) var(--sp-12);
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--text-2);
  font-size: var(--fs-12);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.lease-card { padding: var(--sp-16); border: 1px solid var(--border); border-radius: 8px; background: var(--surface-2); }
.meta-grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 0; }

.raw-details { margin-top: var(--sp-24); padding-top: var(--sp-16); border-top: 1px solid var(--border); }
.raw-summary { display: flex; align-items: center; gap: var(--sp-8); color: var(--text-2); font-size: var(--fs-13); font-weight: 600; cursor: pointer; list-style: none; }
.raw-summary::-webkit-details-marker { display: none; }
.raw-summary::before { content: "▸"; color: var(--text-3); font-size: var(--fs-12); transition: transform 0.15s ease; }
.raw-details[open] .raw-summary::before { transform: rotate(90deg); }
.raw-json {
  max-height: 400px;
  margin: var(--sp-12) 0 0;
  padding: var(--sp-12);
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text-2);
  font-size: var(--fs-12);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.detail-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 60vh; padding: var(--sp-24); text-align: center; }
.placeholder-art { display: flex; flex-direction: column; gap: var(--sp-8); width: 140px; margin-bottom: var(--sp-24); }
.placeholder-row { display: block; height: 8px; border: 1px solid var(--border); border-radius: 999px; background: var(--surface-2); }
.placeholder-row:nth-child(2) { width: 80%; margin-left: auto; }
.placeholder-row:nth-child(3) { width: 60%; }
.placeholder-title { margin-bottom: var(--sp-8); font-size: var(--fs-20); font-weight: 700; }
.placeholder-text { max-width: 440px; color: var(--text-2); font-size: var(--fs-14); }
.placeholder-hint { margin-top: var(--sp-12); color: var(--text-3); font-size: var(--fs-12); }

.loading-state { display: flex; align-items: center; justify-content: center; gap: var(--sp-12); min-height: 200px; color: var(--text-3); font-size: var(--fs-13); }
.spinner { width: 16px; height: 16px; border: 2px solid var(--border-strong); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
.detail-error { display: flex; flex-direction: column; align-items: flex-start; gap: var(--sp-12); padding: var(--sp-24); border: 1px solid var(--red-border); border-radius: 12px; background: var(--red-soft); }
.detail-error-title { color: var(--red); font-size: var(--fs-20); font-weight: 700; }
.detail-error-text { color: var(--text); font-size: var(--fs-14); overflow-wrap: anywhere; }

.app-foot {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--sp-8);
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 var(--sp-24) var(--sp-24);
  color: var(--text-3);
  font-size: var(--fs-12);
}

@media (max-width: 1080px) {
  .meta-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 960px) {
  .app-bar { padding: var(--sp-12) var(--sp-16); }
  .brand-text h1 { font-size: var(--fs-20); }
  .app-main { grid-template-columns: 1fr; padding: var(--sp-16); }
  .list-card { position: static; max-height: none; }
  .task-list { max-height: 360px; }
  .detail-card { min-height: 0; }
  .detail-scroll { padding: var(--sp-16); }
  .alert { margin: var(--sp-16) var(--sp-16) 0; }
  .app-foot { padding: 0 var(--sp-16) var(--sp-16); }
}
@media (max-width: 560px) {
  .app-bar { flex-wrap: wrap; align-items: flex-start; }
  .app-actions { width: 100%; justify-content: space-between; }
  .health { max-width: 100%; white-space: normal; }
  .meta-grid, .meta-grid-2 { grid-template-columns: 1fr; }
  .detail-title-row { flex-direction: column; gap: var(--sp-8); }
  .acceptance-item { padding-left: var(--sp-24); }
}
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
</style>
</head>
<body>
<a class="skip-link" href="#main">跳到主要内容</a>
<header class="app-bar">
  <div class="brand">
    <div class="brand-mark" aria-hidden="true">SK</div>
    <div class="brand-text">
      <h1>SAGE-Kit Control</h1>
      <p class="brand-sub">本地控制面 · 只读面板 · 无写入操作</p>
    </div>
    <span class="badge">只读</span>
  </div>
  <div class="app-actions">
    <span class="health" role="status" aria-live="polite"><span id="health-dot" class="dot dot-idle" aria-hidden="true"></span><span id="health-text">连接中…</span></span>
    <button id="refresh" class="btn btn-primary" type="button" title="重新加载健康状态与任务列表">
      <span class="btn-icon" aria-hidden="true">⟳</span><span>刷新</span>
    </button>
  </div>
</header>
<div id="alert" class="alert" role="alert" hidden></div>
<main id="main" class="app-main">
  <section class="card list-card" aria-labelledby="list-heading">
    <div class="card-head">
      <h2 id="list-heading" class="card-title">任务列表</h2>
      <span id="task-count" class="card-sub">—</span>
    </div>
    <div class="list-toolbar">
      <label class="search" for="task-filter"><span class="search-label">筛选</span></label>
      <input id="task-filter" type="search" placeholder="按标题 / ID / 状态过滤" autocomplete="off" spellcheck="false">
    </div>
    <div id="tasks" class="task-list" aria-label="任务列表" aria-busy="true"></div>
  </section>
  <section class="card detail-card" aria-labelledby="detail-heading">
    <div id="detail" class="detail-scroll"></div>
  </section>
</main>
<footer class="app-foot">
  <span>只读接口：GET /v1/health · GET /v1/tasks · GET /v1/tasks/&lt;id&gt;</span>
  <span id="updated">尚未刷新</span>
</footer>
<noscript><p class="noscript">此面板需要 JavaScript 才能读取本地控制面 API。</p></noscript>
<script>
(function () {
  'use strict';

  var STATUS = {
    imported: { label: '已导入', cls: 's-imported' },
    ready: { label: '待执行', cls: 's-ready' },
    running: { label: '运行中', cls: 's-running' },
    review: { label: '待审查', cls: 's-review' },
    done: { label: '已完成', cls: 's-done' },
    blocked: { label: '已阻塞', cls: 's-blocked' },
    failed: { label: '失败', cls: 's-failed' },
    cancelled: { label: '已取消', cls: 's-cancelled' },
    interrupted: { label: '已中断', cls: 's-interrupted' }
  };

  var RUN_STATUS = {
    starting: { label: '启动中', cls: 's-ready' },
    running: { label: '运行中', cls: 's-running' },
    exited: { label: '已退出', cls: 's-done' },
    failed: { label: '失败', cls: 's-failed' },
    cancelled: { label: '已取消', cls: 's-cancelled' },
    interrupted: { label: '已中断', cls: 's-interrupted' }
  };

  var state = {
    tasks: [],
    filter: '',
    selectedId: null,
    detail: null,
    detailSeq: 0,
    loading: false,
    health: null,
    updatedAt: null
  };

  var els = {
    tasks: document.getElementById('tasks'),
    count: document.getElementById('task-count'),
    detail: document.getElementById('detail'),
    alert: document.getElementById('alert'),
    healthDot: document.getElementById('health-dot'),
    healthText: document.getElementById('health-text'),
    refresh: document.getElementById('refresh'),
    filter: document.getElementById('task-filter'),
    updated: document.getElementById('updated')
  };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function add(parent, child) {
    if (!parent || child === undefined || child === null || child === false) return parent;
    if (Array.isArray(child)) {
      for (var i = 0; i < child.length; i++) add(parent, child[i]);
      return parent;
    }
    if (typeof child === 'string' || typeof child === 'number') {
      parent.appendChild(document.createTextNode(String(child)));
      return parent;
    }
    parent.appendChild(child);
    return parent;
  }

  function clear(node) {
    while (node && node.firstChild) node.removeChild(node.firstChild);
  }

  function pad2(n) {
    return n < 10 ? '0' + n : String(n);
  }

  function dateOf(iso) {
    if (!iso) return null;
    var d = new Date(iso);
    return isNaN(d.getTime()) ? null : d;
  }

  function fmtTime(iso, fallback) {
    var d = dateOf(iso);
    if (!d) return fallback === undefined ? '—' : fallback;
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
  }

  function fmtRelative(iso) {
    var d = dateOf(iso);
    if (!d) return '';
    var diff = Date.now() - d.getTime();
    var future = diff < 0;
    var abs = Math.abs(diff);
    var sec = Math.floor(abs / 1000);
    var min = Math.floor(sec / 60);
    var hour = Math.floor(min / 60);
    var day = Math.floor(hour / 24);
    if (sec < 45) return future ? '即将' : '刚刚';
    if (min < 60) return min + ' 分钟' + (future ? '后' : '前');
    if (hour < 24) return hour + ' 小时' + (future ? '后' : '前');
    if (day < 30) return day + ' 天' + (future ? '后' : '前');
    return fmtTime(iso).slice(0, 10);
  }

  function durationText(ms) {
    var sec = Math.round(ms / 1000);
    if (sec < 1) return '不足 1 秒';
    if (sec < 60) return sec + ' 秒';
    var min = Math.floor(sec / 60);
    var rem = sec % 60;
    if (min < 60) return min + ' 分 ' + rem + ' 秒';
    var hour = Math.floor(min / 60);
    var mrem = min % 60;
    if (hour < 24) return hour + ' 小时 ' + mrem + ' 分';
    return Math.floor(hour / 24) + ' 天 ' + (hour % 24) + ' 小时';
  }

  function shortId(id) {
    var text = String(id === undefined || id === null ? '' : id);
    if (text.length <= 16) return text;
    return text.slice(0, 8) + '…' + text.slice(-4);
  }

  function statusOf(status) {
    return STATUS[status] || { label: status ? String(status) : '未知', cls: 's-unknown' };
  }

  function runStatusOf(status) {
    return RUN_STATUS[status] || { label: status ? String(status) : '未知', cls: 's-unknown' };
  }

  function pill(label, cls, title) {
    var node = el('span', 'pill ' + (cls || 's-unknown'));
    add(node, el('span', 'pill-dot'));
    add(node, label);
    if (title) node.title = title;
    return node;
  }

  function statusPill(status, isRun) {
    var meta = isRun ? runStatusOf(status) : statusOf(status);
    return pill(meta.label, meta.cls, 'status: ' + String(status === undefined || status === null ? '' : status));
  }

  function metaItem(label, value, mono) {
    var wrap = el('div', 'meta-item');
    add(wrap, el('dt', 'meta-label', label));
    var empty = value === undefined || value === null || value === '';
    var dd = el('dd', 'meta-value' + (mono ? ' mono' : '') + (empty ? ' is-empty' : ''), empty ? '—' : String(value));
    add(wrap, dd);
    return wrap;
  }

  function section(title, metaText) {
    var sec = el('section', 'detail-section');
    var head = el('div', 'section-head');
    add(head, el('h3', 'section-title', title));
    if (metaText) add(head, el('span', 'section-meta', metaText));
    add(sec, head);
    return sec;
  }

  function emptyBox(text) {
    var box = el('div', 'empty-box');
    add(box, el('p', 'empty-text', text));
    return box;
  }

  function textPreview(value, max) {
    var text;
    try {
      text = typeof value === 'string' ? value : JSON.stringify(value);
    } catch (err) {
      text = String(value);
    }
    if (typeof text !== 'string') text = String(text);
    if (max > 0 && text.length > max) text = text.slice(0, max) + '…';
    return text;
  }

  function setHealth(text, stateName, title) {
    if (!els.healthText || !els.healthDot) return;
    els.healthText.textContent = text;
    els.healthDot.className = 'dot dot-' + stateName;
    els.healthText.title = title || text;
  }

  function clearAlert() {
    if (!els.alert) return;
    clear(els.alert);
    els.alert.hidden = true;
  }

  function showAlert(message, withRetry) {
    if (!els.alert) return;
    clear(els.alert);
    els.alert.hidden = false;
    add(els.alert, el('span', 'alert-text', message));
    if (withRetry) {
      var button = el('button', 'btn btn-small alert-retry', '重试');
      button.type = 'button';
      button.addEventListener('click', function () { loadAll(); });
      add(els.alert, button);
    }
  }

  function setLoading(loading) {
    state.loading = loading;
    if (els.refresh) {
      els.refresh.disabled = loading;
      els.refresh.className = loading ? 'btn btn-primary is-loading' : 'btn btn-primary';
    }
    if (els.tasks) els.tasks.setAttribute('aria-busy', loading ? 'true' : 'false');
  }

  function renderHealth() {
    if (state.health) {
      var health = state.health;
      var schema = health.schemaVersion === undefined || health.schemaVersion === null ? '?' : health.schemaVersion;
      setHealth(
        '服务正常 · schema v' + schema,
        'ok',
        'service: ' + String(health.service || '?') + ' · apiVersion: ' + String(health.apiVersion || '?') + ' · now: ' + String(health.now || '?')
      );
    } else {
      setHealth('服务不可用', 'err');
    }
  }

  function api(path) {
    return fetch(path, { headers: { accept: 'application/json' }, cache: 'no-store' }).then(function (res) {
      return res.text().then(function (text) {
        var body = null;
        if (text) {
          try {
            body = JSON.parse(text);
          } catch (err) {
            body = null;
          }
        }
        if (!res.ok) {
          var message = '';
          if (body && body.error && body.error.message) message = body.error.message;
          else if (body && body.message) message = body.message;
          if (!message) message = res.status + ' ' + (res.statusText || 'HTTP 错误');
          var code = body && body.error && body.error.code ? ' [' + body.error.code + ']' : '';
          throw new Error(message + code);
        }
        if (body === null) throw new Error('服务端返回了非 JSON 响应');
        return body;
      });
    });
  }

  function normalizeDetail(payload, taskId) {
    var p = payload || {};
    var task = p.task && typeof p.task === 'object' ? p.task : null;
    if (!task && p.id && p.title) task = p;
    if (!task) throw new Error('详情响应缺少 task 字段');
    if (!task.id) task.id = taskId;
    return {
      task: task,
      runs: Array.isArray(p.runs) ? p.runs : [],
      events: Array.isArray(p.events) ? p.events : [],
      lease: p.lease && typeof p.lease === 'object' ? p.lease : null,
      raw: p
    };
  }

  function filteredTasks() {
    var q = state.filter.trim().toLowerCase();
    if (!q) return state.tasks.slice();
    return state.tasks.filter(function (task) {
      var parts = [task.title || '', task.id || '', task.status || '', task.source || '', task.externalId || ''];
      return parts.join(' ').toLowerCase().indexOf(q) !== -1;
    });
  }

  function updateActiveRows() {
    if (!els.tasks) return;
    var nodes = els.tasks.querySelectorAll('.task-item');
    for (var i = 0; i < nodes.length; i++) {
      var active = nodes[i].getAttribute('data-task-id') === state.selectedId;
      if (active) nodes[i].classList.add('is-active');
      else nodes[i].classList.remove('is-active');
      nodes[i].setAttribute('aria-pressed', active ? 'true' : 'false');
    }
  }

  function renderListMessage(title, text, withRetry) {
    clear(els.tasks);
    var box = el('div', 'list-empty');
    add(box, el('p', 'list-empty-title', title));
    add(box, el('p', 'list-empty-text', text));
    if (withRetry) {
      var button = el('button', 'btn btn-small', '重试');
      button.type = 'button';
      button.addEventListener('click', function () { loadAll(); });
      add(box, button);
    }
    add(els.tasks, box);
  }

  function renderTasks() {
    if (!els.tasks) return;
    clear(els.tasks);
    var all = state.tasks;
    var list = filteredTasks();
    if (els.count) {
      els.count.textContent = all.length === 0 ? '0 个' : (list.length === all.length ? '共 ' + all.length + ' 个' : '显示 ' + list.length + ' / ' + all.length);
    }
    if (all.length === 0) {
      renderListMessage('暂无任务', '任务列表为空。使用 sage-kit task create 创建任务，或在控制面 store 中写入任务后点击“刷新”。', false);
      return;
    }
    if (list.length === 0) {
      renderListMessage('没有匹配任务', '调整筛选关键词后重试。', false);
      return;
    }
    list.forEach(function (task) {
      var button = el('button', 'task-item');
      button.type = 'button';
      button.setAttribute('data-task-id', String(task.id));
      button.setAttribute('aria-pressed', 'false');
      if (task.id === state.selectedId) {
        button.classList.add('is-active');
        button.setAttribute('aria-pressed', 'true');
      }
      var top = el('span', 'task-item-top');
      add(top, el('span', 'task-item-title', task.title || '(无标题任务)'));
      add(top, statusPill(task.status, false));
      add(button, top);
      var meta = el('span', 'task-item-meta');
      add(meta, el('code', 'id-inline mono', shortId(task.id)));
      add(meta, el('span', 'dot-sep', '·'));
      add(meta, el('span', null, '更新 ' + (fmtRelative(task.updatedAt) || '—')));
      if (typeof task.priority === 'number' && task.priority !== 0) add(meta, el('span', 'priority-chip', 'P' + task.priority));
      add(button, meta);
      button.addEventListener('click', function () { selectTask(task.id); });
      add(els.tasks, button);
    });
  }

  function showDetailLoading(id) {
    if (!els.detail) return;
    clear(els.detail);
    var box = el('div', 'loading-state');
    add(box, el('span', 'spinner'));
    add(box, el('span', null, '正在加载任务详情…'));
    add(box, el('code', 'id-inline mono', shortId(id)));
    add(els.detail, box);
  }

  function showDetailError(message, id) {
    if (!els.detail) return;
    clear(els.detail);
    var box = el('div', 'detail-error');
    add(box, el('h2', 'detail-error-title', '加载详情失败'));
    add(box, el('p', 'detail-error-text', message));
    var button = el('button', 'btn btn-small', '重试');
    button.type = 'button';
    button.addEventListener('click', function () { loadDetail(id); });
    add(box, button);
    add(box, el('p', 'section-note', '任务 ID：' + String(id)));
    add(els.detail, box);
  }

  function renderMeta(task) {
    var created = task.createdAt ? fmtTime(task.createdAt) + ' · ' + fmtRelative(task.createdAt) : '';
    var updated = task.updatedAt ? fmtTime(task.updatedAt) + ' · ' + fmtRelative(task.updatedAt) : '';
    var grid = el('dl', 'meta-grid');
    add(grid, metaItem('状态', statusOf(task.status).label));
    add(grid, metaItem('优先级', task.priority));
    add(grid, metaItem('版本', task.version === undefined || task.version === null ? '' : 'v' + task.version));
    add(grid, metaItem('创建时间', created));
    add(grid, metaItem('更新时间', updated));
    add(grid, metaItem('分支', task.branch, true));
    add(grid, metaItem('工作树', task.worktreePath, true));
    add(grid, metaItem('来源', task.source));
    add(grid, metaItem('外部 ID', task.externalId, true));
    add(grid, metaItem('外部链接', task.externalUrl, true));
    add(grid, metaItem('幂等键', task.idempotencyKey, true));
    return grid;
  }

  function renderAcceptance(acceptance) {
    var sec = section('验收标准', acceptance.length ? acceptance.length + ' 项' : null);
    if (acceptance.length === 0) {
      add(sec, emptyBox('暂无验收标准。'));
      return sec;
    }
    var list = el('ol', 'acceptance');
    acceptance.forEach(function (item) {
      add(list, el('li', 'acceptance-item', String(item)));
    });
    add(sec, list);
    return sec;
  }

  function renderEvidence(evidence) {
    var sec = section('证据', evidence.length + ' 条');
    if (evidence.length === 0) {
      add(sec, emptyBox('暂无证据记录。evidence 由控制面 store 写入，文件模式任务没有该字段。'));
      return sec;
    }
    var timeline = el('div', 'timeline');
    evidence.forEach(function (item) {
      item = item || {};
      var row = el('div', 'timeline-item');
      add(row, el('span', 'timeline-dot'));
      var body = el('div', 'timeline-body');
      var top = el('div', 'timeline-top');
      add(top, el('span', 'timeline-note', item.note ? String(item.note) : '（无说明）'));
      add(top, el('time', 'timeline-time', fmtTime(item.at) + ' · ' + fmtRelative(item.at)));
      add(body, top);
      if (item.source) add(body, el('code', 'timeline-source mono', String(item.source)));
      add(row, body);
      add(timeline, row);
    });
    add(sec, timeline);
    return sec;
  }

  function renderRuns(runs) {
    var sec = section('运行记录', runs.length ? runs.length + ' 次' : null);
    if (runs.length === 0) {
      add(sec, emptyBox('暂无运行记录。run 由控制面 store 记录，文件模式任务没有该字段。'));
      return sec;
    }
    var sorted = runs.slice().sort(function (a, b) {
      return String((b && b.startedAt) || '').localeCompare(String((a && a.startedAt) || ''));
    });
    var wrap = el('div', 'table-wrap');
    var table = el('table', 'data-table');
    var thead = el('thead');
    var headRow = el('tr');
    ['运行 ID', '状态', '开始', '耗时', '退出码', '主机'].forEach(function (label) {
      add(headRow, el('th', null, label));
    });
    add(thead, headRow);
    add(table, thead);
    var tbody = el('tbody');
    sorted.forEach(function (run) {
      run = run || {};
      var tr = el('tr');
      var idCell = el('td');
      var idCode = el('code', 'cell-mono', String(run.id || '—'));
      idCode.title = (Array.isArray(run.command) ? run.command.join(' ') : String(run.command || '')) || String(run.id || '');
      add(idCell, idCode);
      add(tr, idCell);
      var statusCell = el('td');
      add(statusCell, statusPill(run.status, true));
      add(tr, statusCell);
      add(tr, el('td', 'cell-muted', fmtTime(run.startedAt) + (run.startedAt ? ' · ' + fmtRelative(run.startedAt) : '')));
      var duration = '—';
      var start = dateOf(run.startedAt);
      if (start) {
        var end = run.endedAt ? dateOf(run.endedAt) : null;
        duration = durationText((end ? end.getTime() : Date.now()) - start.getTime()) + (run.endedAt ? '' : '（进行中）');
      }
      add(tr, el('td', null, duration));
      add(tr, el('td', 'cell-mono', run.exitCode === undefined || run.exitCode === null ? '—' : String(run.exitCode)));
      add(tr, el('td', 'cell-mono', run.host || '—'));
      add(tbody, tr);
      if (run.errorCode || run.errorMessage) {
        var errRow = el('tr', 'run-error-row');
        var errCell = el('td');
        errCell.setAttribute('colspan', '6');
        add(errCell, el('code', 'cell-mono', [run.errorCode, run.errorMessage].filter(Boolean).join(': ')));
        add(errRow, errCell);
        add(tbody, errRow);
      }
    });
    add(table, tbody);
    add(wrap, table);
    add(sec, wrap);
    return sec;
  }

  function renderEvents(events) {
    var sec = section('最近事件', events.length ? '共 ' + events.length + ' 条' : null);
    if (events.length === 0) {
      add(sec, emptyBox('暂无事件记录。'));
      return sec;
    }
    var sorted = events.slice().sort(function (a, b) {
      var seqA = a && typeof a.seq === 'number' ? a.seq : 0;
      var seqB = b && typeof b.seq === 'number' ? b.seq : 0;
      if (seqA !== seqB) return seqB - seqA;
      return String((b && b.createdAt) || '').localeCompare(String((a && a.createdAt) || ''));
    });
    var shown = sorted.slice(0, 30);
    var list = el('div', 'event-list');
    shown.forEach(function (event) {
      event = event || {};
      var row = el('div', 'event-row');
      var main = el('div', 'event-main');
      add(main, el('time', 'event-time mono', fmtTime(event.createdAt)));
      add(main, el('span', 'event-type', event.type ? String(event.type) : 'unknown'));
      add(main, el('span', 'event-meta mono', '#' + (event.seq === undefined || event.seq === null ? '?' : String(event.seq))));
      if (event.runId) add(main, el('span', 'event-meta mono', 'run ' + shortId(event.runId)));
      add(row, main);
      if (event.data !== undefined && event.data !== null) add(row, el('code', 'event-data mono', textPreview(event.data, 220)));
      add(list, row);
    });
    add(sec, list);
    if (events.length > shown.length) add(sec, el('p', 'section-note', '仅显示最近 ' + shown.length + ' 条，完整事件见下方原始 JSON。'));
    return sec;
  }

  function renderLease(lease) {
    var sec = section('租约');
    if (!lease) {
      add(sec, emptyBox('当前没有活动租约。使用控制面 lease 执行的任务才会产生租约记录。'));
      return sec;
    }
    var grid = el('dl', 'meta-grid meta-grid-2');
    add(grid, metaItem('持有者', lease.owner, true));
    add(grid, metaItem('运行 ID', lease.runId || '', true));
    add(grid, metaItem('获取时间', fmtTime(lease.acquiredAt) + (lease.acquiredAt ? ' · ' + fmtRelative(lease.acquiredAt) : '')));
    add(grid, metaItem('最近心跳', lease.heartbeatAt ? fmtTime(lease.heartbeatAt) + ' · ' + fmtRelative(lease.heartbeatAt) : ''));
    var expires = dateOf(lease.expiresAt);
    var remaining = expires === null ? null : expires.getTime() - Date.now();
    var expiryText = lease.expiresAt ? fmtTime(lease.expiresAt) + ' · ' + (remaining === null ? '—' : remaining <= 0 ? '已过期' : '剩余 ' + durationText(remaining)) : '';
    var expiryItem = metaItem('到期时间', expiryText);
    if (remaining !== null && remaining <= 0) {
      var dd = expiryItem.querySelector('.meta-value');
      if (dd) dd.classList.add('is-expired');
    }
    add(grid, expiryItem);
    var card = el('div', 'lease-card');
    add(card, grid);
    add(card, el('p', 'section-note', '租约（lease）是控制面单写者保护：过期只会把任务标记为 interrupted，不会自动重跑。'));
    add(sec, card);
    return sec;
  }

  function renderDetail(payload, taskId) {
    var detail;
    try {
      detail = normalizeDetail(payload, taskId);
    } catch (err) {
      showDetailError(err && err.message ? err.message : String(err), taskId);
      return;
    }
    state.detail = detail;
    var task = detail.task;
    clear(els.detail);

    var wrap = el('div', 'detail-body');

    var head = el('header', 'detail-head');
    var titleRow = el('div', 'detail-title-row');
    var title = el('h2', 'detail-title', task.title || '(无标题任务)');
    title.id = 'detail-heading';
    add(titleRow, title);
    add(titleRow, statusPill(task.status, false));
    add(head, titleRow);
    var sub = el('div', 'detail-sub');
    add(sub, el('code', 'id-chip mono', task.id || taskId || '—'));
    if (task.version !== undefined && task.version !== null) add(sub, el('span', 'sub-item', 'v' + task.version));
    if (typeof task.priority === 'number') add(sub, el('span', 'sub-item', '优先级 ' + task.priority));
    add(head, sub);
    add(wrap, head);
    add(wrap, renderMeta(task));

    var descSec = section('描述');
    if (task.description) add(descSec, el('p', 'prose', task.description));
    else add(descSec, emptyBox('暂无描述。'));
    add(wrap, descSec);

    if (task.blockedReason) {
      var callout = el('div', 'callout callout-warn');
      add(callout, el('div', 'callout-title', '阻塞原因'));
      add(callout, el('p', 'callout-text', task.blockedReason));
      add(wrap, callout);
    } else if (task.status === 'blocked') {
      add(wrap, emptyBox('任务状态为 blocked，但没有记录 blockedReason。'));
    }

    add(wrap, renderAcceptance(Array.isArray(task.acceptance) ? task.acceptance : []));
    add(wrap, renderEvidence(Array.isArray(task.evidence) ? task.evidence : []));
    add(wrap, renderRuns(detail.runs));
    add(wrap, renderEvents(detail.events));
    add(wrap, renderLease(detail.lease));

    var raw = el('details', 'raw-details');
    add(raw, el('summary', 'raw-summary', '原始 JSON（GET /v1/tasks/' + String(task.id || taskId) + '）'));
    var pre = el('pre', 'raw-json mono');
    pre.textContent = JSON.stringify(detail.raw, null, 2);
    add(raw, pre);
    add(wrap, raw);

    add(els.detail, wrap);
  }

  function renderEmptyDetail() {
    if (!els.detail) return;
    clear(els.detail);
    var box = el('div', 'detail-placeholder');
    var art = el('div', 'placeholder-art');
    art.setAttribute('aria-hidden', 'true');
    for (var i = 0; i < 3; i++) add(art, el('span', 'placeholder-row'));
    add(box, art);
    var title = el('h2', 'placeholder-title', '选择一个任务查看详情');
    title.id = 'detail-heading';
    add(box, title);
    add(box, el('p', 'placeholder-text', '点击左侧任意任务行，会立即加载该任务的完整信息，无需再点额外按钮。'));
    add(box, el('p', 'placeholder-hint', '按 / 聚焦筛选，按 ↑ / ↓ 在任务之间移动。'));
    add(els.detail, box);
  }

  function selectTask(id) {
    if (!id) return;
    state.selectedId = id;
    updateActiveRows();
    loadDetail(id);
  }

  function loadDetail(id) {
    var seq = ++state.detailSeq;
    showDetailLoading(id);
    api('/v1/tasks/' + encodeURIComponent(id)).then(function (payload) {
      if (seq !== state.detailSeq) return;
      renderDetail(payload, id);
    }).catch(function (err) {
      if (seq !== state.detailSeq) return;
      showDetailError(err && err.message ? err.message : String(err), id);
    });
  }

  function loadAll() {
    clearAlert();
    setLoading(true);
    var healthPromise = api('/v1/health').then(function (health) {
      state.health = health;
      renderHealth();
    }).catch(function (err) {
      state.health = null;
      renderHealth();
      showAlert('无法连接 /v1/health：' + (err && err.message ? err.message : String(err)), true);
    });
    var tasksPromise = api('/v1/tasks').then(function (payload) {
      var list = [];
      if (payload && Array.isArray(payload.tasks)) list = payload.tasks;
      else if (Array.isArray(payload)) list = payload;
      state.tasks = list;
      state.updatedAt = new Date();
      renderTasks();
    }).catch(function (err) {
      state.tasks = [];
      state.updatedAt = null;
      renderListMessage('加载任务列表失败', (err && err.message ? err.message : String(err)) + '。检查控制面服务是否运行，然后点击“重试”。', true);
      showAlert('无法加载任务列表：' + (err && err.message ? err.message : String(err)), true);
    });
    Promise.all([healthPromise, tasksPromise]).then(function () {
      setLoading(false);
      if (els.updated) {
        els.updated.textContent = state.updatedAt
          ? '最后刷新 ' + fmtTime(state.updatedAt) + ' · ' + fmtRelative(state.updatedAt)
          : '尚未刷新';
      }
      if (!state.selectedId) return;
      var exists = state.tasks.some(function (task) { return task.id === state.selectedId; });
      if (exists) {
        loadDetail(state.selectedId);
      } else {
        state.selectedId = null;
        state.detail = null;
        renderEmptyDetail();
      }
    });
  }

  function boot() {
    if (els.refresh) {
      els.refresh.addEventListener('click', function () { loadAll(); });
    }
    if (els.filter) {
      els.filter.addEventListener('input', function () {
        state.filter = els.filter.value;
        renderTasks();
        updateActiveRows();
      });
    }
    if (els.tasks) {
      els.tasks.addEventListener('keydown', function (event) {
        if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
        var items = Array.prototype.slice.call(els.tasks.querySelectorAll('.task-item'));
        var index = items.indexOf(document.activeElement);
        if (index === -1) return;
        event.preventDefault();
        var next = items[index + (event.key === 'ArrowDown' ? 1 : -1)];
        if (next) next.focus();
      });
    }
    document.addEventListener('keydown', function (event) {
      var tag = document.activeElement && document.activeElement.tagName;
      var typing = tag === 'INPUT' || tag === 'TEXTAREA';
      if (event.key === '/' && !typing) {
        event.preventDefault();
        if (els.filter) els.filter.focus();
        return;
      }
      if (event.key === 'Escape' && document.activeElement === els.filter) {
        els.filter.value = '';
        state.filter = '';
        renderTasks();
        updateActiveRows();
        els.filter.blur();
      }
    });
    renderEmptyDetail();
    loadAll();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
</script>
</body>
</html>`;
}
