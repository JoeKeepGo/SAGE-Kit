/**
 * GitHub REST feedback adapter (read-only).
 *
 * Endpoints (assumption checked against the public GitHub REST docs):
 *   GET /repos/{owner}/{repo}/issues?state=all&sort=updated&direction=asc
 *       + per_page, optional since, Link: rel="next" pagination
 *   GET /repos/{owner}/{repo}/pulls/comments?sort=updated&direction=asc
 *       + per_page, Link pagination; no server-side `since`, so older results
 *       are filtered locally against the stored cursor.
 *
 * Auth: `GITHUB_TOKEN` (Bearer). Base URL: `GITHUB_API_URL` (default
 * https://api.github.com; useful for GitHub Enterprise Server or the local
 * fixture server). Write-back is not implemented.
 */
import {
  asRecord,
  pickNumber,
  pickString,
  readLabels,
  sanitizeTimestamp,
} from "../normalize.js";
import { SageError } from "../../core/errors.js";
import {
  expectArray,
  httpGetJson,
  isSameOrigin,
  nextLink,
  type FetchLike,
} from "../http.js";
import type {
  AdapterDeps,
  ExternalFeedback,
  FeedbackCapabilities,
  FeedbackPage,
  FeedbackSourceAdapter,
  ListFeedbackInput,
} from "../types.js";

const DEFAULT_BASE_URL = "https://api.github.com";
const DEFAULT_PAGE_SIZE = 100;
const DEFAULT_MAX_PAGES = 10;

interface GitHubCursor {
  issues?: string;
  reviews?: string;
}

function maxIso(a: string | undefined, b: string | undefined): string | undefined {
  if (!a) return b;
  if (!b) return a;
  return b > a ? b : a;
}

function decodeCursor(cursor: string | undefined): GitHubCursor {
  if (!cursor) return {};
  try {
    const record = asRecord(JSON.parse(cursor) as unknown);
    if (!record) return {};
    const result: GitHubCursor = {};
    const issues = sanitizeTimestamp(record.issues);
    const reviews = sanitizeTimestamp(record.reviews);
    if (issues) result.issues = issues;
    if (reviews) result.reviews = reviews;
    return result;
  } catch {
    return {};
  }
}

function encodeCursor(cursor: GitHubCursor): string {
  return JSON.stringify({ issues: cursor.issues ?? null, reviews: cursor.reviews ?? null });
}

export class GitHubFeedbackAdapter implements FeedbackSourceAdapter {
  readonly name = "github";
  readonly contractVersion = "1";
  private readonly deps: AdapterDeps;

  constructor(deps: AdapterDeps = {}) {
    this.deps = deps;
  }

  capabilities(): FeedbackCapabilities {
    return {
      pagination: true,
      incremental: true,
      comments: true,
      checks: false,
      writeBack: false,
      auth: "token",
    };
  }

