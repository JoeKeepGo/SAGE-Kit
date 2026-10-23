/**
 * Normalization helpers shared by all feedback adapters and the store.
 *
 * Everything that crosses the external boundary is flattened to a single line
 * and length-capped so it cannot forge brief sections or smuggle control
 * characters, and only http(s) URLs are kept.
 */
import { nowIso, sha256 } from "../core/fs-utils.js";
import { SageError } from "../core/errors.js";
import {
  isFeedbackKind,
  type ExternalFeedback,
  type FeedbackItem,
  type FeedbackProvider,
} from "./types.js";

export interface FeedbackItemContext {
  provider: FeedbackProvider;
  repo: string;
  now?: string;
}

export function truncateChars(value: string, maxChars: number): string {
  if (maxChars <= 0) return "";
  const chars = Array.from(value);
  if (chars.length <= maxChars) return value;
  const suffix = "…";
  const budget = Math.max(0, maxChars - suffix.length);
  return `${chars.slice(0, budget).join("")}${suffix}`;
}

/** Collapse every control character/run of whitespace into single spaces. */
export function flattenText(value: string, maxChars: number): string {
  const flattened = value
    .replace(/[\u0000-\u001f\u007f-\u009f]+/g, " ")
    .replace(/\s+/gu, " ")
    .trim();
  return truncateChars(flattened, maxChars);
}

export function sanitizeUrl(value: unknown): string | undefined {
  if (typeof value !== "string" || !value.trim()) return undefined;
  try {
    const parsed = new URL(value.trim());
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return undefined;
    return parsed.href.slice(0, 2048);
  } catch {
    return undefined;
  }
}

export function sanitizeTimestamp(value: unknown): string | undefined {
  if (typeof value !== "string" || !value.trim()) return undefined;
  const time = Date.parse(value.trim());
  if (!Number.isFinite(time)) return undefined;
  return new Date(time).toISOString();
}

export function sanitizeMetadata(
  value: Record<string, unknown> | undefined,
): Record<string, unknown> | undefined {
  if (!value) return undefined;
  const output: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value).slice(0, 20)) {
    const cleanKey = key.slice(0, 64);
    if (typeof item === "string") output[cleanKey] = truncateChars(item, 200);
    else if (typeof item === "number" || typeof item === "boolean" || item === null) output[cleanKey] = item;
    // Nested structures are intentionally dropped in M1.
  }
  if (Object.keys(output).length === 0) return undefined;
  if (JSON.stringify(output).length > 2000) return { note: "[metadata omitted: too large]" };
  return output;
}

export function feedbackId(
  provider: FeedbackProvider,
  repo: string,
  kind: string,
  externalId: string,
): string {
  return `${provider}:${repo}:${kind}:${externalId}`;
}

export function feedbackFingerprint(input: {
  provider: FeedbackProvider;
  repo: string;
  kind: string;
  externalId: string;
  updatedAt?: string;
}): string {
  return `sha256:${sha256(
    JSON.stringify([
      input.provider,
      input.repo,
      input.kind,
      input.externalId,
      input.updatedAt ?? "",
    ]),
  )}`;
}

function requireExternalId(external: ExternalFeedback): string {
  if (typeof external.externalId !== "string" || !external.externalId.trim()) {
    throw new SageError("Feedback item is missing a non-empty externalId", "E_FEEDBACK_BAD_ITEM", 1);
  }
  return external.externalId.trim().slice(0, 200);
}

function requireKind(external: ExternalFeedback): ExternalFeedback["kind"] {
  if (!isFeedbackKind(external.kind)) {
    throw new SageError(`Unknown feedback kind: ${String(external.kind)}`, "E_FEEDBACK_BAD_ITEM", 1);
  }
  return external.kind;
}

/** Convert a normalized external item into the append-only stored record. */
export function toFeedbackItem(external: ExternalFeedback, context: FeedbackItemContext): FeedbackItem {
  const externalId = requireExternalId(external);
  const kind = requireKind(external);
  const updatedAt = sanitizeTimestamp(external.updatedAt);
  const createdAt = sanitizeTimestamp(external.createdAt);
  const item: FeedbackItem = {
    schemaVersion: 1,
    id: feedbackId(context.provider, context.repo, kind, externalId),
    provider: context.provider,
    repo: context.repo,
    kind,
    externalId,
    fingerprint: feedbackFingerprint({
      provider: context.provider,
      repo: context.repo,
      kind,
      externalId,
      ...(updatedAt ? { updatedAt } : {}),
    }),
    title: flattenText(external.title ?? "", 300) || "(untitled)",
    bodyPreview: flattenText(external.body ?? "", 1000),
    labels: (external.labels ?? [])
      .slice(0, 20)
      .map((label) => flattenText(String(label), 100))
      .filter(Boolean),
    syncedAt: context.now ?? nowIso(),
  };
  const author = external.author === undefined ? undefined : flattenText(String(external.author), 200);
  if (author) item.author = author;
  const state = external.state === undefined ? undefined : flattenText(String(external.state), 100);
  if (state) item.state = state;
  const url = sanitizeUrl(external.url);
  if (url) item.url = url;
  if (createdAt) item.createdAt = createdAt;
  if (updatedAt) item.updatedAt = updatedAt;
  const metadata = sanitizeMetadata(external.metadata);
  if (metadata) item.metadata = metadata;
  return item;
}

// ---------------------------------------------------------------------------
// Small readers for untrusted JSON shapes (used by remote adapters).
// ---------------------------------------------------------------------------

export function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

export function pickString(record: Record<string, unknown> | undefined, ...keys: string[]): string | undefined {
  if (!record) return undefined;
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return undefined;
}

export function pickNumber(record: Record<string, unknown> | undefined, ...keys: string[]): number | undefined {
  if (!record) return undefined;
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  }
  return undefined;
}

export function readLabels(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const labels: string[] = [];
  for (const entry of value.slice(0, 20)) {
    if (typeof entry === "string") labels.push(entry);
    else {
      const record = asRecord(entry);
      const name = pickString(record, "name", "title");
      if (name) labels.push(name);
    }
  }
  return labels;
}
