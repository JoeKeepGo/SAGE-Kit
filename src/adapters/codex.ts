import { join } from "node:path";
import { exists } from "../core/fs-utils.js";
import type { HostAdapter, HostDetection, InstructionTarget } from "./types.js";
import type { HookEvent } from "../core/hooks.js";
import type { InstallScope } from "../core/config.js";

function codexHome(env: NodeJS.ProcessEnv = process.env, home = ""): string {
  return env.CODEX_HOME || join(home || env.HOME || env.USERPROFILE || ".", ".codex");
}

/**
 * Codex adapter.
 *
 * Codex reads AGENTS.md and supports project/global skill folders under
 * `.agents/skills`. P0 installs files only; no Codex hook wiring is claimed.
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
      notes: ["P0 installs Skill + AGENTS.md; native hooks are not claimed."],
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
