import { join } from "node:path";
import { exists } from "../core/fs-utils.js";
import type { HostAdapter, HostDetection, InstructionTarget } from "./types.js";
import type { HookEvent } from "../core/hooks.js";
import type { InstallScope } from "../core/config.js";

/**
 * Claude Code adapter.
 *
 * Claude Code stores project skills under `.claude/skills` and reads
 * `CLAUDE.md` (and AGENTS.md) for instructions. P0 installs files only; hook
 * settings are not claimed until verified against a real host.
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
      notes: ["P0 installs Skill + CLAUDE.md; hook settings are M1."],
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
