import { timingSafeEqual } from "node:crypto";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { SageError } from "../core/errors.js";
import type { TaskStatus } from "../core/tasks.js";
import { MAX_HTTP_BODY_BYTES } from "./schema.js";
import type { ControlStore } from "./store.js";

const LOOPBACK_HOST = "127.0.0.1";
const LOOPBACK_CLIENTS = new Set(["127.0.0.1", "::1", "::ffff:127.0.0.1"]);
const LOOPBACK_HOST_HEADERS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);
const BEARER_PATTERN = /^Bearer\s+(.+)$/i;

export interface ControlServerOptions {
  store: ControlStore;
  token: string;
  host?: string;
  port?: number;
}

export interface ControlServer {
  readonly server: Server;
  readonly host: string;
  readonly port: number;
  readonly url: string;
  close(): Promise<void>;
}

interface HealthPayload {
  ok: true;
  service: "sage-kit-control";
  apiVersion: number;
  schemaVersion: number;
  now: string;
}

function requireToken(token: unknown): string {
  if (typeof token !== "string" || token.trim().length === 0) {
    throw new SageError("A non-empty control API Bearer token is required", "E_BAD_TOKEN", 2);
  }
  const value = token.trim();
  if (value.length > 512) throw new SageError("Control API token must be <= 512 characters", "E_BAD_TOKEN", 2);
  return value;
}

function isLoopbackAddress(address: string | undefined): boolean {
  return address !== undefined && LOOPBACK_CLIENTS.has(address);
}

function authorized(req: IncomingMessage, token: string): boolean {
  const header = req.headers.authorization;
  if (typeof header !== "string") return false;
  const match = BEARER_PATTERN.exec(header.trim());
  if (!match) return false;
  const provided = Buffer.from((match[1] ?? "").trim(), "utf8");
  const expected = Buffer.from(token, "utf8");
  if (provided.length !== expected.length) return false;
  return timingSafeEqual(provided, expected);
}

/** DNS-rebinding guard: a loopback-bound server must only see loopback Host names. */
function requireLoopbackHost(req: IncomingMessage): void {
  const header = req.headers.host;
  if (typeof header !== "string" || header.length === 0) return;
  const hostnamePart = header.startsWith("[") ? header.slice(0, header.indexOf("]") + 1) : header.split(":")[0];
  const normalized = (hostnamePart ?? "").toLowerCase();
  if (!LOOPBACK_HOST_HEADERS.has(normalized)) {
    throw new SageError("Control API only accepts loopback Host headers", "E_NON_LOOPBACK", 1);
  }
}

function sendJson(res: ServerResponse, status: number, payload: unknown): void {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body, "utf8"),
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  res.end(body);
}

function sendError(res: ServerResponse, status: number, code: string, message: string): void {
  sendJson(res, status, { error: { code, message } });
}

function statusForError(code: string): number {
  if (code === "E_UNAUTHORIZED" || code === "E_BAD_TOKEN") return 401;
  if (code === "E_NON_LOOPBACK" || code === "E_FORBIDDEN") return 403;
  if (code === "E_NOT_FOUND" || code === "E_TASK_NOT_FOUND" || code === "E_RUN_NOT_FOUND" || code === "E_LEASE_NOT_HELD") {
    return 404;
  }
  if (code === "E_METHOD_NOT_ALLOWED") return 405;
  if (code === "E_BODY_TOO_LARGE") return 413;
  if (
    [
      "E_LEASE_HELD",
      "E_LEASE_EXPIRED",
      "E_LEASE_OWNER_MISMATCH",
      "E_BAD_TRANSITION",
      "E_TASK_EXISTS",
      "E_RUN_EXISTS",
      "E_TASK_VERSION_CONFLICT",
      "E_RUN_ALREADY_FINISHED",
      "E_DONE_WITHOUT_EVIDENCE",
      "E_EVENT_SCOPE_MISMATCH",
    ].includes(code)
  ) {
    return 409;
  }
  if (code.startsWith("E_BAD_") || code === "E_USAGE" || code === "E_INVALID_REQUEST") return 400;
  return 500;
}

