import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { exists, nowIso, readJsonFile, writeJsonAtomic } from "./fs-utils.js";
import { SageError } from "./errors.js";
import type { StatePaths } from "./paths.js";

export type HostName = string;
export type InstallScope = "project" | "global";
export type SkillMode = "copy" | "symlink";

export interface SkillInstall {
  path: string;
  mode: SkillMode;
  files: string[];
  installedAt: string;
  /**
   * True only when this installer created/replaced the skill directory. A
   * pre-existing user skill that was kept on init must survive uninstall.
   * Optional for configs written before ownership tracking.
   */
  owned?: boolean;
}

export interface InstructionsInstall {
  path: string;
  blockId: string;
  /** True when uninstall may remove a file created solely by this install. */
  created?: boolean;
}

export interface BriefInstall {
  path: string;
  /** True when uninstall may delete the brief because this installer created it. */
  created?: boolean;
}

export interface SageConfig {
  schemaVersion: 1;
  packageVersion: string;
  host: HostName;
  scope: InstallScope;
  mode: "file";
  projectRoot: string;
  createdAt: string;
  updatedAt: string;
  skill: SkillInstall;
  instructions?: InstructionsInstall;
  brief?: BriefInstall;
  /** False when `.sage-kit/` already existed and must not be purged wholesale. */
  stateDirCreated?: boolean;
}

export async function configExists(paths: StatePaths): Promise<boolean> {
  return exists(paths.config);
}

export async function loadConfig(paths: StatePaths): Promise<SageConfig | null> {
  if (!(await exists(paths.config))) return null;
  const raw = await readJsonFile<unknown>(paths.config);
  if (!raw || typeof raw !== "object") {
    throw new SageError("config.json must be an object", "E_BAD_CONFIG", 1);
  }
  const config = raw as Partial<SageConfig>;
  if (config.schemaVersion !== 1) throw new SageError("config.json schemaVersion must be 1", "E_BAD_CONFIG", 1);
  if (config.mode !== "file") throw new SageError("config.json mode must be 'file'", "E_BAD_CONFIG", 1);
  if (config.scope !== "project" && config.scope !== "global") {
    throw new SageError("config.json scope must be project or global", "E_BAD_CONFIG", 1);
  }
  if (typeof config.host !== "string" || !config.host) throw new SageError("config.json host is required", "E_BAD_CONFIG", 1);
  if (!config.skill || typeof config.skill.path !== "string" || !config.skill.path) {
    throw new SageError("config.json skill.path is required", "E_BAD_CONFIG", 1);
  }
  if (!Array.isArray(config.skill.files)) throw new SageError("config.json skill.files must be an array", "E_BAD_CONFIG", 1);
  return config as SageConfig;
}

export async function saveConfig(paths: StatePaths, config: SageConfig): Promise<void> {
  config.updatedAt = nowIso();
  await writeJsonAtomic(paths.config, config);
}

export async function readPackageVersion(pkgRoot: string): Promise<string> {
  const pkg = await readJsonFile<{ version?: string }>(join(pkgRoot, "package.json"));
  return typeof pkg.version === "string" && pkg.version ? pkg.version : "0.0.0";
}

export async function readPackageName(pkgRoot: string): Promise<string> {
  const pkg = await readJsonFile<{ name?: string }>(join(pkgRoot, "package.json"));
  return typeof pkg.name === "string" ? pkg.name : "sage-kit";
}

export async function readRawConfig(path: string): Promise<string> {
  return readFile(path, "utf8");
}
