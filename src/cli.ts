#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { getAdapter, listAdapters } from "./adapters/index.js";
import { buildBrief } from "./core/brief.js";
import { readPackageVersion } from "./core/config.js";
import { detectHosts, formatDoctor, runDoctor } from "./core/doctor.js";
import { SageError, toSageError } from "./core/errors.js";
import { executeHookSafely, HOOK_TIMEOUT_EXIT_CODE, parseHookTimeout, type HookOptions, type HookOutput } from "./core/hooks.js";
import { initSageKit, uninstallSageKit } from "./core/install.js";
import { entryPackageRoot, findProjectRoot, homeDirectory, statePaths } from "./core/paths.js";
import {
  createTask,
  isTaskStatus,
  listTasks,
  readTask,
  updateTaskStatus,
  type TaskStatus,
} from "./core/tasks.js";
import { createWorktree, listWorktrees, removeWorktree } from "./core/worktree.js";
import { startRun } from "./core/runs.js";

interface Parsed {
  positional: string[];
  flags: Record<string, string | boolean>;
  multi: Record<string, string[]>;
}

interface ParseSpec {
  boolean?: string[];
  value?: string[];
  multi?: string[];
}

function parseArgs(argv: string[], spec: ParseSpec): Parsed {
  const result: Parsed = { positional: [], flags: {}, multi: {} };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index] as string;
    if (arg === "-h" || arg === "--help") {
      result.flags.help = true;
      continue;
    }
    if (!arg.startsWith("--")) {
      result.positional.push(arg);
      continue;
    }
    const body = arg.slice(2);
    const equals = body.indexOf("=");
    const name = equals >= 0 ? body.slice(0, equals) : body;
    const inline = equals >= 0 ? body.slice(equals + 1) : undefined;
    if (spec.boolean?.includes(name)) {
      if (inline !== undefined) throw new SageError(`--${name} does not take a value`, "E_USAGE", 2);
      result.flags[name] = true;
      continue;
    }
    if (spec.value?.includes(name)) {
      const value = inline ?? argv[index + 1];
      if (value === undefined || value.startsWith("--")) throw new SageError(`--${name} requires a value`, "E_USAGE", 2);
      result.flags[name] = value;
      if (inline === undefined) index += 1;
      continue;
    }
    if (spec.multi?.includes(name)) {
      const value = inline ?? argv[index + 1];
      if (value === undefined) throw new SageError(`--${name} requires a value`, "E_USAGE", 2);
      (result.multi[name] ??= []).push(value);
      if (inline === undefined) index += 1;
      continue;
    }
    throw new SageError(`Unknown option: --${name}`, "E_USAGE", 2);
  }
  return result;
}

