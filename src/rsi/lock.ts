/**
 * One-candidate-at-a-time evaluation lock.
 *
 * File mode has no SQLite lease table of its own (see docs/m3-rsi.md §8 for the
 * M2 integration gap), so the evaluator uses a small PID lock file like the M2
 * control plane's `writer.lock`: the lock is created exclusively, released by
 * its owner, and a lock whose owner PID is gone is treated as stale and taken
 * over (crash recovery).
 */
import { mkdir, readFile, rename, rmdir, stat, unlink, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { SageError } from "../core/errors.js";
import { randomToken } from "../core/fs-utils.js";
import type { RsiStore } from "./store.js";

export interface EvaluationLock {
  readonly owner: string;
  readonly path: string;
  release(): Promise<void>;
}

interface LockFileInfo {
  pid: number;
  owner: string;
  startedAt: string;
}

function isProcessAlive(pid: number): boolean {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM";
  }
}

function parseLockFile(text: string): LockFileInfo | undefined {
  try {
    const parsed = JSON.parse(text) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return undefined;
    const record = parsed as Record<string, unknown>;
    if (typeof record.pid !== "number" || !Number.isInteger(record.pid)) return undefined;
    if (typeof record.owner !== "string" || !record.owner) return undefined;
    if (typeof record.startedAt !== "string") return undefined;
    return { pid: record.pid, owner: record.owner, startedAt: record.startedAt };
  } catch {
    return undefined;
  }
}

export interface EvaluationLockStatus {
  state: "free" | "live" | "stale";
  pid?: number;
  owner?: string;
}

/** Read the lock without taking it; recovery must not disturb a live evaluator. */
export async function inspectEvaluationLock(store: RsiStore): Promise<EvaluationLockStatus> {
  const text = await readLockText(store.paths.lockPath);
  if (!text) return { state: "free" };
  const existing = parseLockFile(text);
  if (!existing) return { state: "stale" };
  return {
    state: isProcessAlive(existing.pid) ? "live" : "stale",
    pid: existing.pid,
    owner: existing.owner,
  };
}

/**
 * Acquire the global evaluation lock for this project.
 *
 * Throws `E_RSI_EVALUATION_LOCKED` while another live evaluation holds it.
 * `runOnce` never starts a second candidate concurrently.
 *
 * In-process calls are serialized. A stale or corrupt mutex is never moved
 * automatically: moving the public mutex path opens a window in which two
 * evaluators can enter the critical section. Instead the caller gets an
 * explicit error and must verify that no evaluator is running, then remove the
 * mutex directory manually.
 */
export async function acquireEvaluationLock(
  store: RsiStore,
  options: { now?: string } = {},
): Promise<EvaluationLock> {
  return serializeLockAccess(() =>
    withLockMutex(store.paths.lockPath, () => acquireEvaluationLockUnsafe(store, options)),
  );
}

const MUTEX_STALE_MS = 30_000;
const MUTEX_WAIT_MS = 5_000;

async function sleep(ms: number): Promise<void> {
  await new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

async function readLockText(path: string): Promise<string> {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      return await readFile(path, "utf8");
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "ENOENT") return "";
      if ((code === "EPERM" || code === "EBUSY" || code === "EACCES") && attempt < 49) {
        await sleep(10);
        continue;
      }
      throw new SageError(`Cannot read RSI lock ${path}: ${(error as Error).message}`, "E_RSI_LOCK_FAILED", 1);
    }
  }
  throw new SageError(`Cannot read RSI lock ${path}`, "E_RSI_LOCK_FAILED", 1);
}

/**
 * Release our own mutex without renaming the public path. Renaming a directory
 * is not reliably atomic on Windows (a concurrent reader/AV scanner can make it
 * fail with EPERM), and a swallowed failure would leave a live mutex behind.
 *
 * The owner file is removed first, then the now-empty directory is removed. A
 * waiter that sees a fresh ownerless directory waits; an old ownerless one is
 * reported as stale and requires manual cleanup. Transient EPERM/EBUSY is
 * retried; a real failure is reported instead of being ignored.
 */