function readRequestBody(req: IncomingMessage): Promise<Buffer> {
  const declared = req.headers["content-length"];
  if (typeof declared === "string" && Number(declared) > MAX_HTTP_BODY_BYTES) {
    return Promise.reject(new SageError(`Request body exceeds ${MAX_HTTP_BODY_BYTES} bytes`, "E_BODY_TOO_LARGE", 1));
  }
  return new Promise<Buffer>((resolvePromise, reject) => {
    const chunks: Buffer[] = [];
    let total = 0;
    let settled = false;
    const cleanup = (): void => {
      req.off("data", onData);
      req.off("end", onEnd);
      req.off("error", onError);
    };
    const fail = (error: Error): void => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    };
    const onData = (chunk: Buffer): void => {
      total += chunk.length;
      if (total > MAX_HTTP_BODY_BYTES) {
        fail(new SageError(`Request body exceeds ${MAX_HTTP_BODY_BYTES} bytes`, "E_BODY_TOO_LARGE", 1));
        return;
      }
      chunks.push(chunk);
    };
    const onEnd = (): void => {
      if (settled) return;
      settled = true;
      cleanup();
      resolvePromise(Buffer.concat(chunks));
    };
    const onError = (error: Error): void => {
      fail(error);
    };
    req.on("data", onData);
    req.on("end", onEnd);
    req.on("error", onError);
  });
}

async function readJsonObject(req: IncomingMessage): Promise<Record<string, unknown>> {
  const raw = await readRequestBody(req);
  const text = raw.toString("utf8").trim();
  if (!text) throw new SageError("Request body is required", "E_BAD_REQUEST", 1);
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch (error) {
    throw new SageError(`Request body must be valid JSON: ${(error as Error).message}`, "E_BAD_JSON", 1);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new SageError("Request body must be a JSON object", "E_BAD_JSON", 1);
  }
  return parsed as Record<string, unknown>;
}

function requireBodyString(body: Record<string, unknown>, key: string, max: number): string {
  const value = body[key];
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new SageError(`Body field "${key}" is required and must be a non-empty string`, "E_BAD_REQUEST", 2);
  }
  const text = value.trim();
  if (text.length > max) throw new SageError(`Body field "${key}" must be <= ${max} characters`, "E_BAD_REQUEST", 2);
  return text;
}

function optionalBodyString(body: Record<string, unknown>, key: string, max: number): string | undefined {
  const value = body[key];
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "string") throw new SageError(`Body field "${key}" must be a string`, "E_BAD_REQUEST", 2);
  const text = value.trim();
  if (!text) return undefined;
  if (text.length > max) throw new SageError(`Body field "${key}" must be <= ${max} characters`, "E_BAD_REQUEST", 2);
  return text;
}

function optionalBodyNumber(body: Record<string, unknown>, key: string): number | undefined {
  const value = body[key];
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new SageError(`Body field "${key}" must be a finite number`, "E_BAD_REQUEST", 2);
  }
  return value;
}

function methodNotAllowed(res: ServerResponse, allowed: string[]): void {
  res.setHeader("allow", allowed.join(", "));
  sendError(res, 405, "E_METHOD_NOT_ALLOWED", `Allowed methods: ${allowed.join(", ")}`);
}

