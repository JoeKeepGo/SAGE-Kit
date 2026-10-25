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

const CLAUDE_PLUGIN_NAME = "sage-kit";
const CLAUDE_MARKETPLACE_NAME = "sage-kit";
const CLAUDE_PLUGIN_MANIFEST = join(".claude-plugin", "plugin.json");
const CLAUDE_MARKETPLACE_PATH = join(".claude-plugin", "marketplace.json");
const CLAUDE_SKILL_RELATIVE_PATH = join("skills", "sage-kit");

function claudeMarketplace(): Record<string, unknown> {
  return {
    $schema: "https://anthropic.com/claude-code/marketplace.schema.json",
    name: CLAUDE_MARKETPLACE_NAME,
    description: "SAGE-Kit thin host plugin: canonical Skill plus a bounded session brief.",
    owner: { name: "SAGE-Kit" },
    plugins: [
      {
        name: CLAUDE_PLUGIN_NAME,
        description: "Task and evidence discipline for Claude Code sessions.",
        source: `./plugins/${CLAUDE_PLUGIN_NAME}`,
        category: "productivity",
      },
    ],
  };
}

/**
 * Claude Code adapter.
 *
 * Claude Code stores project skills under `.claude/skills` and reads
 * `CLAUDE.md` (and AGENTS.md) for instructions. `packages/host-claude` holds the
 * thin Claude Code plugin template (manifest + SessionStart bridge);
 * `installClaudeHostBundle` stages it plus a copy of the canonical Skill so a
 * Claude Code marketplace can install it. The Claude Code CLI was not present
 * on the verification machine, so real plugin install/activation is
 * NOT_EXECUTED; only the file/JSON layer is verified here.
 */
export class ClaudeAdapter implements HostAdapter {
  readonly name = "claude";
  readonly capabilities = {
    skills: true,
    hooks: [] as HookEvent[],
    launch: true,
    mcp: false,
    subagents: false,
  };

  async detect(env: NodeJS.ProcessEnv = process.env, home = "", projectRoot = process.cwd()): Promise<HostDetection> {
    const evidence: string[] = [];
    if (env.CLAUDECODE || env.CLAUDE_CODE) evidence.push("CLAUDECODE env");
    if (await exists(join(home || env.HOME || env.USERPROFILE || ".", ".claude"))) {
      evidence.push(join(home || env.HOME || env.USERPROFILE || ".", ".claude"));
    }
    if (await exists(join(projectRoot, ".claude"))) evidence.push(join(projectRoot, ".claude"));
    if (await exists(join(projectRoot, "CLAUDE.md"))) evidence.push(join(projectRoot, "CLAUDE.md"));
    return {
      host: this.name,
      found: evidence.length > 0,
      evidence,
      notes: [
        "P0 init installs Skill + CLAUDE.md; hook settings are M1.",
        "Thin Claude Code plugin bundle (canonical Skill copy + SessionStart brief) is staged by installClaudeHostBundle; real Claude Code install and activation are NOT_EXECUTED.",
      ],
    };
  }

  skillTarget(scope: InstallScope, projectRoot: string, _env: NodeJS.ProcessEnv = process.env, home = ""): string {
    return scope === "project"
      ? join(projectRoot, ".claude", "skills", "sage-kit")
      : join(home || projectRoot, ".claude", "skills", "sage-kit");
  }

  instructionsTarget(
    scope: InstallScope,
    projectRoot: string,
    _env: NodeJS.ProcessEnv = process.env,
    home = "",
  ): InstructionTarget {
    return {
      path: scope === "project" ? join(projectRoot, "CLAUDE.md") : join(home || projectRoot, ".claude", "CLAUDE.md"),
      blockId: "sage-kit-claude",
    };
  }

  launchCommand(): string[] {
    return ["claude"];
  }

  mapHook(_event: HookEvent): { mode: "external"; command: string[] } | null {
    // The host plugin bundle owns the SessionStart hook; see codex.ts.
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

export function claudeHostBundleRoot(projectRoot: string): string {
  return join(projectRoot, ".sage-kit", "hosts", "claude");
}

export function claudeHostBundlePaths(projectRoot: string): HostBundlePaths {
  return hostBundlePaths({
    bundleRoot: claudeHostBundleRoot(projectRoot),
    pluginName: CLAUDE_PLUGIN_NAME,
    skillRelativePath: CLAUDE_SKILL_RELATIVE_PATH,
    marketplacePath: CLAUDE_MARKETPLACE_PATH,
  });
}

/**
 * Stage the Claude Code host bundle. Registration stays with Claude Code:
 *
 *   /plugin marketplace add <staged marketplace root>
 *   /plugin install sage-kit@sage-kit
 *
 * Only the file/JSON layer is verified; the Claude Code CLI was not available.
 */
export async function installClaudeHostBundle(options: HostBundleInstallOptions = {}): Promise<HostBundleInstallResult> {
  const projectRoot = resolve(options.projectRoot ?? process.cwd());
  const root = options.packageRoot ?? packageRoot(import.meta.url);
  return installHostBundle({
    host: "claude",
    bundleRoot: claudeHostBundleRoot(projectRoot),
    pluginName: CLAUDE_PLUGIN_NAME,
    pluginSource: join(root, "packages", "host-claude"),
    pluginManifestPath: CLAUDE_PLUGIN_MANIFEST,
    marketplacePath: CLAUDE_MARKETPLACE_PATH,
    marketplace: claudeMarketplace(),
    skillSource: skillSourceDir(root),
    skillRelativePath: CLAUDE_SKILL_RELATIVE_PATH,
    version: options.version ?? (await readPackageVersion(root)),
    force: options.force,
  });
}

/** Remove only the staged bundle; Claude Code marketplace state is left to the host. */
export async function uninstallClaudeHostBundle(
  options: { projectRoot?: string } = {},
): Promise<HostBundleUninstallResult> {
  const projectRoot = resolve(options.projectRoot ?? process.cwd());
  return uninstallHostBundle({ bundleRoot: claudeHostBundleRoot(projectRoot), host: "claude" });
}
