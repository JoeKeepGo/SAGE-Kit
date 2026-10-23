import type { HostName, InstallScope } from "../core/config.js";
import type { HookEvent } from "../core/hooks.js";

export interface HostDetection {
  found: boolean;
  host: HostName;
  version?: string;
  evidence: string[];
  notes: string[];
}

export interface HostCapabilities {
  skills: boolean;
  hooks: HookEvent[];
  launch: boolean;
  mcp: boolean;
  subagents: boolean;
}

export interface InstructionTarget {
  path: string;
  blockId: string;
}

export interface HostAdapter {
  readonly name: HostName;
  readonly capabilities: HostCapabilities;
  detect(env?: NodeJS.ProcessEnv, home?: string, projectRoot?: string): Promise<HostDetection>;
  skillTarget(scope: InstallScope, projectRoot: string, env?: NodeJS.ProcessEnv, home?: string): string | null;
  instructionsTarget(
    scope: InstallScope,
    projectRoot: string,
    env?: NodeJS.ProcessEnv,
    home?: string,
  ): InstructionTarget | null;
  launchCommand(projectRoot: string): string[];
  mapHook(event: HookEvent): { mode: "external"; command: string[] } | null;
  diagnosticPaths(projectRoot: string, env?: NodeJS.ProcessEnv, home?: string): string[];
}
