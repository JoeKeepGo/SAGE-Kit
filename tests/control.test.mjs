import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { request as httpRequest } from "node:http";
import { homedir } from "node:os";
import { join } from "node:path";
import { after, describe, it } from "node:test";
import {
  CONTROL_SCHEMA_VERSION,
  DEFAULT_HEARTBEAT_MS,
  DEFAULT_LEASE_TTL_MS,
  acquireLease,
  controlDbPath,
  controlPaths,
  createControlServer,
  expireLeases,
  getLease,
  listLeases,
  openControl,
  recoverStale,
  releaseLease,
  renewLease,
} from "../dist/control/index.js";

const TEST_TMP_BASE =
  process.env.SAGE_KIT_TEST_TMPDIR ?? join(homedir(), ".cache", "sage-kit-tests");
const TOKEN = "sage-kit-control-test-token";
const cleanups = [];
await mkdir(TEST_TMP_BASE, { recursive: true });

after(async () => {
  for (const cleanup of cleanups.reverse()) {
    await Promise.resolve()
      .then(cleanup)
      .catch(() => {});
  }
});

async function tempProject() {
  const dir = await mkdtemp(join(TEST_TMP_BASE, "sage-kit-control-"));
  cleanups.push(() => rm(dir, { recursive: true, force: true }));
  return dir;
}

/** Deterministic clock so 30s leases and expiry scans do not sleep. */
function fakeClock(startIso = "2026-01-01T00:00:00.000Z") {
  let current = Date.parse(startIso);
  const clock = () => new Date(current);
  clock.advance = (ms) => {
    current += ms;
  };
  clock.now = () => new Date(current).toISOString();
  return clock;
}

function trackStore(store) {
  cleanups.push(async () => {
    try {
      store.close();
    } catch {
      // already closed
    }
  });
  return store;
}

async function withStore(fn, options = {}) {
  const dir = await tempProject();
  const store = trackStore(openControl(dir, options));
  return fn({ dir, store });
}

function expectCode(fn, code) {
  assert.throws(fn, (error) => {
    assert.equal(error.code, code, `expected ${code}, got ${error.code}: ${error.message}`);
    return true;
  });
}

async function expectRejects(promise, code) {
  await assert.rejects(promise, (error) => {
    assert.equal(error.code, code, `expected ${code}, got ${error.code}: ${error.message}`);
    return true;
  });
}

async function withControlServer(fn) {
  const dir = await tempProject();
  const store = trackStore(openControl(dir));
  const server = await createControlServer({ store, token: TOKEN });
  try {
    return await fn({ dir, store, server });
  } finally {
    await server.close();
  }
}

async function api(server, path, options = {}) {
  const headers = { ...(options.headers ?? {}) };
  let body;
  if (options.body !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(options.body);
  } else if (options.rawBody !== undefined) {
    headers["content-type"] = headers["content-type"] ?? "application/json";
    body = options.rawBody;
  }
  if (options.token !== null) headers.authorization = `Bearer ${options.token ?? TOKEN}`;
  const response = await fetch(`${server.url}${path}`, {
    method: options.method ?? "GET",
    headers,
    body,
    signal: AbortSignal.timeout(5_000),
  });
  const text = await response.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    json = undefined;
  }
  return {
    status: response.status,
    headers: Object.fromEntries(response.headers.entries()),
    text,
    json,
  };
}

/** Raw HTTP helper for chunked bodies and spoofed Host headers. */
function rawRequest(server, { method = "GET", path = "/", headers = {}, body } = {}) {
  return new Promise((resolvePromise, reject) => {
    const req = httpRequest(
      {
        host: "127.0.0.1",
        port: server.port,
        method,
        path,
        headers: { host: `127.0.0.1:${server.port}`, ...headers },
      },
      (res) => {
        let text = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          text += chunk;
        });
        res.on("end", () => {
          let json;
          try {
            json = JSON.parse(text);
          } catch {
            json = undefined;
          }
          resolvePromise({ status: res.statusCode, headers: res.headers, text, json });
        });
      },
    );
    req.on("error", reject);
    if (body !== undefined) {
      // Deliberately chunked (no Content-Length) so the server's stream limit,
      // not an early header check, is exercised.
      req.write(body.slice(0, 128));
      req.write(body.slice(128));
    }
    req.end();
  });
}

