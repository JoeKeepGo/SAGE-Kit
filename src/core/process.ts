import { spawn } from "node:child_process";

export interface ProcessResult {
  code: number | null;
  signal: NodeJS.Signals | null;
  stdout: string;
  stderr: string;
}

export function runCommand(
  command: string,
  args: string[],
  cwd: string,
  options: { timeoutMs?: number; env?: NodeJS.ProcessEnv } = {},
): Promise<ProcessResult> {
  return new Promise((resolvePromise) => {
    const child = spawn(command, args, {
      cwd,
      shell: false,
      windowsHide: true,
      env: { ...process.env, GIT_TERMINAL_PROMPT: "0", ...options.env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const finish = (code: number | null, signal: NodeJS.Signals | null): void => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolvePromise({ code, signal, stdout, stderr });
    };
    const timer = options.timeoutMs
      ? setTimeout(() => {
          child.kill();
          finish(null, "SIGTERM");
        }, options.timeoutMs)
      : undefined;
    child.stdout?.on("data", (chunk: Buffer) => {
      stdout = (stdout + chunk.toString()).slice(-200_000);
    });
    child.stderr?.on("data", (chunk: Buffer) => {
      stderr = (stderr + chunk.toString()).slice(-200_000);
    });
    child.on("error", (error) => {
      stderr += `${error.message}\n`;
      finish(null, null);
    });
    child.on("close", (code, signal) => finish(code, signal));
  });
}

export async function git(cwd: string, args: string[]): Promise<ProcessResult> {
  return runCommand("git", args, cwd, { timeoutMs: 60_000 });
}
