#!/usr/bin/env bun
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import {
  AdapterError, adapterMain, assertToolSet, openSession, policyPrompt, requireApi, resultFromMessage,
  validateCredentialSnapshot,
} from './common.mjs';

/** OMP is a Bun SDK. Exporting the runner permits dependency-injected offline contract tests. */
export async function runOmp(input, sdk, context) {
  requireApi(sdk, ['createAgentSession', 'AuthStorage.create', 'ModelRegistry',
    'Settings.isolated', 'SessionManager.inMemory', 'SessionManager.open']);
  const settings = sdk.Settings.isolated({
    'compaction.enabled': false,
    'retry.enabled': true,
    'advisor.enabled': false,
    'contextPromotion.enabled': false,
    'skills.enabled': false,
  });
  // A worker can edit source, so credentials must not be a file it can rewrite
  // into a command-backed credential or a different provider configuration.
  const authStorage = await sdk.AuthStorage.create(':memory:');
  let session;
  let unsubscribe;
  let lastAssistant;
  try {
    await authStorage.credentials.reload();
    if (input.auth_file) {
      const sourceAuth = await sdk.AuthStorage.create(context.authPath);
      try {
        await sourceAuth.credentials.reload();
        const credentials = sourceAuth.credentials.all();
        validateCredentialSnapshot(credentials, input.provider);
        if (credentials[input.provider]) await authStorage.credentials.set(input.provider, credentials[input.provider]);
      } finally { sourceAuth.close(); }
      for (const suffix of ['', '-wal', '-shm']) await fs.rm(context.authPath + suffix, { force: true });
    }
    const modelRegistry = new sdk.ModelRegistry(authStorage, path.join(context.directory, 'models.yml'), {
      settings, ignoreLocalModelConfig: true, cacheDbPath: path.join(context.directory, 'models.db'),
      fetch: async () => { throw new AdapterError('CATALOG_NETWORK', 'Factory workers use the pinned offline model catalog.'); },
    });
    await modelRegistry.refresh('offline');
    const model = modelRegistry.find(input.provider, input.model);
    if (!model || model.provider !== input.provider || model.id !== input.model) {
      throw new AdapterError('MODEL_NOT_FOUND', 'The exact configured provider/model is unavailable in this SDK catalog.');
    }
    const sessionManager = await openSession(sdk, input, 'omp', context.cwd);
    ({ session } = await sdk.createAgentSession({
      cwd: context.cwd, agentDir: context.directory, settings, authStorage, modelRegistry, model, sessionManager,
      toolNames: input.tools, restrictToolNames: true, allowRestrictedCustomTools: false,
      customTools: [], extensions: [], additionalExtensionPaths: [], disableExtensionDiscovery: true,
      skills: [], rules: [], contextFiles: [], noContextFiles: true, promptTemplates: [], slashCommands: [],
      enableMCP: false, enableLsp: false, enableIrc: false, skipPythonPreflight: true,
      disableModelFallback: true, disableServerSideFallback: true, suppressAutoPrewalk: true,
      cacheWarming: false, hasUI: false, autoApprove: true,
      appendSystemPrompt: policyPrompt(input.role),
      assertDispatchModel: candidate => {
        if (candidate.provider !== input.provider || candidate.id !== input.model) {
          throw new AdapterError('MODEL_CHANGED', 'Dispatch to an unconfigured model is forbidden.');
        }
      },
    }));
    assertToolSet(session.getEnabledToolNames(), input.tools);
    unsubscribe = session.subscribe(event => {
      context.emit({ type: 'event', event });
      if (event.type === 'message_end' && event.message?.role === 'assistant') lastAssistant = event.message;
    });
    const accepted = await session.prompt(input.prompt);
    if (accepted === false) throw new AdapterError('PROMPT_CONSUMED', 'A local command consumed the prompt; no worker turn ran.');
    await session.waitForIdle();
    assertToolSet(session.getEnabledToolNames(), input.tools);
    if (session.model?.provider !== input.provider || session.model?.id !== input.model) {
      throw new AdapterError('MODEL_CHANGED', 'The session changed the configured model.');
    }
    return resultFromMessage(lastAssistant, input.role);
  } finally {
    unsubscribe?.();
    try { await session?.dispose(); }
    finally { authStorage.close(); }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await adapterMain('omp', runOmp);