describe("M2 control store: schema and pragmas", () => {
  it("creates .sage-kit/control/control.db with WAL, foreign keys, busy_timeout and synchronous=FULL", async () => {
    await withStore(({ dir, store }) => {
      const info = store.debugInfo();
      assert.equal(info.dbPath, controlDbPath(dir));
      assert.equal(info.dbPath, join(dir, ".sage-kit", "control", "control.db"));
      assert.equal(info.journalMode, "wal");
      assert.equal(info.foreignKeys, 1);
      assert.equal(info.busyTimeout, 5000);
      assert.equal(info.synchronous, 2); // FULL
      assert.equal(info.userVersion, CONTROL_SCHEMA_VERSION);
      assert.equal(info.leaseTtlMs, DEFAULT_LEASE_TTL_MS);
      assert.equal(info.heartbeatMs, DEFAULT_HEARTBEAT_MS);
      assert.ok(existsSync(info.dbPath));
      store.createTask({ title: "wal file" });
      assert.ok(existsSync(controlPaths(dir).walPath), "WAL file should exist while the connection is open");
    });
  });

  it("migrates to schema version 1 with tasks/runs/events/leases tables", async () => {
    await withStore(({ store }) => {
      const tables = store.db
        .prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        .all()
        .map((row) => row.name);
      for (const table of ["tasks", "runs", "events", "leases"]) {
        assert.ok(tables.includes(table), `missing table ${table}`);
      }
      assert.equal(store.db.prepare("SELECT COUNT(*) AS count FROM tasks").get().count, 0);
    });
  });

  it("is single writer: a second open is rejected until the first closes", async () => {
    const dir = await tempProject();
    const first = openControl(dir);
    try {
      expectCode(() => openControl(dir), "E_WRITER_LOCKED");
    } finally {
      first.close();
    }
    const second = openControl(dir);
    try {
      assert.equal(second.debugInfo().userVersion, CONTROL_SCHEMA_VERSION);
    } finally {
      second.close();
    }
  });

  it("takes over a stale writer lock left by a dead process", async () => {
    const dir = await tempProject();
    const seed = openControl(dir);
    seed.close();
    const child = spawnSync(process.execPath, ["-e", "process.exit(0)"]);
    assert.equal(child.status, 0);
    const lockPath = controlPaths(dir).lockPath;
    await writeFile(
      lockPath,
      `${JSON.stringify({ pid: child.pid, owner: "dead-worker", startedAt: new Date().toISOString() })}\n`,
    );
    const store = openControl(dir);
    try {
      assert.ok(store.debugInfo().dbPath.endsWith("control.db"));
    } finally {
      store.close();
    }
  });

  it("supports a read-only open that can read but not write", async () => {
    const dir = await tempProject();
    const writer = openControl(dir);
    const task = writer.createTask({ title: "read me" });
    writer.close();
    const reader = openControl(dir, { readOnly: true });
    try {
      assert.equal(reader.debugInfo().readOnly, true);
      assert.equal(reader.getTask(task.id).title, "read me");
      expectCode(() => reader.createTask({ title: "nope" }), "E_CONTROL_READ_ONLY");
    } finally {
      reader.close();
    }
    const missing = join(dir, "no-project");
    expectCode(() => openControl(missing, { readOnly: true }), "E_CONTROL_DB_NOT_FOUND");
  });
});

