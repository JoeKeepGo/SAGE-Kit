import { spawn, type ChildProcess } from "node:child_process";
import { readdir } from "node:fs/promises";
import { join } from "node:path";
import { appendEvent } from "./events.js";
import { SageError } from "./errors.js";
import { exists, nowIso, randomToken, readJsonFile, writeJsonAtomic } from "./fs-utils.js";
import type { StatePaths } from "./paths.js";
import { readTask, updateTaskStatus, type TaskStatus } from "./tasks.js";
import { createWorktree } from "./worktree.js";

export interface RunRecord {
  schemaVersion: 1;
  id: string;
  taskId: string;
  command: string[];
  cwd: string;
  status: "running" | "exited" | "failed" | "interrupted";
  pid?: number;
  exitCode?: number | null;
  signal?: string | null;
  startedAt: string;
  endedAt?: string;
  /** Task-scoped monotonic ordinal; assigned by startRun and never rewritten. */
  generation?: number;
}

function runFile(paths: StatePaths, id: string): string {
  return join(paths.runsDir, `${id}.json`);
}

function redactCommand(argv: string[]): string[] {
  const result: string[] = [];
  let maskNext = false;
  for (const arg of argv) {
    if (maskNext) {
      result.push("<redacted>");
      maskNext = false;
      continue;
    }
    if (/^--?(token|api[-_]?key|password|secret|authorization)$/i.test(arg)) {
      result.push(arg);
      maskNext = true;
    } else if (/^(bearer\s+)|^(sk-)|^(ghp_)/i.test(arg)) {
      result.push("<redacted>");
    } else {
      result.push(arg.slice(0, 500));
    }
  }
  return result;
}

function isAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM";
  }
}

