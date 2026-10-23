/**
 * File-mode feedback storage.
 *
 * Layout (under `.sage-kit/feedback/`):
 *   items.jsonl    append-only feedback versions; dedupe by `fingerprint`
 *   cursors.json   one cursor record per source+repo (written only on success)
 *
 * `appendFeedbackItems` is serialized inside one process and is idempotent on
 * retry: the same fingerprint is never appended twice. Cross-process writes are
 * out of scope for file mode (single user, single writer).
 */
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import {
  appendLine,
  ensureDir,
  readText,
  writeJsonAtomic,
} from "../core/fs-utils.js";
import { SageError } from "../core/errors.js";
import type { StatePaths } from "../core/paths.js";
import {
  emptyFeedbackCursors,
  isFeedbackKind,
  isFeedbackProvider,
  type FeedbackCursorsFile,
  type FeedbackCursorRecord,
  type FeedbackItem,
} from "./types.js";

export interface FeedbackStorePaths {
  dir: string;
  itemsFile: string;
  cursorsFile: string;
  /** Default local JSONL inbox used when `feedback sync --source local` has no --file. */
  inboxFile: string;
}

export function feedbackPaths(paths: StatePaths): FeedbackStorePaths {
  const dir = join(paths.stateDir, "feedback");
  return {
    dir,
    itemsFile: join(dir, "items.jsonl"),
    cursorsFile: join(dir, "cursors.json"),
    inboxFile: join(dir, "inbox.jsonl"),
  };
}

let storeTail: Promise<unknown> = Promise.resolve();

/** Serialize store mutations within this process (file mode has one writer). */
function withStoreLock<T>(task: () => Promise<T>): Promise<T> {
  const result = storeTail.then(task, task);
  storeTail = result.then(
    () => undefined,
    () => undefined,
  );
  return result;
}

function isNotFound(error: unknown): boolean {
  return (error as NodeJS.ErrnoException | undefined)?.code === "ENOENT";
}

const FORBIDDEN_ITEM_KEYS = new Set(["__proto__", "constructor", "prototype"]);

function validateStoredItem(value: unknown): FeedbackItem | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const item = value as Partial<FeedbackItem>;
  if (item.schemaVersion !== 1) return undefined;
  if (typeof item.id !== "string" || !item.id) return undefined;
  if (!isFeedbackProvider(item.provider)) return undefined;
  if (!isFeedbackKind(item.kind)) return undefined;
  if (typeof item.repo !== "string" || typeof item.externalId !== "string") return undefined;
  if (typeof item.fingerprint !== "string" || !item.fingerprint) return undefined;
  if (typeof item.title !== "string" || typeof item.bodyPreview !== "string") return undefined;
  if (!Array.isArray(item.labels)) return undefined;
  if (item.syncedAt !== undefined && typeof item.syncedAt !== "string") return undefined;
  if (item.metadata !== undefined && item.metadata !== null && typeof item.metadata !== "object") {
    return undefined;
  }
  return item as FeedbackItem;
}

/** Read every stored version, oldest first. Malformed lines are skipped. */
export async function readFeedbackItems(paths: StatePaths): Promise<FeedbackItem[]> {
  const file = feedbackPaths(paths).itemsFile;
  let text: string;
  try {
    text = await readText(file);
  } catch (error) {
    if (isNotFound(error)) return [];
    throw error;
  }
  const items: FeedbackItem[] = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      const item = validateStoredItem(JSON.parse(line) as unknown);
      if (item) items.push(item);
    } catch {
      // A malformed line must not make `list`/`brief` crash; it is skipped.
    }
  }
  return items;
}

function latestTimestamp(item: FeedbackItem): string {
  return item.updatedAt ?? item.syncedAt ?? "";
}

/** One newest version per feedback id, newest first. */
export function latestFeedbackItems(items: FeedbackItem[]): FeedbackItem[] {
  const latest = new Map<string, FeedbackItem>();
  for (const item of items) {
    const current = latest.get(item.id);
    if (!current || latestTimestamp(item) >= latestTimestamp(current)) latest.set(item.id, item);
  }
  return [...latest.values()].sort(
    (a, b) => latestTimestamp(b).localeCompare(latestTimestamp(a)) || a.id.localeCompare(b.id),
  );
}

export async function listFeedback(paths: StatePaths): Promise<FeedbackItem[]> {
  return latestFeedbackItems(await readFeedbackItems(paths));
}

/** Newest stored feedback item, or undefined. Never throws (used by `brief`). */
export async function readLatestFeedbackItem(paths: StatePaths): Promise<FeedbackItem | undefined> {
  try {
    return (await listFeedback(paths))[0];
  } catch {
    return undefined;
  }
}