describe("M2 control store: tasks", () => {
  it("creates, reads and lists tasks and appends a task.created event", async () => {
    await withStore(({ store }) => {
      const task = store.createTask({
        title: "  Ship it  ",
        description: "deliver the thing",
        acceptance: ["tests pass"],
        source: "local",
      });
      assert.equal(task.title, "Ship it");
      assert.equal(task.description, "deliver the thing");
      assert.equal(task.status, "ready");
      assert.equal(task.version, 1);
      assert.deepEqual(task.acceptance, ["tests pass"]);
      assert.deepEqual(task.evidence, []);
      assert.equal(task.createdAt, task.updatedAt);
      assert.equal(store.getTask(task.id).id, task.id);
      assert.equal(store.listTasks().length, 1);
      const events = store.listEvents({ taskId: task.id });
      assert.equal(events.length, 1);
      assert.equal(events[0].type, "task.created");
      assert.equal(events[0].seq, 1);
      expectCode(() => store.getTask("task-missing"), "E_TASK_NOT_FOUND");
      expectCode(() => store.getTask("Not An Id"), "E_BAD_TASK_ID");
    });
  });

  it("validates input, rejects done at creation and duplicate ids", async () => {
    await withStore(({ store }) => {
      expectCode(() => store.createTask({ title: "    " }), "E_BAD_TASK");
      expectCode(() => store.createTask({ title: "x".repeat(201) }), "E_BAD_TASK");
      expectCode(() => store.createTask({ title: "x", status: "nope" }), "E_BAD_STATUS");
      expectCode(() => store.createTask({ title: "x", status: "done" }), "E_BAD_STATUS");
      expectCode(() => store.createTask({ title: "x", id: "Bad ID" }), "E_BAD_TASK_ID");
      const created = store.createTask({ title: "one", id: "task-duplicate" });
      assert.equal(created.id, "task-duplicate");
      expectCode(() => store.createTask({ title: "two", id: "task-duplicate" }), "E_TASK_EXISTS");
      assert.equal(store.listTasks().length, 1);
    });
  });

  it("follows the authoritative status transitions", async () => {
    await withStore(({ store }) => {
      const task = store.createTask({ title: "transitions" });
      assert.equal(store.updateTaskStatus(task.id, "running").status, "running");
      assert.equal(store.updateTaskStatus(task.id, "review").status, "review");
      expectCode(() => store.updateTaskStatus(task.id, "done"), "E_DONE_WITHOUT_EVIDENCE");
      const done = store.updateTaskStatus(task.id, "done", { evidence: ["reviewed"], note: "ship" });
      assert.equal(done.status, "done");
      assert.equal(done.evidence.length, 1);
      assert.equal(done.evidence[0].note, "reviewed");
      expectCode(() => store.updateTaskStatus(task.id, "running"), "E_BAD_TRANSITION");
      expectCode(() => store.updateTaskStatus(task.id, "cancelled"), "E_BAD_TRANSITION");

      const direct = store.createTask({ title: "direct done" });
      expectCode(() => store.updateTaskStatus(direct.id, "done", { evidence: ["x"] }), "E_BAD_TRANSITION");

      const finished = store.createTask({ title: "cancel me" });
      assert.equal(store.updateTaskStatus(finished.id, "cancelled").status, "cancelled");
      expectCode(() => store.updateTaskStatus(finished.id, "ready"), "E_BAD_TRANSITION");
      expectCode(() => store.updateTaskStatus(task.id, "nope"), "E_BAD_STATUS");
    });
  });

  it("tracks blocked_reason and clears it when leaving blocked", async () => {
    await withStore(({ store }) => {
      const task = store.createTask({ title: "blocked" });
      const blocked = store.updateTaskStatus(task.id, "blocked", { blockedReason: "waiting on review" });
      assert.equal(blocked.status, "blocked");
      assert.equal(blocked.blockedReason, "waiting on review");
      const ready = store.updateTaskStatus(task.id, "ready");
      assert.equal(ready.status, "ready");
      assert.equal(ready.blockedReason, undefined);
    });
  });

  it("supports idempotency keys and optimistic versions", async () => {
    await withStore(({ store }) => {
      const first = store.createTask({ title: "idem", id: "task-idem", idempotencyKey: "create-1" });
      const second = store.createTask({ title: "idem retry", id: "task-idem", idempotencyKey: "create-1" });
      assert.equal(second.id, first.id);
      assert.equal(second.title, "idem");
      assert.equal(store.listTasks().length, 1);

      const updated = store.updateTaskStatus(first.id, "running", { expectedVersion: 1 });
      assert.equal(updated.version, 2);
      expectCode(() => store.updateTaskStatus(first.id, "review", { expectedVersion: 1 }), "E_TASK_VERSION_CONFLICT");
      assert.equal(store.updateTaskStatus(first.id, "review", { expectedVersion: 2 }).version, 3);
    });
  });
});

