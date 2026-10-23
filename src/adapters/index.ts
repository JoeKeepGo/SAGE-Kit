import { SageError } from "../core/errors.js";
import { ClaudeAdapter } from "./claude.js";
import { CodexAdapter } from "./codex.js";
import { DshAdapter } from "./dsh.js";
import { FakeAdapter } from "./fake.js";
import type { HostAdapter, HostDetection } from "./types.js";

const ADAPTERS: HostAdapter[] = [new DshAdapter(), new CodexAdapter(), new ClaudeAdapter(), new FakeAdapter()];

export function listAdapters(): string[] {
  return ADAPTERS.map((adapter) => adapter.name);
}

export function getAdapter(name: string): HostAdapter {
  const adapter = ADAPTERS.find((item) => item.name === name);
  if (!adapter) {
    throw new SageError(`Unknown host adapter: ${name} (known: ${listAdapters().join(", ")})`, "E_BAD_HOST", 2);
  }
  return adapter;
}

export async function detectAdapters(
  env: NodeJS.ProcessEnv = process.env,
  home = "",
  projectRoot = process.cwd(),
): Promise<HostDetection[]> {
  const detections: HostDetection[] = [];
  for (const adapter of ADAPTERS) {
    detections.push(await adapter.detect(env, home, projectRoot));
  }
  return detections;
}

export type { HostAdapter, HostDetection } from "./types.js";
