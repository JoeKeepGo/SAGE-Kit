import { lstat, readdir, readFile, rmdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
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
import { ensureStateDirs, findProjectRoot, packageRoot, skillSourceDir, statePaths, writeProjectRegistry, type StatePaths } from "./paths.js";
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
    "- At the start of work, use the host's SAGE-Kit brief tool if one is exposed (DSH plugin: `sage_brief`); otherwise run `npx sage-kit brief` (or a locally installed `sage-kit brief`) and follow it.",
    "- Create or update a task with the host's SAGE-Kit task tools if available (DSH plugin: `sage_task_*`); otherwise use `npx sage-kit task ...`; keep work inside its scope.",
    "- Record exact evidence before claiming done with the host task tool if available, otherwise: `npx sage-kit task status <id> done --evidence \"...\"`.",
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

async function actualSkillMode(target: string): Promise<SkillMode> {
  try {
    const info = await lstat(target);
    return info.isSymbolicLink() ? "symlink" : "copy";
  } catch {
    return "copy";
  }
}

async function installSkill(
  source: string,
  target: string,
  mode: SkillMode,
  force: boolean,
  warnings: string[],
): Promise<{ files: string[]; mode: SkillMode; owned: boolean }> {
  if (!(await exists(join(source, "SKILL.md")))) {
    throw new SageError(`Skill source is missing SKILL.md: ${source}`, "E_SKILL_SOURCE", 1);
  }
  if (await exists(target)) {
    if (!force) {
      if (!(await exists(join(target, "SKILL.md")))) {
        throw new SageError(
          `Existing skill directory is missing SKILL.md: ${target}; move the preserved directory aside before running init again.`,
          "E_SKILL_INCOMPLETE",
          1,
        );
      }
      warnings.push(`Skill already exists at ${target}; kept it (use --force to replace).`);
      // Record the mode the installed copy actually has, not the requested one.
      return { files: [], mode: await actualSkillMode(target), owned: false };
    }
    await removePath(target);
  }
  await ensureDir(join(target, ".."));
  if (mode === "symlink") {
    try {
      const { symlink } = await import("node:fs/promises");
      await symlink(source, target, process.platform === "win32" ? "junction" : "dir");
      return { files: ["SKILL.md"], mode: "symlink", owned: true };
    } catch {
      warnings.push("Directory symlink failed; copied the skill instead.");
    }
  }
  const files = await copyDirectory(source, target);
  return { files, mode: "copy", owned: true };
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
  const requestedRoot = resolve(options.projectRoot ?? process.cwd());
  // `init` from a linked worktree must initialize the same project root that
  // task/brief commands resolve, not a second state dir next to the linked
  // checkout. An explicit --project-root is never rewritten; without one, a
  // linked worktree with no trusted main path is rejected instead of silently
  // creating a second state root.
  const projectRoot = options.projectRoot ? requestedRoot : await findProjectRoot(requestedRoot, { strict: true });
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
  const stateDirExisted = await exists(paths.stateDir);
  const briefExisted = await exists(paths.briefPath);
  const existing = await loadConfig(paths);

  if (existing && !options.force && (existing.host !== adapter.name || existing.scope !== scope)) {
    throw new SageError(
      `Already initialized for host=${existing.host} scope=${existing.scope}; use --force to reinitialize.`,
      "E_ALREADY_INITIALIZED",
      1,
    );
  }

  const installed = await installSkill(source, target, mode, Boolean(options.force), warnings);
  const previousSkillOwned =
    existing?.skill.path === target ? (existing.skill.owned ?? existing.skill.files.length > 0) : false;
  // A normal re-init keeps an existing skill (`installed.files` is empty). Do
  // not downgrade ownership recorded by the first install, or uninstall would
  // leave a skill that SAGE-Kit itself created. `--force` replaces it and the
  // installer owns the new copy again.
  const skillOwned = installed.owned || (installed.files.length === 0 && previousSkillOwned);
  let instructions: InstructionsInstall | undefined = existing?.instructions;
  const instructionTarget = adapter.instructionsTarget(scope, projectRoot, env, home);
  const shouldWriteInstructions = options.instructions ?? (scope === "project");
  if (shouldWriteInstructions && instructionTarget) {
    const instructionExisted = await exists(instructionTarget.path);
    const created =
      existing?.instructions?.path === instructionTarget.path
        ? existing.instructions.created ?? !instructionExisted
        : !instructionExisted;
    await writeInstructions(instructionTarget.path, instructionTarget.blockId, instructionBlock(instructionTarget.blockId));
    instructions = { path: instructionTarget.path, blockId: instructionTarget.blockId, created };
  }

  const now = nowIso();
  const briefCreated =
    existing?.brief?.path === paths.briefPath ? existing.brief.created ?? !briefExisted : !briefExisted;
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
      owned: skillOwned,
    },
    ...(instructions ? { instructions } : {}),
    brief: { path: paths.briefPath, created: briefCreated },
    stateDirCreated: existing?.stateDirCreated ?? !stateDirExisted,
  };
  await ensureStateDirs(paths);
  await saveConfig(paths, config);
  await writeProjectRegistry(projectRoot);
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