describe("M2 control store: runs and events", () => {
  it("records and finishes runs with a per-run event sequence", async () => {
    await withStore(({ store }) => {
      const task = store.createTask({ title: "run me" });
      const run = store.recordRun({ taskId: task.id, command: ["node", "--version"] });
      assert.equal(run.status, "running");
      assert.equal(run.taskId, task.id);
      assert.ok(run.host.length > 0);
      assert.deepEqual(run.command, ["node", "--version"]);
      assert.equal(run.endedAt, undefined);
      assert.equal(store.listRuns({ taskId: task.id }).length, 1);
      const started = store.listEvents({ runId: run.id });
      assert.deepEqual(
        started.map((event) => [event.type, event.seq]),
        [["run.started", 1]],
      );
      const finished = store.finishRun(run.id, { status: "exited", exitCode: 0 });
      assert.equal(finished.status, "exited");
      assert.equal(finished.exitCode, 0);
      assert.ok(finished.endedAt);
      const runEvents = store.listEvents({ runId: run.id });
      assert.deepEqual(
        runEvents.map((event) => [event.type, event.seq]),
        [
          ["run.started", 1],
          ["run.finished", 2],
        ],
      );
      expectCode(() => store.getRun("run-missing"), "E_RUN_NOT_FOUND");
      expectCode(() => store.recordRun({ taskId: "task-missing" }), "E_TASK_NOT_FOUND");
      expectCode(() => store.recordRun({ taskId: task.id, status: "exited" }), "E_BAD_RUN_STATUS");
    });
  });

  it("redacts credentials in stored commands and event payloads", async () => {
    await withStore(({ store }) => {
      const task = store.createTask({ title: "redact" });
      const run = store.recordRun({
        taskId: task.id,
        command: ["node", "--token=super-secret", "sk-abcdefgh12345678"],
      });
      assert.ok(!JSON.stringify(run.command).includes("super-secret"));
      assert.ok(!JSON.stringify(run.command).includes("sk-abcdefgh"));
      store.appendEvent({
        type: "test.redaction",
        taskId: task.id,
        data: { token: "plain-token-value", note: "token=leak-me", nested: { authorization: "Bearer abc" } },
      });
      const event = store.listEvents({ taskId: task.id, type: "test.redaction" })[0];
      const serialized = JSON.stringify(event.data);
      assert.ok(!serialized.includes("plain-token-value"));
      assert.ok(!serialized.includes("leak-me"));
      assert.ok(!serialized.includes("Bearer abc"));
      assert.ok(serialized.includes("[REDACTED]"));
    });
  });

  it("treats finishRun as idempotent for the same terminal status", async () => {
    await withStore(({ store }) => {
      const task = store.createTask({ title: "idem run" });
      const run = store.recordRun({ taskId: task.id });
      const first = store.finishRun(run.id, { status: "failed", exitCode: 2, errorCode: "E_TEST" });
      const again = store.finishRun(run.id, { status: "failed" });
      assert.equal(again.status, "failed");
      assert.equal(again.endedAt, first.endedAt);
      expectCode(() => store.finishRun(run.id, { status: "exited", exitCode: 0 }), "E_RUN_ALREADY_FINISHED");
    });
  });

  it("validates event types, scopes and payload size", async () => {
    await withStore(({ store }) => {
      const a = store.createTask({ title: "a" });
      const b = store.createTask({ title: "b" });
      const run = store.recordRun({ taskId: a.id });
      expectCode(() => store.appendEvent({ type: "Bad Type" }), "E_BAD_EVENT");
      expectCode(() => store.appendEvent({ type: "test.event", taskId: "task-missing" }), "E_TASK_NOT_FOUND");
      expectCode(
        () => store.appendEvent({ type: "test.event", taskId: b.id, runId: run.id }),
        "E_EVENT_SCOPE_MISMATCH",
      );
      const huge = {
        blob: Array.from({ length: 20 }, () => Array.from({ length: 20 }, () => "x".repeat(500))),
      };
      expectCode(() => store.appendEvent({ type: "test.huge", data: huge }), "E_EVENT_TOO_LARGE");
      const taskEvents = store.listEvents({ taskId: a.id });
      const taskScoped = taskEvents.filter((event) => event.runId === undefined);
      assert.deepEqual(
        taskScoped.map((event) => event.seq),
        [1],
      );
      assert.deepEqual(
        taskEvents.map((event) => event.type).sort(),
        ["run.started", "task.created"],
      );
    });
  });
});

