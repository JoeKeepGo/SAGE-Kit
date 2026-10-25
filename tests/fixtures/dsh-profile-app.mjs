import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import { defineTool } from '@deepseek-ai/dsh-tools';
export const name = 'sage-profile-fixture';
export const inject = ['agentLoop', 'tools', 'llm', 'approval', 'appReady', 'appExit'];
export function apply(ctx, config) {
  const observed = { requests: [], events: [], errors: [], writes: 0, approvals: [], adoptedPolicyObserved: false };
  ctx.on('session/event', (_session, event) => observed.events.push(event));
  ctx.on('agent/error', ({ error }) => observed.errors.push(String(error)));
  ctx.tools.register(defineTool({ name: 'fixture_write', description: 'Write only this isolated fixture.', parameters: {}, output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] }, execute: async (_args, exec) => {
    exec.signal.throwIfAborted();
    observed.writes++;
    await writeFile(join(config.projectRoot, 'output.txt'), 'delivered');
    assert.equal(await readFile(join(config.projectRoot, 'output.txt'), 'utf8'), 'delivered');
    await writeFile(join(config.projectRoot, 'check.txt'), 'Verified output.txt equals delivered.');
    return 'delivered and verified';
  } }));
  ctx.on('approval/request', async request => {
    assert.ok(['sage_rsi_adopt', 'sage_rsi_rollback'].includes(request.toolName));
    assert.match(request.reason, /policy\.txt/);
    assert.match(request.reason, /proposalDigest/);
    assert.match(request.reason, /evaluationDigest/);
    assert.equal(await readFile(join(config.projectRoot, 'policy.txt'), 'utf8'), request.toolName === 'sage_rsi_adopt' ? 'old policy\n' : 'new policy\n');
    observed.approvals.push({ toolName: request.toolName, callId: request.callId, reason: request.reason });
    return 'allowed-once'; // Test answerer only; this is not a real human decision.
  });
  const actions = [
    ['sage_begin', { stepId: 'first', attemptId: 'profile-first' }],
    ['fixture_write', {}],
    ['sage_finish', { attemptId: 'profile-first', result: JSON.stringify({ outcome: 'passed', checks: [{ id: 'test', passed: true, evidence: 'check.txt' }] }) }],
  ];
  ctx.on('llm/stream', options => {
    observed.requests.push({ messages: options.messages, tools: options.tools, provider: options.provider, model: options.model });
    const action = actions.shift();
    return (async function* () {
      if (action) {
        if (action[0] === 'sage_rsi_rollback') {
          assert.equal(await readFile(join(config.projectRoot, 'policy.txt'), 'utf8'), 'new policy\n');
          observed.adoptedPolicyObserved = true;
        }
        yield { type: 'tool-call-delta', index: 0, id: `profile-call-${observed.requests.length}`, name: action[0], argumentsDelta: JSON.stringify(action[1]) };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
      } else {
        yield { type: 'text-delta', index: 0, text: 'Fixture finished.' };
        yield { type: 'finish', reason: { kind: 'stop' } };
      }
    })();
  });
  const disposeReady = ctx.appReady.onReady(() => {
    void (async () => {
      const agent = await ctx.agentLoop.create('profile-probe', { provider: 'fixture-only', model: 'deterministic' }, { cwd: config.projectRoot });
      const timer = setTimeout(() => agent.cancel({ kind: 'user' }), 8000);
      try {
        agent.followup(createUserMessage({ content: [{ type: 'text', text: 'Perform the admitted local fixture.' }], source: { kind: 'user' } }));
        await agent.whenIdle();
        assert.deepEqual(observed.errors, []);
        assert.equal(observed.writes, 1);
        assert.equal(observed.requests.length, 4);
        assert.match(JSON.stringify(observed.requests[0].messages), /Governed profile fixture/);
        assert.equal(observed.events.findLast(event => event.type === 'turn/end')?.data.reason.kind, 'completed');
        const state = JSON.parse(await readFile(join(config.projectRoot, 'state.json'), 'utf8'));
        assert.equal(state.attempts[0].outcome, 'passed');
        actions.push(
          ['sage_rsi_propose', { hypothesis: 'Replace the policy to fix the recorded check failure.', feedback: JSON.stringify([{ path: 'rsi-feedback.txt', kind: 'failure' }]), files: JSON.stringify([{ path: 'policy.txt', content: 'new policy\n' }]) }],
          ['sage_rsi_evaluate', {}], ['sage_rsi_adopt', {}], ['sage_rsi_rollback', {}],
        );
        agent.followup(createUserMessage({ content: [{ type: 'text', text: 'Evaluate the evidence-linked RSI proposal; adoption and rollback require separate test approvals.' }], source: { kind: 'user' } }));
        await agent.whenIdle();
        assert.deepEqual(observed.errors, []);
        assert.equal(observed.requests.length, 9);
        assert.equal(observed.approvals.length, 2);
        assert.equal(observed.adoptedPolicyObserved, true);
        assert.equal(await readFile(join(config.projectRoot, 'policy.txt'), 'utf8'), 'old policy\n');
        const rsiState = JSON.parse(await readFile(join(config.projectRoot, 'rsi-state.json'), 'utf8'));
        assert.equal(rsiState.status, 'rolled_back');
        assert.equal(observed.events.findLast(event => event.type === 'turn/end')?.data.reason.kind, 'completed');
        await writeFile(config.evidencePath, JSON.stringify({ ok: true, ...observed }, null, 2));
        ctx.appExit(0);
      } finally { clearTimeout(timer); }
    })().catch(async error => {
      await writeFile(config.evidencePath, JSON.stringify({ ok: false, failure: String(error), ...observed }, null, 2));
      console.error(String(error));
      ctx.appExit(1);
    });
  });
  ctx.effect(() => disposeReady);
}
