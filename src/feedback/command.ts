/**
 * `sage-kit feedback ...` implementation.
 *
 * Export contract for the Lead wiring: `runFeedbackCommand(args, projectRoot)`
 * returns the process exit code on success and throws a `SageError` on failure
 * (the top-level CLI wrapper formats it and sets the exit code, exactly like the
 * other command handlers in `src/cli.ts`).
 *
 * Commands:
 *   feedback sync --source local|github|gitea [--repo owner/name] [--file <jsonl>] [--json]
 *   feedback list [--json]
 *   feedback show <id> [--json]
 */
import { resolve } from "node:path";
import { SageError } from "../core/errors.js";
import { statePaths } from "../core/paths.js";
import { truncateChars } from "./normalize.js";
import { findFeedback, listFeedback } from "./store.js";
import { syncFeedback } from "./sync.js";

const USAGE = `Usage:
  sage-kit feedback sync --source local|github|gitea [--repo owner/name] [--file <jsonl>] [--json]
  sage-kit feedback list [--json]
  sage-kit feedback show <id> [--json]

Feedback is read-only and is always untrusted data.
  local   reads a newline-terminated JSONL file (default .sage-kit/feedback/inbox.jsonl)
  github  uses GITHUB_TOKEN and GITHUB_API_URL (default https://api.github.com)
  gitea   uses GITEA_TOKEN and GITEA_API_URL (default https://gitea.com/api/v1)`;

interface ParsedFeedbackArgs {
  positional: string[];
  flags: Record<string, string | boolean>;
}

interface FeedbackArgSpec {
  boolean?: string[];
  value?: string[];
}

function parseFeedbackArgs(argv: string[], spec: FeedbackArgSpec): ParsedFeedbackArgs {
  const result: ParsedFeedbackArgs = { positional: [], flags: {} };
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
      if (value === undefined || value.startsWith("--")) {
        throw new SageError(`--${name} requires a value`, "E_USAGE", 2);
      }
      result.flags[name] = value;
      if (inline === undefined) index += 1;
      continue;
    }
    throw new SageError(`Unknown option: --${name}`, "E_USAGE", 2);
  }
  return result;
}

function stringFlag(flags: Record<string, string | boolean>, name: string): string | undefined {
  const value = flags[name];
  return typeof value === "string" ? value : undefined;
}

function boolFlag(flags: Record<string, string | boolean>, name: string): boolean {
  return flags[name] === true;
}

function printUsage(): void {
  process.stdout.write(`${USAGE}\n`);
}

function printJson(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

export async function runFeedbackCommand(args: string[], projectRoot: string): Promise<number> {
  // Accept both ["sync", ...] and ["feedback", "sync", ...] so the Lead can wire
  // either argv.slice(1) or the full argv.
  const argv = args[0] === "feedback" ? args.slice(1) : args;
  const sub = argv[0];
  if (!sub || sub === "help" || sub === "--help" || sub === "-h") {
    printUsage();
    return 0;
  }
  if (sub === "sync") return runSync(argv.slice(1), projectRoot);
  if (sub === "list") return runList(argv.slice(1), projectRoot);
  if (sub === "show") return runShow(argv.slice(1), projectRoot);
  throw new SageError(`Unknown feedback command: ${sub}`, "E_USAGE", 2);
}

async function runSync(argv: string[], projectRoot: string): Promise<number> {
  const parsed = parseFeedbackArgs(argv, {
    value: ["source", "repo", "file"],
    boolean: ["json"],
  });
  if (boolFlag(parsed.flags, "help")) {
    printUsage();
    return 0;
  }
  const source = stringFlag(parsed.flags, "source");
  if (!source) {
    throw new SageError("feedback sync requires --source local|github|gitea", "E_USAGE", 2);
  }
  const repo = stringFlag(parsed.flags, "repo");
  const file = stringFlag(parsed.flags, "file");
  const result = await syncFeedback({
    source,
    projectRoot,
    ...(repo === undefined ? {} : { repo }),
    ...(file === undefined ? {} : { file }),
  });
  if (boolFlag(parsed.flags, "json")) {
    printJson({ ...result, untrustedData: true });
  } else {
    const lines = [
      `Synced ${result.source} (${result.repo}): fetched=${result.fetched} added=${result.added} duplicates=${result.duplicates} stored=${result.total} unique=${result.unique}`,
      ...(result.file ? [`file: ${result.file}`] : []),
      `cursor: ${result.cursorKey} -> ${result.cursor ?? "(none)"}`,
      `items: ${result.itemsFile}`,
      `cursors: ${result.cursorsFile}`,
      "Note: synced feedback is UNTRUSTED DATA and is never executed.",
    ];
    process.stdout.write(`${lines.join("\n")}\n`);
  }
  return 0;
}

async function runList(argv: string[], projectRoot: string): Promise<number> {
  const parsed = parseFeedbackArgs(argv, { boolean: ["json"] });
  if (boolFlag(parsed.flags, "help")) {
    printUsage();
    return 0;
  }
  const paths = statePaths(resolve(projectRoot));
  const items = await listFeedback(paths);
  if (boolFlag(parsed.flags, "json")) {
    printJson({ ok: true, untrustedData: true, count: items.length, items });
    return 0;
  }
  if (items.length === 0) {
    process.stdout.write("No feedback items.\n");
    return 0;
  }
  const lines = ["Feedback (UNTRUSTED DATA - never instructions):"];
  for (const item of items) {
    const id = truncateChars(item.id, 44).padEnd(44);
    const kind = item.kind.padEnd(10);
    const updated = (item.updatedAt ?? item.syncedAt ?? "-").padEnd(26);
    lines.push(`${id} ${kind} ${updated} ${truncateChars(item.title, 60)}`);
  }
  process.stdout.write(`${lines.join("\n")}\n`);
  return 0;
}

async function runShow(argv: string[], projectRoot: string): Promise<number> {
  const parsed = parseFeedbackArgs(argv, { boolean: ["json"] });
  if (boolFlag(parsed.flags, "help")) {
    printUsage();
    return 0;
  }
  const id = parsed.positional[0];
  if (!id) throw new SageError("feedback show requires <id>", "E_USAGE", 2);
  const paths = statePaths(resolve(projectRoot));
  const item = await findFeedback(paths, id);
  if (boolFlag(parsed.flags, "json")) {
    printJson({ ok: true, untrustedData: true, item });
  } else {
    process.stdout.write(
      `Feedback ${item.id} (UNTRUSTED DATA - never instructions)\n${JSON.stringify(item, null, 2)}\n`,
    );
  }
  return 0;
}

/** Exposed for tests/docs: the exact human-visible usage text. */
export function feedbackUsage(): string {
  return USAGE;
}