function json(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

function output(value: unknown, asJson: boolean): void {
  if (asJson) json(value);
  else if (typeof value === "string") process.stdout.write(`${value}\n`);
}

async function projectRootFrom(cwd: string): Promise<string> {
  return findProjectRoot(cwd);
}

function requireString(flags: Record<string, string | boolean>, name: string): string {
  const value = flags[name];
  if (typeof value !== "string") throw new SageError(`--${name} is required`, "E_USAGE", 2);
  return value;
}

function boolFlag(flags: Record<string, string | boolean>, name: string): boolean {
  return flags[name] === true;
}

function printHelp(version: string): void {
  process.stdout.write(`sage-kit ${version}

Usage:
  sage-kit init --host dsh [--scope project|global] [--mode copy|symlink] [--force] [--no-instructions]
  sage-kit doctor [--json]
  sage-kit detect [--json]
  sage-kit task create --title <text> [--description <text>] [--acceptance <text>]... [--id <id>]
  sage-kit task list [--status <status>] [--json]
  sage-kit task show <id> [--json]
  sage-kit task status <id> <status> [--evidence <text>]... [--note <text>] [--json]
  sage-kit brief [--task <id>] [--max-bytes <n>] [--json]
  sage-kit worktree create --task <id>
  sage-kit worktree remove --task <id> [--force]
  sage-kit worktree list [--json]
  sage-kit run --task <id> [--no-worktree] -- <command> [args...]
  sage-kit control serve [--port <n>] [--recover] [--json]
  sage-kit control status [--json]
  sage-kit control recover [--json]
  sage-kit feedback sync --source local|github|gitea [--repo <owner/name>] [--file <path>] [--json]
  sage-kit feedback list [--json]
  sage-kit feedback show <id> [--json]
  sage-kit rsi create --file <proposal.json>
  sage-kit rsi list [--status <status>] [--json]
  sage-kit rsi run-once --test-command <json-array> [--json]
  sage-kit rsi request-approval <proposal-id> [--json]
  sage-kit rsi rollback-point --base-commit <sha> --base-version <ver> [--json]
  sage-kit rsi approve <proposal-id> --token <t> --decided-by <name> --rollback-point <id> [--json]
  sage-kit rsi reject <proposal-id> --decided-by <name> --reason <text> [--json]
  sage-kit hook [--event session.start|command.after|stop] [--strict] [--timeout <ms>]
  sage-kit uninstall [--purge]
  sage-kit version

Commands run in the nearest git project root. Hooks read one JSON object from stdin.
`);
}

async function packageVersion(): Promise<string> {
  try {
    return await readPackageVersion(entryPackageRoot(import.meta.url));
  } catch {
    return "0.0.0";
  }
}

async function readStdin(): Promise<string> {
  if (process.stdin.isTTY) return "";
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  return Buffer.concat(chunks).toString("utf8");
}

const NODE_MAJOR = Number(process.versions.node.split(".")[0] ?? 0);
if (NODE_MAJOR < 22) {
  process.stderr.write(`sage-kit requires Node.js >=22 (current ${process.versions.node}).\n`);
  process.exit(1);
}

async function main(argv: string[]): Promise<number> {
  const command = argv[0];
  if (!command || command === "help" || command === "--help" || command === "-h") {
    printHelp(await packageVersion());
    return 0;
  }
  if (command === "version" || command === "--version") {
    process.stdout.write(`${await packageVersion()}\n`);
    return 0;
  }

  const cwd = process.cwd();
  if (command === "init") {
    const parsed = parseArgs(argv.slice(1), {
      value: ["host", "scope", "mode", "project-root"],
      boolean: ["force", "instructions", "no-instructions"],
      multi: [],
    });
    let instructions: boolean | undefined;
    if (parsed.flags["no-instructions"] === true) instructions = false;
    if (parsed.flags.instructions === true) instructions = true;
    const scope = parsed.flags.scope;
    if (scope !== undefined && scope !== "project" && scope !== "global") {
      throw new SageError("--scope must be project or global", "E_USAGE", 2);
    }
    const mode = parsed.flags.mode;
    if (mode !== undefined && mode !== "copy" && mode !== "symlink") {
      throw new SageError("--mode must be copy or symlink", "E_USAGE", 2);
    }
    const projectRoot = await projectRootFrom(
      typeof parsed.flags["project-root"] === "string" ? parsed.flags["project-root"] : cwd,
    );
    const result = await initSageKit({
      ...(typeof parsed.flags.host === "string" ? { host: parsed.flags.host } : {}),
      ...(scope ? { scope } : {}),
      ...(mode ? { mode } : {}),
      force: boolFlag(parsed.flags, "force"),
      ...(instructions === undefined ? {} : { instructions }),
      projectRoot,
    });
    const lines = [
      `Initialized SAGE-Kit (${result.host}, ${result.scope}).`,
      `config: ${result.configPath}`,
      `skill:  ${result.skillPath}`,
      ...(result.instructionsPath ? [`instructions: ${result.instructionsPath}`] : ["instructions: skipped"]),
      ...result.warnings.map((warning) => `warning: ${warning}`),
    ];
    output(lines.join("\n"), false);
    return 0;
  }

  if (command === "detect") {
    const parsed = parseArgs(argv.slice(1), { boolean: ["json"] });
    const root = await projectRootFrom(cwd);
    const result = await detectHosts(root);
    if (boolFlag(parsed.flags, "json")) {
      json({ ok: true, projectRoot: root, ...result, adapters: listAdapters() });
    } else {
      const lines = [`project: ${root}`];
      for (const detection of result.detections) {
        lines.push(`${detection.found ? "[found]" : "[missing]"} ${detection.host}: ${detection.evidence.join(", ")}`);
        for (const note of detection.notes) lines.push(`  note: ${note}`);
      }
      output(lines.join("\n"), false);
    }
    return 0;
  }

  if (command === "doctor") {
    const parsed = parseArgs(argv.slice(1), { boolean: ["json"] });
    const root = await projectRootFrom(cwd);
    const result = await runDoctor(root, process.env, homeDirectory(process.env));
    if (boolFlag(parsed.flags, "json")) json(result);
    else process.stdout.write(`${formatDoctor(result)}\n`);
    return result.ok ? 0 : 1;
  }

  if (command === "brief") {
    const parsed = parseArgs(argv.slice(1), { value: ["task", "max-bytes"], boolean: ["json"] });
    const root = await projectRootFrom(cwd);
    const paths = statePaths(root);
    const maxBytes = parsed.flags["max-bytes"] ? Number(parsed.flags["max-bytes"]) : 2048;
    if (!Number.isFinite(maxBytes) || maxBytes < 128) {
      throw new SageError("--max-bytes must be >=128", "E_USAGE", 2);
    }
    const brief = await buildBrief(paths, typeof parsed.flags.task === "string" ? parsed.flags.task : undefined, maxBytes);
    if (boolFlag(parsed.flags, "json")) json(brief);
    else process.stdout.write(`${brief.text}\n`);
    return 0;
  }

  if (command === "run") {
    const separator = argv.indexOf("--");
    if (separator < 2) throw new SageError("usage: sage-kit run --task <id> -- <command> [args...]", "E_USAGE", 2);
    const parsed = parseArgs(argv.slice(1, separator), { value: ["task"], boolean: ["no-worktree"], multi: [] });
    const taskId = requireString(parsed.flags, "task");
    const run = await startRun(statePaths(await projectRootFrom(cwd)), taskId, argv.slice(separator + 1), {
      worktree: parsed.flags["no-worktree"] !== true,
    });
    json({ ok: run.status === "exited", run });
    return run.status === "exited" ? 0 : 1;
  }

  if (command === "worktree") {
    const sub = argv[1];
    const root = await projectRootFrom(cwd);
    const paths = statePaths(root);
    if (sub === "create") {
      const parsed = parseArgs(argv.slice(2), { value: ["task"], boolean: ["json"] });
      const task = await createWorktree(paths, requireString(parsed.flags, "task"));
      if (boolFlag(parsed.flags, "json")) json({ ok: true, task });
      else process.stdout.write(`${task.id}: ${task.worktree} (${task.branch})\n`);
      return 0;
    }
    if (sub === "remove") {
      const parsed = parseArgs(argv.slice(2), { value: ["task"], boolean: ["force", "json"] });
      const task = await removeWorktree(paths, requireString(parsed.flags, "task"), boolFlag(parsed.flags, "force"));
      if (boolFlag(parsed.flags, "json")) json({ ok: true, task });
      else process.stdout.write(`${task.id}: worktree removed\n`);
      return 0;
    }
    if (sub === "list") {
      const parsed = parseArgs(argv.slice(2), { boolean: ["json"] });
      const worktrees = await listWorktrees(paths);
      if (boolFlag(parsed.flags, "json")) json({ ok: true, worktrees });
      else process.stdout.write(`${worktrees.map((item) => `${item.path} ${item.branch ?? ""}`).join("\n")}\n`);
      return 0;
    }
    throw new SageError("worktree requires create|remove|list", "E_USAGE", 2);
  }

  if (command === "hook") {
    const parsed = parseArgs(argv.slice(1), {
      value: ["event", "timeout"],
      boolean: ["strict"],
      multi: [],
    });
    const timeoutMs = parseHookTimeout(parsed.flags.timeout);
    const options: HookOptions = {
      ...(typeof parsed.flags.event === "string" ? { event: parsed.flags.event } : {}),
      strict: boolFlag(parsed.flags, "strict"),
    };
    // Hard budget for the whole hook path (stdin wait + local processing). On
    // expiry emit a valid HookOutput and exit 124; hosts ignore/record it.
    const timeoutOutput: HookOutput = {
      contractVersion: "1",
      action: "warn",
      message: `Hook timed out after ${timeoutMs}ms`,
      code: "E_HOOK_TIMEOUT",
    };
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      process.stdout.write(`${JSON.stringify(timeoutOutput)}\n`, () => process.exit(HOOK_TIMEOUT_EXIT_CODE));
    }, timeoutMs);
    try {
      const raw = await readStdin();
      let hookCwd = cwd;
      try {
        const parsedInput = JSON.parse(raw) as { cwd?: unknown };
        if (typeof parsedInput.cwd === "string" && parsedInput.cwd.length > 0) hookCwd = parsedInput.cwd;
      } catch {
        // Invalid JSON is handled by the hook runner; retain the process cwd.
      }
      const root = await projectRootFrom(hookCwd);
      const result = await executeHookSafely(statePaths(root), raw, options);
      if (settled) return HOOK_TIMEOUT_EXIT_CODE;
      settled = true;
      clearTimeout(timer);
      json(result.output);
      return result.exitCode;
    } finally {
      clearTimeout(timer);
    }
  }

  if (command === "uninstall") {
    const parsed = parseArgs(argv.slice(1), { boolean: ["purge"], value: ["project-root"] });
    const root = await projectRootFrom(
      typeof parsed.flags["project-root"] === "string" ? parsed.flags["project-root"] : cwd,
    );
    const result = await uninstallSageKit({ projectRoot: root, purge: boolFlag(parsed.flags, "purge") });
    process.stdout.write(
      [
        "Uninstalled SAGE-Kit.",
        ...result.removed.map((path) => `removed: ${path}`),
        ...result.kept.map((path) => `kept: ${path}`),
        ...result.warnings.map((warning) => `warning: ${warning}`),
      ].join("\n") + "\n",
    );
    return 0;
  }

  if (command === "task") {
    return await runTaskCommand(argv.slice(1), cwd);
  }

  if (command === "control") {
    return await runControlCommand(argv.slice(1), cwd);
  }

  if (command === "feedback") {
    const { runFeedbackCommand } = await import("./feedback/command.js");
    return await runFeedbackCommand(argv.slice(1), await projectRootFrom(cwd));
  }

  if (command === "rsi") {
    return await runRsiCommand(argv.slice(1), await projectRootFrom(cwd));
  }

  throw new SageError(`Unknown command: ${command}`, "E_USAGE", 2);
}

