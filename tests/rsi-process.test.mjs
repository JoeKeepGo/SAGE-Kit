import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { runFixed } from '../adapters/rsi-process.mjs';
import { spawn } from 'node:child_process';

const options = { timeout: 10000, skip: process.platform === 'win32' ? 'POSIX process-group cleanup only; Windows runner explicitly rejects' : false };
async function fixture(t) {
  const cwd = await mkdtemp(join(tmpdir(), 'sage-rsi-process-'));
  t.after(() => rm(cwd, { recursive: true, force: true }));
  return cwd;
}
const command = source => [process.execPath, '-e', source];
const execute = (cwd, source, overrides = {}) => runFixed(command(source), { cwd, timeoutMs: 2000, maxOutputBytes: 4096, ...overrides });

test('fixed argv succeeds with minimal environment and literal shell metacharacters', options, async t => {
  const cwd = await fixture(t);
  const saved = Object.fromEntries(['RSI_FIXTURE_SECRET', 'NODE_OPTIONS', 'GIT_CONFIG_COUNT'].map(name => [name, process.env[name]]));
  Object.assign(process.env, { RSI_FIXTURE_SECRET: 'fake-secret', NODE_OPTIONS: '--not-a-real-option', GIT_CONFIG_COUNT: '999' });
  t.after(() => { for (const [name, value] of Object.entries(saved)) { if (value === undefined) delete process.env[name]; else process.env[name] = value; } });
  const literal = '; touch must-not-exist';
  const result = await runFixed([...command('process.stdout.write(JSON.stringify({env:process.env,arg:process.argv[1]}))'), literal], {
    cwd, timeoutMs: 2000, maxOutputBytes: 4096,
  });
  assert.equal(result.exitCode, 0);
  assert.equal(result.signal, null);
  assert.equal(result.timedOut || result.cancelled || result.outputExceeded, false);
  const actual = JSON.parse(result.stdout);
  assert.deepEqual(Object.keys(actual.env).sort(), ['HOME', 'PATH', 'TMPDIR']);
  assert.equal(actual.env.HOME, cwd);
  assert.equal(actual.env.TMPDIR, cwd);
  assert.equal(actual.arg, literal);
  await assert.rejects(stat(join(cwd, 'must-not-exist')), { code: 'ENOENT' });
});

test('nonzero exit and stderr remain structured', options, async t => {
  const cwd = await fixture(t);
  const result = await execute(cwd, "process.stderr.write('expected failure');process.exitCode=7");
  assert.equal(result.exitCode, 7);
  assert.equal(result.stderr, 'expected failure');
  assert.equal(result.signal, null);
});

test('missing executable and invalid cwd return promptly as failed starts', options, async t => {
  const cwd = await fixture(t);
  for (const [argv, directory] of [[[join(cwd, 'missing-executable')], cwd], [command(''), join(cwd, 'missing-directory')]]) {
    const result = await runFixed(argv, { cwd: directory, timeoutMs: 1000, maxOutputBytes: 1000 });
    assert.equal(result.exitCode, null);
    assert.match(result.stderr, /ENOENT/);
    assert.equal(result.timedOut, false);
  }
});

test('combined stdout and stderr overflow kills execution with bounded captured text', options, async t => {
  const cwd = await fixture(t);
  const result = await execute(cwd, `process.stdout.write('a'.repeat(700));process.stderr.write('b'.repeat(700));setInterval(()=>{},1000)`, { maxOutputBytes: 1000 });
  assert.equal(result.outputExceeded, true);
  assert.equal(result.signal, 'SIGKILL');
  assert.ok(Buffer.byteLength(result.stdout) + Buffer.byteLength(result.stderr) <= 1000);
  assert.equal(result.timedOut, false);
});

test('invalid and split UTF-8 output cannot expand beyond the returned byte budget', options, async t => {
  const cwd = await fixture(t);
  const result = await execute(cwd, 'process.stdout.write(Buffer.alloc(1000,255));setInterval(()=>{},1000)', { maxOutputBytes: 17 });
  assert.equal(result.outputExceeded, true);
  assert.ok(Buffer.byteLength(result.stdout) + Buffer.byteLength(result.stderr) <= 17);
});

