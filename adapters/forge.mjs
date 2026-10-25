// Explicit read-only platform observations. Never called by a governance hook.
import { realpath, lstat, mkdir, open, link, unlink } from 'node:fs/promises';
import { join, isAbsolute } from 'node:path';
import { createHash, randomUUID } from 'node:crypto';

const MiB = 1024 * 1024;
const digest = value => createHash('sha256').update(value).digest('hex');
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const integer = value => Number.isSafeInteger(value) && value > 0;
const sha = value => typeof value === 'string' && /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(value);
const pathName = value => typeof value === 'string' && value.length <= 1024 && !isAbsolute(value) && !/[\\:\0]/.test(value)
  && value.split('/').length <= 16 && value.split('/').every(p => p && p !== '.' && p !== '..');
const fail = (code, message) => { throw Object.assign(new Error(message), { code }); };
const require = (test, message, code = 'E_FORGE_DATA') => { if (!test) fail(code, message); };
const keys = (value, allowed) => object(value) && Object.keys(value).every(k => allowed.includes(k));
const pick = (value, names) => Object.fromEntries(names.filter(k => value[k] !== undefined).map(k => [k, value[k]]));

function sourceConfig(value) {
  require(keys(value, ['provider', 'apiBase', 'repo', 'tokenEnv']) && ['github', 'gitea'].includes(value.provider), 'Invalid forge source', 'E_FORGE_CONFIG');
  require(typeof value.repo === 'string' && /^[\w.-]+\/[\w.-]+$/.test(value.repo) && value.repo.length <= 200 && value.repo.split('/').every(p => !['.', '..'].includes(p)), 'Invalid repository', 'E_FORGE_CONFIG');
  let url;
  try { url = new URL(value.apiBase); } catch { fail('E_FORGE_CONFIG', 'Explicit API base required'); }
  require(!url.username && !url.password && !url.search && !url.hash &&
    (url.protocol === 'https:' || (url.protocol === 'http:' && ['127.0.0.1', '[::1]', 'localhost'].includes(url.hostname))), 'HTTPS or explicit loopback required', 'E_FORGE_CONFIG');
  require(!value.tokenEnv || (typeof value.tokenEnv === 'string' && /^[A-Z_][A-Z0-9_]{0,127}$/.test(value.tokenEnv)), 'Invalid credential environment name', 'E_FORGE_CONFIG');
  return { ...value, apiBase: url.href.replace(/\/$/, '') };
}

function assess(run, jobs, args, provider) {
  const reasons = [];
  if (run.head_sha !== args.expectedSha) reasons.push('commit_mismatch');
  if (run.path !== args.workflowPath) reasons.push('workflow_mismatch');
  if (!jobs.length) reasons.push('no_jobs');
  for (const name of args.requiredJobs) {
    if (jobs.filter(j => j.name === name).length !== 1) reasons.push('required_job_missing_or_ambiguous');
  }
  if (jobs.some(j => j.head_sha !== run.head_sha || (j.run_attempt !== run.run_attempt && !(provider === 'gitea' && run.run_attempt === 1 && j.run_attempt === undefined)))) reasons.push('job_version_unbound');
  if (run.status !== 'completed' || jobs.some(j => j.status !== 'completed')) reasons.push('not_completed');
  if (run.conclusion !== 'success' || jobs.some(j => j.conclusion !== 'success')) reasons.push('not_successful');
  const failed = [run, ...jobs].some(item => item.conclusion === 'failure' || item.conclusion === 'timed_out' || item.conclusion === 'action_required');
  return { result: reasons.length ? (failed ? 'FAIL' : 'INCOMPLETE') : 'PASS', reasons: [...new Set(reasons)],
    scope: 'Only this observed run and attempt; not branch-wide CI, deployment, authority or acceptance.' };
}

