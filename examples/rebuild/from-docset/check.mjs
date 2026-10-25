// Fixed acceptance asset. The implementation worker must not edit this file.
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdtemp, rm, readdir } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';

const mode = process.argv[2];
assert.ok(['core', 'cli', 'all'].includes(mode), 'Choose core, cli or all');
const { analyze } = await import(pathToFileURL(resolve('src/analyze.mjs')));
assert.equal(typeof analyze, 'function', 'TL-A01: exported analyze function');
const tasks = [
  { id: 'z', status: 'todo', dependsOn: ['a', 'd'] },
  { id: 'd', status: 'done', dependsOn: [] },
  { id: 'a', status: 'doing', dependsOn: ['d'] },
  { id: 'b', status: 'todo', dependsOn: ['d'] },
  { id: 'A', status: 'todo', dependsOn: [] },
  { id: 'm', status: 'todo', dependsOn: ['z', 'b'] },
];
const expected = { total: 6, counts: { todo: 4, doing: 1, done: 1 }, ready: ['A', 'b'],
  blocked: [{ id: 'm', waitingFor: ['b', 'z'] }, { id: 'z', waitingFor: ['a'] }] };
const original = JSON.stringify(tasks);
assert.deepEqual(analyze(tasks), expected, 'TL-A02: counts, ordering and direct blockers');
assert.equal(JSON.stringify(tasks), original, 'TL-A01: input unchanged');
assert.deepEqual(analyze([]), { total: 0, counts: { todo: 0, doing: 0, done: 0 }, ready: [], blocked: [] });
assert.deepEqual(analyze([...tasks].reverse()), expected, 'TL-A02: input ordering independent');
assert.deepEqual(analyze([{ id: '__proto__', status: 'todo', dependsOn: [] },
  { id: 'constructor', status: 'done', dependsOn: [] }]), {
  total: 2, counts: { todo: 1, doing: 0, done: 1 }, ready: ['__proto__'], blocked: [],
}, 'TL-A01: arbitrary nonempty IDs');
const invalid = [null, {}, 'tasks', [null], [{}],
  [{ id: '', status: 'todo', dependsOn: [] }],
  [{ id: 42, status: 'todo', dependsOn: [] }],
  [{ id: 'a', status: 'pending', dependsOn: [] }],
  [{ id: 'a', status: 'todo', dependsOn: 'x' }],
  [{ id: 'a', status: 'todo', dependsOn: [42] }],
  [{ id: 'a', status: 'todo', dependsOn: ['missing'] }],
  [{ id: 'a', status: 'todo', dependsOn: ['a'] }],
  [{ id: 'a', status: 'todo', dependsOn: [] }, { id: 'a', status: 'done', dependsOn: [] }],
  [{ id: 'a', status: 'todo', dependsOn: ['b', 'b'] }, { id: 'b', status: 'done', dependsOn: [] }],
  [{ id: 'a', status: 'done', dependsOn: ['b'] }, { id: 'b', status: 'done', dependsOn: ['a'] }],
  [{ id: 'a', status: 'todo', dependsOn: ['b'] }, { id: 'b', status: 'todo', dependsOn: ['c'] }, { id: 'c', status: 'todo', dependsOn: ['a'] }],
  Array.from({ length: 1001 }, (_, i) => ({ id: String(i), status: 'todo', dependsOn: [] })),
];
for (const value of invalid) assert.throws(() => analyze(value), Error, 'TL-A01: reject invalid task graph');
const boundary = Array.from({ length: 1000 }, (_, i) => ({ id: String(i), status: 'done', dependsOn: i ? [String(i - 1)] : [] }));
assert.deepEqual(analyze(boundary), { total: 1000, counts: { todo: 0, doing: 0, done: 1000 }, ready: [], blocked: [] });
console.log('TL-A01/TL-A02 PASS: actual library, invalid graphs, ordering, bounds and input preservation');

if (mode !== 'core') {
  const dir = await mkdtemp(join(tmpdir(), 'task-lens-acceptance-'));
  const invoke = args => {
    const result = spawnSync(process.execPath, ['bin/task-lens.mjs', ...args], {
      encoding: 'utf8', timeout: 5000, maxBuffer: 65536,
    });
    assert.ifError(result.error); assert.equal(result.signal, null, 'CLI must terminate normally');
    return result;
  };
  try {
    const input = join(dir, 'tasks with spaces.json');
    await writeFile(input, original);
    let run = invoke([input]);
    assert.equal(run.status, 0, run.stderr);
    assert.equal(run.stderr, ''); assert.ok(run.stdout.endsWith('\n'));
    assert.deepEqual(JSON.parse(run.stdout), expected);
    assert.equal(await readFile(input, 'utf8'), original, 'TL-A03: CLI must not rewrite input');
    run = invoke(['--help']); assert.equal(run.status, 0); assert.match(run.stdout, /usage/i);
    const bad = join(dir, 'bad.json'), graph = join(dir, 'graph.json');
    await writeFile(bad, '{'); await writeFile(graph, JSON.stringify(invalid[10]));
    for (const args of [[], [input, input], ['--unknown'], [join(dir, 'missing.json')], [bad], [graph]]) {
      run = invoke(args); assert.equal(run.status, 2, JSON.stringify({ args, run }));
      assert.equal(run.stdout, ''); assert.ok(run.stderr.trim(), 'TL-A03: useful stderr on error');
    }
    console.log('TL-A03 PASS: actual CLI success, help, errors and input preservation');
  } finally { await rm(dir, { recursive: true, force: true }); }
}
if (mode === 'all') {
  const pkg = JSON.parse(await readFile('package.json', 'utf8'));
  for (const field of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies']) {
    assert.equal(Object.keys(pkg[field] ?? {}).length, 0, 'TL-A04: no external dependencies');
  }
  assert.ok((await readFile('README.md', 'utf8')).trim().length > 100, 'TL-A04: product usage documentation');
  assert.ok((await readdir('tests')).some(name => name.endsWith('.test.mjs')), 'TL-A04: own regression suite');
  console.log('TL-A04 artifacts present; run own tests separately and obtain independent quality review');
}
