/**
 * Gitea REST feedback adapter (read-only).
 *
 * Endpoint (assumption checked against the public Gitea API docs):
 *   GET /api/v1/repos/{owner}/{repo}/issues
 *       ?state=all&limit=N&page=P[&since=ISO8601]
 *       + X-Total-Count header when available; page fallback otherwise.
 *
 * Auth: `GITEA_TOKEN` sent as `Authorization: token <token>`.
 * Base URL: `GITEA_API_URL` (default https://gitea.com/api/v1). Self-hosted
 * Gitea instances must set this variable to `<host>/api/v1`.
 *
 * Gitea review-comment endpoints are per-pull-request; they are not synced in
 * M1 (capabilities().comments = false) to keep the request count bounded.
 */
import { SageError } from "../../core/errors.js";
import {
  asRecord,
  pickNumber,
  pickString,
  readLabels,
  sanitizeTimestamp,
} from "../normalize.js";
import { expectArray, httpGetJson, type FetchLike } from "../http.js";
import type {
  AdapterDeps,
  ExternalFeedback,
  FeedbackCapabilities,
  FeedbackPage,
  FeedbackSourceAdapter,
  ListFeedbackInput,
} from "../types.js";

const DEFAULT_BASE_URL = "https://gitea.com/api/v1";
const DEFAULT_PAGE_SIZE = 50;
const DEFAULT_MAX_PAGES = 20;

function maxIso(a: string | undefined, b: string | undefined): string | undefined {
  if (!a) return b;
  if (!b) return a;
  return b > a ? b : a;
}

export class GiteaFeedbackAdapter implements FeedbackSourceAdapter {
  readonly name = "gitea";
  readonly contractVersion = "1";
  private readonly deps: AdapterDeps;

  constructor(deps: AdapterDeps = {}) {
    this.deps = deps;
  }

  capabilities(): FeedbackCapabilities {
    return {
      pagination: true,
      incremental: true,
      comments: false,
      checks: false,
      writeBack: false,
      auth: "token",
    };
  }

  normalize(raw: unknown): ExternalFeedback {
    const record = asRecord(raw);
    if (!record) throw new SageError("Gitea issue must be a JSON object", "E_FEEDBACK_BAD_ITEM", 1);
    const number = pickNumber(record, "number", "id");
    if (number === undefined) {
      throw new SageError("Gitea issue is missing number/id", "E_FEEDBACK_BAD_ITEM", 1);
    }
    const user = asRecord(record.user);
    const item: ExternalFeedback = {
      externalId: String(number),
      kind: "issue",
      metadata: {
        number,
        comments: pickNumber(record, "comments") ?? 0,
        isPullRequest: record.pull_request !== undefined && record.pull_request !== null,
      },
    };
    const title = pickString(record, "title");
    if (title) item.title = title;
    const body = pickString(record, "body");
    if (body) item.body = body;
    const author = pickString(user, "login", "username");
    if (author) item.author = author;
    const state = pickString(record, "state");
    if (state) item.state = state;
    const labels = readLabels(record.labels);
    if (labels) item.labels = labels;
    const url = pickString(record, "html_url", "url");
    if (url) item.url = url;
    const createdAt = sanitizeTimestamp(record.created_at);
    if (createdAt) item.createdAt = createdAt;
    const updatedAt = sanitizeTimestamp(record.updated_at);
    if (updatedAt) item.updatedAt = updatedAt;
    return item;
  }

  async list(input: ListFeedbackInput): Promise<FeedbackPage> {
    const env = this.deps.env ?? process.env;
    const token = (env.GITEA_TOKEN ?? "").trim() || undefined;
    const baseUrl = (this.deps.baseUrl ?? env.GITEA_API_URL ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    const pageSize = input.pageSize ?? DEFAULT_PAGE_SIZE;
    const maxPages = input.maxPages ?? DEFAULT_MAX_PAGES;
    const since = input.cursor ? sanitizeTimestamp(input.cursor) : undefined;
    const [owner, name] = splitRepo(input.repo);

    const items: ExternalFeedback[] = [];
    let maxUpdated = since;
    let page = 1;
    for (; page <= maxPages; page += 1) {
      const params = new URLSearchParams({
        state: "all",
        page: String(page),
        limit: String(pageSize),
      });
      if (since) params.set("since", since);
      const url = `${baseUrl}/repos/${owner}/${name}/issues?${params.toString()}`;
      const response = await this.request(url, token);
      const array = expectArray(response.json, "issues", url);
      for (const raw of array) {
        try {
          const item = this.normalize(raw);
          items.push(item);
          maxUpdated = maxIso(maxUpdated, item.updatedAt);
        } catch {
          // One malformed remote entry must not block the rest of the sync.
        }
      }
      if (array.length === 0) break;
      const totalHeader = response.headers.get("x-total-count");
      const total = totalHeader === null ? Number.NaN : Number(totalHeader);
      if (Number.isFinite(total)) {
        if (page * pageSize >= total) break;
      } else if (array.length < pageSize) {
        break;
      }
    }

    return { items, nextCursor: maxUpdated ?? null };
  }

  private async request(url: string, token: string | undefined): Promise<{
    json: unknown;
    headers: Headers;
  }> {
    const fetchImpl: FetchLike | undefined = this.deps.fetchImpl;
    const response = await httpGetJson({
      url,
      ...(token ? { token } : {}),
      authScheme: "token",
      accept: "application/json",
      ...(this.deps.timeoutMs === undefined ? {} : { timeoutMs: this.deps.timeoutMs }),
      ...(fetchImpl ? { fetchImpl } : {}),
    });
    return { json: response.json, headers: response.headers };
  }
}

function splitRepo(repo: string): [string, string] {
  const match = /^([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)$/.exec(repo.trim());
  if (!match) {
    throw new SageError("--repo must look like owner/name", "E_USAGE", 2);
  }
  return [encodeURIComponent(match[1] as string), encodeURIComponent(match[2] as string)];
}
