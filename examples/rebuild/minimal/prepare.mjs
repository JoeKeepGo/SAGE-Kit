// Example setup only: run in an explicitly authorized disposable project copy.
import assert from 'node:assert/strict';
import { readFile, writeFile, realpath } from 'node:fs/promises';

const expiresAt = process.argv[2], remaining = Date.parse(expiresAt) - Date.now();
assert.ok(remaining > 0 && remaining <= 60 * 60 * 1000, 'Supply an explicit ISO expiry in the next hour');
assert.equal(new Date(expiresAt).toISOString(), expiresAt, 'Use an ISO timestamp including milliseconds and Z');
const plan = JSON.parse(await readFile('plan.template.json', 'utf8'));
const config = JSON.parse(await readFile('host.template.json', 'utf8'));
plan.expiresAt = expiresAt;
config.projectRoot = await realpath(process.cwd());
await writeFile('plan.json', JSON.stringify(plan, null, 2) + '\n', { flag: 'wx' });
await writeFile('host.json', JSON.stringify(config, null, 2) + '\n', { flag: 'wx' });
console.log(`Prepared a local round expiring ${expiresAt}; inspect and begin before task effects.`);
