#!/usr/bin/env node
"use strict";

/**
 * SAGE-Kit SessionStart bridge for Codex / Claude Code host plugins.
 *
 * The host runs this file from a SessionStart hook with the host hook payload
 * on stdin. The bridge is intentionally dumb and bounded:
 *
 *   1. resolve the project directory from `cwd` (host payload, else process cwd);
 *   2. stay silent unless `<project>/.sage-kit/config.json` exists;
 *   3. run `sage-kit brief --json --max-bytes <n>` with a hard timeout;
 *   4. emit the host's `hookSpecificOutput.additionalContext` JSON.
 *
 * It never reads or writes SAGE-Kit state directly, never touches the network
 * and never fails the session: any error/timeout produces `{}` and exit code 0.
 */

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const DEFAULT_MAX_BYTES = 2048;
const MIN_MAX_BYTES = 128;
const MAX_MAX_BYTES = 8192;
const DEFAULT_TIMEOUT_MS = 1500;
const MIN_TIMEOUT_MS = 100;
const MAX_TIMEOUT_MS = 2000;
const STDIN_FALLBACK_MS = 500;
const MAX_STDIN_BYTES = 65536;
const MAX_PARENT_LOOKUPS = 64;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function intFromEnv(name, fallback, min, max) {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? clamp(Math.trunc(parsed), min, max) : fallback;
}

function emit(value) {
  process.stdout.write(JSON.stringify(value));
}

function empty() {
  emit({});
}

function parseCwd(raw) {
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.cwd === "string" && parsed.cwd.length > 0) return path.resolve(parsed.cwd);
  } catch {
    // Malformed host input: fall back to the process working directory.
  }
  return process.cwd();
}

function hasProjectMarker(start) {
  let dir = start;
  for (let index = 0; index < MAX_PARENT_LOOKUPS; index += 1) {
    if (fs.existsSync(path.join(dir, ".sage-kit", "config.json"))) return true;
    const parent = path.dirname(dir);
    if (parent === dir) return false;
    dir = parent;
  }
  return false;
}

function readBrief(cwd, maxBytes) {
  const timeoutMs = intFromEnv("SAGE_KIT_HOOK_TIMEOUT_MS", DEFAULT_TIMEOUT_MS, MIN_TIMEOUT_MS, MAX_TIMEOUT_MS);
  const explicit = process.env.SAGE_KIT_BIN;
  const args = ["brief", "--json", "--require-initialized", "--max-bytes", String(maxBytes)];
  let command;
  let options = { cwd, encoding: "utf8", timeout: timeoutMs, windowsHide: true, maxBuffer: 1024 * 1024 };
  if (explicit) {
    if (/\.(c|m)?js$/i.test(explicit)) {
      command = process.execPath;
      args.unshift(explicit);
    } else {
      command = explicit;
    }
  } else {
    command = "sage-kit";
    if (process.platform === "win32") options = Object.assign({}, options, { shell: true });
  }
  const result = spawnSync(command, args, options);
  if (!result || result.error || result.status !== 0 || typeof result.stdout !== "string") return null;
  try {
    const parsed = JSON.parse(result.stdout);
    if (parsed && typeof parsed.text === "string" && parsed.text.trim().length > 0) return parsed.text;
  } catch {
    // Non-JSON output from an older CLI: fail open with no injection.
  }
  return null;
}

function truncateUtf8(text, maxBytes) {
  const buffer = Buffer.from(text, "utf8");
  if (buffer.length <= maxBytes) return text;
  let end = maxBytes;
  while (end > 0 && ((buffer[end] || 0) & 0xc0) === 0x80) end -= 1;
  return buffer.subarray(0, end).toString("utf8");
}

function hasGitMarker(start) {
  let dir = start;
  for (let index = 0; index < MAX_PARENT_LOOKUPS; index += 1) {
    if (fs.existsSync(path.join(dir, ".git"))) return true;
    const parent = path.dirname(dir);
    if (parent === dir) return false;
    dir = parent;
  }
  return false;
}

function finish(raw) {
  try {
    const cwd = parseCwd(raw);
    // A linked worktree has a `.git` file and may resolve to a main worktree
    // outside this directory ancestry. The CLI resolves that root and checks
    // its config before generating a brief, including in a plain Git repo.
    if (!hasProjectMarker(cwd) && !hasGitMarker(cwd)) return empty();
    const maxBytes = intFromEnv("SAGE_KIT_BRIEF_MAX_BYTES", DEFAULT_MAX_BYTES, MIN_MAX_BYTES, MAX_MAX_BYTES);
    const text = readBrief(cwd, maxBytes);
    if (!text) return empty();
    emit({
      hookSpecificOutput: {
        hookEventName: "SessionStart",
        additionalContext: truncateUtf8(text.trim(), maxBytes),
      },
    });
  } catch {
    empty();
  }
}

function main() {
  if (process.stdin.isTTY) {
    finish("");
    return;
  }
  let raw = "";
  let settled = false;
  const done = () => {
    if (settled) return;
    settled = true;
    clearTimeout(timer);
    try {
      process.stdin.destroy();
    } catch {
      // stdin was already closed by the host.
    }
    finish(raw);
  };
  const timer = setTimeout(done, STDIN_FALLBACK_MS);
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => {
    if (raw.length < MAX_STDIN_BYTES) raw += chunk;
  });
  process.stdin.on("end", done);
  process.stdin.on("error", done);
}

try {
  main();
} catch {
  empty();
}