/**
 * Remove only the skill files recorded by the install, then prune empty
 * directories. A user file added inside the installed skill directory must
 * survive an ordinary uninstall; recursively deleting the whole skill root
 * (the old behavior) silently lost that file.
 */
async function removeOwnedSkillTree(
  skillRoot: string,
  files: string[],
  removed: string[],
  kept: string[],
  warnings: string[],
): Promise<void> {
  const rootInfo = await lstat(skillRoot).catch(() => null);
  if (!rootInfo) return;
  if (rootInfo.isSymbolicLink()) {
    // A symlink-mode install has no user content beneath the link; removing the
    // link itself must never follow into the canonical source directory.
    await removePath(skillRoot);
    removed.push(skillRoot);
    return;
  }
  if (files.length === 0) {
    warnings.push(`Skill ownership has no recorded files; left it untouched: ${skillRoot}`);
    kept.push(skillRoot);
    return;
  }
  const base = resolve(skillRoot);
  const removedDirs = new Set<string>();
  for (const file of [...files].reverse()) {
    const target = resolve(base, file);
    if (!isPathInside(base, target)) {
      warnings.push(`Refusing to remove a recorded skill path outside the skill root: ${file}`);
      continue;
    }
    const info = await lstat(target).catch(() => null);
    if (!info) continue;
    if (info.isDirectory()) {
      warnings.push(`Skipped a directory recorded as a skill file: ${file}`);
      continue;
    }
    await removePath(target);
    removed.push(target);
    removedDirs.add(dirname(target));
  }
  for (const dir of [...removedDirs].sort((left, right) => right.length - left.length)) {
    let current = resolve(dir);
    while (current !== base && isPathInside(base, current)) {
      const entries = await readdir(current).catch(() => null);
      if (!entries || entries.length > 0) break;
      await rmdir(current);
      current = dirname(current);
    }
  }
  if (await exists(base)) {
    const entries = await readdir(base).catch(() => null);
    if (entries && entries.length === 0) {
      await rmdir(base);
      removed.push(base);
    } else {
      kept.push(base);
      warnings.push(`Kept user files inside the installed skill directory: ${base}`);
    }
  }
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
  // Legacy configs predate ownership metadata; an empty files list means init
  // kept a user-installed skill, so do not delete it on uninstall.
  const skillOwned = config.skill.owned ?? (config.skill.files.length > 0);
  if (expected && resolve(config.skill.path) === resolve(expected)) {
    if (await exists(expected)) {
      if (skillOwned) {
        await removeOwnedSkillTree(expected, config.skill.files, removed, kept, warnings);
      } else {
        warnings.push(`Skill was not created by this install; left it untouched: ${config.skill.path}`);
        kept.push(config.skill.path);
      }
    }
  } else {
    warnings.push(`Skill path did not match the host adapter; left it untouched: ${config.skill.path}`);
    kept.push(config.skill.path);
  }
  if (config.instructions) {
    const hadInstructions = await exists(config.instructions.path);
    const removedBlock = await removeInstructions(config.instructions.path, config.instructions.blockId);
    if (removedBlock) {
      const remaining = (await readText(config.instructions.path).catch(() => "")).trim();
      if (hadInstructions && config.instructions.created === true && remaining.length === 0) {
        await removePath(config.instructions.path);
        removed.push(config.instructions.path);
      }
    }
  }
  if (config.brief?.path === paths.briefPath && (await exists(paths.briefPath))) {
    if (config.brief.created === true) {
      await removePath(paths.briefPath);
      removed.push(paths.briefPath);
    } else {
      warnings.push(`Brief existed before this install; left it untouched: ${paths.briefPath}`);
      kept.push(paths.briefPath);
    }
  }
  await removePath(paths.config);
  removed.push(paths.config);
  if (options.purge) {
    // A legacy config without stateDirCreated cannot prove that this install
    // created the directory. Preserve it rather than risk deleting user state.
    if (config.stateDirCreated !== true) {
      warnings.push(
        config.stateDirCreated === false
          ? `State directory existed before this install; left it untouched: ${paths.stateDir}`
          : `State directory ownership is unknown (legacy config); left it untouched: ${paths.stateDir}`,
      );
      kept.push(paths.stateDir);
    } else {
      await removePath(paths.stateDir);
      removed.push(paths.stateDir);
    }
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