describe("M2 control store: leases", () => {
  it("acquires exactly one lease per task and moves it to running", async () => {
    const clock = fakeClock();
    await withStore(
      ({ store }) => {
        const task = store.createTask({ title: "lease me" });
        const lease = store.acquireLease(task.id, { owner: "worker-1" });
        assert.equal(lease.owner, "worker-1");
        assert.equal(lease.acquiredAt, clock.now());
        assert.equal(lease.heartbeatAt, clock.now());
        assert.equal(lease.expiresAt, "2026-01-01T00:00:30.000Z");
        assert.equal(store.getTask(task.id).status, "running");
        assert.equal(store.getLease(task.id).owner, "worker-1");
        assert.equal(store.listLeases().length, 1);
        expectCode(() => store.acquireLease(task.id, { owner: "worker-2" }), "E_LEASE_HELD");
        expectCode(() => store.acquireLease(task.id, { owner: "worker-1" }), "E_LEASE_HELD");
        assert.equal(store.getLease(task.id).owner, "worker-1");
      },
      { clock },
    );
  });

  it("renews with heartbeat and releases with owner checks", async () => {
    const clock = fakeClock();
    await withStore(
      ({ store }) => {
        const task = store.createTask({ title: "renew" });
        store.acquireLease(task.id, { owner: "worker-1" });
        clock.advance(5_000);
        const renewed = store.renewLease(task.id, { owner: "worker-1" });
        assert.equal(renewed.heartbeatAt, clock.now());
        assert.equal(renewed.expiresAt, "2026-01-01T00:00:35.000Z");
        expectCode(() => store.renewLease(task.id, { owner: "worker-2" }), "E_LEASE_OWNER_MISMATCH");
        expectCode(() => store.releaseLease(task.id, { owner: "worker-2" }), "E_LEASE_OWNER_MISMATCH");
        const released = store.releaseLease(task.id, { owner: "worker-1" });
        assert.equal(released.taskId, task.id);
        assert.equal(store.getLease(task.id), undefined);
        expectCode(() => store.releaseLease(task.id), "E_LEASE_NOT_HELD");
        expectCode(() => store.renewLease(task.id, { owner: "worker-1" }), "E_LEASE_NOT_HELD");
        const reacquired = store.acquireLease(task.id, { owner: "worker-2" });
        assert.equal(reacquired.owner, "worker-2");
        assert.equal(store.getTask(task.id).status, "running");
      },
      { clock },
    );
  });

  it("supports configured ttl/heartbeat and run binding validation", async () => {
    const clock = fakeClock();
    await withStore(
      ({ store }) => {
        const info = store.debugInfo();
        assert.equal(info.leaseTtlMs, 5_000);
        assert.equal(info.heartbeatMs, 1_000);
        const task = store.createTask({ title: "ttl" });
        const lease = store.acquireLease(task.id, { owner: "w" });
        assert.equal(lease.expiresAt, "2026-01-01T00:00:05.000Z");
        const short = store.acquireLease(store.createTask({ title: "custom ttl" }).id, { owner: "w", ttlMs: 60_000 });
        assert.ok(short.expiresAt.endsWith("00:01:00.000Z"));
        expectCode(() => store.acquireLease(task.id, { owner: "w", runId: "run-missing" }), "E_RUN_NOT_FOUND");
        const other = store.createTask({ title: "other" });
        const foreignRun = store.recordRun({ taskId: other.id });
        expectCode(() => store.acquireLease(task.id, { owner: "w", runId: foreignRun.id }), "E_RUN_TASK_MISMATCH");
      },
      { clock, leaseTtlMs: 5_000, heartbeatMs: 1_000 },
    );
  });

  it("expired lease interrupts the task and run, and refuses re-lease", async () => {
    const clock = fakeClock();
    await withStore(
      ({ store }) => {
        const task = store.createTask({ title: "expire" });
        const run = store.recordRun({ taskId: task.id });
        store.acquireLease(task.id, { owner: "worker-1", runId: run.id });
        clock.advance(31_000);
        expectCode(() => store.acquireLease(task.id, { owner: "worker-2" }), "E_LEASE_EXPIRED");
        assert.equal(store.getTask(task.id).status, "interrupted");
        assert.equal(store.getLease(task.id), undefined);
        assert.equal(store.getRun(run.id).status, "interrupted");
        assert.equal(store.listRuns({ taskId: task.id }).length, 1, "recovery must never start a new run");
        const types = store.listEvents({ taskId: task.id }).map((event) => event.type);
        assert.ok(types.includes("lease.expired"));
        assert.ok(types.includes("task.status_changed"));
        // Explicit re-acquire after recovery is allowed (no automatic rerun).
        const reacquired = store.acquireLease(task.id, { owner: "worker-2" });
        assert.equal(reacquired.owner, "worker-2");
        assert.equal(store.getTask(task.id).status, "running");
      },
      { clock },
    );
  });

  it("renew after expiry interrupts and refuses the renewal", async () => {
    const clock = fakeClock();
    await withStore(
      ({ store }) => {
        const task = store.createTask({ title: "renew expired" });
        store.acquireLease(task.id, { owner: "worker-1" });
        clock.advance(30_000);
        expectCode(() => store.renewLease(task.id, { owner: "worker-1" }), "E_LEASE_EXPIRED");
        assert.equal(store.getTask(task.id).status, "interrupted");
        assert.equal(store.getLease(task.id), undefined);
        assert.ok(store.listEvents({ taskId: task.id }).some((event) => event.type === "lease.expired"));
      },
      { clock },
    );
  });

  it("rejects leased acquisition of imported/done tasks with E_BAD_TRANSITION", async () => {
    const clock = fakeClock();
    await withStore(
      ({ store }) => {
        const imported = store.createTask({ title: "imported", status: "imported" });
        expectCode(() => store.acquireLease(imported.id, { owner: "w" }), "E_BAD_TRANSITION");
        const finished = store.createTask({ title: "cancel" });
        store.updateTaskStatus(finished.id, "cancelled");
        expectCode(() => store.acquireLease(finished.id, { owner: "w" }), "E_BAD_TRANSITION");
        const ready = store.createTask({ title: "ready" });
        assert.equal(acquireLease(store, ready.id, { owner: "standalone" }).owner, "standalone");
        assert.equal(getLease(store, ready.id).owner, "standalone");
        assert.equal(listLeases(store).length, 1);
        assert.equal(releaseLease(store, ready.id, { owner: "standalone" }).owner, "standalone");
        assert.deepEqual(expireLeases(store, { now: clock.now() }), []);
      },
      { clock },
    );
  });
});

