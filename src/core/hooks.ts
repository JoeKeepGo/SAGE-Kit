import { buildBrief } from "./brief.js";
import { appendEvent } from "./events.js";
import { redactRecord, validateTaskId } from "./fs-utils.js";
import { SageError } from "./errors.js";
import { findActiveTask, listTasks, readTask } from "./tasks.js";
import type { StatePaths } from "./paths.js";

export const HOOK_EVENTS = ["session.start", "command.after", "stop"] as const;
export type HookEvent = (typeof HOOK_EVENTS)[number];

// Hard budget for one hook invocation. The CLI enforces it around the whole
// hook path (including waiting for stdin) and exits 124 with a valid
// HookOutput when exceeded; see docs/hooks-and-host-adapters.md §3.4.
export const HOOK_TIMEOUT_DEFAULT_MS = 2000;
export const HOOK_TIMEOUT_MIN_MS = 50;
export const HOOK_TIMEOUT_MAX_MS = 2000;
export const HOOK_TIMEOUT_EXIT_CODE = 124;

export interface HookInput {
  contractVersion?: 1;
  event?: string;
  cwd?: string;
  taskId?: string;
  session?: { id?: string };
  command?: {
    argv?: string[];
    exitCode?: number;
    durationMs?: number;
    stdoutTail?: string;
    stderrTail?: string;
  };
  [key: string]: unknown;
}

export interface HookOutput {
  contractVersion: "1";
  action: "inject_context" | "noop" | "warn" | "block";
  context?: string;
  message?: string;
  code?: string;
}

export interface HookOptions {
  event?: string;
  strict?: boolean;
}

export function parseHookTimeout(value: string | boolean | undefined): number {
  if (value === undefined || value === false) return HOOK_TIMEOUT_DEFAULT_MS;
  if (typeof value !== "string") {
    throw new SageError("--timeout requires a value", "E_USAGE", 2);
  }
  const timeoutMs = Number(value);
  if (
    !Number.isFinite(timeoutMs) ||
    !Number.isInteger(timeoutMs) ||
    timeoutMs < HOOK_TIMEOUT_MIN_MS ||
    timeoutMs > HOOK_TIMEOUT_MAX_MS
  ) {
    throw new SageError(
      `--timeout must be an integer between ${HOOK_TIMEOUT_MIN_MS} and ${HOOK_TIMEOUT_MAX_MS} ms`,
      "E_USAGE",
      2,
    );
  }
  return timeoutMs;
}

export function isHookEvent(value: string): value is HookEvent {
  return (HOOK_EVENTS as readonly string[]).includes(value);
}

export function parseHookInput(raw: string): HookInput {
  if (Buffer.byteLength(raw, "utf8") > 64 * 1024) {
    throw new SageError("Hook input exceeds 64 KB", "E_HOOK_INPUT_TOO_LARGE", 2);
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new SageError("Hook input must be valid JSON", "E_HOOK_BAD_JSON", 2);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new SageError("Hook input must be a JSON object", "E_HOOK_BAD_INPUT", 2);
  }
  return parsed as HookInput;
}

function resolveEvent(input: HookInput, options: HookOptions): HookEvent {
  const value = options.event ?? input.event;
  if (typeof value !== "string" || !isHookEvent(value)) {
    throw new SageError("Hook event must be session.start, command.after or stop", "E_HOOK_BAD_EVENT", 2);
  }
  if (options.event && input.event && options.event !== input.event) {
    throw new SageError("Hook --event does not match input.event", "E_HOOK_EVENT_MISMATCH", 2);
  }
  return value;
}

function taskForInput(paths: StatePaths, input: HookInput) {
  if (input.taskId !== undefined) {
    if (typeof input.taskId !== "string") throw new SageError("taskId must be a string", "E_HOOK_BAD_INPUT", 2);
    return readTask(paths, validateTaskId(input.taskId));
  }
  return listTasks(paths).then(findActiveTask);
}

