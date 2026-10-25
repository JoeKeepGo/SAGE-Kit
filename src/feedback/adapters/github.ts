/**
 * GitHub REST feedback adapter (read-only).
 *
 * Endpoints (assumption checked against the public GitHub REST docs):
 *   GET /repos/{owner}/{repo}/issues?state=all&sort=updated&direction=asc
 *       + per_page, optional since, Link: rel="next" pagination
 *   GET /repos/{owner}/{repo}/pulls/comments?sort=updated&direction=asc
 *       + per_page, since, Link pagination. Review comments are re-read from
 *       page 1 on every sync, first using the updated-time watermark and then
 *       reconciling the full history, rather than resuming a page number. An edit or
 *       delete can move an item between pages; a page cursor would skip it
 *       permanently.
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
// Review comments are scanned until GitHub stops returning a next link. A
// fixed page resume point is unsafe because edits/deletes move items between
// pages; the hard cap only prevents a malformed Link header loop.
const MAX_REVIEW_PAGES = 1_000;

interface GitHubCursor {
  issues?: string;
  reviews?: string;
  /** Legacy page cursor from before the watermark-only review scan. Kept so old state decodes. */
  reviewsPage?: number;
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
    const reviewsPage = record.reviewsPage;
    if (issues) result.issues = issues;
    if (reviews) result.reviews = reviews;
    if (typeof reviewsPage === "number" && Number.isSafeInteger(reviewsPage) && reviewsPage > 0) {
      result.reviewsPage = reviewsPage;
    }
    return result;
  } catch {
    return {};
  }
}

function encodeCursor(cursor: GitHubCursor): string {
  return JSON.stringify({
    issues: cursor.issues ?? null,
    reviews: cursor.reviews ?? null,
    reviewsPage: cursor.reviewsPage ?? null,
  });
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
        // Every review sync also re-reads the full history. Never resume a
        // mutable page number or assume a time overlap is being subtracted.
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
    // Like review comments, the issue list is mutable and updated-sorted. A
    // watermark scan can skip an item when an edit moves it across a page
    // boundary. A truncated or page-shifted scan cannot establish a watermark;
    // require a complete, unshifted full reconciliation in that case.
    const first = await this.scanIssues(baseUrl, token, owner, name, since, pageSize, maxPages);
    if (first.complete && !first.pageShifted) {
      return { items: first.items, ...(first.maxUpdated ? { maxUpdated: first.maxUpdated } : {}) };
    }
    const second = await this.scanIssues(baseUrl, token, owner, name, undefined, pageSize, maxPages);
    if (!second.complete || second.pageShifted) {
      throw new SageError(
        !second.complete
          ? `Issue reconciliation did not reach the end within ${maxPages} pages; refusing to advance the cursor`
          : "Issue reconciliation observed a page shift; refusing to advance the cursor",
        !second.complete ? "E_FEEDBACK_PAGE_LIMIT" : "E_FEEDBACK_PAGE_SHIFT",
        1,
      );
    }
    const byId = new Map<string, ExternalFeedback>();
    for (const item of [...first.items, ...second.items]) byId.set(item.externalId, item);
    const maxUpdated = maxIso(first.maxUpdated, second.maxUpdated);
    return { items: [...byId.values()], ...(maxUpdated ? { maxUpdated } : {}) };
  }

  private async scanIssues(
    baseUrl: string,
    token: string | undefined,
    owner: string,
    name: string,
    since: string | undefined,
    pageSize: number,
    maxPages: number,
  ): Promise<{ items: ExternalFeedback[]; maxUpdated?: string; complete: boolean; pageShifted: boolean }> {
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
    const seen = new Set<string>();
    let pageShifted = false;
    let complete = false;
    for (let page = 0; page < maxPages && url; page += 1) {
      const response = await this.request(url, token);
      const array = expectArray(response.json, "issues", url);
      const pageIds = new Set<string>();
      for (const raw of array) {
        try {
          const item = this.normalize(raw);
          if (seen.has(item.externalId)) pageShifted = true;
          pageIds.add(item.externalId);
          items.push(item);
          maxUpdated = maxIso(maxUpdated, item.updatedAt);
        } catch {
          // One malformed remote entry must not block the rest of the sync.
        }
      }
      for (const id of pageIds) seen.add(id);
      const next = nextLink(response.headers);
      complete = next === null;
      url = next && isSameOrigin(next, baseUrl) ? next : null;
    }
    return { items, ...(maxUpdated ? { maxUpdated } : {}), complete, pageShifted };
  }

  private async listReviewComments(
    baseUrl: string,
    token: string | undefined,
    owner: string,
    name: string,
    since: string | undefined,
    pageSize: number,
    _maxPages: number,
  ): Promise<{ items: ExternalFeedback[]; maxUpdated?: string }> {
    // Review comments are a mutable, updated-sorted collection. A single
    // watermark scan can skip an item when an edit moves it between pages
    // (`since` then excludes it permanently). Re-scan the full collection once
    // without `since` and merge by external id; the cursor is only advanced
    // after both passes complete. `maxPages` is intentionally not applied here:
    // a bounded page cap must fail rather than claim a partial collection is
    // complete.
    const first = await this.scanReviewComments(baseUrl, token, owner, name, since, pageSize);
    const second = await this.scanReviewComments(baseUrl, token, owner, name, undefined, pageSize);
    const byId = new Map<string, ExternalFeedback>();
    for (const item of [...first.items, ...second.items]) byId.set(item.externalId, item);
    const maxUpdated = maxIso(first.maxUpdated, second.maxUpdated);
    return { items: [...byId.values()], ...(maxUpdated ? { maxUpdated } : {}) };
  }

  private async scanReviewComments(
    baseUrl: string,
    token: string | undefined,
    owner: string,
    name: string,
    since: string | undefined,
    pageSize: number,
  ): Promise<{ items: ExternalFeedback[]; maxUpdated?: string }> {
    const params = new URLSearchParams({
      sort: "updated",
      direction: "asc",
      per_page: String(pageSize),
    });
    if (since) params.set("since", since);
    let url: string | null = `${baseUrl}/repos/${owner}/${name}/pulls/comments?${params.toString()}`;
    const items: ExternalFeedback[] = [];
    let maxUpdated = since;
    for (let fetched = 0; fetched < MAX_REVIEW_PAGES && url; fetched += 1) {
      const response = await this.request(url, token);
      const array = expectArray(response.json, "pull comments", url);
      for (const raw of array) {
        try {
          const item = this.normalizeReviewComment(raw);
          maxUpdated = maxIso(maxUpdated, item.updatedAt);
          items.push(item);
        } catch {
          // Skip malformed remote entries.
        }
      }
      const next = nextLink(response.headers);
      url = next && isSameOrigin(next, baseUrl) ? next : null;
    }
    if (url) {
      throw new SageError(
        `Review comment scan exceeded ${MAX_REVIEW_PAGES} pages; refusing to advance the cursor`,
        "E_FEEDBACK_PAGE_LIMIT",
        1,
      );
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

