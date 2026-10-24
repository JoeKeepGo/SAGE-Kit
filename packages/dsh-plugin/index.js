/**
 * SAGE-Kit DeepSeek Harness plugin.
 *
 * This is a host adapter, not a second source of truth. Every tool calls the
 * same `sage-kit` library and file-mode state as the CLI; the plugin never
 * writes its own task database and never starts the M2 control plane.
 */
import { createHash } from "node:crypto";
import { defineTool } from "@deepseek-ai/dsh-tools";
import { createUserMessage } from "@deepseek-ai/dsh-llm";
import Schema from "@deepseek-ai/schemastery";
import * as sage from "sage-kit";
import { clampBriefBytes, configuredRoot, discoverRoot } from "./lib.js";

export const name = "sage-kit-dsh";
export const inject = ["tools"];

export const Config = Schema.object({
  projectRoot: Schema.string().description(
    "Absolute SAGE-Kit project root. Omit to discover the nearest initialized .sage-kit from the DSH session working directory.",
  ),
  autoBrief: Schema.boolean().default(true).description(
    "Inject the current SAGE-Kit brief into the next model step when the project is initialized.",
  ),
  maxBriefBytes: Schema.number().default(2048).description(
    "Upper bound for an automatically injected brief (256..8192 bytes).",
  ),
});

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

function directoryFor(ctx, agent) {
  try {
    const service = typeof ctx.get === "function" ? ctx.get("workingDirectory") : ctx.workingDirectory;
    if (service && agent?.session && typeof service.get === "function") {
      const value = service.get(agent.session);
      if (typeof value === "string" && value.length > 0) return value;
    }
  } catch {
    // Fall through to the process directory; the plugin must never break a turn.
  }
  return process.cwd();
}

function pathsFor(ctx, exec, config) {
  const start = directoryFor(ctx, exec?.agent);
  const root = configuredRoot(config?.projectRoot) ?? discoverRoot(start);
  if (root === undefined) {
    throw new Error(
      "SAGE-Kit is not initialized for this project. Run `sage-kit init --host dsh --scope project` (or `npx sage-kit init ...`) first.",
    );
  }
  return sage.statePaths(root);
}

function json(value) {
  return JSON.stringify(value, null, 2);
}

function textOutput() {
  return {
    output: {
      schema: { type: "string" },
      render: (_args, value) => [{ type: "text", text: value }],
    },
  };
}

function taskParameters(extra = {}) {
  return {
    id: { type: "string", description: "Existing SAGE-Kit task id" },
    ...extra,
  };
}

/**
 * Register one tool against the DSH registry. `defineTool` validates arguments
 * against the declared schema before execute is called.
 */
function register(ctx, definition) {
  ctx.tools.register(defineTool(definition));
}

