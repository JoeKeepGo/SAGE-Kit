import { spawn } from "node:child_process";
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

export async function startRun(
  paths: StatePaths,
  taskId: string,
  argv: string[],
  options: { worktree?: boolean } = {},
): Promise<RunRecord> {
  if (argv.length === 0) throw new SageError("run requires a command after --", "E_USAGE", 2);
  let task = await readTask(paths, taskId);
  if (!["ready", "blocked", "review", "failed", "interrupted", "imported"].includes(task.status)) {
    throw new SageError(`Cannot run task in status ${task.status}`, "E_BAD_TRANSITION", 1);
  }
  if (options.worktree !== false && !task.worktree) {
    task = await createWorktree(paths, taskId);
  }
  const cwd = task.worktree ?? paths.projectRoot;
  const run: RunRecord = {
    schemaVersion: 1,
    id: `run-${new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14)}-${randomToken().slice(0, 6)}`,
    taskId,
    command: redactCommand(argv),
    cwd,
    status: "running",
    startedAt: nowIso(),
  };
  await updateTaskStatus(paths, taskId, "running", { note: `run ${run.id}` });
  const child = spawn(argv[0] as string, argv.slice(1), {
    cwd,
    shell: false,
    windowsHide: true,
    stdio: "inherit",
  });
  run.pid = child.pid;
  await writeRun(paths, run);
  await appendEvent(paths, "run.started", { runId: run.id, pid: run.pid, cwd }, taskId);
  return new Promise<RunRecord>((resolvePromise) => {
    let settled = false;
    const finish = async (code: number | null, signal: NodeJS.Signals | null): Promise<void> => {
      if (settled) return;
      settled = true;
      run.exitCode = code;
      run.signal = signal;
      run.endedAt = nowIso();
      run.status = signal ? "interrupted" : code === 0 ? "exited" : "failed";
      await writeRun(paths, run);
      const next: TaskStatus = signal ? "interrupted" : code === 0 ? "review" : "failed";
      try {
        await updateTaskStatus(paths, taskId, next, {
          note: `run ${run.id} ${run.status}`,
          ...(code === 0 ? { evidence: [`run:${run.id} exit 0`] } : {}),
        });
      } catch {
        // The task may have been changed by another process; the run record remains authoritative.
      }
      await appendEvent(paths, "run.finished", { runId: run.id, status: run.status, exitCode: code }, taskId);
      resolvePromise(run);
    };
    child.on("error", async (error) => {
      run.status = "failed";
      run.endedAt = nowIso();
      run.signal = null;
      await writeRun(paths, run);
      try {
        await updateTaskStatus(paths, taskId, "failed", { note: error.message });
      } catch {
        // ignore
      }
      resolvePromise(run);
    });
    child.on("close", (code, signal) => void finish(code, signal));
  });
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
  return runs.sort((a, b) => b.startedAt.localeCompare(a.startedAt));
}

export async function recoverStaleRuns(paths: StatePaths): Promise<RunRecord[]> {
  const recovered: RunRecord[] = [];
  for (const run of await listRuns(paths)) {
    if (run.status !== "running") continue;
    if (run.pid && isAlive(run.pid)) continue;
    run.status = "interrupted";
    run.endedAt = nowIso();
    run.signal = null;
    await writeRun(paths, run);
    recovered.push(run);
    try {
      const task = await readTask(paths, run.taskId);
      if (task.status === "running" && (await exists(runFile(paths, run.id)))) {
        await updateTaskStatus(paths, run.taskId, "interrupted", { note: `stale run ${run.id}` });
      }
    } catch {
      // A task may be missing after a manual reset; keep the run record.
    }
  }
  return recovered;
}
