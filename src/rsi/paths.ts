/**
 * File-mode RSI state layout (single authoritative writer, D-005):
 *
 *   <project-root>/.sage-kit/rsi/
 *     proposals/<id>.json
 *     evaluations/<id>.json
 *     approvals/<id>.json
 *     rollback-points/<id>.json
 *     exports/<evaluation-id>.json
 *     evaluation.lock
 *
 * `.gitignore` already ignores `.sage-kit/`, so none of this state can be
 * committed accidentally.
 */
import { randomBytes } from "node:crypto";
import { join, resolve } from "node:path";
import { ensureDir } from "../core/fs-utils.js";
import { statePaths } from "../core/paths.js";

export interface RsiPaths {
  projectRoot: string;
  rsiDir: string;
  proposalsDir: string;
  evaluationsDir: string;
  approvalsDir: string;
  rollbackPointsDir: string;
  exportsDir: string;
  lockPath: string;
}

export function rsiPaths(projectRoot: string): RsiPaths {
  const root = resolve(projectRoot);
  const rsiDir = join(statePaths(root).stateDir, "rsi");
  return {
    projectRoot: root,
    rsiDir,
    proposalsDir: join(rsiDir, "proposals"),
    evaluationsDir: join(rsiDir, "evaluations"),
    approvalsDir: join(rsiDir, "approvals"),
    rollbackPointsDir: join(rsiDir, "rollback-points"),
    exportsDir: join(rsiDir, "exports"),
    lockPath: join(rsiDir, "evaluation.lock"),
  };
}

/** Create the state directories. Only called by write paths. */
export async function ensureRsiPaths(paths: RsiPaths): Promise<void> {
  for (const dir of [
    paths.proposalsDir,
    paths.evaluationsDir,
    paths.approvalsDir,
    paths.rollbackPointsDir,
    paths.exportsDir,
  ]) {
    await ensureDir(dir);
  }
}

export type RsiIdPrefix = "prop" | "eval" | "appr" | "rb";

/** `prop-20260101000000-a1b2c3` — always matches `[a-z0-9][a-z0-9-]{0,63}`. */
export function newRsiId(prefix: RsiIdPrefix, nowIso: string, token = randomBytes(3).toString("hex")): string {
  const stamp = nowIso.replace(/[-:T]/g, "").slice(0, 14);
  return `${prefix}-${stamp}-${token}`;
}

export function proposalFile(paths: RsiPaths, id: string): string {
  return join(paths.proposalsDir, `${id}.json`);
}

export function evaluationFile(paths: RsiPaths, id: string): string {
  return join(paths.evaluationsDir, `${id}.json`);
}

export function approvalFile(paths: RsiPaths, id: string): string {
  return join(paths.approvalsDir, `${id}.json`);
}

export function rollbackPointFile(paths: RsiPaths, id: string): string {
  return join(paths.rollbackPointsDir, `${id}.json`);
}