async function route(req: IncomingMessage, res: ServerResponse, store: ControlStore, token: string): Promise<void> {
  try {
    if (!isLoopbackAddress(req.socket.remoteAddress)) {
      throw new SageError("Control API accepts loopback connections only", "E_NON_LOOPBACK", 1);
    }
    requireLoopbackHost(req);
    if (!authorized(req, token)) {
      throw new SageError("Missing or invalid Authorization: Bearer token", "E_UNAUTHORIZED", 1);
    }
    let url: URL;
    try {
      url = new URL(req.url ?? "/", `http://${LOOPBACK_HOST}`);
    } catch {
      throw new SageError("Malformed request URL", "E_BAD_REQUEST", 1);
    }
    const pathname = url.pathname;
    const method = (req.method ?? "GET").toUpperCase();

    if (pathname === "/v1/health") {
      if (method !== "GET") return methodNotAllowed(res, ["GET"]);
      const payload: HealthPayload = {
        ok: true,
        service: "sage-kit-control",
        apiVersion: 1,
        schemaVersion: store.debugInfo().userVersion,
        now: store.nowIso(),
      };
      sendJson(res, 200, payload);
      return;
    }
    if (pathname === "/v1/tasks") {
      if (method !== "GET") return methodNotAllowed(res, ["GET"]);
      const status = url.searchParams.get("status");
      const tasks = store.listTasks(status === null ? {} : { status: status as TaskStatus });
      sendJson(res, 200, { tasks });
      return;
    }
    if (pathname.startsWith("/v1/tasks/")) {
      if (method !== "GET") return methodNotAllowed(res, ["GET"]);
      const id = pathname.slice("/v1/tasks/".length);
      sendJson(res, 200, { task: store.getTask(id) });
      return;
    }
    if (pathname === "/v1/leases/acquire") {
      if (method !== "POST") return methodNotAllowed(res, ["POST"]);
      const body = await readJsonObject(req);
      const taskId = requireBodyString(body, "taskId", 64);
      const owner = requireBodyString(body, "owner", 200);
      const runId = optionalBodyString(body, "runId", 64);
      const ttlMs = optionalBodyNumber(body, "ttlMs");
      const lease = store.acquireLease(taskId, {
        owner,
        ...(runId !== undefined ? { runId } : {}),
        ...(ttlMs !== undefined ? { ttlMs } : {}),
      });
      sendJson(res, 200, { lease });
      return;
    }
    if (pathname === "/v1/leases/release") {
      if (method !== "POST") return methodNotAllowed(res, ["POST"]);
      const body = await readJsonObject(req);
      const taskId = requireBodyString(body, "taskId", 64);
      const owner = optionalBodyString(body, "owner", 200);
      const lease = store.releaseLease(taskId, owner === undefined ? {} : { owner });
      sendJson(res, 200, { released: true, lease });
      return;
    }
    throw new SageError(`Unknown control API route: ${pathname}`, "E_NOT_FOUND", 1);
  } catch (error) {
    const sage = error instanceof SageError ? error : new SageError("Internal control server error", "E_INTERNAL", 1);
    if (!res.headersSent) {
      sendError(res, statusForError(sage.code), sage.code, sage.message);
    } else if (!res.writableEnded) {
      res.end();
    }
    if (sage.code === "E_BODY_TOO_LARGE") req.resume();
  }
}

/**
 * Start the minimal local control API.
 *
 * - Binds `127.0.0.1` only; any other `host` is rejected before listening.
 * - Every request (including health) needs `Authorization: Bearer <token>`.
 * - Loopback socket + loopback Host header are both required.
 * - JSON in, JSON out; unknown paths -> 404; wrong methods -> 405.
 */
export async function createControlServer(options: ControlServerOptions): Promise<ControlServer> {
  if (!options || typeof options !== "object") {
    throw new SageError("createControlServer requires options", "E_BAD_CONFIG", 2);
  }
  const store = options.store;
  if (
    !store ||
    typeof store.getTask !== "function" ||
    typeof store.listTasks !== "function" ||
    typeof store.acquireLease !== "function" ||
    typeof store.releaseLease !== "function" ||
    typeof store.debugInfo !== "function"
  ) {
    throw new SageError("createControlServer requires an open ControlStore", "E_BAD_CONFIG", 2);
  }
  const token = requireToken(options.token);
  const host = options.host ?? LOOPBACK_HOST;
  if (host !== LOOPBACK_HOST) {
    throw new SageError(`Control API must bind ${LOOPBACK_HOST} only (got ${host})`, "E_BAD_HOST", 2);
  }
  const port = options.port ?? 0;
  if (!Number.isInteger(port) || port < 0 || port > 65_535) {
    throw new SageError("port must be an integer between 0 and 65535", "E_BAD_PORT", 2);
  }
  const server = createServer((req, res) => {
    void route(req, res, store, token);
  });
  server.on("clientError", (_error, socket) => {
    if (socket.writable) socket.end("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n");
  });
  await new Promise<void>((resolvePromise, reject) => {
    const onError = (error: Error): void => {
      server.off("listening", onListening);
      reject(new SageError(`Cannot start control server: ${error.message}`, "E_LISTEN_FAILED", 1));
    };
    const onListening = (): void => {
      server.off("error", onError);
      resolvePromise();
    };
    server.once("error", onError);
    server.once("listening", onListening);
    server.listen(port, host);
  });
  const address = server.address();
  if (!address || typeof address === "string") {
    server.close();
    throw new SageError("Control server has no TCP address", "E_LISTEN_FAILED", 1);
  }
  if (!isLoopbackAddress(address.address)) {
    server.close();
    throw new SageError(`Control server bound to non-loopback address ${address.address}`, "E_BAD_HOST", 1);
  }
  return {
    server,
    host: LOOPBACK_HOST,
    port: address.port,
    url: `http://${LOOPBACK_HOST}:${address.port}`,
    async close(): Promise<void> {
      if (!server.listening) return;
      server.closeIdleConnections();
      await new Promise<void>((resolvePromise) => {
        server.close(() => resolvePromise());
      });
    },
  };
}