async function removeOwnedMutex(mutex: string, ownerToken: string): Promise<void> {
  const ownerPath = join(mutex, "owner");
  const ownerText = await readLockText(ownerPath);
  let owner: string | undefined;
  try {
    const parsed = JSON.parse(ownerText) as { owner?: unknown };
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed) && typeof parsed.owner === "string") {
      owner = parsed.owner;
    }
  } catch {
    throw new SageError(`Cannot release RSI lock mutex ${mutex}: owner record is corrupt`, "E_RSI_LOCK_FAILED", 1);
  }
  if (!owner) {
    // A syntactically valid JSON object with a missing/wrong/empty owner token
    // is a schema corruption, not "another owner": do not silently leave our
    // mutex behind.
    throw new SageError(`Cannot release RSI lock mutex ${mutex}: owner record is corrupt`, "E_RSI_LOCK_FAILED", 1);
  }
  if (owner !== ownerToken) return;

  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      await unlink(ownerPath);
      break;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "ENOENT") break;
      if (attempt === 99) {
        throw new SageError(
          `Cannot release RSI lock mutex ${mutex}: ${(error as Error).message}`,
          "E_RSI_LOCK_FAILED",
          1,
        );
      }
      await sleep(10);
    }
  }

  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      await rmdir(mutex);
      return;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "ENOENT") return;
      if (attempt === 99) {
        throw new SageError(
          `Cannot remove released RSI lock mutex ${mutex}: ${(error as Error).message}`,
          "E_RSI_LOCK_FAILED",
          1,
        );
      }
      await sleep(10);
    }
  }
}

async function withLockMutex<T>(lockPath: string, task: () => Promise<T>): Promise<T> {
  const mutex = `${lockPath}.mutex`;
  const ownerToken = randomToken();
  const deadline = Date.now() + MUTEX_WAIT_MS;
  await mkdir(dirname(mutex), { recursive: true, mode: 0o700 });
  for (;;) {
    try {
      await mkdir(mutex, { recursive: false, mode: 0o700 });
      await writeFile(join(mutex, "owner"), JSON.stringify({ pid: process.pid, owner: ownerToken }), {
        encoding: "utf8",
        flag: "wx",
        mode: 0o600,
      });
      break;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "ENOENT") {
        // The mutex directory disappeared between checks (for example a
        // concurrent release); retry without treating it as a hard failure.
        if (Date.now() >= deadline) throw new SageError(`Timed out waiting for RSI lock mutex ${mutex}`, "E_RSI_LOCK_FAILED", 1);
        await sleep(10);
        continue;
      }
      if (code !== "EEXIST") {
        if ((code === "EPERM" || code === "EBUSY" || code === "EACCES") && Date.now() < deadline) {
          await sleep(10);
          continue;
        }
        throw new SageError(`Cannot create RSI lock mutex ${mutex}: ${(error as Error).message}`, "E_RSI_LOCK_FAILED", 1);
      }
      const info = await stat(mutex).catch(() => undefined);
      const ownerText = await readFile(join(mutex, "owner"), "utf8").catch(() => "");
      let ownerPid: number | undefined;
      try {
        const parsed = JSON.parse(ownerText) as { pid?: unknown };
        if (typeof parsed.pid === "number" && Number.isInteger(parsed.pid)) ownerPid = parsed.pid;
      } catch {
        // A mutex created but not yet published has no owner file; wait below.
      }
      if (ownerPid !== undefined && !isProcessAlive(ownerPid)) {
        // Never move the public mutex: another process may already have
        // replaced it after our read, and the temporary gap would let a third
        // process enter. Fail closed and require explicit cleanup.
        throw new SageError(
          `RSI lock mutex ${mutex} is stale (pid ${ownerPid}); verify no evaluator is running, then remove that directory manually`,
          "E_RSI_LOCK_STALE",
          1,
        );
      }
      if (info && ownerPid === undefined && Date.now() - info.mtimeMs > MUTEX_STALE_MS) {
        // The owner file is missing/corrupt: the creator likely died between
        // mkdir and writeFile. Age alone is not evidence against a live owner,
        // so only an old, ownerless directory is reported as stale.
        throw new SageError(
          `RSI lock mutex ${mutex} has no usable owner record; verify no evaluator is running, then remove that directory manually`,
          "E_RSI_LOCK_STALE",
          1,
        );
      }
      if (Date.now() >= deadline) {
        throw new SageError(
          `Timed out waiting for RSI lock mutex ${mutex}; another evaluator is stuck or still starting`,
          "E_RSI_LOCK_FAILED",
          1,
        );
      }
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 25));
    }
  }
  try {
    return await task();
  } finally {
    await removeOwnedMutex(mutex, ownerToken);
  }
}

let lockQueue: Promise<unknown> = Promise.resolve();

/**
 * Acquires in one process share a FIFO queue so two in-process callers do not
 * both enter the mutex-wait loop for the same candidate. Release intentionally
 * does not use this queue: it is lock-free on the evaluation lock file (see
 * makeLock), which prevents a stream of acquires from starving a release.
 */
