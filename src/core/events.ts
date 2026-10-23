import { nowIso, appendLine, redactRecord } from "./fs-utils.js";
import { eventsFile } from "./paths.js";
import type { StatePaths } from "./paths.js";

export interface SageEvent {
  ts: string;
  type: string;
  taskId?: string;
  data?: unknown;
}

export async function appendEvent(paths: StatePaths, type: string, data?: unknown, taskId?: string): Promise<void> {
  const event: SageEvent = {
    ts: nowIso(),
    type,
    ...(taskId ? { taskId } : {}),
    ...(data === undefined ? {} : { data: redactRecord(data) }),
  };
  await appendLine(eventsFile(paths), JSON.stringify(event));
}
