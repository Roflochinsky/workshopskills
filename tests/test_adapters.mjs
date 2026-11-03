// Offline contract tests only. The SDK objects below make no provider requests.
// Run with: node --test tests/test_adapters.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { runPi } from '../adapters/pi.mjs';
import { runOmp } from '../adapters/omp.mjs';
import {
  validateInput, validateVerdict, validateCredentialSnapshot, assertToolSet,
  resultFromMessage, openSession, assertRuntime, loadSdk, privateRuntime, readonlyCredentialStore,
} from '../adapters/common.mjs';

const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const verdict = { status: 'PASS', covered_ac: ['AC-1'], lenses: ['spec', 'correctness', 'tests'], findings: [] };
const input = {
  schema_version: 1, role: 'review', prompt: 'Review candidate', output_dir: '/tmp/result',
  session_path: null, provider: 'example', model: 'model-1',
  sdk_module: '/opt/example/index.mjs', tools: ['read', 'grep', 'find'],
};

function fakeSdk(override = {}) {
  const record = { disposed: false, events: [], options: null };
  let listener;
  const model = { provider: input.provider, id: input.model };
  const session = {
    model,
    getActiveToolNames: () => override.tools ?? input.tools,
    getEnabledToolNames: () => override.tools ?? input.tools,
    subscribe: callback => { listener = callback; return () => {}; },
    prompt: async () => {
      listener({ type: 'message_end', message: {
        role: 'assistant', stopReason: 'stop',
        content: [{ type: 'text', text: override.text ?? JSON.stringify(verdict) }],
      } });
      return true;
    },
    waitForIdle: async () => {},
    dispose: async () => { record.disposed = true; },
  };
  const sdk = {
    createAgentSession: async options => { record.options = options; return { session }; },
    createExtensionRuntime: () => ({}),
    ModelRuntime: { create: async options => {
      record.runtimeOptions = options;
      return { getModel: () => model };
    } },
    SettingsManager: { inMemory: options => options },
    SessionManager: {
      inMemory: cwd => ({ getCwd: () => cwd }),
      open: () => ({ getCwd: () => '/foreign-worktree' }),
    },
    Settings: { isolated: options => options },
    AuthStorage: { create: async authPath => {
      record.authPath = authPath;
      return { credentials: { reload: async () => {} }, close: () => { record.authClosed = true; } };
    } },
    ModelRegistry: class {
      constructor(authStorage) { this.authStorage = authStorage; }
      async refresh(strategy) { record.refresh = strategy; }
      find() { return model; }
    },
  };
  return { sdk, record };
}

function context(record) {
  return {
    cwd: repository, directory: '/tmp/harness-runtime', authPath: '/tmp/harness-runtime/auth',
    emit: frame => record.events.push(frame),
  };
}

test('strict verdict, fixed role tools, terminal errors and credential boundaries', () => {
  assert.deepEqual(validateVerdict(JSON.stringify(verdict)), verdict);
  for (const bad of [
    '```json\n' + JSON.stringify(verdict) + '\n```',
    JSON.stringify({ ...verdict, covered_ac: [] }),
    JSON.stringify({ ...verdict, lenses: ['spec'] }),
    JSON.stringify({ ...verdict, extra: true }),
    JSON.stringify({ ...verdict, findings: ['unresolved'] }),
    'I approve ' + JSON.stringify(verdict),
  ]) assert.throws(() => validateVerdict(bad));
  assert.throws(() => validateInput({ ...input, tools: ['read', 'bash'] }, 'pi'), /unavailable/);
  assert.throws(() => validateInput({ ...input, role: 'implement', tools: ['read', 'bash'] }, 'pi'), /unavailable/);
  assert.throws(() => validateInput({ ...input, role: 'implement', tools: ['read', 'bash'] }, 'omp'), /unavailable/);
  assert.throws(() => validateInput({ ...input, tools: ['ls'] }, 'omp'), /unavailable/);
  assert.throws(() => validateInput({ ...input, session_path: '/tmp/old.jsonl' }, 'pi'), /fresh/);
  assert.throws(() => assertToolSet(['read', 'task'], ['read']), /outside/);
  assert.throws(() => assertToolSet([], ['read']), /every/);
  assert.throws(() => resultFromMessage({
    role: 'assistant', content: [{ type: 'text', text: 'partial' }], stopReason: 'error',
  }, 'implement'), /normally/);
  assert.throws(() => validateCredentialSnapshot({ example: { type: 'oauth', access: 'a', refresh: 'b' } }, 'example'), /literal API/);
  assert.throws(() => validateCredentialSnapshot({ example: { type: 'api_key', key: '!helper' } }, 'example'), /literal API/);
  validateCredentialSnapshot({ example: { type: 'api_key', key: 'placeholder-api-key' } }, 'example');
  assert.throws(() => assertRuntime('omp'), /Bun/);
});

