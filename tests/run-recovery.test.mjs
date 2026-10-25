import assert from "node:assert/strict";
import childProcess from "node:child_process";
import { EventEmitter } from "node:events";
import fs from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { after, it, mock } from "node:test";
import { runDoctor } from "../dist/core/doctor.js";
import { initSageKit } from "../dist/core/install.js";
import { statePaths } from "../dist/core/paths.js";
import { recoverStaleRuns, startRun } from "../dist/core/runs.js";
import { createTask, readTask, updateTaskStatus } from "../dist/core/tasks.js";

const roots = [];
const base = process.env.SAGE_KIT_TEST_TMPDIR ?? tmpdir();
await fs.mkdir(base, { recursive: true });
after(async () => {
  for (const root of roots) await fs.rm(root, { recursive: true, force: true });
});

async function fixture(status = "ready") {
  const root = await fs.mkdtemp(join(base, "sage-run-recovery-"));
  roots.push(root);
  const paths = statePaths(root);
  const task = await createTask(paths, { id: "task-recovery", title: "Recovery", status });
  return { root, paths, task };
}

async function record(paths, task, status = "running", generation = 1) {
  await fs.mkdir(paths.runsDir, { recursive: true });
  const run = {
    schemaVersion: 1, id: `run-${generation}`, taskId: task.id, command: ["fixture"],
    cwd: paths.projectRoot, status, startedAt: "2020-01-01T00:00:00.000Z", generation,
  };
  if (status !== "running") run.endedAt = "2020-01-01T00:00:01.000Z";
  await fs.writeFile(join(paths.runsDir, `${run.id}.json`), JSON.stringify(run));
  return run;
}

function alive(pid) {
  try { process.kill(pid, 0); return true; }
  catch (error) { return error.code === "EPERM"; }
}

it("startup recovery covers every permitted starting status and reports actual transitions", async () => {
  for (const status of ["ready", "blocked", "review", "failed", "interrupted", "running"]) {
    const { paths, task } = await fixture(status);
    await record(paths, task);
    const result = await recoverStaleRuns(paths);
    assert.equal(result.recovered.length, 1, status);
    assert.deepEqual(result.errors, [], status);
    assert.equal((await readTask(paths, task.id)).status, "interrupted", status);
    assert.deepEqual(result.taskChanges, status === "interrupted" ? [] : [
      { taskId: task.id, from: status, to: "interrupted" },
    ], status);
  }
});

it("already-terminal runs preserve explicit failed/interrupted resets to ready", async () => {
  for (const status of ["failed", "interrupted"]) {
    const { paths, task } = await fixture(status);
    await record(paths, task, status);
    await updateTaskStatus(paths, task.id, "ready");
    const result = await recoverStaleRuns(paths);
    assert.equal((await readTask(paths, task.id)).status, "ready");
    assert.deepEqual(result, { recovered: [], taskChanges: [], errors: [] });
  }
});

it("recovery preserves completed/cancelled/imported tasks and older generations", async () => {
  for (const status of ["done", "cancelled", "imported"]) {
    const { paths, task } = await fixture(status === "done" ? "review" : status);
    if (status === "done") await updateTaskStatus(paths, task.id, "done", { evidence: ["manual acceptance"] });
    await record(paths, task);
    const result = await recoverStaleRuns(paths);
    assert.equal(result.recovered.length, 1);
    assert.deepEqual(result.taskChanges, []);
    assert.equal((await readTask(paths, task.id)).status, status);
  }
  const { paths, task } = await fixture("review");
  await record(paths, task, "running", 1);
  await record(paths, task, "exited", 2);
  const result = await recoverStaleRuns(paths);
  assert.equal(result.recovered.length, 1);
  assert.deepEqual(result.taskChanges, []);
  assert.equal((await readTask(paths, task.id)).status, "review");
});

it("terminal reconciliation reports its actual change without a stale run", async () => {
  const { paths, task } = await fixture("running");
  await record(paths, task, "failed");
  const result = await recoverStaleRuns(paths);
  assert.deepEqual(result.recovered, []);
  assert.deepEqual(result.taskChanges, [{ taskId: task.id, from: "running", to: "failed" }]);
  assert.equal((await readTask(paths, task.id)).status, "failed");
});

it("doctor reports task-write failure, keeps the stale run retriable, and counts actual changes", async () => {
  const { root, paths, task } = await fixture("blocked");
  await initSageKit({ projectRoot: root, host: "fake", scope: "project", instructions: false });
  await record(paths, task);
  const rename = fs.rename;
  mock.method(fs, "rename", async (from, to) => {
    if (to === join(paths.tasksDir, `${task.id}.json`)) throw new Error("injected task write failure");
    return rename(from, to);
  });
  syncBuiltinESMExports();
  try {
    const doctor = await runDoctor(root);
    const runs = doctor.checks.find((check) => check.name === "runs");
    assert.equal(runs.status, "warn");
    assert.match(runs.detail, /injected task write failure/);
    assert.match(runs.detail, /0 task/);
    assert.equal((await readTask(paths, task.id)).status, "blocked");
    assert.equal(JSON.parse(await fs.readFile(join(paths.runsDir, "run-1.json"), "utf8")).status, "running");
  } finally { mock.restoreAll(); syncBuiltinESMExports(); }
  const doctor = await runDoctor(root);
  const runs = doctor.checks.find((check) => check.name === "runs");
  assert.match(runs.detail, /1 task/);
  assert.match(runs.detail, /blocked.*interrupted/);
});

