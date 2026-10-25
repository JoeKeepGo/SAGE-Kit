import { join, resolve } from "node:path";
import { exists } from "../core/fs-utils.js";
import { readPackageVersion, type InstallScope } from "../core/config.js";
import { packageRoot, skillSourceDir } from "../core/paths.js";
import type { HostAdapter, HostDetection, InstructionTarget } from "./types.js";
import type { HookEvent } from "../core/hooks.js";
import {
  hostBundlePaths,
  installHostBundle,
  uninstallHostBundle,
  type HostBundleInstallOptions,
  type HostBundleInstallResult,
  type HostBundlePaths,
  type HostBundleUninstallResult,
} from "./host-bundle.js";

function codexHome(env: NodeJS.ProcessEnv = process.env, home = ""): string {
  return env.CODEX_HOME || join(home || env.HOME || env.USERPROFILE || ".", ".codex");
}

const CODEX_PLUGIN_NAME = "sage-kit";
const CODEX_MARKETPLACE_NAME = "sage-kit";
const CODEX_PLUGIN_MANIFEST = join(".codex-plugin", "plugin.json");
const CODEX_MARKETPLACE_PATH = join(".agents", "plugins", "marketplace.json");
const CODEX_SKILL_RELATIVE_PATH = join("skills", "sage-kit");

function codexMarketplace(): Record<string, unknown> {
  return {
    name: CODEX_MARKETPLACE_NAME,
    interface: { displayName: "SAGE-Kit" },
    plugins: [
      {
        name: CODEX_PLUGIN_NAME,
        source: { source: "local", path: `./plugins/${CODEX_PLUGIN_NAME}` },
        policy: { installation: "AVAILABLE", authentication: "ON_INSTALL" },
        category: "Productivity",
      },
    ],
  };
}

/**
 * Codex adapter.
 *
 * Codex reads AGENTS.md and supports project/global skill folders under
 * `.agents/skills`. Separately, `packages/host-codex` holds the thin Codex
 * plugin template (manifest + SessionStart bridge); `installCodexHostBundle`
 * stages it plus a copy of the canonical Skill inside the project so the
 * Codex CLI can register the staged marketplace. SAGE-Kit never edits Codex
 * config files itself, and real-session hook activation is NOT_EXECUTED.
 */
export class CodexAdapter implements HostAdapter {
  readonly name = "codex";
  readonly capabilities = {
    skills: true,
    hooks: [] as HookEvent[],
    launch: true,
    mcp: false,
    subagents: false,
  };

  async detect(env: NodeJS.ProcessEnv = process.env, home = "", projectRoot = process.cwd()): Promise<HostDetection> {
    const evidence: string[] = [];
    if (await exists(codexHome(env, home))) evidence.push(codexHome(env, home));
    if (await exists(join(projectRoot, "AGENTS.md"))) evidence.push(join(projectRoot, "AGENTS.md"));
    if (await exists(join(projectRoot, ".agents", "skills"))) evidence.push(join(projectRoot, ".agents", "skills"));
    return {
      host: this.name,
      found: evidence.length > 0,
      evidence,
      notes: [
        "P0 init installs Skill + AGENTS.md only.",
        "Thin Codex plugin bundle (canonical Skill copy + SessionStart brief) is staged by installCodexHostBundle; the host still has to trust the hook, and real-session activation is NOT_EXECUTED.",
      ],
    };
  }

  skillTarget(scope: InstallScope, projectRoot: string, _env: NodeJS.ProcessEnv = process.env, home = ""): string {
    return scope === "project"
      ? join(projectRoot, ".agents", "skills", "sage-kit")
      : join(home || projectRoot, ".agents", "skills", "sage-kit");
  }

  instructionsTarget(
    scope: InstallScope,
    projectRoot: string,
    _env: NodeJS.ProcessEnv = process.env,
    home = "",
  ): InstructionTarget {
    return {
      path: scope === "project" ? join(projectRoot, "AGENTS.md") : join(home || projectRoot, ".codex", "AGENTS.md"),
      blockId: "sage-kit-codex",
    };
  }

  launchCommand(): string[] {
    return ["codex"];
  }

  mapHook(_event: HookEvent): { mode: "external"; command: string[] } | null {
    // The host plugin bundle owns the SessionStart hook. The core CLI does not
    // externalize a host hook process yet, so no mapping is claimed here.
    return null;
  }

  diagnosticPaths(projectRoot: string, env: NodeJS.ProcessEnv = process.env, home = ""): string[] {
    return [
      this.skillTarget("project", projectRoot, env, home),
      this.skillTarget("global", projectRoot, env, home),
      this.instructionsTarget("project", projectRoot, env, home).path,
    ];
  }
}

export function codexHostBundleRoot(projectRoot: string): string {
  return join(projectRoot, ".sage-kit", "hosts", "codex");
}

export function codexHostBundlePaths(projectRoot: string): HostBundlePaths {
  return hostBundlePaths({
    bundleRoot: codexHostBundleRoot(projectRoot),
    pluginName: CODEX_PLUGIN_NAME,
    skillRelativePath: CODEX_SKILL_RELATIVE_PATH,
    marketplacePath: CODEX_MARKETPLACE_PATH,
  });
}

/**
 * Stage the Codex host bundle. Registration stays with the Codex CLI:
 *
 *   codex plugin marketplace add <staged marketplace root>
 *   codex plugin add sage-kit@sage-kit
 *
 * This function only writes files it owns; it never edits `~/.codex/config.toml`.
 */
export async function installCodexHostBundle(options: HostBundleInstallOptions = {}): Promise<HostBundleInstallResult> {
  const projectRoot = resolve(options.projectRoot ?? process.cwd());
  const root = options.packageRoot ?? packageRoot(import.meta.url);
  return installHostBundle({
    host: "codex",
    bundleRoot: codexHostBundleRoot(projectRoot),
    pluginName: CODEX_PLUGIN_NAME,
    pluginSource: join(root, "packages", "host-codex"),
    pluginManifestPath: CODEX_PLUGIN_MANIFEST,
    marketplacePath: CODEX_MARKETPLACE_PATH,
    marketplace: codexMarketplace(),
    skillSource: skillSourceDir(root),
    skillRelativePath: CODEX_SKILL_RELATIVE_PATH,
    version: options.version ?? (await readPackageVersion(root)),
    force: options.force,
  });
}

/** Remove only the staged bundle; Codex config/plugin cache is left to the host CLI. */
export async function uninstallCodexHostBundle(options: { projectRoot?: string } = {}): Promise<HostBundleUninstallResult> {
  const projectRoot = resolve(options.projectRoot ?? process.cwd());
  return uninstallHostBundle({ bundleRoot: codexHostBundleRoot(projectRoot), host: "codex" });
}