test('timeout kills a running parent and its real child before a delayed side effect', options, async t => {
  const cwd = await fixture(t);
  const childSource = "require('node:fs').writeFileSync('child-ready','yes');setTimeout(()=>require('node:fs').writeFileSync('late-effect','bad'),900);setInterval(()=>{},1000)";
  const source = `require('node:child_process').spawn(process.execPath,['-e',${JSON.stringify(childSource)}],{stdio:'inherit'});setInterval(()=>{},1000)`;
  const result = await execute(cwd, source, { timeoutMs: 400 });
  assert.equal(result.timedOut, true);
  assert.equal(result.signal, 'SIGKILL');
  assert.equal(await readFile(join(cwd, 'child-ready'), 'utf8'), 'yes');
  await delay(650);
  await assert.rejects(stat(join(cwd, 'late-effect')), { code: 'ENOENT' });
});

test('abort kills the process group after the child confirms startup', options, async t => {
  const cwd = await fixture(t);
  const abort = new AbortController();
  const childSource = "require('node:fs').writeFileSync('child-ready','yes');setTimeout(()=>require('node:fs').writeFileSync('late-effect','bad'),500);setInterval(()=>{},1000)";
  const source = `require('node:child_process').spawn(process.execPath,['-e',${JSON.stringify(childSource)}],{stdio:'inherit'});setInterval(()=>{},1000)`;
  const pending = execute(cwd, source, { signal: abort.signal });
  const deadline = Date.now() + 1200;
  while (true) {
    try { await stat(join(cwd, 'child-ready')); break; }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    assert.ok(Date.now() < deadline, 'real child must start before cancellation');
    await delay(10);
  }
  abort.abort();
  const result = await pending;
  assert.equal(result.cancelled, true);
  assert.equal(result.timedOut, false);
  await delay(550);
  await assert.rejects(stat(join(cwd, 'late-effect')), { code: 'ENOENT' });
});

for (const stdio of ['inherit', 'ignore']) {
  test(`successful exited parent cannot leave a child running with ${stdio} stdio`, options, async t => {
    const cwd = await fixture(t);
    const childPath = join(cwd, 'child.mjs');
    await writeFile(childPath, "import {writeFileSync} from 'node:fs';writeFileSync('child-ready','yes');process.send('ready');setTimeout(()=>writeFileSync('late-effect','bad'),400);setInterval(()=>{},1000)");
    const source = `const c=require('node:child_process').spawn(process.execPath,[${JSON.stringify(childPath)}],{stdio:['ignore',${JSON.stringify(stdio)},${JSON.stringify(stdio)},'ipc']});c.on('message',()=>process.exit(0));`;
    const result = await execute(cwd, source);
    assert.equal(await readFile(join(cwd, 'child-ready'), 'utf8'), 'yes');
    assert.equal(result.exitCode, 0);
    assert.equal(result.timedOut, false);
    await delay(450);
    await assert.rejects(stat(join(cwd, 'late-effect')), { code: 'ENOENT' });
  });
}

test('pre-cancelled call does not launch a command', options, async t => {
  const cwd = await fixture(t);
  const result = await execute(cwd, "require('node:fs').writeFileSync('effect','bad')", { signal: AbortSignal.abort() });
  assert.equal(result.cancelled, true);
  assert.equal(result.exitCode, null);
  await assert.rejects(stat(join(cwd, 'effect')), { code: 'ENOENT' });
});

test('relative executables and unbounded timing inputs are rejected', options, async t => {
  const cwd = await fixture(t);
  await assert.rejects(runFixed(['node', '-e', ''], { cwd }), { code: 'E_COMMAND_CONFIG' });
  await assert.rejects(runFixed(command(''), { cwd, timeoutMs: Infinity }), { code: 'E_COMMAND_CONFIG' });
});

test('Windows process-tree management is explicitly unsupported', { skip: process.platform !== 'win32' }, async () => {
  await assert.rejects(runFixed([process.execPath], { cwd: process.cwd() }), { code: 'E_PLATFORM_UNSUPPORTED' });
});

