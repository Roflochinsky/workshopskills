#!/usr/bin/env node
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import {
  AdapterError, adapterMain, assertToolSet, openSession, policyPrompt, requireApi, resultFromMessage,
  readonlyCredentialStore, validateCredentialSnapshot,
} from './common.mjs';

/** Exported for offline protocol tests. The executable path always uses the version-checked SDK loader. */
export async function runPi(input, sdk, context) {
  requireApi(sdk, ['createAgentSession', 'createExtensionRuntime', 'ModelRuntime.create',
    'SettingsManager.inMemory', 'SessionManager.inMemory', 'SessionManager.open']);
  const credentials = input.auth_file ? JSON.parse(await fs.readFile(context.authPath, 'utf8')) : {};
  validateCredentialSnapshot(credentials, input.provider);
  if (input.auth_file) await fs.rm(context.authPath);
  const modelRuntime = await sdk.ModelRuntime.create({
    credentials: readonlyCredentialStore(credentials),
    modelsPath: null,
    allowModelNetwork: false,
  });
  const model = modelRuntime.getModel(input.provider, input.model);
  if (!model || model.provider !== input.provider || model.id !== input.model) {
    throw new AdapterError('MODEL_NOT_FOUND', 'The exact configured provider/model is unavailable in this SDK catalog.');
  }
  const settingsManager = sdk.SettingsManager.inMemory({
    compaction: { enabled: false },
    retry: { enabled: true, maxRetries: 2 },
  });
  // This is the upstream full-control ResourceLoader contract. No filesystem discovery occurs.
  const extensionRuntime = sdk.createExtensionRuntime();
  const resourceLoader = {
    getExtensions: () => ({ extensions: [], errors: [], runtime: extensionRuntime }),
    getSkills: () => ({ skills: [], diagnostics: [] }),
    getPrompts: () => ({ prompts: [], diagnostics: [] }),
    getThemes: () => ({ themes: [], diagnostics: [] }),
    getAgentsFiles: () => ({ agentsFiles: [] }),
    getSystemPrompt: () => undefined,
    getSystemPromptSource: () => undefined,
    getAppendSystemPrompt: () => [policyPrompt(input.role)],
    getAppendSystemPromptSources: () => [],
    extendResources: () => {},
    reload: async () => {},
  };
  const sessionManager = await openSession(sdk, input, 'pi', context.cwd);
  const { session } = await sdk.createAgentSession({
    cwd: context.cwd, agentDir: context.directory, model, modelRuntime, settingsManager, sessionManager,
    resourceLoader, tools: input.tools, excludeTools: ['mcp__*'], customTools: [],
  });
  let unsubscribe;
  let lastAssistant;
  try {
    assertToolSet(session.getActiveToolNames(), input.tools);
    unsubscribe = session.subscribe(event => {
      context.emit({ type: 'event', event });
      if (event.type === 'message_end' && event.message?.role === 'assistant') lastAssistant = event.message;
    });
    await session.prompt(input.prompt);
    await session.waitForIdle();
    assertToolSet(session.getActiveToolNames(), input.tools);
    if (session.model?.provider !== input.provider || session.model?.id !== input.model) {
      throw new AdapterError('MODEL_CHANGED', 'The session changed the configured model.');
    }
    return resultFromMessage(lastAssistant, input.role);
  } finally {
    unsubscribe?.();
    await session.dispose();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await adapterMain('pi', runPi);
