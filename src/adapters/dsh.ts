import { join } from "node:path";
import { exists } from "../core/fs-utils.js";
import type { HostAdapter, HostDetection, InstructionTarget } from "./types.js";
import type { HookEvent } from "../core/hooks.js";
import type { InstallScope } from "../core/config.js";

export function dshHome(env: NodeJS.ProcessEnv = process.env, home = ""): string {
  return env.DSH_HOME || join(home || env.HOME || env.USERPROFILE || ".", ".dsh");
}

export class DshAdapter implements HostAdapter {
  readonly name = "dsh";
  readonly capabilities = {
    // Fixed DSH reads skill folders and AGENTS.md; it exposes no external hook
    // process to a third-party package, so hooks are handled by the generic CLI.
    skills: true,
    hooks: [] as HookEvent[],
    launch: true,
    mcp: true,
    subagents: true,
  };

  async detect(env: NodeJS.ProcessEnv = process.env, home = "", _projectRoot = process.cwd()): Promise<HostDetection> {
    const root = dshHome(env, home);
    const found = await exists(root);
    return {
      found,
      host: this.name,
      ...(env.DSH_VERSION ? { version: env.DSH_VERSION } : {}),
      evidence: [root],
      notes: found
        ? [
            "DSH_HOME detected; skill files go to <DSH_HOME>/skills and optional instructions to <DSH_HOME>/AGENTS.md.",
            "No external hook process was found in the fixed DSH version; hooks use `sage-kit hook` manually or the fake adapter for contract tests.",
          ]
        : ["DSH_HOME was not found; set DSH_HOME or install the DSH desktop app."],
    };
  }

  skillTarget(scope: InstallScope, projectRoot: string, env: NodeJS.ProcessEnv = process.env, home = ""): string {
    return scope === "project"
      ? join(projectRoot, ".dsh", "skills", "sage-kit")
      : join(dshHome(env, home), "skills", "sage-kit");
  }

  instructionsTarget(
    scope: InstallScope,
    projectRoot: string,
    env: NodeJS.ProcessEnv = process.env,
    home = "",
  ): InstructionTarget | null {
    return {
      path: scope === "project" ? join(projectRoot, "AGENTS.md") : join(dshHome(env, home), "AGENTS.md"),
      blockId: "sage-kit",
    };
  }

  launchCommand(): string[] {
    return ["dsh"];
  }

  mapHook(_event: HookEvent): { mode: "external"; command: string[] } | null {
    return null;
  }

  diagnosticPaths(projectRoot: string, env: NodeJS.ProcessEnv = process.env, home = ""): string[] {
    return [
      this.skillTarget("project", projectRoot, env, home),
      this.skillTarget("global", projectRoot, env, home),
      join(dshHome(env, home), "AGENTS.md"),
    ];
  }
}
