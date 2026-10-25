import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

assert.equal(await readFile('output/greeting.txt', 'utf8'), 'Hello, SAGE-Kit!\n', 'MIN-ACC-01: exact UTF-8 greeting and newline');
console.log('MIN-ACC-01 PASS: actual output/greeting.txt matches MIN-REQ-01.');