describe("M2 control store: recovery", () => {
  it("recoverStale sweeps expired leases without starting new runs", async () => {
    const clock = fakeClock();
    await withStore(
      ({ store }) => {
        const task = store.createTask({ title: "recover" });
        const run = store.recordRun({ taskId: task.id });
        store.acquireLease(task.id, { owner: "worker-1", runId: run.id });
        clock.advance(31_000);
        const report = store.recoverStale();
        assert.equal(report.expiredLeases.length, 1);
        assert.equal(report.expiredLeases[0].taskId, task.id);
        assert.equal(report.interruptedRuns.length, 0, "linked run is interrupted by lease expiry");
        assert.equal(store.getTask(task.id).status, "interrupted");
        assert.equal(store.getRun(run.id).status, "interrupted");
        assert.equal(store.listRuns({ taskId: task.id }).length, 1);
        assert.ok(store.listEvents().some((event) => event.type === "control.recovered"));
        const second = recoverStale(store);
        assert.deepEqual(second.expiredLeases, []);
        assert.deepEqual(second.interruptedRuns, []);
        assert.deepEqual(second.interruptedTasks, []);
      },
      { clock },
    );
  });

  it("recoverStale interrupts active runs with no live lease and their running task", async () => {
    await withStore(({ store }) => {
      const task = store.createTask({ title: "orphan run" });
      store.updateTaskStatus(task.id, "running");
      const run = store.recordRun({ taskId: task.id });
      const report = store.recoverStale();
      assert.equal(report.interruptedRuns.length, 1);
      assert.equal(report.interruptedRuns[0].id, run.id);
      assert.ok(report.interruptedRuns[0].endedAt);
      assert.deepEqual(report.interruptedTasks, [task.id]);
      assert.equal(store.getRun(run.id).status, "interrupted");
      assert.equal(store.getTask(task.id).status, "interrupted");
    });
  });

  it("recoverStale leaves an active run untouched while its lease is live", async () => {
    const clock = fakeClock();
    await withStore(
      ({ store }) => {
        const task = store.createTask({ title: "live" });
        const run = store.recordRun({ taskId: task.id });
        store.acquireLease(task.id, { owner: "worker-1", runId: run.id });
        const report = store.recoverStale();
        assert.deepEqual(report.expiredLeases, []);
        assert.deepEqual(report.interruptedRuns, []);
        assert.deepEqual(report.interruptedTasks, []);
        assert.equal(store.getRun(run.id).status, "running");
        assert.equal(store.getTask(task.id).status, "running");
      },
      { clock },
    );
  });

  it("recoverStale honors staleRunAfterMs", async () => {
    const clock = fakeClock();
    await withStore(
      ({ store }) => {
        const task = store.createTask({ title: "window" });
        store.updateTaskStatus(task.id, "running");
        const run = store.recordRun({ taskId: task.id });
        clock.advance(1_000);
        const early = store.recoverStale({ staleRunAfterMs: 60_000 });
        assert.deepEqual(early.interruptedRuns, []);
        assert.equal(store.getRun(run.id).status, "running");
        const late = store.recoverStale({ staleRunAfterMs: 500 });
        assert.equal(late.interruptedRuns.length, 1);
        assert.equal(store.getTask(task.id).status, "interrupted");
      },
      { clock },
    );
  });

  it("interrupts every orphaned active run and never creates a replacement run", async () => {
    await withStore(({ store }) => {
      const task = store.createTask({ title: "two runs" });
      store.updateTaskStatus(task.id, "running");
      const first = store.recordRun({ taskId: task.id, startedAt: "2026-01-01T00:00:00.000Z" });
      const second = store.recordRun({ taskId: task.id, startedAt: "2026-01-01T00:00:01.000Z" });
      const report = store.recoverStale({ staleRunAfterMs: 0, now: "2026-01-01T00:00:02.000Z" });
      assert.equal(report.interruptedRuns.length, 2);
      assert.equal(store.getRun(first.id).status, "interrupted");
      assert.equal(store.getRun(second.id).status, "interrupted");
      assert.equal(store.getTask(task.id).status, "interrupted");
      assert.equal(store.listRuns({ taskId: task.id }).length, 2, "recovery must not create runs");
      const again = store.recoverStale();
      assert.deepEqual(again.interruptedRuns, []);
      assert.deepEqual(again.interruptedTasks, []);
    });
  });
});