function serializeLockAccess<T>(task: () => Promise<T>): Promise<T> {
  const next = lockQueue.then(task, task);
  lockQueue = next.then(
    () => undefined,
    () => undefined,
  );
  return next;
}

async function acquireEvaluationLockUnsafe(
  store: RsiStore,
  options: { now?: string } = {},
): Promise<EvaluationLock> {
  const path = store.paths.lockPath;
  await mkdir(dirname(path), { recursive: true, mode: 0o700 });
  const owner = randomToken();
  const info: LockFileInfo = {
    pid: process.pid,
    owner,
    startedAt: options.now ?? store.nowIso(),
  };
  const tryCreate = async (): Promise<boolean> => {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      try {
        await writeFile(path, `${JSON.stringify(info)}\n`, { encoding: "utf8", flag: "wx", mode: 0o600 });
        return true;
      } catch (error) {
        const code = (error as NodeJS.ErrnoException).code;
        if (code === "EEXIST") return false;
        if ((code === "EPERM" || code === "EBUSY" || code === "EACCES") && attempt < 49) {
          // Windows can report a transient EPERM while another process is
          // unlinking/creating the same path; retry instead of failing a
          // normal concurrent acquisition.
          await sleep(10);
          continue;
        }
        throw new SageError(`Cannot create RSI evaluation lock ${path}: ${(error as Error).message}`, "E_RSI_LOCK_FAILED", 1);
      }
    }
    throw new SageError(`Cannot create RSI evaluation lock ${path}`, "E_RSI_LOCK_FAILED", 1);
  };
  if (!(await tryCreate())) {
    const existingText = await readLockText(path);
    const existing = parseLockFile(existingText);
    if (existing && isProcessAlive(existing.pid)) {
      throw new SageError(
        `Another RSI evaluation holds ${path} (pid ${existing.pid}); only one candidate may be evaluated at a time`,
        "E_RSI_EVALUATION_LOCKED",
        1,
      );
    }
    // Take over a stale/corrupt lock without deleting a lock that another
    // process may have created between the read and the takeover. rename() is
    // atomic; if it moved a different owner's fresh lock, put it back.
    const stalePath = `${path}.stale.${process.pid}.${randomToken()}`;
    try {
      await rename(path, stalePath);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
        throw new SageError(`Cannot take over stale RSI lock ${path}: ${(error as Error).message}`, "E_RSI_LOCK_FAILED", 1);
      }
      if (await tryCreate()) return makeLock(path, owner);
      throw new SageError(`RSI evaluation lock is already held: ${path}`, "E_RSI_EVALUATION_LOCKED", 1);
    }
    const movedText = await readLockText(stalePath);
    const moved = parseLockFile(movedText);
    if (existing && moved && moved.owner !== existing.owner) {
      // We moved a lock created after our read. Restore it if the path is
      // still free; otherwise leave the other owner's lock in place.
      try {
        await rename(stalePath, path);
      } catch {
        await unlink(stalePath).catch(() => undefined);
      }
      throw new SageError(`RSI evaluation lock changed during takeover: ${path}`, "E_RSI_EVALUATION_LOCKED", 1);
    }
    await unlink(stalePath).catch(() => undefined);
    if (!(await tryCreate())) {
      throw new SageError(`RSI evaluation lock is already held: ${path}`, "E_RSI_EVALUATION_LOCKED", 1);
    }
  }
  return makeLock(path, owner);
}

function makeLock(path: string, owner: string): EvaluationLock {
  let releasing: Promise<void> | undefined;
  let released = false;
  return {
    owner,
    path,
    release: async (): Promise<void> => {
      if (released) return;
      if (releasing) return releasing;
      // Release is lock-free on purpose. It owns the evaluation lock file and
      // only needs to unlink it; routing release through the same mutex as
      // acquire made a continuous stream of acquisitions starve the release
      // (and left the evaluation lock behind after the 5 s timeout). A
      // concurrent acquire sees either the live lock (and is refused) or the
      // already-unlinked path (and may create a new lock); both are safe for
      // cooperative local processes. Owner validation still prevents deleting
      // another process's lock.
      releasing = (async (): Promise<void> => {
        const text = await readLockText(path);
        const current = parseLockFile(text);
        if (current && current.owner !== owner) {
          throw new SageError(`RSI evaluation lock owner mismatch at ${path}`, "E_RSI_LOCK_OWNER_MISMATCH", 1);
        }
        await unlink(path).catch((error: NodeJS.ErrnoException) => {
          if (error.code !== "ENOENT") throw error;
        });
        released = true;
      })();
      try {
        await releasing;
      } finally {
        releasing = undefined;
      }
    },
  };
}
