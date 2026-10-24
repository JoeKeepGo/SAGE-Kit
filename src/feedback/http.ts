/**
 * Minimal read-only HTTP helper for the feedback adapters.
 *
 * - one GET per call, 15s default timeout via AbortSignal.timeout
 * - tokens live only in request headers; error messages and bodies are
 *   sanitized so a token can never be logged or persisted
 * - only same-origin `Link: rel="next"` URLs are followed (no token leaks to a
 *   third-party host)
 */
import { redactString } from "../core/fs-utils.js";
import { SageError } from "../core/errors.js";

export type FetchLike = typeof fetch;

export interface HttpGetOptions {
  url: string;
  token?: string;
  authScheme?: "bearer" | "token";
  accept?: string;
  timeoutMs?: number;
  fetchImpl?: FetchLike;
  headers?: Record<string, string>;
}

export interface HttpJsonResponse {
  status: number;
  headers: Headers;
  json: unknown;
  url: string;
}

const DEFAULT_TIMEOUT_MS = 15_000;

function urlPath(url: string): string {
  try {
    const parsed = new URL(url);
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return "invalid-url";
  }
}

export function sanitizeHttpText(text: string, token?: string): string {
  const withoutToken = token ? text.split(token).join("[REDACTED]") : text;
  return redactString(withoutToken.replace(/\s+/g, " ").trim()).slice(0, 300);
}

function safeError(error: unknown, token: string | undefined, url: string, timeoutMs: number): SageError {
  const name = (error as { name?: string } | undefined)?.name;
  if (name === "TimeoutError" || name === "AbortError") {
    return new SageError(
      `Feedback request timed out after ${timeoutMs}ms (${urlPath(url)})`,
      "E_FEEDBACK_TIMEOUT",
      1,
    );
  }
  const message = sanitizeHttpText((error as Error | undefined)?.message ?? String(error), token);
  return new SageError(`Feedback request failed: ${message} (${urlPath(url)})`, "E_FEEDBACK_NETWORK", 1);
}

export async function httpGetJson(options: HttpGetOptions): Promise<HttpJsonResponse> {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const headers: Record<string, string> = {
    accept: options.accept ?? "application/json",
    "user-agent": "sage-kit-feedback/0.1",
    ...(options.headers ?? {}),
  };
  if (options.token) {
    headers.authorization =
      options.authScheme === "token" ? `token ${options.token}` : `Bearer ${options.token}`;
  }

  let response: Response;
  try {
    response = await fetchImpl(options.url, {
      method: "GET",
      headers,
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    throw safeError(error, options.token, options.url, timeoutMs);
  }

  let text: string;
  try {
    text = await response.text();
  } catch (error) {
    throw safeError(error, options.token, options.url, timeoutMs);
  }

  if (!response.ok) {
    const excerpt = text.trim() ? `: ${sanitizeHttpText(text, options.token)}` : "";
    throw new SageError(
      `Feedback request failed: HTTP ${response.status} ${response.statusText} (${urlPath(options.url)})${excerpt}`,
      "E_FEEDBACK_HTTP",
      1,
    );
  }

  let json: unknown = null;
  if (text.trim()) {
    try {
      json = JSON.parse(text) as unknown;
    } catch {
      throw new SageError(
        `Feedback response was not valid JSON (${urlPath(options.url)})`,
        "E_FEEDBACK_BAD_RESPONSE",
        1,
      );
    }
  }
  return { status: response.status, headers: response.headers, json, url: options.url };
}

/** Parse RFC 5988 `Link: <url>; rel="next"`, if present. */
export function nextLink(headers: Headers): string | null {
  const header = headers.get("link");
  if (!header) return null;
  for (const part of header.split(",")) {
    const match = /<([^>]+)>\s*;\s*rel\s*=\s*"?next"?/i.exec(part.trim());
    if (match?.[1]) return match[1];
  }
  return null;
}

export function isSameOrigin(candidate: string, baseUrl: string): boolean {
  try {
    return new URL(candidate).origin === new URL(baseUrl).origin;
  } catch {
    return false;
  }
}

export function expectArray(value: unknown, label: string, url: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new SageError(
      `Feedback response was not a JSON array (${label}; ${urlPath(url)})`,
      "E_FEEDBACK_BAD_RESPONSE",
      1,
    );
  }
  return value;
}

export function expectObject(value: unknown, label: string, url: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new SageError(
      `Feedback response was not a JSON object (${label}; ${urlPath(url)})`,
      "E_FEEDBACK_BAD_RESPONSE",
      1,
    );
  }
  return value as Record<string, unknown>;
}