async function runRsiCommand(argv: string[], root: string): Promise<number> {
  const sub = argv[0];
  if (!sub) throw new SageError("rsi requires a subcommand", "E_USAGE", 2);
  const rsi = await import("./rsi/index.js");
  const store = rsi.openRsi(root);

  if (sub === "list") {
    const parsed = parseArgs(argv.slice(1), { value: ["status"], boolean: ["json"] });
    const proposals = await store.listProposals(
      typeof parsed.flags.status === "string" ? { status: parsed.flags.status as never } : {},
    );
    if (boolFlag(parsed.flags, "json")) json({ ok: true, proposals });
    else if (proposals.length === 0) process.stdout.write("No RSI proposals.\n");
    else {
      process.stdout.write(
        proposals.map((proposal) => `${proposal.id}\t${proposal.status}\t${proposal.hypothesis}`).join("\n") + "\n",
      );
    }
    return 0;
  }

  if (sub === "create") {
    const parsed = parseArgs(argv.slice(1), { value: ["file"], boolean: ["json"] });
    const file = requireString(parsed.flags, "file");
    let text = await readFile(resolve(root, file), "utf8");
    if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
    const input = JSON.parse(text) as Parameters<typeof store.createProposal>[0];
    const proposal = await store.createProposal(input);
    if (boolFlag(parsed.flags, "json")) json({ ok: true, proposal });
    else process.stdout.write(`created ${proposal.id} (${proposal.status})\n`);
    return 0;
  }

  if (sub === "run-once") {
    const parsed = parseArgs(argv.slice(1), { value: ["test-command"], boolean: ["json"] });
    const command = JSON.parse(requireString(parsed.flags, "test-command")) as string[];
    if (!Array.isArray(command) || command.some((item) => typeof item !== "string") || command.length === 0) {
      throw new SageError("--test-command must be a non-empty JSON string array", "E_USAGE", 2);
    }
    const result = await rsi.runOnce({ projectRoot: root, testCommand: command });
    if (boolFlag(parsed.flags, "json")) json({ ok: true, result });
    else process.stdout.write(`${result.outcome}: evaluated=${result.evaluated}${result.proposalId ? ` ${result.proposalId}` : ""}\n`);
    return result.outcome === "failed" ? 1 : 0;
  }

  if (sub === "request-approval") {
    const parsed = parseArgs(argv.slice(1), { boolean: ["json"] });
    const proposalId = parsed.positional[0];
    if (!proposalId) throw new SageError("rsi request-approval requires <proposal-id>", "E_USAGE", 2);
    const challenge = await rsi.requestApproval({ projectRoot: root, proposalId });
    if (boolFlag(parsed.flags, "json")) json({ ok: true, challenge });
    else process.stdout.write(`approval token (shown once): ${challenge.approvalToken}\nexpires: ${challenge.expiresAt}\n`);
    return 0;
  }

  if (sub === "rollback-point") {
    const parsed = parseArgs(argv.slice(1), {
      value: ["base-commit", "base-version", "artifact", "note"],
      boolean: ["json"],
    });
    const point = await rsi.createRollbackPoint({
      projectRoot: root,
      baseCommit: requireString(parsed.flags, "base-commit"),
      baseVersion: requireString(parsed.flags, "base-version"),
      ...(typeof parsed.flags.artifact === "string" ? { artifactPath: parsed.flags.artifact } : {}),
      ...(typeof parsed.flags.note === "string" ? { note: parsed.flags.note } : {}),
    });
    if (boolFlag(parsed.flags, "json")) json({ ok: true, point });
    else process.stdout.write(`${point.id}\t${point.rollbackCommand}\n`);
    return 0;
  }

  if (sub === "approve") {
    const parsed = parseArgs(argv.slice(1), {
      value: ["token", "decided-by", "rollback-point", "note"],
      boolean: ["json"],
    });
    const proposalId = parsed.positional[0];
    if (!proposalId) throw new SageError("rsi approve requires <proposal-id>", "E_USAGE", 2);
    const approval = await rsi.approve({
      projectRoot: root,
      proposalId,
      approvalToken: requireString(parsed.flags, "token"),
      decidedBy: requireString(parsed.flags, "decided-by"),
      rollbackPointId: requireString(parsed.flags, "rollback-point"),
      ...(typeof parsed.flags.note === "string" ? { note: parsed.flags.note } : {}),
    });
    if (boolFlag(parsed.flags, "json")) json({ ok: true, approval });
    else process.stdout.write(`${proposalId}: ${approval.decision}\n`);
    return 0;
  }

  if (sub === "reject") {
    const parsed = parseArgs(argv.slice(1), {
      value: ["decided-by", "reason"],
      boolean: ["json"],
    });
    const proposalId = parsed.positional[0];
    if (!proposalId) throw new SageError("rsi reject requires <proposal-id>", "E_USAGE", 2);
    const approval = await rsi.rejectProposal({
      projectRoot: root,
      proposalId,
      decidedBy: requireString(parsed.flags, "decided-by"),
      reason: requireString(parsed.flags, "reason"),
    });
    if (boolFlag(parsed.flags, "json")) json({ ok: true, approval });
    else process.stdout.write(`${proposalId}: ${approval.decision}\n`);
    return 0;
  }

  throw new SageError(`Unknown rsi command: ${sub}`, "E_USAGE", 2);
}

