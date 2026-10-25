/**
 * Local JSONL feedback source (offline imports and tests).
 *
 * Each newline-terminated line is one JSON object. The cursor is the byte
 * offset after the last complete line; a trailing unterminated line is left for
 * the next sync so a concurrent writer is never half-read. Re-reading is safe
 * because the store dedupes by fingerprint.
 */
import { readFile } from "node:fs/promises";
import { SageError } from "../../core/errors.js";
import {
  asRecord,
  flattenText,
  pickString,
  readLabels,
  sanitizeTimestamp,
  truncateChars,
} from "../normalize.js";
import {
  isFeedbackKind,
  type AdapterDeps,
  type ExternalFeedback,
  type FeedbackCapabilities,
  type FeedbackPage,
  type FeedbackSourceAdapter,
  type ListFeedbackInput,
} from "../types.js";

const MAX_LINE_LENGTH = 1_000_000;

function parsePosition(cursor: string | undefined): number {
  if (!cursor) return 0;
  const parsed = Number(cursor);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
}

export class LocalFeedbackAdapter implements FeedbackSourceAdapter {
  readonly name = "local";
  readonly contractVersion = "1";

  constructor(_deps: AdapterDeps = {}) {}

  capabilities(): FeedbackCapabilities {
    return {
      pagination: false,
      incremental: true,
      comments: false,
      checks: false,
      writeBack: false,
      auth: "none",
    };
  }

  async list(input: ListFeedbackInput): Promise<FeedbackPage> {
    if (!input.file) {
      throw new SageError(
        "local feedback source requires --file <path to .jsonl>",
        "E_USAGE",
        2,
      );
    }
    let buffer: Buffer;
    try {
      buffer = await readFile(input.file);
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      throw new SageError(
        `Cannot read local feedback file ${input.file}${code ? ` (${code})` : ""}`,
        "E_FEEDBACK_FILE",
        1,
      );
    }
    let start = parsePosition(input.cursor);
    if (start > buffer.length) start = 0; // file was truncated or replaced
    const slice = buffer.subarray(start);
    const lastNewline = slice.lastIndexOf(10);
    const complete = lastNewline >= 0 ? slice.subarray(0, lastNewline) : Buffer.alloc(0);
    const nextPosition = start + (lastNewline >= 0 ? lastNewline + 1 : 0);
    const lines = complete
      .toString("utf8")
      .split(/\r?\n/)
      .filter((line) => line.trim().length > 0);

    const items: ExternalFeedback[] = [];
    for (const [index, line] of lines.entries()) {
      if (line.length > MAX_LINE_LENGTH) {
        throw new SageError(
          `Local feedback line ${index + 1} exceeds ${MAX_LINE_LENGTH} characters`,
          "E_FEEDBACK_BAD_FIXTURE",
          1,
        );
      }
      let raw: unknown;
      try {
        raw = JSON.parse(line) as unknown;
      } catch {
        throw new SageError(
          `Invalid JSON on local feedback line ${index + 1} (bytes before ${nextPosition})`,
          "E_FEEDBACK_BAD_FIXTURE",
          1,
        );
      }
      try {
        items.push(this.normalize(raw));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        throw new SageError(
          `Invalid local feedback line ${index + 1}: ${message}`,
          "E_FEEDBACK_BAD_FIXTURE",
          1,
        );
      }
    }
    return { items, nextCursor: String(nextPosition) };
  }

  normalize(raw: unknown): ExternalFeedback {
    const record = asRecord(raw);
    if (!record) throw new SageError("feedback line must be a JSON object", "E_FEEDBACK_BAD_FIXTURE", 1);
    const externalId = pickString(record, "externalId", "id", "number");
    if (!externalId) {
      throw new SageError("feedback line must have a non-empty externalId (or id)", "E_FEEDBACK_BAD_FIXTURE", 1);
    }
    const rawKind = record.kind;
    if (rawKind !== undefined && !isFeedbackKind(rawKind)) {
      throw new SageError(`unknown feedback kind: ${String(rawKind)}`, "E_FEEDBACK_BAD_FIXTURE", 1);
    }
    const item: ExternalFeedback = {
      externalId: truncateChars(flattenText(externalId, 200), 200),
      kind: isFeedbackKind(rawKind) ? rawKind : "issue",
    };
    const title = pickString(record, "title", "subject");
    if (title) item.title = title;
    const body = pickString(record, "body", "description", "text");
    if (body) item.body = body;
    const author = pickString(record, "author", "user", "login");
    if (author) item.author = author;
    const state = pickString(record, "state", "status");
    if (state) item.state = state;
    const labels = readLabels(record.labels);
    if (labels) item.labels = labels;
    const url = pickString(record, "url", "htmlUrl", "html_url");
    if (url) item.url = url;
    const createdAt = sanitizeTimestamp(record.createdAt ?? record.created_at);
    if (createdAt) item.createdAt = createdAt;
    const updatedAt = sanitizeTimestamp(record.updatedAt ?? record.updated_at);
    if (updatedAt) item.updatedAt = updatedAt;
    const metadata = asRecord(record.metadata);
    if (metadata) item.metadata = metadata;
    return item;
  }
}
