import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
import { exists, ensureDir } from "./fs-utils.js";

export interface StatePaths {
  projectRoot: string;
  stateDir: string;
  config: string;
  tasksDir: string;
  eventsDir: string;
  runsDir: string;
  worktreesDir: string;
  briefPath: string;
  cacheDir: string;
}

export async function findProjectRoot(start: string): Promise<string> {
  let current = resolve(start);
  for (;;) {
    if (await exists(join(current, ".git"))) return current;
    const parent = dirname(current);
    if (parent === current) return resolve(start);
    current = parent;
  }
}

export function homeDirectory(env: NodeJS.ProcessEnv = process.env): string {
  return env.HOME || env.USERPROFILE || resolve(".");
}

export function packageRoot(importMetaUrl: string): string {
  return resolve(dirname(fileURLToPath(importMetaUrl)), "..", "..");
}

// For the CLI entry point (dist/cli.js or src/cli.ts) the package root is one
// level above the entry file's directory. Do not confuse it with packageRoot(),
// which is for modules nested one level below the package root (dist/core/*.js).
export function entryPackageRoot(importMetaUrl: string): string {
  return resolve(dirname(fileURLToPath(importMetaUrl)), "..");
}

export function skillSourceDir(root: string): string {
  return join(root, "skills", "sage-kit");
}

export function statePaths(projectRoot: string): StatePaths {
  const stateDir = join(projectRoot, ".sage-kit");
  return {
    projectRoot,
    stateDir,
    config: join(stateDir, "config.json"),
    tasksDir: join(stateDir, "state", "tasks"),
    eventsDir: join(stateDir, "state", "events"),
    runsDir: join(stateDir, "state", "runs"),
    worktreesDir: join(stateDir, "worktrees"),
    briefPath: join(projectRoot, "SESSION_BRIEF.md"),
    cacheDir: join(stateDir, "cache"),
  };
}

export async function ensureStateDirs(paths: StatePaths): Promise<void> {
  for (const dir of [paths.stateDir, paths.tasksDir, paths.eventsDir, paths.runsDir, paths.cacheDir]) {
    await ensureDir(dir);
  }
}

export function taskFile(paths: StatePaths, id: string): string {
  return join(paths.tasksDir, `${id}.json`);
}

export function eventsFile(paths: StatePaths): string {
  return join(paths.eventsDir, "events.jsonl");
}