it("PID persistence failure waits for a real child to terminate before rejecting", async () => {
  const { root, paths, task } = await fixture();
  const ready = join(root, "child-ready");
  const rename = fs.rename;
  let runWrites = 0;
  let pid;
  mock.method(fs, "rename", async (from, to) => {
    if (to.startsWith(paths.runsDir) && ++runWrites === 2) {
      const deadline = Date.now() + 10_000;
      while (Date.now() < deadline) {
        try { pid = Number(await fs.readFile(ready, "utf8")); break; }
        catch (error) { if (error.code !== "ENOENT") throw error; }
        await delay(10);
      }
      assert.ok(pid, "child installed its SIGTERM handler before the injected failure");
      throw new Error("injected PID write failure");
    }
    return rename(from, to);
  });
  syncBuiltinESMExports();
  try {
    await assert.rejects(startRun(paths, task.id, [process.execPath, "-e",
      "process.on('SIGTERM', () => {}); require('node:fs').writeFileSync(process.argv[1], String(process.pid)); setInterval(() => {}, 1000)", ready,
    ], { worktree: false }), /injected PID write failure/);
    assert.equal(alive(pid), false, "failure is not returned while the child is alive");
    const [name] = await fs.readdir(paths.runsDir);
    const run = JSON.parse(await fs.readFile(join(paths.runsDir, name), "utf8"));
    assert.equal(run.status, "failed");
    assert.equal(run.pid, pid);
  } finally {
    mock.restoreAll(); syncBuiltinESMExports();
    if (pid && alive(pid)) process.kill(pid, "SIGKILL");
  }
});

it("unconfirmed setup termination reports the unresolved PID and keeps a running record", async () => {
  const { paths, task } = await fixture();
  const child = new EventEmitter();
  Object.assign(child, { pid: 999999, exitCode: null, signalCode: null });
  const signals = [];
  child.kill = (signal) => { signals.push(signal); return false; };
  const rename = fs.rename;
  let runWrites = 0;
  mock.method(childProcess, "spawn", () => child);
  mock.method(fs, "rename", async (from, to) => {
    if (to.startsWith(paths.runsDir) && ++runWrites === 2) throw new Error("injected PID write failure");
    return rename(from, to);
  });
  syncBuiltinESMExports();
  try {
    await assert.rejects(startRun(paths, task.id, ["fixture"], { worktree: false }),
      (error) => error.code === "E_RUN_CLEANUP" && /999999/.test(error.message));
    assert.deepEqual(signals, ["SIGTERM", "SIGKILL"]);
    const [name] = await fs.readdir(paths.runsDir);
    const run = JSON.parse(await fs.readFile(join(paths.runsDir, name), "utf8"));
    assert.equal(run.status, "running");
    assert.equal(run.pid, child.pid);
    assert.equal((await readTask(paths, task.id)).status, "ready");
  } finally { mock.restoreAll(); syncBuiltinESMExports(); }
});

it("recovery reports a committed task change even when its event append fails", async () => {
  const { paths, task } = await fixture("ready");
  await record(paths, task);
  const open = fs.open;
  mock.method(fs, "open", async (path, flags, ...args) => {
    if (path === join(paths.eventsDir, "events.jsonl") && flags === "a") throw new Error("injected event failure");
    return open(path, flags, ...args);
  });
  syncBuiltinESMExports();
  try {
    const result = await recoverStaleRuns(paths);
    assert.deepEqual(result.taskChanges, [{ taskId: task.id, from: "ready", to: "interrupted" }]);
    assert.match(result.errors.join("; "), /injected event failure/);
    assert.equal((await readTask(paths, task.id)).status, "interrupted");
    assert.equal(result.recovered.length, 0);
  } finally { mock.restoreAll(); syncBuiltinESMExports(); }
  const retried = await recoverStaleRuns(paths);
  assert.equal(retried.recovered.length, 1);
  assert.deepEqual(retried.taskChanges, []);
  assert.deepEqual(retried.errors, []);
});

it("setup cleanup escalates past ignored SIGTERM and waits for confirmed SIGKILL exit", async () => {
  const { paths, task } = await fixture();
  const child = new EventEmitter();
  Object.assign(child, { pid: 999999, exitCode: null, signalCode: null });
  const signals = [];
  let exited = false;
  child.kill = (signal) => {
    signals.push(signal);
    if (signal === "SIGKILL") setTimeout(() => {
      exited = true;
      child.signalCode = "SIGKILL";
      child.emit("exit", null, "SIGKILL");
      child.emit("close", null, "SIGKILL");
    }, 25);
    return true;
  };
  const rename = fs.rename;
  let runWrites = 0;
  mock.method(childProcess, "spawn", () => child);
  mock.method(fs, "rename", async (from, to) => {
    if (to.startsWith(paths.runsDir) && ++runWrites === 2) throw new Error("injected PID write failure");
    return rename(from, to);
  });
  syncBuiltinESMExports();
  try {
    await assert.rejects(startRun(paths, task.id, ["fixture"], { worktree: false }),
      (error) => error.code === "E_RUN_SETUP" && /injected PID write failure/.test(error.message));
    assert.deepEqual(signals, ["SIGTERM", "SIGKILL"]);
    assert.equal(exited, true, "setup failure was not reported before the exit confirmation");
    const [name] = await fs.readdir(paths.runsDir);
    const run = JSON.parse(await fs.readFile(join(paths.runsDir, name), "utf8"));
    assert.equal(run.status, "failed");
  } finally { mock.restoreAll(); syncBuiltinESMExports(); }
});
