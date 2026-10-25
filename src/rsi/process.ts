/**
 * Fixed-command runner for the Evaluator.
 *
 * The command array comes from the evaluator wiring (never from a proposal) and
 * is always spawned without a shell. Output is captured tail-first so a noisy
 * suite cannot exhaust memory; the caller truncates further before persisting.
 *
 * Timeout behaviour: terminate the POSIX process group or Windows direct child,
 * then bound the wait for inherited output pipes (docs/m3-rsi.md §12).
 */
import { spawn } from "node:child_process";

export interface FixedCommandResult {
  exitCode: number | null;
  signal: string | null;
  stdout: string;
  stderr: string;
  durationMs: number;
  timedOut: boolean;
  /** Set when the process could not be spawned at all (e.g. ENOENT). */
  spawnError?: string;
}

const MAX_CAPTURE_CHARS = 200_000;
const KILL_GRACE_MS = 2_000;

/**
 * Host test-runner variables must not leak into the fixed suite: when the RSI
 * evaluator itself runs under `node --test`, the inherited `NODE_TEST_CONTEXT`
 * makes a nested `node --test` believe it is a runner child and exit 0 without
 * executing the fixture suite. The evaluator therefore strips the host test
 * context and runs the suite with a clean, offline-friendly environment.
 */
function fixedCommandEnvironment(): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env, GIT_TERMINAL_PROMPT: "0" };
  delete env.NODE_TEST_CONTEXT;
  delete env.NODE_TEST_REPORTER;
  delete env.NODE_V8_COVERAGE;
  return env;
}

export function runFixedCommand(
  command: readonly string[],
  cwd: string,
  options: { timeoutMs: number },
): Promise<FixedCommandResult> {
  const startedAt = Date.now();
  return new Promise((resolvePromise) => {
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    let spawnError: string | undefined;
    let settled = false;
    let timer: NodeJS.Timeout | undefined;
    let killTimer: NodeJS.Timeout | undefined;
    let closeTimer: NodeJS.Timeout | undefined;

    const child = spawn(command[0] as string, command.slice(1), {
      cwd,
      shell: false,
      windowsHide: true,
      detached: process.platform !== "win32",
      stdio: ["ignore", "pipe", "pipe"],
      env: fixedCommandEnvironment(),
    });

    const settle = (exitCode: number | null, signal: string | null): void => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      if (killTimer) clearTimeout(killTimer);
      if (closeTimer) clearTimeout(closeTimer);
      resolvePromise({
        exitCode,
        signal,
        stdout,
        stderr,
        durationMs: Date.now() - startedAt,
        timedOut,
        ...(spawnError === undefined ? {} : { spawnError }),
      });
    };

    timer = setTimeout(() => {
      timedOut = true;
      if (child.pid) {
        try {
          if (process.platform === "win32") child.kill("SIGTERM");
          else process.kill(-child.pid, "SIGTERM");
        } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== "ESRCH") {
            stderr = `${stderr}\nProcess-group termination failed: ${(error as Error).message}`.slice(-MAX_CAPTURE_CHARS);
          }
        }
      }
      killTimer = setTimeout(() => {
        if (child.pid) {
          try {
            if (process.platform === "win32") child.kill("SIGKILL");
            else process.kill(-child.pid, "SIGKILL");
          } catch (error) {
            if ((error as NodeJS.ErrnoException).code !== "ESRCH") {
              stderr = `${stderr}\nProcess-group kill failed: ${(error as Error).message}`.slice(-MAX_CAPTURE_CHARS);
            }
          }
        }
        closeTimer = setTimeout(() => {
          stderr = `${stderr}\nProcess cleanup deadline expired; descendants may still be running (unresolved inherited output pipes).`.slice(-MAX_CAPTURE_CHARS);
          child.stdout?.destroy();
          child.stderr?.destroy();
          child.unref();
          settle(child.exitCode, child.signalCode);
        }, KILL_GRACE_MS);
      }, KILL_GRACE_MS);
    }, options.timeoutMs);

    child.stdout?.on("data", (chunk: Buffer) => {
      stdout = `${stdout}${chunk.toString("utf8")}`.slice(-MAX_CAPTURE_CHARS);
    });
    child.stderr?.on("data", (chunk: Buffer) => {
      stderr = `${stderr}${chunk.toString("utf8")}`.slice(-MAX_CAPTURE_CHARS);
    });
    child.on("error", (error) => {
      spawnError = error.message;
      settle(null, null);
    });
    child.on("close", (code, signal) => {
      settle(code, signal);
    });
  });
}
