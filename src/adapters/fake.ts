import { join } from "node:path";
import type { HostAdapter, HostDetection } from "./types.js";
import type { HookEvent } from "../core/hooks.js";
import type { InstallScope } from "../core/config.js";

export class FakeAdapter implements HostAdapter {
  readonly name = "fake";
  readonly capabilities = {
    skills: true,
    hooks: ["session.start", "command.after", "stop"] as HookEvent[],
    launch: true,
    mcp: false,
    subagents: false,
  };

  async detect(_env?: NodeJS.ProcessEnv, _home?: string, _projectRoot?: string): Promise<HostDetection> {
    return {
      found: true,
      host: this.name,
      version: "test",
      evidence: ["tests use the fake adapter"],
      notes: ["Not a real host; used by automated tests."],
    };
  }

  skillTarget(scope: InstallScope, projectRoot: string, _env?: NodeJS.ProcessEnv, home = ""): string {
    return scope === "project"
      ? join(projectRoot, ".fake", "skills", "sage-kit")
      : join(home || projectRoot, ".fake-global", "skills", "sage-kit");
  }

  instructionsTarget(scope: InstallScope, projectRoot: string, _env?: NodeJS.ProcessEnv, home = "") {
    return {
      path: scope === "project" ? join(projectRoot, "AGENTS.md") : join(home || projectRoot, ".fake-global", "AGENTS.md"),
      blockId: "sage-kit",
    };
  }

  launchCommand(): string[] {
    return ["fake-agent"];
  }

  mapHook(_event: HookEvent): { mode: "external"; command: string[] } | null {
    return null;
  }

  diagnosticPaths(projectRoot: string, _env?: NodeJS.ProcessEnv, home = ""): string[] {
    return [this.skillTarget("project", projectRoot), this.skillTarget("global", projectRoot, _env, home)];
  }
}