  normalize(raw: unknown): ExternalFeedback {
    const record = asRecord(raw);
    if (!record) throw new SageError("GitHub issue must be a JSON object", "E_FEEDBACK_BAD_ITEM", 1);
    const number = pickNumber(record, "number", "id");
    if (number === undefined) {
      throw new SageError("GitHub issue is missing number/id", "E_FEEDBACK_BAD_ITEM", 1);
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
    const author = pickString(user, "login");
    if (author) item.author = author;
    const state = pickString(record, "state");
    if (state) item.state = state;
    const labels = readLabels(record.labels);
    if (labels) item.labels = labels;
    const url = pickString(record, "html_url");
    if (url) item.url = url;
    const createdAt = sanitizeTimestamp(record.created_at);
    if (createdAt) item.createdAt = createdAt;
    const updatedAt = sanitizeTimestamp(record.updated_at);
    if (updatedAt) item.updatedAt = updatedAt;
    return item;
  }

  /** Normalize one PR review comment (`/pulls/comments` shape). */
  normalizeReviewComment(raw: unknown): ExternalFeedback {
    const record = asRecord(raw);
    if (!record) throw new SageError("GitHub review comment must be a JSON object", "E_FEEDBACK_BAD_ITEM", 1);
    const id = pickNumber(record, "id");
    if (id === undefined) {
      throw new SageError("GitHub review comment is missing id", "E_FEEDBACK_BAD_ITEM", 1);
    }
    const user = asRecord(record.user);
    const path = pickString(record, "path");
    const pullRequestUrl = pickString(record, "pull_request_url", "html_url");
    const item: ExternalFeedback = {
      externalId: String(id),
      kind: "pr_review",
      title: path ? `PR review comment on ${path}` : "PR review comment",
      metadata: { isPullRequest: true, ...(path ? { path } : {}), ...(pullRequestUrl ? { pullRequestUrl } : {}) },
    };
    const body = pickString(record, "body");
    if (body) item.body = body;
    const author = pickString(user, "login");
    if (author) item.author = author;
    const url = pickString(record, "html_url");
    if (url) item.url = url;
    const createdAt = sanitizeTimestamp(record.created_at);
    if (createdAt) item.createdAt = createdAt;
    const updatedAt = sanitizeTimestamp(record.updated_at);
    if (updatedAt) item.updatedAt = updatedAt;
    return item;
  }

  async list(input: ListFeedbackInput): Promise<FeedbackPage> {
    const env = this.deps.env ?? process.env;
    const token = (env.GITHUB_TOKEN ?? "").trim() || undefined;
    const baseUrl = (this.deps.baseUrl ?? env.GITHUB_API_URL ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    const pageSize = input.pageSize ?? DEFAULT_PAGE_SIZE;
    const maxPages = input.maxPages ?? DEFAULT_MAX_PAGES;
    const cursor = decodeCursor(input.cursor);
    const [owner, name] = splitRepo(input.repo);

    const issues = await this.listIssues(baseUrl, token, owner, name, cursor.issues, pageSize, maxPages);
    const reviews = await this.listReviewComments(
      baseUrl,
      token,
      owner,
      name,
      cursor.reviews,
      pageSize,
      maxPages,
    );

    return {
      items: [...issues.items, ...reviews.items],
      nextCursor: encodeCursor({
        issues: maxIso(cursor.issues, issues.maxUpdated),
        reviews: maxIso(cursor.reviews, reviews.maxUpdated),
      }),
    };
  }

  private async request(url: string, token: string | undefined): Promise<{
    json: unknown;
    headers: Headers;
  }> {
    const fetchImpl: FetchLike | undefined = this.deps.fetchImpl;
    const response = await httpGetJson({
      url,
      ...(token ? { token } : {}),
      authScheme: "bearer",
      accept: "application/vnd.github+json",
      headers: { "x-github-api-version": "2022-11-28" },
      ...(this.deps.timeoutMs === undefined ? {} : { timeoutMs: this.deps.timeoutMs }),
      ...(fetchImpl ? { fetchImpl } : {}),
    });
    return { json: response.json, headers: response.headers };
  }

  private async listIssues(
    baseUrl: string,
    token: string | undefined,
    owner: string,
    name: string,
    since: string | undefined,
    pageSize: number,
    maxPages: number,
  ): Promise<{ items: ExternalFeedback[]; maxUpdated?: string }> {
    const params = new URLSearchParams({
      state: "all",
      sort: "updated",
      direction: "asc",
      per_page: String(pageSize),
    });
    if (since) params.set("since", since);
    let url: string | null = `${baseUrl}/repos/${owner}/${name}/issues?${params.toString()}`;
    const items: ExternalFeedback[] = [];
    let maxUpdated = since;
    for (let page = 0; page < maxPages && url; page += 1) {
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
      const next = nextLink(response.headers);
      url = next && isSameOrigin(next, baseUrl) ? next : null;
    }
    return { items, ...(maxUpdated ? { maxUpdated } : {}) };
  }

  private async listReviewComments(
    baseUrl: string,
    token: string | undefined,
    owner: string,
    name: string,
    since: string | undefined,
    pageSize: number,
    maxPages: number,
  ): Promise<{ items: ExternalFeedback[]; maxUpdated?: string }> {
    // This endpoint has no `since`; fetch pages and filter against the cursor.
    const params = new URLSearchParams({
      sort: "updated",
      direction: "asc",
      per_page: String(pageSize),
    });
    let url: string | null = `${baseUrl}/repos/${owner}/${name}/pulls/comments?${params.toString()}`;
    const items: ExternalFeedback[] = [];
    let maxUpdated = since;
    for (let page = 0; page < maxPages && url; page += 1) {
      const response = await this.request(url, token);
      const array = expectArray(response.json, "pull comments", url);
      for (const raw of array) {
        try {
          const item = this.normalizeReviewComment(raw);
          maxUpdated = maxIso(maxUpdated, item.updatedAt);
          if (since && item.updatedAt && item.updatedAt < since) continue;
          items.push(item);
        } catch {
          // Skip malformed remote entries.
        }
      }
      const next = nextLink(response.headers);
      url = next && isSameOrigin(next, baseUrl) ? next : null;
    }
    return { items, ...(maxUpdated ? { maxUpdated } : {}) };
  }
}

function splitRepo(repo: string): [string, string] {
  const match = /^([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)$/.exec(repo.trim());
  if (!match) {
    throw new SageError("--repo must look like owner/name", "E_USAGE", 2);
  }
  return [encodeURIComponent(match[1] as string), encodeURIComponent(match[2] as string)];
}
