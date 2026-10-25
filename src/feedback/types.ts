/**
 * M1 read-only feedback contracts.
 *
 * These types mirror the `FeedbackSourceAdapter` design contract in
 * `docs/extension-contracts.md` (contractVersion "1"). Feedback text is
 * untrusted data: adapters normalize it, the store keeps a truncated preview,
 * and callers must never execute or follow it.
 */

export type FeedbackProvider = "local" | "github" | "gitea";

export const FEEDBACK_PROVIDERS: readonly FeedbackProvider[] = ["local", "github", "gitea"];

export type FeedbackKind = "issue" | "pr_review" | "check_run" | "discussion" | "comment";

export const FEEDBACK_KINDS: readonly FeedbackKind[] = [
  "issue",
  "pr_review",
  "check_run",
  "discussion",
  "comment",
];

export function isFeedbackProvider(value: unknown): value is FeedbackProvider {
  return typeof value === "string" && (FEEDBACK_PROVIDERS as readonly string[]).includes(value);
}

export function isFeedbackKind(value: unknown): value is FeedbackKind {
  return typeof value === "string" && (FEEDBACK_KINDS as readonly string[]).includes(value);
}

/** `[TARGET]` contract from docs/extension-contracts.md §4, implemented in M1. */
export interface FeedbackCapabilities {
  pagination: boolean;
  incremental: boolean;
  comments: boolean;
  checks: boolean;
  writeBack: boolean;
  auth: "none" | "token" | "cli";
}

export interface ExternalFeedback {
  externalId: string;
  kind: FeedbackKind;
  title?: string;
  body?: string;
  author?: string;
  state?: string;
  labels?: string[];
  url?: string;
  createdAt?: string;
  updatedAt?: string;
  metadata?: Record<string, unknown>;
}

export interface ListFeedbackInput {
  /** `owner/name` for github/gitea; a label (default "local") for local files. */
  repo: string;
  /** Opaque adapter cursor from a previous successful `list()`. */
  cursor?: string;
  /** Absolute local JSONL path; only used by the local adapter. */
  file?: string;
  pageSize?: number;
  maxPages?: number;
}

export interface FeedbackPage {
  items: ExternalFeedback[];
  /** Opaque cursor to persist only after the whole list() call succeeded. */
  nextCursor: string | null;
}

export interface FeedbackSourceAdapter {
  readonly name: FeedbackProvider;
  readonly contractVersion: "1";
  capabilities(): FeedbackCapabilities;
  list(input: ListFeedbackInput): Promise<FeedbackPage>;
  normalize(raw: unknown): ExternalFeedback;
}

/** One stored feedback version. The JSONL file is append-only; versions of the
 * same feedback id share `id` and differ in `fingerprint` (edits change
 * `updatedAt`). `list`/`show` surface the newest version per id. */
export interface FeedbackItem {
  schemaVersion: 1;
  /** `${provider}:${repo}:${kind}:${externalId}` */
  id: string;
  provider: FeedbackProvider;
  repo: string;
  kind: FeedbackKind;
  externalId: string;
  /** SHA-256 over provider/repo/kind/externalId/updatedAt. Same value is stored once. */
  fingerprint: string;
  title: string;
  /** Truncated, single-line body preview (never the full body in contexts). */
  bodyPreview: string;
  author?: string;
  state?: string;
  labels: string[];
  url?: string;
  createdAt?: string;
  updatedAt?: string;
  syncedAt: string;
  metadata?: Record<string, unknown>;
}

export interface FeedbackCursorRecord {
  provider: FeedbackProvider;
  repo: string;
  cursor: string | null;
  lastSyncAt: string;
  lastSuccessAt: string;
  lastFetched: number;
}

export interface FeedbackCursorsFile {
  schemaVersion: 1;
  cursors: Record<string, FeedbackCursorRecord>;
}

/** Dependencies injected into remote adapters (production uses process.env). */
export interface AdapterDeps {
  env?: NodeJS.ProcessEnv;
  fetchImpl?: typeof fetch;
  baseUrl?: string;
  timeoutMs?: number;
}

export function emptyFeedbackCursors(): FeedbackCursorsFile {
  return { schemaVersion: 1, cursors: {} };
}