for (const [harness, run] of [['pi', runPi], ['omp', runOmp]]) {
  test(`${harness}: restricted SDK configuration, strict result and failure disposal`, async () => {
    const validated = validateInput(input, harness);
    const { sdk, record } = fakeSdk();
    const result = await run(validated, sdk, context(record));
    assert.equal(result.status, 'PASS');
    assert.equal(record.disposed, true);
    assert.equal(record.events[0].type, 'event');
    if (harness === 'pi') {
      assert.deepEqual(record.options.resourceLoader.getExtensions().extensions, []);
      assert.deepEqual(record.options.resourceLoader.getAgentsFiles().agentsFiles, []);
      assert.equal(record.runtimeOptions.modelsPath, null);
      assert.equal(record.runtimeOptions.authPath, undefined);
      assert.equal(typeof record.runtimeOptions.credentials.read, 'function');
    } else {
      assert.equal(record.options.restrictToolNames, true);
      assert.equal(record.options.enableMCP, false);
      assert.equal(record.options.settings['advisor.enabled'], false);
      assert.equal(record.options.disableExtensionDiscovery, true);
      assert.equal(record.refresh, 'offline');
      assert.equal(record.authClosed, true);
      assert.equal(record.authPath, ':memory:');
    }
    const leaking = fakeSdk({ tools: ['read', 'task'] });
    await assert.rejects(run(validated, leaking.sdk, context(leaking.record)), /outside/);
    assert.equal(leaking.record.disposed, true);
    const malformed = fakeSdk({ text: 'Looks good' });
    await assert.rejects(run(validated, malformed.sdk, context(malformed.record)), /JSON object/);
    assert.equal(malformed.record.disposed, true);
  });
}

test('Pi credential storage cannot be mutated through a file, returned object or refresh callback', async () => {
  const entries = { example: { type: 'api_key', key: 'immutable-placeholder' } };
  const store = readonlyCredentialStore(entries);
  entries.example.key = '!changed-source';
  const returned = await store.read('example');
  assert.equal(returned.key, 'immutable-placeholder');
  returned.key = '!changed-returned-copy';
  assert.equal((await store.read('example')).key, 'immutable-placeholder');
  await assert.rejects(store.modify('example', async () => ({ type: 'oauth' })), /immutable/);
  await assert.rejects(store.delete('example'), /immutable/);
});

test('production entry rejects fake package before import; errors, resume and auth copying fail safely', async () => {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'law-adapter-negative-'));
  try {
    const sdkDirectory = path.join(temporary, 'sdk');
    await fs.mkdir(sdkDirectory);
    const modulePath = path.join(sdkDirectory, 'index.mjs');
    await fs.writeFile(modulePath, 'throw new Error("untrusted module was imported");');
    await fs.writeFile(path.join(sdkDirectory, 'package.json'), JSON.stringify({
      name: 'untrusted-fake', version: '1.5.0', main: './index.mjs',
    }));
    await assert.rejects(loadSdk(modulePath, 'pi'), /Expected @earendil/);
    const invocation = { ...input, output_dir: path.join(temporary, 'out'), sdk_module: modulePath, tools: ['read'] };
    const inputFile = path.join(temporary, 'input.json');
    await fs.writeFile(inputFile, JSON.stringify(invocation));
    const pi = spawnSync(process.execPath, [path.join(repository, 'adapters/pi.mjs'), inputFile], { encoding: 'utf8' });
    assert.equal(pi.status, 2);
    assert.equal(JSON.parse(pi.stdout.trim()).status, 'BLOCKED');
    assert.equal(JSON.parse(await fs.readFile(path.join(temporary, 'out/result.json'), 'utf8')).findings[0].code, 'SDK_VERSION');
    const omp = spawnSync(process.execPath, [path.join(repository, 'adapters/omp.mjs'), inputFile], { encoding: 'utf8' });
    assert.equal(omp.status, 2);
    assert.equal(JSON.parse(omp.stdout.trim()).findings[0].code, 'RUNTIME_VERSION');
    await assert.rejects(openSession({ SessionManager: { open: () => ({ getCwd: () => '/foreign' }) } }, {
      ...invocation, role: 'implement', session_path: path.join(temporary, 'session.jsonl'),
    }, 'pi', repository), /different worktree/);
    const original = path.join(temporary, 'auth.json');
    const snapshot = JSON.stringify({ example: { type: 'api_key', key: 'test-placeholder-key' } });
    await fs.writeFile(original, snapshot);
    const privateState = await privateRuntime({ ...invocation, auth_file: original }, 'pi');
    try {
      assert.notEqual(privateState.authPath, original);
      await fs.writeFile(privateState.authPath, '{}');
      assert.equal(await fs.readFile(original, 'utf8'), snapshot);
    } finally { await privateState.cleanup(); }
  } finally { await fs.rm(temporary, { recursive: true, force: true }); }
});