function registerTaskTools(ctx, config) {
  register(ctx, {
    name: "sage_task_create",
    description:
      "Create a SAGE-Kit file-mode task in the current project. Use this instead of editing .sage-kit/state/tasks manually.",
    parameters: {
      title: { type: "string", required: true, description: "Short task title" },
      description: { type: "string", description: "Optional task description" },
      acceptance: {
        type: "array",
        items: { type: "string" },
        description: "Acceptance criteria (zero or more strings)",
      },
    },
    ...textOutput(),
    async execute(args, exec) {
      const paths = pathsFor(ctx, exec, config);
      await sage.ensureStateDirs(paths);
      const task = await sage.createTask(paths, {
        title: args.title,
        ...(typeof args.description === "string" ? { description: args.description } : {}),
        acceptance: Array.isArray(args.acceptance) ? args.acceptance : [],
      });
      return json({ ok: true, task });
    },
  });

  register(ctx, {
    name: "sage_task_list",
    description:
      "List SAGE-Kit file-mode tasks in the current project. Returns JSON with tasks.",
    parameters: {
      status: {
        type: "string",
        enum: [...sage.TASK_STATUSES],
        description: "Optional status filter",
      },
    },
    ...textOutput(),
    async execute(args, exec) {
      const paths = pathsFor(ctx, exec, config);
      const all = await sage.listTasks(paths);
      const tasks =
        typeof args.status === "string" ? all.filter((task) => task.status === args.status) : all;
      return json({ ok: true, tasks });
    },
  });

  register(ctx, {
    name: "sage_task_show",
    description: "Show one SAGE-Kit file-mode task as JSON.",
    parameters: taskParameters(),
    ...textOutput(),
    async execute(args, exec) {
      const paths = pathsFor(ctx, exec, config);
      const task = await sage.readTask(paths, args.id);
      return json({ ok: true, task });
    },
  });

  register(ctx, {
    name: "sage_task_status",
    description:
      "Move a SAGE-Kit file-mode task through its lifecycle. Include at least one evidence string when marking done.",
    parameters: {
      id: { type: "string", required: true, description: "Existing SAGE-Kit task id" },
      status: {
        type: "string",
        required: true,
        enum: [...sage.TASK_STATUSES],
        description: "Target status",
      },
      evidence: {
        type: "array",
        items: { type: "string" },
        description: "Evidence notes for the transition (required for done)",
      },
      note: { type: "string", description: "Optional transition note" },
    },
    ...textOutput(),
    async execute(args, exec) {
      const paths = pathsFor(ctx, exec, config);
      const task = await sage.updateTaskStatus(paths, args.id, args.status, {
        evidence: Array.isArray(args.evidence) ? args.evidence : [],
        ...(typeof args.note === "string" ? { note: args.note } : {}),
        source: "dsh-plugin",
      });
      return json({ ok: true, task });
    },
  });

  register(ctx, {
    name: "sage_brief",
    description:
      "Read the current SAGE-Kit brief (active task, acceptance, evidence, optional latest feedback). Use it before resuming work.",
    parameters: {
      taskId: { type: "string", description: "Optional task id; defaults to the active task" },
      maxBytes: { type: "number", description: "Optional byte budget (default 2048)" },
    },
    ...textOutput(),
    async execute(args, exec) {
      const paths = pathsFor(ctx, exec, config);
      const brief = await sage.buildBrief(
        paths,
        typeof args.taskId === "string" ? args.taskId : undefined,
        clampBriefBytes(args.maxBytes),
      );
      return json(brief);
    },
  });
}

function registerBriefInjection(ctx, config) {
  if (config?.autoBrief === false) return;

  // Per-session cache avoids injecting the same brief on every step. A changed
  // task/updatedAt produces a new fingerprint and therefore a new context.
  const lastBrief = new WeakMap();

  ctx.on("agent/pre-step", async (payload, next) => {
    const decision = await next();
    try {
      if (decision.kind === "reject") return decision;
      const start = directoryFor(ctx, payload.agent);
      const root = configuredRoot(config?.projectRoot) ?? discoverRoot(start);
      if (root === undefined) return decision;
      const brief = await sage.buildBrief(sage.statePaths(root), undefined, clampBriefBytes(config?.maxBriefBytes));
      if (!brief.text.trim()) return decision;
      const fingerprint = sha256(brief.text);
      const session = payload.agent?.session;
      if (session && lastBrief.get(session) === fingerprint) return decision;

      const message = createUserMessage({
        content: [
          {
            type: "text",
            text: `<sage-kit-brief>\n${brief.text.trim()}\n</sage-kit-brief>`,
          },
        ],
        source: { kind: "sage-kit" },
      });
      if (session) lastBrief.set(session, fingerprint);
      const lastClaimed = decision.messages.findLastIndex((item) => payload.messages.includes(item));
      const index = lastClaimed >= 0 ? lastClaimed + 1 : decision.messages.length;
      return { ...decision, messages: decision.messages.toSpliced(index, 0, message) };
    } catch (error) {
      // Auto-brief is an enhancement; a bad project must not block the turn.
      try {
        ctx.logger?.warn?.(`sage-kit-dsh: skipped auto brief: ${String(error)}`);
      } catch {
        // Logging must not throw either.
      }
      return decision;
    }
  });
}

export function apply(ctx, config) {
  registerTaskTools(ctx, config);
  registerBriefInjection(ctx, config);
}
