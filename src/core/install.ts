import { lstat, readdir, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import {
  atomicWrite,
  copyDirectory,
  ensureDir,
  exists,
  isPathInside,
  nowIso,
  readText,
  removePath,
  sha256,
} from "./fs-utils.js";
import { SageError } from "./errors.js";
import { detectAdapters, getAdapter } from "../adapters/index.js";
import type { HostAdapter } from "../adapters/types.js";
import {
  type InstructionsInstall,
  type SageConfig,
  type SkillMode,
  type InstallScope,
  loadConfig,
  readPackageVersion,
  saveConfig,
} from "./config.js";
import { ensureStateDirs, packageRoot, skillSourceDir, statePaths, type StatePaths } from "./paths.js";
import { buildBrief } from "./brief.js";

export interface InitOptions {
  host?: string;
  scope?: InstallScope;
  mode?: SkillMode;
  force?: boolean;
  instructions?: boolean;
  projectRoot?: string;
  env?: NodeJS.ProcessEnv;
  home?: string;
}

export interface InitResult {
  host: string;
  scope: InstallScope;
  projectRoot: string;
  configPath: string;
  skillPath: string;
  skillMode: SkillMode;
  instructionsPath?: string;
  briefPath: string;
  created: boolean;
  warnings: string[];
  files: string[];
}

function beginMarker(blockId: string): string {
  return `<!-- ${blockId}:begin -->`;
}

function endMarker(blockId: string): string {
  return `<!-- ${blockId}:end -->`;
}

export function instructionBlock(blockId: string): string {
  return [
    beginMarker(blockId),
    "## SAGE-Kit",
    "",
    "This repository uses SAGE-Kit for evidence-backed tasks.",
    "",
    "- At the start of work, run `npx sage-kit brief` (or `sage-kit brief`) and follow it.",
    "- Create or update a task with `npx sage-kit task ...`; keep work inside its scope.",
    "- Record exact evidence before claiming done: `npx sage-kit task status <id> done --evidence \"...\"`.",
    "- If blocked, mark the task `blocked` and report the concrete condition.",
    "",
    endMarker(blockId),
    "",
  ].join("\n");
}

export async function writeInstructions(target: string, blockId: string, content: string): Promise<void> {
  const existing = (await exists(target)) ? await readText(target) : "";
  const begin = existing.indexOf(beginMarker(blockId));
  const end = existing.indexOf(endMarker(blockId));
  let next: string;
  if (begin >= 0 && end > begin) {
    const after = existing.slice(end + endMarker(blockId).length);
    next = `${existing.slice(0, begin)}${content}${after.replace(/^\s*\n/, "\n")}`;
  } else {
    next = `${existing.replace(/\s*$/, "")}\n\n${content}`;
  }
  await atomicWrite(target, next.replace(/\n{3,}/g, "\n\n"));
}

export async function removeInstructions(target: string, blockId: string): Promise<boolean> {
  if (!(await exists(target))) return false;
  const existing = await readText(target);
  const begin = existing.indexOf(beginMarker(blockId));
  const end = existing.indexOf(endMarker(blockId));
  if (begin < 0 || end <= begin) return false;
  const next = `${existing.slice(0, begin)}${existing.slice(end + endMarker(blockId).length)}`
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd();
  await atomicWrite(target, next ? `${next}\n` : "");
  return true;
}

async function installSkill(
  source: string,
  target: string,
  mode: SkillMode,
  force: boolean,
  warnings: string[],
): Promise<{ files: string[]; mode: SkillMode }> {
  if (!(await exists(join(source, "SKILL.md")))) {
    throw new SageError(`Skill source is missing SKILL.md: ${source}`, "E_SKILL_SOURCE", 1);
  }
  if (await exists(target)) {
    if (!force) {
      warnings.push(`Skill already exists at ${target}; kept it (use --force to replace).`);
      return { files: [], mode };
    }
    await removePath(target);
  }
  await ensureDir(join(target, ".."));
  if (mode === "symlink") {
    try {
      const { symlink } = await import("node:fs/promises");
      await symlink(source, target, process.platform === "win32" ? "junction" : "dir");
      return { files: ["SKILL.md"], mode: "symlink" };
    } catch {
      warnings.push("Directory symlink failed; copied the skill instead.");
    }
  }
  const files = await copyDirectory(source, target);
  return { files, mode: "copy" };
}

async function validateSkillSource(source: string): Promise<void> {
  const files = await readdir(source);
  if (!files.includes("SKILL.md")) {
    throw new SageError(`Skill source is missing SKILL.md: ${source}`, "E_SKILL_SOURCE", 1);
  }
}

export async function initSageKit(options: InitOptions = {}): Promise<InitResult> {
  const env = options.env ?? process.env;
  const home = options.home ?? env.HOME ?? env.USERPROFILE ?? ".";
  const projectRoot = resolve(options.projectRoot ?? process.cwd());
  const scope: InstallScope = options.scope ?? "project";
  const mode: SkillMode = options.mode ?? "copy";
  const warnings: string[] = [];
  const pkgRoot = packageRoot(import.meta.url);
  const source = skillSourceDir(pkgRoot);
  await validateSkillSource(source);

  let adapter: HostAdapter;
  if (options.host) {
    adapter = getAdapter(options.host);
  } else {
    const detections = await detectAdapters(env, home, projectRoot);
    const dsh = detections.find((item) => item.host === "dsh" && item.found);
    if (!dsh) {
      throw new SageError("No supported host detected; pass --host dsh (or --host fake in tests).", "E_NO_HOST", 2);
    }
    adapter = getAdapter("dsh");
  }
  const target = adapter.skillTarget(scope, projectRoot, env, home);
  if (!target) throw new SageError(`Host ${adapter.name} does not support skills`, "E_HOST_NO_SKILLS", 2);
  const paths = statePaths(projectRoot);
  const existing = await loadConfig(paths);

  if (existing && !options.force && (existing.host !== adapter.name || existing.scope !== scope)) {
    throw new SageError(
      `Already initialized for host=${existing.host} scope=${existing.scope}; use --force to reinitialize.`,
      "E_ALREADY_INITIALIZED",
      1,
    );
  }

  const installed = await installSkill(source, target, mode, Boolean(options.force), warnings);
  let instructions: InstructionsInstall | undefined = existing?.instructions;
  const instructionTarget = adapter.instructionsTarget(scope, projectRoot, env, home);
  const shouldWriteInstructions = options.instructions ?? (scope === "project");
  if (shouldWriteInstructions && instructionTarget) {
    await writeInstructions(instructionTarget.path, instructionTarget.blockId, instructionBlock(instructionTarget.blockId));
    instructions = { path: instructionTarget.path, blockId: instructionTarget.blockId };
  }

  const now = nowIso();
  const config: SageConfig = {
    schemaVersion: 1,
    packageVersion: await readPackageVersion(pkgRoot),
    host: adapter.name,
    scope,
    mode: "file",
    projectRoot,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
    skill: {
      path: target,
      mode: installed.mode,
      files: installed.files.length ? installed.files : existing?.skill.files ?? [],
      installedAt: now,
    },
    ...(instructions ? { instructions } : {}),
  };
  await ensureStateDirs(paths);
  await saveConfig(paths, config);
  const brief = await buildBrief(paths, undefined, 2048);
  await atomicWrite(paths.briefPath, `${brief.text}\n`);
  return {
    host: adapter.name,
    scope,
    projectRoot,
    configPath: paths.config,
    skillPath: target,
    skillMode: installed.mode,
    ...(instructions ? { instructionsPath: instructions.path } : {}),
    briefPath: paths.briefPath,
    created: !existing,
    warnings,
    files: installed.files,
  };
}

export interface UninstallResult {
  removed: string[];
  kept: string[];
  warnings: string[];
}

export async function uninstallSageKit(options: {
  projectRoot?: string;
  purge?: boolean;
  env?: NodeJS.ProcessEnv;
  home?: string;
} = {}): Promise<UninstallResult> {
  const env = options.env ?? process.env;
  const home = options.home ?? env.HOME ?? env.USERPROFILE ?? ".";
  const projectRoot = resolve(options.projectRoot ?? process.cwd());
  const paths: StatePaths = statePaths(projectRoot);
  const config = await loadConfig(paths);
  if (!config) throw new SageError("SAGE-Kit is not initialized here.", "E_NOT_INITIALIZED", 1);
  const adapter = getAdapter(config.host);
  const expected = adapter.skillTarget(config.scope, config.projectRoot, env, home);
  const removed: string[] = [];
  const kept: string[] = [];
  const warnings: string[] = [];
  if (expected && resolve(config.skill.path) === resolve(expected)) {
    if (await exists(expected)) {
      await removePath(expected);
      removed.push(expected);
    }
  } else {
    warnings.push(`Skill path did not match the host adapter; left it untouched: ${config.skill.path}`);
    kept.push(config.skill.path);
  }
  if (config.instructions) {
    if (await removeInstructions(config.instructions.path, config.instructions.blockId)) removed.push(config.instructions.path);
  }
  if (await exists(paths.briefPath)) {
    await removePath(paths.briefPath);
    removed.push(paths.briefPath);
  }
  await removePath(paths.config);
  removed.push(paths.config);
  if (options.purge) {
    await removePath(paths.stateDir);
    removed.push(paths.stateDir);
  } else {
    kept.push(paths.stateDir);
  }
  return { removed, kept, warnings };
}

export async function hashSkill(source: string): Promise<string> {
  return sha256(await readFile(join(source, "SKILL.md"), "utf8"));
}

export async function skillDirExists(path: string): Promise<boolean> {
  try {
    const info = await lstat(path);
    return info.isDirectory() || info.isSymbolicLink();
  } catch {
    return false;
  }
}

export function assertInside(root: string, target: string): void {
  if (!isPathInside(root, target)) throw new SageError(`Refusing to write outside ${root}: ${target}`, "E_PATH_OUTSIDE", 1);
}