describe("M2 control HTTP API", () => {
  it("binds loopback only and requires the bearer token", async () => {
    await withControlServer(async ({ server }) => {
      assert.equal(server.host, "127.0.0.1");
      assert.equal(server.url, `http://127.0.0.1:${server.port}`);
      const address = server.server.address();
      assert.equal(address.address, "127.0.0.1");
      assert.equal(address.family, "IPv4");

      const missing = await api(server, "/v1/health", { token: null });
      assert.equal(missing.status, 401);
      assert.equal(missing.json.error.code, "E_UNAUTHORIZED");
      assert.ok(!missing.text.includes(TOKEN));

      const wrong = await api(server, "/v1/health", { token: "wrong-token" });
      assert.equal(wrong.status, 401);
      const basic = await api(server, "/v1/health", { token: null, headers: { authorization: "Basic abc" } });
      assert.equal(basic.status, 401);

      const health = await api(server, "/v1/health");
      assert.equal(health.status, 200);
      assert.equal(health.headers["content-type"], "application/json; charset=utf-8");
      assert.equal(health.headers["cache-control"], "no-store");
      assert.equal(health.json.ok, true);
      assert.equal(health.json.service, "sage-kit-control");
      assert.equal(health.json.apiVersion, 1);
      assert.equal(health.json.schemaVersion, CONTROL_SCHEMA_VERSION);
    });
  });

  it("rejects non-loopback binds and invalid options", async () => {
    await withStore(async ({ store }) => {
      await expectRejects(createControlServer({ store, token: "" }), "E_BAD_TOKEN");
      await expectRejects(createControlServer({ store, token: "   " }), "E_BAD_TOKEN");
      await expectRejects(createControlServer({ store, token: TOKEN, host: "0.0.0.0" }), "E_BAD_HOST");
      await expectRejects(createControlServer({ store, token: TOKEN, host: "::1" }), "E_BAD_HOST");
      await expectRejects(createControlServer({ store, token: TOKEN, port: 70_000 }), "E_BAD_PORT");
      await expectRejects(createControlServer({ token: TOKEN }), "E_BAD_CONFIG");
    });
  });

  it("serves health, task list/get and 404/405", async () => {
    await withControlServer(async ({ store, server }) => {
      const ready = store.createTask({ title: "one" });
      const running = store.createTask({ title: "two" });
      store.updateTaskStatus(running.id, "running");

      const list = await api(server, "/v1/tasks");
      assert.equal(list.status, 200);
      assert.equal(list.json.tasks.length, 2);
      assert.deepEqual(
        list.json.tasks.map((task) => task.id).sort(),
        [ready.id, running.id].sort(),
      );
      const filtered = await api(server, "/v1/tasks?status=running");
      assert.equal(filtered.json.tasks.length, 1);
      assert.equal(filtered.json.tasks[0].id, running.id);
      const badFilter = await api(server, "/v1/tasks?status=nope");
      assert.equal(badFilter.status, 400);
      assert.equal(badFilter.json.error.code, "E_BAD_STATUS");

      const single = await api(server, `/v1/tasks/${ready.id}`);
      assert.equal(single.status, 200);
      assert.equal(single.json.task.title, "one");
      const notFound = await api(server, "/v1/tasks/task-missing");
      assert.equal(notFound.status, 404);
      assert.equal(notFound.json.error.code, "E_TASK_NOT_FOUND");
      const badId = await api(server, "/v1/tasks/Bad%20Id");
      assert.equal(badId.status, 400);
      assert.equal(badId.json.error.code, "E_BAD_TASK_ID");

      const wrongMethod = await api(server, "/v1/tasks", { method: "POST", body: { title: "x" } });
      assert.equal(wrongMethod.status, 405);
      assert.equal(wrongMethod.headers.allow, "GET");
      const unknown = await api(server, "/v1/nope");
      assert.equal(unknown.status, 404);
      assert.equal(unknown.json.error.code, "E_NOT_FOUND");
    });
  });

  it("acquires and releases leases over HTTP with conflict codes", async () => {
    await withControlServer(async ({ store, server }) => {
      const task = store.createTask({ title: "http lease" });
      const acquire = await api(server, "/v1/leases/acquire", {
        method: "POST",
        body: { taskId: task.id, owner: "http-worker" },
      });
      assert.equal(acquire.status, 200);
      assert.equal(acquire.json.lease.owner, "http-worker");
      assert.equal(acquire.json.lease.taskId, task.id);
      assert.equal(store.getTask(task.id).status, "running");

      const conflict = await api(server, "/v1/leases/acquire", {
        method: "POST",
        body: { taskId: task.id, owner: "other-worker" },
      });
      assert.equal(conflict.status, 409);
      assert.equal(conflict.json.error.code, "E_LEASE_HELD");

      const release = await api(server, "/v1/leases/release", {
        method: "POST",
        body: { taskId: task.id, owner: "http-worker" },
      });
      assert.equal(release.status, 200);
      assert.equal(release.json.released, true);
      assert.equal(store.getLease(task.id), undefined);

      const releaseAgain = await api(server, "/v1/leases/release", {
        method: "POST",
        body: { taskId: task.id, owner: "http-worker" },
      });
      assert.equal(releaseAgain.status, 404);
      assert.equal(releaseAgain.json.error.code, "E_LEASE_NOT_HELD");

      const reacquired = await api(server, "/v1/leases/acquire", {
        method: "POST",
        body: { taskId: task.id, owner: "http-worker" },
      });
      assert.equal(reacquired.status, 200);
      const wrongOwner = await api(server, "/v1/leases/release", {
        method: "POST",
        body: { taskId: task.id, owner: "not-the-owner" },
      });
      assert.equal(wrongOwner.status, 409);
      assert.equal(wrongOwner.json.error.code, "E_LEASE_OWNER_MISMATCH");
    });
  });

  it("rejects malformed JSON, missing bodies and non-loopback Host headers", async () => {
    await withControlServer(async ({ store, server }) => {
      const task = store.createTask({ title: "bad body" });
      const badJson = await api(server, "/v1/leases/acquire", { method: "POST", rawBody: "{not json" });
      assert.equal(badJson.status, 400);
      assert.equal(badJson.json.error.code, "E_BAD_JSON");

      const empty = await api(server, "/v1/leases/acquire", { method: "POST" });
      assert.equal(empty.status, 400);
      assert.equal(empty.json.error.code, "E_BAD_REQUEST");

      const missingOwner = await api(server, "/v1/leases/acquire", {
        method: "POST",
        body: { taskId: task.id },
      });
      assert.equal(missingOwner.status, 400);
      assert.equal(missingOwner.json.error.code, "E_BAD_REQUEST");

      const wrongType = await api(server, "/v1/leases/acquire", {
        method: "POST",
        body: { taskId: 42, owner: "w" },
      });
      assert.equal(wrongType.status, 400);

      const okRaw = await rawRequest(server, {
        method: "GET",
        path: "/v1/health",
        headers: { authorization: `Bearer ${TOKEN}` },
      });
      assert.equal(okRaw.status, 200);

      const evilHost = await rawRequest(server, {
        method: "GET",
        path: "/v1/health",
        headers: { host: "evil.example", authorization: `Bearer ${TOKEN}` },
      });
      assert.equal(evilHost.status, 403);
      assert.equal(evilHost.json.error.code, "E_NON_LOOPBACK");
    });
  });

  it("rejects oversized request bodies", async () => {
    await withControlServer(async ({ store, server }) => {
      const task = store.createTask({ title: "too big" });
      const oversized = JSON.stringify({ taskId: task.id, owner: "w", padding: "x".repeat(70_000) });
      const response = await rawRequest(server, {
        method: "POST",
        path: "/v1/leases/acquire",
        headers: { authorization: `Bearer ${TOKEN}`, "content-type": "application/json" },
        body: oversized,
      });
      assert.equal(response.status, 413);
      assert.equal(response.json.error.code, "E_BODY_TOO_LARGE");
    });
  });

  it("closes idempotently", async () => {
    const dir = await tempProject();
    const store = trackStore(openControl(dir));
    const server = await createControlServer({ store, token: TOKEN });
    await server.close();
    await server.close();
    store.close();
    expectCode(() => store.getTask("task-any"), "E_CONTROL_CLOSED");
  });
});