function parsePort(value: unknown): number {
  if (value === undefined) return 0;
  if (typeof value !== "string" || !/^\d+$/.test(value)) {
    throw new SageError("--port must be an integer between 0 and 65535", "E_USAGE", 2);
  }
  const port = Number(value);
  if (!Number.isSafeInteger(port) || port < 0 || port > 65535) {
    throw new SageError("--port must be an integer between 0 and 65535", "E_USAGE", 2);
  }
  return port;
}

async function runControlCommand(argv: string[], cwd: string): Promise<number> {
  const sub = argv[0] ?? "status";
  const root = await projectRootFrom(cwd);
  const control = await import("./control/index.js");

  if (sub === "status") {
    const parsed = parseArgs(argv.slice(1), { boolean: ["json"] });
    const store = control.openControl(root);
    try {
      const tasks = store.listTasks({ limit: 500 });
      const runs = store.listRuns({ limit: 500 });
      const leases = store.listLeases();
      const payload = {
        ok: true,
        projectRoot: root,
        dbPath: store.debugInfo().dbPath,
        counts: { tasks: tasks.length, runs: runs.length, leases: leases.length },
        statuses: Object.fromEntries(
          [...new Set(tasks.map((task) => task.status))].sort().map((status) => [
            status,
            tasks.filter((task) => task.status === status).length,
          ]),
        ),
        activeLeases: leases.filter((lease) => lease.expiresAt > new Date().toISOString()).length,
      };
      if (boolFlag(parsed.flags, "json")) json(payload);
      else {
        const statusLines = Object.entries(payload.statuses).map(([status, count]) => `${status}=${count}`);
        process.stdout.write(
          `control db: ${payload.dbPath}\ntasks: ${payload.counts.tasks}${
            statusLines.length ? ` (${statusLines.join(", ")})` : ""
          }\nruns: ${payload.counts.runs}\nleases: ${payload.counts.leases} (active ${payload.activeLeases})\n`,
        );
      }
      return 0;
    } finally {
      store.close();
    }
  }

  if (sub === "recover") {
    const parsed = parseArgs(argv.slice(1), { boolean: ["json"] });
    const store = control.openControl(root);
    try {
      const report = store.recoverStale();
      if (boolFlag(parsed.flags, "json")) json({ ok: true, report });
      else {
        process.stdout.write(
          `recovered runs=${report.interruptedRuns.length} leases=${report.expiredLeases.length} tasks=${report.interruptedTasks.length}\n`,
        );
      }
      return 0;
    } finally {
      store.close();
    }
  }

  if (sub !== "serve") {
    throw new SageError(`Unknown control command: ${sub}`, "E_USAGE", 2);
  }

  const parsed = parseArgs(argv.slice(1), {
    value: ["port"],
    boolean: ["recover", "json"],
    multi: [],
  });
  const port = parsePort(parsed.flags.port);
  const store = control.openControl(root);
  if (boolFlag(parsed.flags, "recover")) store.recoverStale();
  const server = await control.createControlServer({ store, port });
  const payload = {
    ok: true,
    url: server.url,
    uiUrl: `${server.url}/ui`,
    host: server.host,
    port: server.port,
  };
  if (boolFlag(parsed.flags, "json")) process.stdout.write(`${JSON.stringify(payload)}\n`);
  else {
    process.stdout.write(`SAGE-Kit control listening on ${server.url}\n`);
    process.stdout.write(`Read-only UI: ${payload.uiUrl}\n`);
    process.stdout.write("Press Ctrl+C to stop.\n");
  }

  await new Promise<void>((resolvePromise) => {
    let stopping = false;
    const stop = () => {
      if (stopping) return;
      stopping = true;
      server
        .close()
        .catch(() => undefined)
        .finally(() => {
          store.close();
          resolvePromise();
        });
    };
    process.once("SIGINT", stop);
    process.once("SIGTERM", stop);
  });
  return 0;
}

