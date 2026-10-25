// Executes only controller-selected argv. This is process lifecycle management,
// not a sandbox: commands that deliberately create new sessions can escape a
// POSIX process group and must not be treated as untrusted executable input.
import { spawn } from 'node:child_process';
import { dirname, isAbsolute } from 'node:path';

const problem = (code, message) => Object.assign(new Error(message), { code });

// A short-lived guardian owns the process group. EOF/disconnect are kernel
// notifications, not polling: even SIGKILL of the controller cannot remove
// the only cleanup owner. Command data is passed as JSON, never interpolated.
const guardianSource = `
import {spawn} from 'node:child_process';
const command = JSON.parse(process.argv[1]);
const terminate = () => {
  try { process.kill(-process.pid, 'SIGKILL'); }
  finally { process.exit(125); }
};
process.stdin.on('end', terminate);
process.stdin.on('error', terminate);
process.stdin.resume();
process.on('disconnect', terminate);
let reported = false;
const report = (exitCode, signal, startupError) => {
  if (reported) return;
  reported = true;
  if (!process.connected) return terminate();
  try {
    // Once the result has been handed to IPC, cleanup cannot depend on the
    // controller being scheduled: it may be stopped or killed at this point.
    process.send({type:'sage-rsi-result',exitCode,signal,startupError}, terminate);
  } catch { terminate(); }
};
try {
  const actual = spawn(command[0], command.slice(1), {
    shell:false, detached:false, stdio:['ignore',1,2], env:process.env,
  });
  actual.once('error', error => report(null,null,error.code ?? error.message));
  actual.once('exit', (code, signal) => report(code,signal));
} catch (error) { report(null,null,error.code ?? error.message); }
`;

function boundedText(chunks, limit) {
  // Invalid output bytes can expand to replacement characters during UTF-8
  // decoding. Bound the returned text too, including a split final code point.
  const encoded = Buffer.from(Buffer.concat(chunks).toString('utf8'));
  let end = Math.min(encoded.length, limit);
  while (end > 0 && (encoded[end] & 0xc0) === 0x80) end--;
  return encoded.subarray(0, end).toString('utf8');
}

export async function runFixed(command, { cwd, timeoutMs = 10000, maxOutputBytes = 65536, signal } = {}) {
  if (process.platform === 'win32') {
    throw problem('E_PLATFORM_UNSUPPORTED', 'RSI command process-tree cleanup is not verified on Windows; use the verified POSIX runner');
  }
  if (!Array.isArray(command) || command.length === 0 || command.some(arg => typeof arg !== 'string' || arg.includes('\0')) ||
      !isAbsolute(command[0]) || typeof cwd !== 'string' || !isAbsolute(cwd)) {
    throw problem('E_COMMAND_CONFIG', 'A fixed argv with an absolute executable and absolute isolated cwd is required');
  }
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 2147483647 ||
      !Number.isSafeInteger(maxOutputBytes) || maxOutputBytes < 1) {
    throw problem('E_COMMAND_CONFIG', 'Command timeout and output budget must be positive bounded integers');
  }
  const began = performance.now();
  const result = { exitCode: null, signal: null, timedOut: false, cancelled: false,
    outputExceeded: false, stdout: '', stderr: '', durationMs: 0 };
  if (signal?.aborted) return { ...result, cancelled: true, durationMs: performance.now() - began };
  return new Promise((resolve, reject) => {
    const stdout = [], stderr = [];
    let child, timeout, cleanupTimer, cleanupError, reported = false, failedToStart = false, settled = false, bytes = 0;
    const append = (chunks, value) => {
      const data = Buffer.isBuffer(value) ? value : Buffer.from(value);
      const available = Math.max(0, maxOutputBytes - bytes);
      if (available) chunks.push(Buffer.from(data.subarray(0, available)));
      bytes += Math.min(data.length, available);
      return data.length > available;
    };
    const dispose = () => {
      clearTimeout(timeout);
      clearTimeout(cleanupTimer);
      signal?.removeEventListener('abort', onAbort);
    };
    const finish = () => {
      if (settled) return;
      settled = true;
      dispose();
      result.stdout = boundedText(stdout, maxOutputBytes);
      result.stderr = boundedText(stderr, maxOutputBytes - Buffer.byteLength(result.stdout));
      result.durationMs = performance.now() - began;
      if (cleanupError) reject(cleanupError);
      else resolve(result);
    };
    const terminateGroup = () => {
      if (child?.pid !== undefined) {
        try { process.kill(-child.pid, 'SIGKILL'); }
        catch (error) {
          if (error.code !== 'ESRCH') {
            cleanupError = problem('E_PROCESS_CLEANUP', `Cannot terminate command process group: ${error.code ?? error.message}`);
            try { child.kill('SIGKILL'); } catch { /* report the group failure */ }
          }
        }
      }
      if (cleanupTimer === undefined) cleanupTimer = setTimeout(() => {
        // Never hang on inherited pipes. Lack of confirmed close is an error,
        // not a successful evaluation or a claim that cleanup was verified.
        cleanupError ??= problem('E_PROCESS_CLEANUP', 'Command did not confirm close within the bounded cleanup interval');
        child?.stdin?.destroy();
        child?.stdout?.destroy();
        child?.stderr?.destroy();
        if (child?.connected) child.disconnect();
        child?.unref();
        finish();
      }, 1000);
    };
    const onAbort = () => { result.cancelled = true; terminateGroup(); };
    try {
      child = spawn(process.execPath, ['--input-type=module', '-e', guardianSource, JSON.stringify(command)], {
        cwd, shell: false, detached: true, stdio: ['pipe', 'pipe', 'pipe', 'ipc'],
        env: { PATH: `${dirname(command[0])}:/usr/bin:/bin`, HOME: cwd, TMPDIR: cwd },
      });
    } catch (error) {
      append(stderr, `Cannot start configured command: ${error.code ?? error.message}`);
      finish();
      return;
    }
    child.stdout.on('data', data => {
      if (append(stdout, data)) { result.outputExceeded = true; terminateGroup(); }
    });
    child.stderr.on('data', data => {
      if (append(stderr, data)) { result.outputExceeded = true; terminateGroup(); }
    });
    child.on('message', message => {
      if (message?.type !== 'sage-rsi-result') return;
      reported = true;
      result.exitCode = message.exitCode;
      result.signal = message.signal;
      if (message.startupError) {
        failedToStart = true;
        append(stderr, `Cannot start configured command: ${message.startupError}`);
      }
    });
    child.once('error', error => {
      failedToStart = true;
      append(stderr, `Cannot start configured command: ${error.code ?? error.message}`);
      terminateGroup();
    });
    child.once('exit', (code, exitSignal) => {
      if (!reported) {
        result.exitCode = null;
        result.signal = exitSignal;
        if (!failedToStart && !result.cancelled && !result.timedOut && !result.outputExceeded) {
          append(stderr, `Command guardian exited without a command result (${code ?? exitSignal})`);
        }
      }
      clearTimeout(timeout);
      // exit precedes close: descendants may still own stdout/stderr or have
      // redirected them. Clean the group even after a successful parent exit.
      terminateGroup();
    });
    child.once('close', (code, exitSignal) => {
      if (failedToStart) result.exitCode = null;
      if (!reported) result.signal = exitSignal;
      finish();
    });
    timeout = setTimeout(() => { result.timedOut = true; terminateGroup(); }, timeoutMs);
    signal?.addEventListener('abort', onAbort, { once: true });
    if (signal?.aborted) onAbort();
  });
}
