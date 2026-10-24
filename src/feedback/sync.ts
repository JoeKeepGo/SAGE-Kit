/**
 * One feedback sync: list from an adapter, append new versions, advance the
 * cursor only after everything succeeded.
 *
 * Failure semantics:
 * - adapter/network/parse failure -> nothing written; the old cursor is kept.
 * - append succeeded but cursor write failed -> retry is safe: fingerprints
 *   dedupe already-stored versions, then the cursor advances.
 */
import { relative, resolve } from "node:path";
import { nowIso } from "../core/fs-utils.js";
import { SageError } from "../core/errors.js";
import { statePaths } from "../core/paths.js";
import { createFeedbackAdapter } from "./adapters/index.js";
import { flattenText, toFeedbackItem } from "./normalize.js";
import {
  appendFeedbackItems,
  feedbackPaths,
  listFeedback,
  readFeedbackCursors,
  writeFeedbackCursors,
} from "./store.js";
import {
  isFeedbackProvider,
  type FeedbackCursorsFile,
  type FeedbackProvider,
} from "./types.js";

export interface SyncFeedbackOptions {
  /** "local" | "github" | "gitea" (validated at runtime). */
  source: string;
  projectRoot: string;
  repo?: string;
  file?: string;
  env?: NodeJS.ProcessEnv;
  fetchImpl?: typeof fetch;
  baseUrl?: string;
}

export interface SyncFeedbackResult {
  ok: true;
  source: FeedbackProvider;
  repo: string;
  /** Absolute path of the local JSONL source, when source = local. */
  file?: string;
  /** Normalized items returned by the source in this sync. */
  fetched: number;
  /** Versions appended to items.jsonl. */
  added: number;
  /** Versions skipped because their fingerprint was already stored. */
  duplicates: number;
  /** Stored versions after the sync. */
  total: number;
  /** Distinct feedback ids after the sync (latest version per id). */
  unique: number;
  cursor: string | null;
  cursorKey: string;
  /** Paths relative to projectRoot (posix separators). */
  itemsFile: string;
  cursorsFile: string;
}

function toPosix(value: string): string {
  return value.split("\\").join("/");
}

export async function syncFeedback(options: SyncFeedbackOptions): Promise<SyncFeedbackResult> {
  const source = options.source;
  if (!isFeedbackProvider(source)) {
    throw new SageError(
      `Unknown feedback source: ${String(source)} (expected local, github or gitea)`,
      "E_USAGE",
      2,
    );
  }
  const projectRoot = resolve(options.projectRoot);
  const paths = statePaths(projectRoot);
  const storePaths = feedbackPaths(paths);

  let repo: string;
  let file: string | undefined;
  if (source === "local") {
    file = resolve(projectRoot, options.file ?? storePaths.inboxFile);
    repo = flattenText(options.repo ?? "", 200) || "local";
  } else {
    const rawRepo = (options.repo ?? "").trim();
    if (!rawRepo) throw new SageError("--repo owner/name is required for github/gitea", "E_USAGE", 2);
    repo = rawRepo;
  }

  const adapter = createFeedbackAdapter(source, {
    ...(options.env ? { env: options.env } : {}),
    ...(options.fetchImpl ? { fetchImpl: options.fetchImpl } : {}),
    ...(options.baseUrl ? { baseUrl: options.baseUrl } : {}),
  });

  const cursors = await readFeedbackCursors(paths);
  const cursorKey =
    source === "local"
      ? `local:${repo}:${toPosix(relative(projectRoot, file as string))}`
      : `${source}:${repo}`;
  const previous = cursors.cursors[cursorKey];

  const page = await adapter.list({
    repo,
    ...(file ? { file } : {}),
    ...(previous?.cursor ? { cursor: previous.cursor } : {}),
  });

  const now = nowIso();
  const items = page.items.map((external) =>
    toFeedbackItem(external, { provider: source, repo, now }),
  );
  const appended = await appendFeedbackItems(paths, items);
  const nextCursor = page.nextCursor ?? previous?.cursor ?? null;

  const nextCursors: FeedbackCursorsFile = {
    schemaVersion: 1,
    cursors: {
      ...cursors.cursors,
      [cursorKey]: {
        provider: source,
        repo,
        cursor: nextCursor,
        lastSyncAt: now,
        lastSuccessAt: now,
        lastFetched: items.length,
      },
    },
  };
  await writeFeedbackCursors(paths, nextCursors);

  const unique = (await listFeedback(paths)).length;
  return {
    ok: true,
    source,
    repo,
    ...(file ? { file } : {}),
    fetched: items.length,
    added: appended.added,
    duplicates: appended.duplicates,
    total: appended.total,
    unique,
    cursor: nextCursor,
    cursorKey,
    itemsFile: toPosix(relative(projectRoot, storePaths.itemsFile)),
    cursorsFile: toPosix(relative(projectRoot, storePaths.cursorsFile)),
  };
}