async function runTaskCommand(argv: string[], cwd: string): Promise<number> {
  const sub = argv[0];
  const root = await projectRootFrom(cwd);
  const paths = statePaths(root);
  if (!sub || sub === "list") {
    const parsed = parseArgs(argv.slice(1), { value: ["status"], boolean: ["json"] });
    const tasks = await listTasks(paths);
    const filtered =
      typeof parsed.flags.status === "string" ? tasks.filter((task) => task.status === parsed.flags.status) : tasks;
    if (boolFlag(parsed.flags, "json")) {
      json({ ok: true, tasks: filtered });
    } else if (filtered.length === 0) {
      process.stdout.write("No tasks.\n");
    } else {
      const lines = ["ID                           STATUS    TITLE"];
      for (const task of filtered) lines.push(`${task.id.padEnd(28)} ${task.status.padEnd(9)} ${task.title}`);
      process.stdout.write(`${lines.join("\n")}\n`);
    }
    return 0;
  }

  if (sub === "create") {
    const parsed = parseArgs(argv.slice(1), {
      value: ["title", "description", "id", "status"],
      multi: ["acceptance"],
      boolean: ["json"],
    });
    const task = await createTask(paths, {
      title: requireString(parsed.flags, "title"),
      ...(typeof parsed.flags.description === "string" ? { description: parsed.flags.description } : {}),
      ...(typeof parsed.flags.id === "string" ? { id: parsed.flags.id } : {}),
      ...(typeof parsed.flags.status === "string"
        ? { status: parsed.flags.status as TaskStatus }
        : {}),
      acceptance: parsed.multi.acceptance ?? [],
    });
    if (boolFlag(parsed.flags, "json")) json({ ok: true, task });
    else process.stdout.write(`Created ${task.id}: ${task.title}\n`);
    return 0;
  }

  if (sub === "show") {
    const parsed = parseArgs(argv.slice(1), { boolean: ["json"] });
    const id = parsed.positional[0];
    if (!id) throw new SageError("task show requires <id>", "E_USAGE", 2);
    const task = await readTask(paths, id);
    if (boolFlag(parsed.flags, "json")) json({ ok: true, task });
    else process.stdout.write(`${JSON.stringify(task, null, 2)}\n`);
    return 0;
  }

  if (sub === "status") {
    const parsed = parseArgs(argv.slice(1), {
      value: ["note", "source"],
      multi: ["evidence"],
      boolean: ["json"],
    });
    const id = parsed.positional[0];
    const next = parsed.positional[1];
    if (!id || !next) throw new SageError("task status requires <id> <status>", "E_USAGE", 2);
    if (!isTaskStatus(next)) throw new SageError(`Unknown task status: ${next}`, "E_USAGE", 2);
    const task = await updateTaskStatus(paths, id, next, {
      evidence: parsed.multi.evidence ?? [],
      ...(typeof parsed.flags.note === "string" ? { note: parsed.flags.note } : {}),
      ...(typeof parsed.flags.source === "string" ? { source: parsed.flags.source } : {}),
    });
    if (boolFlag(parsed.flags, "json")) json({ ok: true, task });
    else process.stdout.write(`${task.id}: ${task.status}\n`);
    return 0;
  }

  throw new SageError(`Unknown task command: ${sub}`, "E_USAGE", 2);
}

main(process.argv.slice(2))
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error) => {
    const sage = toSageError(error);
    const wantsJson = process.argv.includes("--json") || process.argv.includes("hook");
    if (wantsJson) {
      json({ ok: false, error: { code: sage.code, message: sage.message } });
    } else {
      process.stderr.write(`sage-kit: ${sage.message}\n`);
    }
    process.exitCode = sage.exitCode;
  });