async function writeRun(paths: StatePaths, run: RunRecord): Promise<void> {
  await writeJsonAtomic(runFile(paths, run.id), run);
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function taskStatusForRun(run: RunRecord): TaskStatus {
  if (run.status === "exited") return "review";
  if (run.status === "interrupted") return "interrupted";
  return "failed";
}

/**
 * Keep a task and its run record consistent after a crash or a failed terminal
 * write. A task in `running` with a terminal run is an orphaned start; a
 * recovered running run may have left its task in `running` or `review`.
 */
async function reconcileTask(paths: StatePaths, run: RunRecord): Promise<void> {
  try {
    const task = await readTask(paths, run.taskId);
    if (run.status === "running") {
      if (task.status === "running" || task.status === "review") {
        await updateTaskStatus(paths, run.taskId, "interrupted", { note: `stale run ${run.id}` });
      }
      return;
    }
    if (task.status === "running") {
      await updateTaskStatus(paths, run.taskId, taskStatusForRun(run), {
        note: `run ${run.id} reconciled after ${run.status}`,
      });
    } else if (run.status === "interrupted" && task.status === "review") {
      // A crash can leave the task in `review` while the run record is still
      // `running`; after recovery the run is interrupted but the task would
      // otherwise claim a review that never completed.
      await updateTaskStatus(paths, run.taskId, "interrupted", {
        note: `stale run ${run.id}; review had no completed run record`,
      });
    }
  } catch {
    // A task may be missing after a manual reset; keep the run record.
  }
}

/**
 * A task can be re-run after a crash. The generation is monotonic within the
 * task so recovery never has to guess which run is newest from mutable status
 * or PID liveness. Legacy records without a generation are treated as 0.
 */
async function nextRunGeneration(paths: StatePaths, taskId: string): Promise<number> {
  const runs = await listRuns(paths);
  let max = 0;
  for (const run of runs) {
    if (run.taskId !== taskId) continue;
    max = Math.max(max, run.generation ?? 0);
  }
  return max + 1;
}

export async function startRun(
  paths: StatePaths,
  taskId: string,
  argv: string[],
  options: { worktree?: boolean } = {},
): Promise<RunRecord> {
  if (argv.length === 0) throw new SageError("run requires a command after --", "E_USAGE", 2);
  if (typeof argv[0] !== "string" || argv[0].trim() === "") {
    // Validate before changing task state: an empty executable used to leave a
    // `running` task with no run record when spawn() threw synchronously.
    throw new SageError("run requires a non-empty command after --", "E_USAGE", 2);
  }
  let task = await readTask(paths, taskId);
  if (!["ready", "blocked", "review", "failed", "interrupted", "imported"].includes(task.status)) {
    throw new SageError(`Cannot run task in status ${task.status}`, "E_BAD_TRANSITION", 1);
  }
  if (options.worktree !== false && !task.worktree) {
    task = await createWorktree(paths, taskId);
  }
  const cwd = task.worktree ?? paths.projectRoot;
  const generation = await nextRunGeneration(paths, taskId);
  const run: RunRecord = {
    schemaVersion: 1,
    id: `run-${new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14)}-${randomToken().slice(0, 6)}`,
    taskId,
    command: redactCommand(argv),
    cwd,
    status: "running",
    startedAt: nowIso(),
    generation,
  };

  let child: ChildProcess;
  try {
    child = spawn(argv[0] as string, argv.slice(1), {
      cwd,
      shell: false,
      windowsHide: true,
      stdio: "inherit",
    });
  } catch (error) {
    // Synchronous spawn failures (invalid executable shape, bad options) must
    // not leave a running task with no run record.
    run.status = "failed";
    run.endedAt = nowIso();
    run.signal = null;
    try {
      await writeRun(paths, run);
    } catch (writeError) {
      await updateTaskStatus(paths, taskId, "failed", {
        note: `run ${run.id}: spawn failed and failed record could not be persisted: ${errorText(writeError).slice(0, 500)}`,
      }).catch(() => undefined);
      throw new SageError(
        `Run ${run.id} could not start and its failed record could not be persisted: ${errorText(writeError)}`,
        "E_RUN_PERSIST",
        1,
      );
    }
    await updateTaskStatus(paths, taskId, "failed", {
      note: `run ${run.id}: ${errorText(error).slice(0, 1000)}`,
    }).catch(() => undefined);
    await appendEvent(paths, "run.finished", { runId: run.id, status: run.status, exitCode: null }, taskId).catch(
      () => undefined,
    );
    return run;
  }
  run.pid = child.pid;

  // Attach exit listeners immediately: an ENOENT/error or a very fast process
  // can settle before the first await finishes. Setup is gated so the run is
  // always persisted and `run.started` is appended before `run.finished`.
  let setupDone = false;
  let settled = false;
  let pendingExit: { code: number | null; signal: NodeJS.Signals | null } | undefined;
  let pendingError: Error | undefined;
  let resolveRun!: (value: RunRecord) => void;
  let rejectRun!: (error: Error) => void;
  const result = new Promise<RunRecord>((resolvePromise, rejectPromise) => {
    resolveRun = resolvePromise;
    rejectRun = rejectPromise;
  });

  const persistOrReject = async (terminal: RunRecord): Promise<boolean> => {
    try {
      await writeRun(paths, terminal);
      return true;
    } catch (error) {
      // A result the caller cannot read back must not be reported as success.
      await updateTaskStatus(paths, taskId, "failed", {
        note: `run ${terminal.id}: terminal state could not be persisted: ${errorText(error).slice(0, 500)}`,
      }).catch(() => undefined);
      await appendEvent(
        paths,
        "run.finished",
        { runId: terminal.id, status: "failed", exitCode: null },
        taskId,
      ).catch(() => undefined);
      rejectRun(
        new SageError(
          `Run ${terminal.id} finished (${terminal.status}) but its terminal state could not be persisted: ${errorText(error)}`,
          "E_RUN_PERSIST",
          1,
        ),
      );
      return false;
    }
  };

  const failRun = async (error: Error): Promise<void> => {
    if (settled) return;
    settled = true;
    run.status = "failed";
    run.endedAt = nowIso();
    run.signal = null;
    if (!(await persistOrReject(run))) return;
    try {
      await updateTaskStatus(paths, taskId, "failed", { note: `run ${run.id}: ${errorText(error).slice(0, 1000)}` });
    } catch {
      // The task may have been changed by another process; reconciliation
      // repairs a `running` task on the next recovery pass.
    }
    await appendEvent(paths, "run.finished", { runId: run.id, status: run.status, exitCode: null }, taskId).catch(
      () => undefined,
    );
    resolveRun(run);
  };

  const finishRun = async (code: number | null, signal: NodeJS.Signals | null): Promise<void> => {
    if (settled) return;
    settled = true;
    run.exitCode = code;
    run.signal = signal;
    run.endedAt = nowIso();
    run.status = signal ? "interrupted" : code === 0 ? "exited" : "failed";
    if (!(await persistOrReject(run))) return;
    const next: TaskStatus = taskStatusForRun(run);
    try {
      await updateTaskStatus(paths, taskId, next, {
        note: `run ${run.id} ${run.status}`,
        ...(code === 0 ? { evidence: [`run:${run.id} exit 0`] } : {}),
      });
    } catch {
      // Keep the run record authoritative; recovery reconciles a `running` task.
    }
    await appendEvent(paths, "run.finished", { runId: run.id, status: run.status, exitCode: code }, taskId).catch(
      () => undefined,
    );
    resolveRun(run);
  };

  const maybeSettle = (): void => {
    if (!setupDone || settled) return;
    if (pendingError) void failRun(pendingError);
    else if (pendingExit) void finishRun(pendingExit.code, pendingExit.signal);
  };

  child.once("error", (error) => {
    pendingError = error;
    maybeSettle();
  });
  child.once("close", (code, signal) => {
    pendingExit = { code, signal };
    maybeSettle();
  });

  try {
    await updateTaskStatus(paths, taskId, "running", { note: `run ${run.id}` });
    await writeRun(paths, run);
    await appendEvent(paths, "run.started", { runId: run.id, pid: run.pid, cwd }, taskId);
  } catch (error) {
    // The run could not be registered. Stop the process rather than leave an
    // untracked child; persist a failed run and fail the task if possible.
    settled = true;
    try {
      child.kill();
    } catch {
      // ignore
    }
    run.status = "failed";
    run.endedAt = nowIso();
    await writeRun(paths, run).catch(() => undefined);
    await updateTaskStatus(paths, taskId, "failed", { note: `run ${run.id}: setup failed: ${errorText(error)}` }).catch(
      () => undefined,
    );
    throw new SageError(`Cannot start run ${run.id}: ${errorText(error)}`, "E_RUN_SETUP", 1);
  }
  setupDone = true;
  maybeSettle();
  return result;
}

function runOrderValue(run: RunRecord): number {
  // A re-run can start in the same millisecond as an older run. A live running
  // record outranks a terminal one; a stale running record (dead/missing PID)
  // must not outrank a newer successful run merely because recovery has not
  // rewritten it yet.
  if (run.status === "running") return run.pid !== undefined && isAlive(run.pid) ? 4 : 1;
  return run.status === "exited" ? 3 : run.status === "failed" ? 2 : 1;
}

function compareRunsDesc(a: RunRecord, b: RunRecord): number {
  // `generation` is assigned once by startRun and is the only immutable order.
  // `startedAt` can tie (same millisecond); `endedAt` is mutable because
  // recovery rewrites it; status and PID liveness change after a crash, so they
  // are only fallbacks for legacy records that predate generation.
  return (
    (b.generation ?? 0) - (a.generation ?? 0) ||
    b.startedAt.localeCompare(a.startedAt) ||
    runOrderValue(b) - runOrderValue(a) ||
    b.id.localeCompare(a.id)
  );
}

export async function listRuns(paths: StatePaths): Promise<RunRecord[]> {
  let names: string[] = [];
  try {
    names = await readdir(paths.runsDir);
  } catch {
    return [];
  }
  const runs: RunRecord[] = [];
  for (const name of names) {
    if (!name.endsWith(".json")) continue;
    try {
      const run = await readJsonFile<RunRecord>(join(paths.runsDir, name));
      if (run.schemaVersion === 1 && run.id) runs.push(run);
    } catch {
      // doctor reports malformed run files separately in the future.
    }
  }
  return runs.sort(compareRunsDesc);
}

export async function recoverStaleRuns(paths: StatePaths): Promise<RunRecord[]> {
  const recovered: RunRecord[] = [];
  const runs = await listRuns(paths);
  // A task can be re-run after an interrupted attempt. Only the newest run for
  // that task may reconcile the task; an older terminal/interrupted record must
  // never overwrite the state produced by a later successful run.
  const latestByTask = new Map<string, string>();
  for (const run of runs) {
    if (!latestByTask.has(run.taskId)) latestByTask.set(run.taskId, run.id);
  }
  // Legacy records predate `generation`. If a task is still `running` and an
  // older successful record ties the newest start with a now-dead running
  // record, the success must not win: the newest attempt died before it could
  // report. Keep the dead run as current so recovery marks the task
  // interrupted instead of falsely claiming a review.
  for (const taskId of new Set(runs.map((run) => run.taskId))) {
    const latest = runs.find((run) => run.id === latestByTask.get(taskId));
    if (!latest || latest.status !== "exited" || latest.generation !== undefined) continue;
    let task;
    try {
      task = await readTask(paths, taskId);
    } catch {
      continue;
    }
    if (task.status !== "running") continue;
    const deadRunning = runs.find(
      (run) =>
        run.taskId === taskId &&
        run.status === "running" &&
        run.generation === undefined &&
        run.startedAt === latest.startedAt &&
        (!run.pid || !isAlive(run.pid)),
    );
    if (deadRunning) latestByTask.set(taskId, deadRunning.id);
  }
  for (const run of runs) {
    const isCurrent = latestByTask.get(run.taskId) === run.id;
    if (run.status !== "running") {
      if (isCurrent) await reconcileTask(paths, run);
      continue;
    }
    if (run.pid && isAlive(run.pid)) continue;
    run.status = "interrupted";
    run.endedAt = nowIso();
    run.signal = null;
    await writeRun(paths, run);
    recovered.push(run);
    if (isCurrent) await reconcileTask(paths, run);
  }
  return recovered;
}