/**
 * Look up one item by exact id, unique id prefix, or unique external id suffix.
 * Throws a readable SageError when absent or ambiguous.
 */
export async function findFeedback(paths: StatePaths, requested: string): Promise<FeedbackItem> {
  const query = requested.trim();
  if (!query) throw new SageError("feedback show requires <id>", "E_USAGE", 2);
  const items = await listFeedback(paths);
  const exact = items.find((item) => item.id === query);
  if (exact) return exact;
  const matches = items.filter(
    (item) => item.id.startsWith(query) || item.id.endsWith(`:${query}`),
  );
  if (matches.length === 1) return matches[0] as FeedbackItem;
  if (matches.length > 1) {
    throw new SageError(
      `Ambiguous feedback id: ${query} matches ${matches.length} items; use the full id`,
      "E_FEEDBACK_AMBIGUOUS",
      2,
    );
  }
  throw new SageError(`Feedback not found: ${query}`, "E_FEEDBACK_NOT_FOUND", 1);
}

export interface AppendFeedbackResult {
  added: number;
  duplicates: number;
  /** Number of stored versions after this append. */
  total: number;
}

/** Idempotently append versions; existing fingerprints are skipped. */
export async function appendFeedbackItems(
  paths: StatePaths,
  items: FeedbackItem[],
): Promise<AppendFeedbackResult> {
  return withStoreLock(async () => {
    const existing = await readFeedbackItems(paths);
    const fingerprints = new Set(existing.map((item) => item.fingerprint));
    const lines: string[] = [];
    let duplicates = 0;
    for (const item of items) {
      if (fingerprints.has(item.fingerprint)) {
        duplicates += 1;
        continue;
      }
      fingerprints.add(item.fingerprint);
      lines.push(JSON.stringify(item));
    }
    if (lines.length > 0) {
      const file = feedbackPaths(paths).itemsFile;
      await ensureDir(dirname(file));
      for (const line of lines) await appendLine(file, line);
    }
    return { added: lines.length, duplicates, total: existing.length + lines.length };
  });
}

function validateCursorRecord(value: unknown): FeedbackCursorRecord | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const record = value as Partial<FeedbackCursorRecord>;
  if (!isFeedbackProvider(record.provider)) return undefined;
  if (typeof record.repo !== "string") return undefined;
  if (record.cursor !== null && typeof record.cursor !== "string") return undefined;
  if (typeof record.lastSyncAt !== "string" || typeof record.lastSuccessAt !== "string") return undefined;
  if (typeof record.lastFetched !== "number") return undefined;
  return record as FeedbackCursorRecord;
}

export async function readFeedbackCursors(paths: StatePaths): Promise<FeedbackCursorsFile> {
  const file = feedbackPaths(paths).cursorsFile;
  let text: string;
  try {
    text = await readText(file);
  } catch (error) {
    if (isNotFound(error)) return emptyFeedbackCursors();
    throw error;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch {
    throw new SageError(`Invalid feedback cursors file: ${file}`, "E_FEEDBACK_BAD_CURSORS", 1);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new SageError(`Invalid feedback cursors file: ${file}`, "E_FEEDBACK_BAD_CURSORS", 1);
  }
  const record = parsed as Partial<FeedbackCursorsFile>;
  if (record.schemaVersion !== 1 || !record.cursors || typeof record.cursors !== "object") {
    throw new SageError(`Invalid feedback cursors file: ${file}`, "E_FEEDBACK_BAD_CURSORS", 1);
  }
  const cursors: Record<string, FeedbackCursorRecord> = {};
  for (const [key, value] of Object.entries(record.cursors)) {
    if (FORBIDDEN_ITEM_KEYS.has(key)) continue;
    const cursor = validateCursorRecord(value);
    if (!cursor) {
      throw new SageError(`Invalid cursor record in ${file}: ${key}`, "E_FEEDBACK_BAD_CURSORS", 1);
    }
    cursors[key] = cursor;
  }
  return { schemaVersion: 1, cursors };
}

/** Callers write this only after the source list() call succeeded. */
export async function writeFeedbackCursors(
  paths: StatePaths,
  cursors: FeedbackCursorsFile,
): Promise<void> {
  return withStoreLock(async () => {
    await writeJsonAtomic(feedbackPaths(paths).cursorsFile, sanitizeCursors(cursors));
  });
}

function sanitizeCursors(cursors: FeedbackCursorsFile): FeedbackCursorsFile {
  const safe: Record<string, FeedbackCursorRecord> = {};
  for (const [key, value] of Object.entries(cursors.cursors)) {
    if (FORBIDDEN_ITEM_KEYS.has(key)) continue;
    safe[key] = value;
  }
  return { schemaVersion: 1, cursors: safe };
}