export async function runHook(
  paths: StatePaths,
  input: HookInput,
  options: HookOptions = {},
): Promise<{ exitCode: number; output: HookOutput }> {
  const event = resolveEvent(input, options);
  const task = await taskForInput(paths, input);

  if (event === "session.start") {
    const brief = await buildBrief(paths, task?.id);
    await appendEvent(paths, "hook.session.start", { taskId: brief.taskId ?? null }, brief.taskId);
    if (!task) {
      return {
        exitCode: 0,
        output: {
          contractVersion: "1",
          action: "warn",
          context: brief.text,
          message: "No task found; create one with `sage-kit task create`.",
          code: "E_NO_TASK",
        },
      };
    }
    return { exitCode: 0, output: { contractVersion: "1", action: "inject_context", context: brief.text } };
  }

  if (event === "command.after") {
    const payload =
      input.payload && typeof input.payload === "object" ? (input.payload as Record<string, unknown>) : {};
    const command =
      input.command && typeof input.command === "object"
        ? input.command
        : payload.command && typeof payload.command === "object"
          ? payload.command
          : {};
    const commandRecord = command as Record<string, unknown>;
    const commandPayload = redactRecord({
      command: {
        argv: Array.isArray(commandRecord.argv) ? commandRecord.argv.slice(0, 50) : [],
        exitCode: typeof commandRecord.exitCode === "number" ? commandRecord.exitCode : null,
        durationMs: typeof commandRecord.durationMs === "number" ? commandRecord.durationMs : null,
        stdoutTail: typeof commandRecord.stdoutTail === "string" ? commandRecord.stdoutTail.slice(0, 500) : "",
        stderrTail: typeof commandRecord.stderrTail === "string" ? commandRecord.stderrTail.slice(0, 500) : "",
      },
    }) as Record<string, unknown>;
    await appendEvent(paths, "hook.command.after", commandPayload, task?.id);
    return { exitCode: 0, output: { contractVersion: "1", action: "noop" } };
  }

  // stop
  if (!task) {
    await appendEvent(paths, "hook.stop", { blocked: false, reason: "no_task" });
    return {
      exitCode: 0,
      output: { contractVersion: "1", action: "warn", message: "No task found.", code: "E_NO_TASK" },
    };
  }
  const missing: string[] = [];
  if (task.acceptance.length === 0) missing.push("acceptance scenarios");
  if (task.evidence.length === 0) missing.push("evidence");
  if (missing.length === 0) {
    await appendEvent(paths, "hook.stop", { blocked: false }, task.id);
    return { exitCode: 0, output: { contractVersion: "1", action: "noop" } };
  }
  const message = `Task ${task.id} is missing ${missing.join(" and ")}; record evidence before claiming done.`;
  await appendEvent(paths, "hook.stop", { blocked: Boolean(options.strict), reason: missing }, task.id);
  if (options.strict) {
    return { exitCode: 1, output: { contractVersion: "1", action: "block", message, code: "E_INCOMPLETE_TASK" } };
  }
  return { exitCode: 0, output: { contractVersion: "1", action: "warn", message, code: "E_INCOMPLETE_TASK" } };
}

export async function executeHookSafely(
  paths: StatePaths,
  raw: string,
  options: HookOptions = {},
): Promise<{ exitCode: number; output: HookOutput }> {
  try {
    const input = parseHookInput(raw);
    return await runHook(paths, input, options);
  } catch (error) {
    const sage = error instanceof SageError ? error : new SageError((error as Error).message);
    if (sage.exitCode === 2) {
      return {
        exitCode: 2,
        output: { contractVersion: "1", action: "warn", message: sage.message, code: sage.code },
      };
    }
    // Hooks fail open by default; --strict asks the host to stop on incomplete work.
    return {
      exitCode: options.strict ? 1 : 0,
      output: { contractVersion: "1", action: "warn", message: sage.message, code: sage.code },
    };
  }
}

export function sanitizeHookForLog(value: unknown): unknown {
  return redactRecord(value);
}