export async function openForgeEvidence({ root, directory, sources }) {
  require(isAbsolute(root ?? '') && pathName(directory) && object(sources) && Object.keys(sources).length > 0 && Object.keys(sources).length <= 10, 'Invalid forge configuration', 'E_FORGE_CONFIG');
  const base = await realpath(root), configured = new Map();
  for (const [name, value] of Object.entries(sources)) {
    require(/^[a-zA-Z0-9_-]{1,64}$/.test(name), 'Invalid source name', 'E_FORGE_CONFIG');
    configured.set(name, sourceConfig(value));
  }
  let active = false;
  async function safeDirectory(create, signal) {
    let path = base;
    for (const part of directory.split('/')) {
      signal.throwIfAborted(); path = join(path, part);
      if (create) await mkdir(path, { mode: 0o700 }).catch(error => { if (error.code !== 'EEXIST') throw error; });
      let stat;
      try { stat = await lstat(path); } catch (error) { if (error.code === 'ENOENT' && !create) return; throw error; }
      require(stat.isDirectory() && !stat.isSymbolicLink(), 'Evidence directory must contain only real directories', 'E_FORGE_PATH');
    }
    return path;
  }
  async function persist(receipt, token, signal, io) {
    const bytes = Buffer.from(JSON.stringify(receipt, null, 2) + '\n');
    require(bytes.length <= MiB, 'Evidence snapshot exceeds 1 MiB', 'E_FORGE_BUDGET');
    require(!token || (!bytes.includes(Buffer.from(token)) && !bytes.includes(Buffer.from(JSON.stringify(token).slice(1, -1)))), 'Source reflected a credential; snapshot refused', 'E_FORGE_SECRET');
    const sha256 = digest(bytes), name = sha256 + '.json';
    const dir = await safeDirectory(true, signal), dest = join(dir, name), temp = join(dir, '.' + randomUUID() + '.tmp');
    let handle;
    try {
      signal.throwIfAborted(); handle = await open(temp, 'wx', 0o600);
      await handle.writeFile(bytes, { signal }); await handle.sync(); await handle.close(); handle = undefined;
      signal.throwIfAborted(); await safeDirectory(false, signal);
      // Atomic create-only publication: another observation is never replaced.
      try { await link(temp, dest); io.bytesWritten = bytes.length; }
      catch (error) {
        if (error.code !== 'EEXIST') throw error;
        const stat = await lstat(dest);
        require(stat.isFile() && !stat.isSymbolicLink() && stat.size === bytes.length, 'Existing receipt conflicts', 'E_FORGE_PATH');
        // Bound the actual read even if another writer grows the file after stat.
        const existing = await open(dest, 'r'), buffer = Buffer.alloc(bytes.length + 1);
        let length = 0;
        try {
          while (length < buffer.length) {
            signal.throwIfAborted();
            const { bytesRead } = await existing.read(buffer, length, buffer.length - length, null);
            if (!bytesRead) break;
            length += bytesRead;
          }
        } finally { await existing.close(); }
        require(length === bytes.length && digest(buffer.subarray(0, length)) === sha256, 'Existing receipt conflicts', 'E_FORGE_PATH');
      }
      return { path: directory + '/' + name, sha256, kind: receipt.kind, assessment: receipt.assessment, io };
    } finally { await handle?.close(); await unlink(temp).catch(error => { if (error.code !== 'ENOENT') throw error; }); }
  }
  return {
    async capture(args, { signal: parent } = {}) {
      require(!active, 'One capture at a time per connection', 'E_FORGE_BUSY');
      require(keys(args, ['source', 'kind', 'id', 'expectedSha', 'workflowPath', 'requiredJobs']) && configured.has(args.source) && ['issue', 'run'].includes(args.kind) && integer(args.id), 'Invalid capture request', 'E_FORGE_ARGUMENT');
      if (args.kind === 'run') require(sha(args.expectedSha) && typeof args.workflowPath === 'string' && args.workflowPath.length > 0 && args.workflowPath.length <= 512 && !/[\r\n\0]/.test(args.workflowPath)
        && Array.isArray(args.requiredJobs) && args.requiredJobs.length > 0 && args.requiredJobs.length <= 100 && args.requiredJobs.every(n => typeof n === 'string' && n.length > 0 && n.length <= 200) && new Set(args.requiredJobs).size === args.requiredJobs.length, 'Run binding and required jobs are mandatory', 'E_FORGE_ARGUMENT');
      else require(Object.keys(args).every(k => ['source', 'kind', 'id'].includes(k)), 'Issue cannot be a CI check', 'E_FORGE_ARGUMENT');
      // Copy model arguments before awaiting; a caller cannot change the target mid-read.
      args = structuredClone(args);
      const source = configured.get(args.source), token = source.tokenEnv ? process.env[source.tokenEnv] : undefined;
      require(!source.tokenEnv || (typeof token === 'string' && token.length >= 8 && token.length <= 8192 && !/[\s\x00-\x1f\x7f]/.test(token)), 'Configured credential unavailable or invalid', 'E_FORGE_AUTH');
      const signal = AbortSignal.any([...(parent ? [parent] : []), AbortSignal.timeout(30000)]);
      const io = { requests: 0, bytesRead: 0, bytesWritten: 0 }, observations = [];
      const prefix = '/repos/' + source.repo.split('/').map(encodeURIComponent).join('/');
      const began = performance.now();
      active = true;
      async function get(path) {
        signal.throwIfAborted();
        require(++io.requests <= 16, 'Request budget exceeded', 'E_FORGE_BUDGET');
        const url = source.apiBase + path;
        let response;
        try { response = await fetch(url, { signal, redirect: 'manual', headers: {
          Accept: 'application/json', 'User-Agent': 'sage-kit-evidence',
          ...(source.provider === 'github' ? { 'X-GitHub-Api-Version': '2026-03-10' } : {}),
          ...(token ? { Authorization: `${source.provider === 'github' ? 'Bearer' : 'token'} ${token}` } : {}),
        } }); } catch { signal.throwIfAborted(); fail('E_FORGE_NETWORK', 'Platform request failed'); }
        if (response.status !== 200) {
          await response.body?.cancel();
          fail('E_FORGE_HTTP', `Platform returned HTTP ${response.status}; no receipt created`);
        }
        const chunks = []; let total = 0;
        try {
          for await (const chunk of response.body) {
            signal.throwIfAborted(); total += chunk.length; io.bytesRead += chunk.length;
            require(total <= MiB && io.bytesRead <= 4 * MiB, 'Platform response budget exceeded', 'E_FORGE_BUDGET'); chunks.push(chunk);
          }
        } catch (error) {
          if (error.code === 'E_FORGE_BUDGET') throw error;
          signal.throwIfAborted(); fail('E_FORGE_NETWORK', 'Platform body read failed');
        }
        const bytes = Buffer.concat(chunks); let data;
        try { data = JSON.parse(bytes.toString('utf8')); } catch { fail('E_FORGE_DATA', 'Invalid platform JSON'); }
        observations.push({ url, observedAt: new Date().toISOString(), bytes: bytes.length, sha256: digest(bytes), etag: response.headers.get('etag') });
        return { data, next: /rel="?next"?/.test(response.headers.get('link') ?? '') };
      }
      try {
        await safeDirectory(false, signal);
        const repo = (await get(prefix)).data;
        require(object(repo) && integer(repo.id) && typeof repo.full_name === 'string' && repo.full_name.toLowerCase() === source.repo.toLowerCase(), 'Repository identity mismatch');
        const version = source.provider === 'gitea' ? (await get('/version')).data.version : '2026-03-10';
        require(typeof version === 'string' && version.length <= 100, 'Missing platform API version');
        let subject, jobs, assessment;
        if (args.kind === 'issue') {
          const issue = (await get(prefix + '/issues/' + args.id)).data;
          require(object(issue) && issue.number === args.id && integer(issue.id) && typeof issue.updated_at === 'string' && Number.isFinite(Date.parse(issue.updated_at)), 'Invalid Issue identity/version');
          subject = pick(issue, ['id', 'number', 'html_url', 'url', 'title', 'body', 'state', 'created_at', 'updated_at', 'closed_at', 'pull_request', 'labels']);
          subject.author = pick(issue.user ?? {}, ['id', 'login']);
          assessment = { result: 'FEEDBACK', scope: 'Issue body only, no comments; untrusted data, never approval or evidence of a fix.' };
        } else {
          const path = prefix + '/actions/runs/' + args.id;
          const run = (await get(path)).data;
          require(object(run) && run.id === args.id && integer(run.run_attempt) && sha(run.head_sha) && typeof run.path === 'string', 'Run identity/version unavailable');
          if (run.repository !== undefined) require(run.repository?.id === repo.id, 'Run repository mismatch');
          jobs = []; let count;
          const jobPath = path + (source.provider === 'github' ? '/attempts/' + run.run_attempt : '') + '/jobs';
          for (let page = 1; ; page++) {
            const { data, next } = await get(jobPath + `?${source.provider === 'github' ? 'per_page' : 'limit'}=100&page=${page}`);
            require(object(data) && Array.isArray(data.jobs) && Number.isSafeInteger(data.total_count) && data.total_count >= 0, 'Jobs pagination identity missing');
            require(data.total_count <= 500 && data.jobs.length <= 100, 'Job count budget exceeded', 'E_FORGE_BUDGET');
            count ??= data.total_count;
            require(count === data.total_count && (data.jobs.length > 0 || jobs.length === count), 'Jobs changed or pagination incomplete');
            for (const job of data.jobs) {
              require(object(job) && integer(job.id) && job.run_id === run.id && !jobs.some(j => j.id === job.id), 'Invalid or duplicate job identity');
              jobs.push(pick(job, ['id', 'run_id', 'run_attempt', 'head_sha', 'name', 'status', 'conclusion', 'started_at', 'completed_at', 'html_url', 'steps']));
            }
            require(jobs.length <= count, 'Jobs exceed reported total');
            if (jobs.length === count) { require(!next, 'Jobs pagination incomplete'); break; }
          }
          const after = (await get(path)).data;
          const fields = ['id', 'run_attempt', 'head_sha', 'path', 'workflow_id', 'status', 'conclusion', 'updated_at', 'run_started_at', 'started_at', 'completed_at'];
          require(object(after) && JSON.stringify(pick(run, fields)) === JSON.stringify(pick(after, fields)), 'Run changed during collection', 'E_FORGE_CHANGED');
          subject = pick(run, [...fields, 'run_number', 'head_branch', 'event', 'html_url', 'url', 'created_at', 'check_suite_id', 'pull_requests']);
          assessment = assess(run, jobs, args, source.provider);
        }
        signal.throwIfAborted();
        const receipt = { version: 1, type: 'sage-forge-observation', untrustedData: true, kind: args.kind,
          source: { name: args.source, provider: source.provider, apiBase: source.apiBase, version, repository: pick(repo, ['id', 'full_name', 'html_url']) },
          request: args, subject, ...(jobs ? { jobs } : {}), assessment, observations };
        const result = await persist(receipt, token, signal, io);
        result.io.elapsedMs = performance.now() - began;
        return result;
      } finally { active = false; }
    },
  };
}
