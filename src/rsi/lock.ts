/**
 * One-candidate-at-a-time evaluation lock.
 *
 * File mode has no SQLite lease table of its own (see docs/m3-rsi.md §8 for the
 * M2 integration gap), so the evaluator uses a small PID lock file like the M2
 * control plane's `writer.lock`: the lock is created exclusively, released by
 * its owner, and a lock whose owner PID is gone is treated as stale and taken
 * over (crash recovery).
 */
import { mkdir, readFile, unlink, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
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

/**
 * Acquire the global evaluation lock for this project.
 *
 * Throws `E_RSI_EVALUATION_LOCKED` while another live evaluation holds it.
 * `runOnce` never starts a second candidate concurrently.
 */
export async function acquireEvaluationLock(
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
    try {
      await writeFile(path, `${JSON.stringify(info)}\n`, { encoding: "utf8", flag: "wx", mode: 0o600 });
      return true;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "EEXIST") return false;
      throw new SageError(`Cannot create RSI evaluation lock ${path}: ${(error as Error).message}`, "E_RSI_LOCK_FAILED", 1);
    }
  };
  if (!(await tryCreate())) {
    const existingText = await readFile(path, "utf8").catch(() => "");
    const existing = parseLockFile(existingText);
    if (existing && isProcessAlive(existing.pid)) {
      throw new SageError(
        `Another RSI evaluation holds ${path} (pid ${existing.pid}); only one candidate may be evaluated at a time`,
        "E_RSI_EVALUATION_LOCKED",
        1,
      );
    }
    // Stale lock from a crashed process (or corrupt lock content): take it over.
    await unlink(path).catch(() => undefined);
    if (!(await tryCreate())) {
      throw new SageError(`RSI evaluation lock is already held: ${path}`, "E_RSI_EVALUATION_LOCKED", 1);
    }
  }
  return {
    owner,
    path,
    release: async (): Promise<void> => {
      const text = await readFile(path, "utf8").catch(() => "");
      const current = parseLockFile(text);
      if (current && current.owner !== owner) {
        throw new SageError(`RSI evaluation lock owner mismatch at ${path}`, "E_RSI_LOCK_OWNER_MISMATCH", 1);
      }
      await unlink(path).catch((error: NodeJS.ErrnoException) => {
        if (error.code !== "ENOENT") throw error;
      });
    },
  };
}
