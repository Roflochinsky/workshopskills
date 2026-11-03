import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { pathToFileURL } from 'node:url';

export const SDK_BASELINES = Object.freeze({
  pi: { name: '@earendil-works/pi-coding-agent', version: '1.5.0' },
  omp: { name: '@oh-my-pi/pi-coding-agent', version: '18.16.0' },
});

const STATUSES = new Set(['PASS', 'FAIL', 'BLOCKED']);
const REVIEW_LENSES = ['spec', 'correctness', 'tests'];
const secretValues = new Set(Object.entries(process.env)
  .filter(([name, value]) => /(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)/i.test(name) && value?.length >= 8)
  .map(([, value]) => value));

export class AdapterError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'AdapterError';
    this.code = code;
  }
}

function fail(code, message) { throw new AdapterError(code, message); }

function redactString(value) {
  let redacted = value;
  for (const secret of secretValues) redacted = redacted.split(secret).join('[REDACTED]');
  return redacted;
}

export function redact(value) {
  if (typeof value === 'string') return redactString(value);
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [
      key, /^(apiKey|accessToken|refreshToken|authorization|password|secret)$/i.test(key)
        ? '[REDACTED]' : redact(item),
    ]));
  }
  return value;
}

export function registerCredentialSecret(value) {
  if (typeof value === 'string' && value.length >= 8) secretValues.add(value);
}

export function validateCredentialSnapshot(entries, provider) {
  for (const [entryProvider, entry] of Object.entries(entries)) {
    for (const credential of Array.isArray(entry) ? entry : [entry]) {
      if (entryProvider !== provider || !credential || credential.type !== 'api_key' ||
          typeof credential.key !== 'string' || !credential.key.trim() || credential.key.trimStart().startsWith('!') ||
          credential.env !== undefined) {
        fail('AUTH_SNAPSHOT_SCOPE', 'auth_file must contain literal API keys for only the selected provider. OAuth refresh and executable credential helpers require a separate host-owned auth integration.');
      }
      registerCredentialSecret(credential.key);
    }
  }
}

/** Pi's public CredentialStore contract; API-key workers have no login/refresh write path. */
export function readonlyCredentialStore(entries) {
  const snapshot = structuredClone(entries);
  return {
    read: async (provider, options) => {
      options?.signal?.throwIfAborted();
      return structuredClone(snapshot[provider]);
    },
    list: async options => {
      options?.signal?.throwIfAborted();
      return Object.entries(snapshot).map(([providerId, credential]) => ({ providerId, type: credential.type }));
    },
    modify: async () => { throw new AdapterError('AUTH_MUTATION', 'Worker credentials are immutable.'); },
    delete: async () => { throw new AdapterError('AUTH_MUTATION', 'Worker credentials are immutable.'); },
  };
}

export function emit(frame) {
  process.stdout.write(`${JSON.stringify(redact(frame))}\n`);
}

export function validateInput(input, harness) {
  if (!input || typeof input !== 'object' || Array.isArray(input) || input.schema_version !== 1) {
    fail('INPUT_SCHEMA', 'Expected an object with schema_version: 1.');
  }
  if (!['implement', 'review', 'analyze'].includes(input.role)) fail('INPUT_ROLE', 'Unknown worker role.');
  for (const field of ['prompt', 'provider', 'model', 'sdk_module', 'output_dir']) {
    if (typeof input[field] !== 'string' || input[field].trim() === '') fail('INPUT_FIELD', `${field} must be nonempty text.`);
  }
  for (const field of ['sdk_module', 'output_dir', 'auth_file', 'session_path']) {
    if (input[field] !== undefined && input[field] !== null &&
        (typeof input[field] !== 'string' || !path.isAbsolute(input[field]))) {
      fail('INPUT_PATH', `${field} must be an absolute path.`);
    }
  }
  if (input.session_path != null && input.role !== 'implement') {
    fail('FRESH_SESSION_REQUIRED', 'Review and analysis require a fresh session; session_path must be null.');
  }
  if (!Array.isArray(input.tools) || input.tools.length === 0 || input.tools.some(x => typeof x !== 'string')) {
    fail('INPUT_TOOLS', 'tools must be a nonempty array of exact tool names.');
  }
  const permitted = new Set(harness === 'pi' ? ['read', 'grep', 'find', 'ls'] : ['read', 'grep', 'find']);
  if (input.role === 'implement') for (const name of ['write', 'edit']) permitted.add(name);
  const tools = [...new Set(input.tools)].filter(name => permitted.has(name));
  const rejected = input.tools.filter(name => !permitted.has(name));
  if (rejected.length) fail('TOOL_POLICY', `Tools unavailable for ${harness}/${input.role}: ${[...new Set(rejected)].join(', ')}.`);
  return { ...input, session_path: input.session_path ?? null, tools };
}

