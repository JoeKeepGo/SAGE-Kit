import {
  access,
  appendFile,
  copyFile,
  mkdir,
  open,
  readdir,
  readFile,
  rename,
  rm,
  stat,
  unlink,
  writeFile,
} from "node:fs/promises";
import { constants as fsConstants } from "node:fs";
import { createHash, randomBytes } from "node:crypto";
import { dirname, join, relative, resolve, sep } from "node:path";
import { SageError } from "./errors.js";

export async function exists(path: string): Promise<boolean> {
  try {
    await access(path, fsConstants.F_OK);
    return true;
  } catch {
    return false;
  }
}

export async function ensureDir(path: string): Promise<void> {
  await mkdir(path, { recursive: true });
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function randomToken(): string {
  return randomBytes(8).toString("hex");
}

export function sha256(value: string | Buffer): string {
  return createHash("sha256").update(value).digest("hex");
}

export async function readJsonFile<T>(path: string): Promise<T> {
  const text = await readFile(path, "utf8");
  try {
    return JSON.parse(text) as T;
  } catch (error) {
    throw new SageError(`Invalid JSON in ${path}: ${(error as Error).message}`, "E_BAD_JSON", 1);
  }
}

export async function writeJsonAtomic(path: string, value: unknown): Promise<void> {
  await atomicWrite(path, `${JSON.stringify(value, null, 2)}\n`);
}

export async function atomicWrite(path: string, content: string, mode = 0o644): Promise<void> {
  await ensureDir(dirname(path));
  const temporary = `${path}.${process.pid}.${randomToken()}.tmp`;
  let handle: Awaited<ReturnType<typeof open>> | undefined;
  try {
    handle = await open(temporary, "w", mode);
    await handle.writeFile(content, "utf8");
    await handle.sync();
    await handle.close();
    handle = undefined;
    await rename(temporary, path);
  } catch (error) {
    if (handle) await handle.close().catch(() => undefined);
    await unlink(temporary).catch(() => undefined);
    throw error;
  }
}

export async function appendLine(path: string, line: string): Promise<void> {
  await ensureDir(dirname(path));
  const handle = await open(path, "a", 0o600);
  try {
    await handle.writeFile(`${line.replace(/\r?\n/g, " ")}\n`, "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
}

export async function readText(path: string): Promise<string> {
  return readFile(path, "utf8");
}

export async function copyDirectory(source: string, target: string): Promise<string[]> {
  const files: string[] = [];
  await ensureDir(target);
  const entries = await readdir(source, { withFileTypes: true });
  for (const entry of entries) {
    const from = join(source, entry.name);
    const to = join(target, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await copyDirectory(from, to)));
    } else if (entry.isFile()) {
      await copyFile(from, to);
      files.push(relative(source, from).split(sep).join("/"));
    }
  }
  return files;
}

export async function removePath(path: string): Promise<void> {
  await rm(path, { recursive: true, force: true });
}

export function isPathInside(parent: string, child: string): boolean {
  const base = resolve(parent);
  const target = resolve(child);
  return target === base || target.startsWith(base + sep);
}

export function validateId(id: string): string {
  if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(id)) {
    throw new SageError(
      "Task id must match [a-z0-9][a-z0-9-]{0,63}",
      "E_BAD_TASK_ID",
      2,
    );
  }
  return id;
}

export function validateTaskId(id: string): string {
  return validateId(id);
}

export function truncateUtf8(text: string, maxBytes: number): { text: string; truncated: boolean } {
  const buffer = Buffer.from(text, "utf8");
  if (buffer.length <= maxBytes) return { text, truncated: false };
  let end = maxBytes;
  while (end > 0 && (buffer[end] ?? 0) >= 0x80 && (buffer[end] ?? 0) < 0xc0) end -= 1;
  const suffix = "\n…[truncated]";
  const suffixBytes = Buffer.byteLength(suffix, "utf8");
  const sliced = buffer.subarray(0, Math.max(0, maxBytes - suffixBytes)).toString("utf8");
  return { text: `${sliced}${suffix}`, truncated: true };
}

export function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export async function fileSize(path: string): Promise<number> {
  try {
    return (await stat(path)).size;
  } catch {
    return 0;
  }
}

export async function safeAppend(path: string, text: string): Promise<void> {
  await ensureDir(dirname(path));
  await appendFile(path, text, "utf8");
}

export function redactString(value: string): string {
  // Keep URLs and paths useful, but remove credential-looking values.
  return value
    .replace(/((?:password|passwd|token|secret|authorization|api[_-]?key)\s*[=:]\s*)([^\s,;]+)/gi, "$1[REDACTED]")
    .replace(/\b(sk-[A-Za-z0-9_-]{8,})\b/g, "[REDACTED]")
    .slice(0, 500);
}

export function redactRecord(value: unknown, depth = 0): unknown {
  if (depth > 4) return "[TRUNCATED]";
  if (typeof value === "string") return redactString(value);
  if (Array.isArray(value)) return value.slice(0, 20).map((item) => redactRecord(item, depth + 1));
  if (value && typeof value === "object") {
    const output: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>).slice(0, 30)) {
      if (/password|passwd|token|secret|authorization|api[_-]?key/i.test(key)) {
        output[key] = "[REDACTED]";
      } else {
        output[key] = redactRecord(item, depth + 1);
      }
    }
    return output;
  }
  return value;
}