test('SIGKILL of the controller triggers guardian cleanup of actual command and grandchild without polling', options, async t => {
  const cwd = await fixture(t);
  const runnerUrl = new URL('../adapters/rsi-process.mjs', import.meta.url).href;
  const outerFile = join(cwd, 'controller.mjs');
  await writeFile(outerFile, `import {runFixed} from ${JSON.stringify(runnerUrl)};
await runFixed(JSON.parse(process.argv[2]),{cwd:process.argv[3],timeoutMs:6000,maxOutputBytes:4096});`);
  const descendant = `const fs=require('node:fs');
fs.writeFileSync('descendant-ready',JSON.stringify({pid:process.pid,group:Number(process.argv[1])}));
setTimeout(()=>fs.writeFileSync('orphan-effect','bad'),700);
setInterval(()=>{},1000);setTimeout(()=>process.exit(0),3000);`;
  const actual = `require('node:child_process').spawn(process.execPath,['-e',${JSON.stringify(descendant)},String(process.ppid)],{stdio:'ignore'});
setInterval(()=>{},1000);setTimeout(()=>process.exit(0),3000);`;
  const env = { ...process.env };
  delete env.NODE_TEST_CONTEXT;
  const outer = spawn(process.execPath, [outerFile, JSON.stringify(command(actual)), cwd], { env, stdio: 'ignore' });
  let group;
  const closed = new Promise(resolve => outer.once('close', (code, signal) => resolve({ code, signal })));
  t.after(() => {
    if (outer.exitCode === null && outer.signalCode === null) outer.kill('SIGKILL');
    if (group) { try { process.kill(-group, 'SIGKILL'); } catch (error) { if (error.code !== 'ESRCH') throw error; } }
  });
  const deadline = Date.now() + 2000;
  while (true) {
    try {
      const marker = JSON.parse(await readFile(join(cwd, 'descendant-ready'), 'utf8'));
      group = marker.group;
      assert.ok(Number.isInteger(group) && group > 0);
      break;
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    assert.ok(Date.now() < deadline, 'the actual grandchild must confirm startup before controller death');
    await delay(10);
  }
  assert.equal(outer.kill('SIGKILL'), true);
  assert.equal((await closed).signal, 'SIGKILL');
  await delay(850);
  await assert.rejects(stat(join(cwd, 'orphan-effect')), { code: 'ENOENT' });
});

test('normal actual exit cleans descendants while the controller is stopped before its SIGKILL', options, async t => {
  const cwd = await fixture(t);
  const runnerUrl = new URL('../adapters/rsi-process.mjs', import.meta.url).href;
  const outerFile = join(cwd, 'controller.mjs');
  await writeFile(outerFile, `import {runFixed} from ${JSON.stringify(runnerUrl)};
await runFixed(JSON.parse(process.argv[2]),{cwd:process.argv[3],timeoutMs:6000,maxOutputBytes:4096});`);
  const descendant = `const fs=require('node:fs');
fs.writeFileSync('descendant-ready',JSON.stringify({group:Number(process.argv[1])}));
setTimeout(()=>fs.writeFileSync('orphan-effect','bad'),900);
setInterval(()=>{},1000);setTimeout(()=>process.exit(0),3000);process.send('ready');`;
  const actual = `const fs=require('node:fs');
const child=require('node:child_process').spawn(process.execPath,['-e',${JSON.stringify(descendant)},String(process.ppid)],{stdio:['ignore','ignore','ignore','ipc']});
child.once('message',()=>{fs.writeFileSync('actual-ready','yes');setTimeout(()=>{fs.writeFileSync('actual-exiting','yes');process.exit(0)},250)});`;
  const env = { ...process.env };
  delete env.NODE_TEST_CONTEXT;
  const outer = spawn(process.execPath, [outerFile, JSON.stringify(command(actual)), cwd], { env, stdio: 'ignore' });
  let group;
  const closed = new Promise(resolve => outer.once('close', (code, signal) => resolve({ code, signal })));
  t.after(() => {
    if (outer.exitCode === null && outer.signalCode === null) outer.kill('SIGKILL');
    if (group) { try { process.kill(-group, 'SIGKILL'); } catch (error) { if (error.code !== 'ESRCH') throw error; } }
  });
  const deadline = Date.now() + 2000;
  while (true) {
    try {
      const marker = JSON.parse(await readFile(join(cwd, 'descendant-ready'), 'utf8'));
      group = marker.group;
      assert.ok(Number.isInteger(group) && group > 0);
      await stat(join(cwd, 'actual-ready'));
      break;
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    assert.ok(Date.now() < deadline, 'the actual command must confirm its child before the controller is stopped');
    await delay(10);
  }
  assert.equal(outer.kill('SIGSTOP'), true);
  await delay(500);
  assert.equal(await readFile(join(cwd, 'actual-exiting'), 'utf8'), 'yes');
  assert.equal(outer.kill('SIGKILL'), true);
  assert.equal((await closed).signal, 'SIGKILL');
  await delay(650);
  await assert.rejects(stat(join(cwd, 'orphan-effect')), { code: 'ENOENT' });
});