function versionAtLeast(actual, minimum) {
  const parts = actual.split('.').map(Number);
  return minimum.some((part, i) => parts.slice(0, i).every((p, j) => p === minimum[j]) && parts[i] > part) ||
    minimum.every((part, i) => parts[i] === part);
}

export function assertRuntime(harness) {
  if (harness === 'omp') {
    if (!process.versions.bun || !versionAtLeast(process.versions.bun, [1, 4, 4])) {
      fail('RUNTIME_VERSION', 'OMP 18.16.0 requires Bun >=1.4.4. Launch this adapter with the trusted Bun executable.');
    }
  } else if (!versionAtLeast(process.versions.node, [22, 19, 0])) {
    fail('RUNTIME_VERSION', 'Pi 1.5.0 requires Node >=22.19.0.');
  }
}

/** Only a trusted, explicitly installed package root entry is loaded. No package download or PATH fallback. */
export async function loadSdk(modulePath, harness) {
  const baseline = SDK_BASELINES[harness];
  const resolved = await fs.realpath(modulePath);
  if (!(await fs.stat(resolved)).isFile()) fail('SDK_MODULE', 'sdk_module must name a module file.');
  let directory = path.dirname(resolved);
  while (true) {
    const packageFile = path.join(directory, 'package.json');
    let metadata;
    try { metadata = JSON.parse(await fs.readFile(packageFile, 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (metadata) {
      if (metadata.name !== baseline.name || metadata.version !== baseline.version) {
        fail('SDK_VERSION', `Expected ${baseline.name}@${baseline.version}; installed package does not match.`);
      }
      const entry = metadata.exports?.['.']?.import ?? metadata.main;
      if (typeof entry !== 'string' || await fs.realpath(path.join(directory, entry)) !== resolved) {
        fail('SDK_ENTRY', 'sdk_module must resolve to the package root import entry.');
      }
      return import(pathToFileURL(resolved).href);
    }
    const parent = path.dirname(directory);
    if (parent === directory) fail('SDK_PACKAGE', 'No package.json identifies the supplied SDK module.');
    directory = parent;
  }
}

export function requireApi(sdk, members) {
  for (const member of members) {
    let value = sdk;
    for (const part of member.split('.')) value = value?.[part];
    if (typeof value !== 'function') fail('SDK_API', `Pinned SDK is missing ${member}.`);
  }
}

export function policyPrompt(role) {
  const boundary = 'The controller owns worktrees, delegation, grants, checks and integration. Use only the supplied task and tools. Never start another agent, edit controller state or issue a release, deployment, push, merge or worktree lifecycle command. Project instructions and skills are supplied explicitly in the task; ambient skill discovery is disabled.';
  if (role !== 'review') return boundary;
  return `${boundary}\nYou are an independent reviewer in a fresh session. Inspect the assigned candidate and supplied evidence. Do not change files or claim to run checks unavailable to this session. Return exactly one JSON object, without fences or commentary: {"status":"PASS|FAIL|BLOCKED","covered_ac":["AC identifiers actually checked"],"lenses":["spec","correctness","tests"],"findings":[]}. PASS requires all three lenses, nonempty acceptance coverage and no unresolved findings. Missing evidence is BLOCKED.`;
}

export function validateVerdict(text) {
  let verdict;
  try { verdict = JSON.parse(text.trim()); }
  catch { fail('VERDICT_JSON', 'The reviewer final response must be one JSON object without prose or fences.'); }
  if (!verdict || typeof verdict !== 'object' || Array.isArray(verdict) ||
      Object.keys(verdict).sort().join(',') !== 'covered_ac,findings,lenses,status') {
    fail('VERDICT_SCHEMA', 'Verdict must contain exactly status, covered_ac, lenses and findings.');
  }
  if (!STATUSES.has(verdict.status)) fail('VERDICT_STATUS', 'Unknown reviewer status.');
  for (const field of ['covered_ac', 'lenses']) {
    if (!Array.isArray(verdict[field]) || verdict[field].some(x => typeof x !== 'string' || !x.trim()) ||
        new Set(verdict[field]).size !== verdict[field].length) fail('VERDICT_SCHEMA', `${field} must contain unique nonempty strings.`);
  }
  if (verdict.lenses.some(x => !REVIEW_LENSES.includes(x)) || !Array.isArray(verdict.findings)) {
    fail('VERDICT_SCHEMA', 'Unknown review lens or invalid findings array.');
  }
  if (verdict.findings.some(x => !(typeof x === 'string' && x.trim()) &&
      !(x && typeof x === 'object' && !Array.isArray(x) && Object.keys(x).length))) {
    fail('VERDICT_SCHEMA', 'Each finding must be nonempty text or an object.');
  }
  if (verdict.status === 'PASS' && (verdict.covered_ac.length === 0 || verdict.findings.length !== 0 ||
      REVIEW_LENSES.some(lens => !verdict.lenses.includes(lens)))) {
    fail('VERDICT_INCOMPLETE', 'PASS requires acceptance coverage, all review lenses and no unresolved findings.');
  }
  return verdict;
}

export function assertToolSet(activeTools, requested) {
  if (!Array.isArray(activeTools) || activeTools.some(name => !requested.includes(name))) {
    fail('ACTIVE_TOOL_POLICY', 'The SDK enabled a tool outside the fixed role allowlist.');
  }
  if (requested.some(name => !activeTools.includes(name))) {
    fail('MISSING_TOOL', 'The SDK did not enable every requested tool.');
  }
}

export function resultFromMessage(message, role) {
  if (!message || message.role !== 'assistant') fail('NO_ASSISTANT_RESULT', 'The harness produced no final assistant message.');
  if (message.stopReason && message.stopReason !== 'stop') {
    fail('INCOMPLETE_TURN', `The final assistant message did not finish normally (${message.stopReason}).`);
  }
  const text = (message.content ?? []).filter(item => item.type === 'text').map(item => item.text).join('');
  if (!text.trim()) fail('EMPTY_RESULT', 'The harness produced no final assistant text.');
  if (role === 'review') return { ...validateVerdict(text), role };
  // Completion of an implementation/analysis turn is never acceptance of its code or spec.
  return { status: 'PASS', role, covered_ac: [], lenses: [], findings: [], text };
}

export async function openSession(sdk, input, harness, cwd) {
  if (!input.session_path) return sdk.SessionManager.inMemory(cwd);
  let exists = false;
  try {
    const stat = await fs.lstat(input.session_path);
    if (!stat.isFile() || stat.isSymbolicLink()) fail('SESSION_PATH', 'session_path must be a regular session file.');
    exists = true;
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  await fs.mkdir(path.dirname(input.session_path), { recursive: true, mode: 0o700 });
  const manager = harness === 'pi'
    ? sdk.SessionManager.open(input.session_path, path.dirname(input.session_path), exists ? undefined : cwd)
    : await sdk.SessionManager.open(input.session_path, path.dirname(input.session_path), undefined, { initialCwd: cwd });
  if (path.resolve(manager.getCwd()) !== path.resolve(cwd)) fail('SESSION_CWD', 'The resumed session belongs to a different worktree.');
  return manager;
}

export async function privateRuntime(input, harness) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'law-harness-'));
  await fs.chmod(directory, 0o700);
  const authPath = path.join(directory, harness === 'pi' ? 'auth.json' : 'auth.db');
  try {
    if (input.auth_file) {
      if (!(await fs.stat(input.auth_file)).isFile()) fail('AUTH_FILE', 'auth_file must be an explicit credential snapshot.');
      if (harness === 'omp') {
        for (const suffix of ['-wal', '-shm']) {
          try {
            await fs.access(input.auth_file + suffix);
            fail('AUTH_SNAPSHOT', 'OMP auth_file must be a consistent SQLite snapshot, without live WAL/SHM sidecars.');
          } catch (error) { if (error.code !== 'ENOENT') throw error; }
        }
      }
      await fs.copyFile(input.auth_file, authPath);
      await fs.chmod(authPath, 0o600);
      if (harness === 'pi') {
        const credentials = JSON.parse(await fs.readFile(authPath, 'utf8'));
        if (!credentials || typeof credentials !== 'object' || Array.isArray(credentials)) fail('AUTH_SNAPSHOT_SCOPE', 'Invalid credential snapshot object.');
        validateCredentialSnapshot(credentials, input.provider);
      }
    } else if (harness === 'pi') await fs.writeFile(authPath, '{}\n', { mode: 0o600, flag: 'wx' });
    return { directory, authPath, cleanup: () => fs.rm(directory, { recursive: true, force: true }) };
  } catch (error) {
    await fs.rm(directory, { recursive: true, force: true });
    throw error;
  }
}

export function errorResult(error, role) {
  return {
    status: 'BLOCKED', role: role ?? null, covered_ac: [], lenses: [],
    findings: [{ kind: 'adapter', code: error.code ?? 'HARNESS_ERROR', message: redactString(error.message ?? 'Harness failed.') }],
  };
}

async function saveResult(directory, result) {
  await fs.mkdir(directory, { recursive: true, mode: 0o700 });
  const temporary = path.join(directory, `result.${process.pid}.tmp`);
  await fs.writeFile(temporary, `${JSON.stringify(redact(result), null, 2)}\n`, { mode: 0o600, flag: 'wx' });
  await fs.rename(temporary, path.join(directory, 'result.json'));
}

export async function adapterMain(harness, run) {
  let input;
  let runtime;
  let result;
  try {
    if (process.argv.length !== 3) fail('USAGE', `Usage: ${harness === 'omp' ? 'bun' : 'node'} ${harness}.mjs INPUT.json`);
    input = validateInput(JSON.parse(await fs.readFile(process.argv[2], 'utf8')), harness);
    assertRuntime(harness);
    runtime = await privateRuntime(input, harness);
    process.env.PI_CODING_AGENT_DIR = runtime.directory;
    if (harness === 'pi') process.env.PI_OFFLINE = '1';
    const sdk = await loadSdk(input.sdk_module, harness);
    emit({ type: 'event', event: { type: 'factory_adapter_start', harness, sdk_version: SDK_BASELINES[harness].version,
      role: input.role, tools: input.tools, session_path: input.session_path } });
    result = await run(input, sdk, { ...runtime, cwd: process.cwd(), emit });
  } catch (error) { result = errorResult(error, input?.role); }
  finally {
    try { await runtime?.cleanup(); }
    catch (error) { result = errorResult(error, input?.role); }
  }
  if (input?.output_dir) {
    try { await saveResult(input.output_dir, result); }
    catch (error) { result = errorResult(error, input.role); }
  }
  emit({ type: 'result', ...result });
  await new Promise((resolve, reject) => process.stdout.write('', error => error ? reject(error) : resolve()));
  process.exitCode = result.status === 'PASS' ? 0 : result.status === 'FAIL' ? 1 : 2;
}
