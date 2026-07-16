import test from 'node:test'
import assert from 'node:assert/strict'

import {
  forgetProviderCredentials,
  loadProviderConfig,
  providerStorageKeys,
  saveProviderConfig,
} from './providerStorage.js'

function memoryStorage() {
  const values = new Map()
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  }
}

test('provider settings and credentials survive a reload', () => {
  const storage = memoryStorage()
  const config = {
    mode: 'openai',
    baseUrl: 'http://localhost:8001',
    apiKey: 'test-key',
    model: 'gpt-test',
    stream: true,
    rememberCredentials: true,
  }
  saveProviderConfig(config, storage)
  assert.deepEqual(loadProviderConfig({ mode: 'local' }, storage), config)
})

test('disabling credential memory keeps settings but removes the key', () => {
  const storage = memoryStorage()
  saveProviderConfig({
    mode: 'anthropic',
    baseUrl: 'http://localhost:8001',
    apiKey: 'secret',
    rememberCredentials: false,
  }, storage)
  const loaded = loadProviderConfig({ mode: 'local' }, storage)
  assert.equal(loaded.mode, 'anthropic')
  assert.equal(loaded.apiKey, '')
  assert.equal(loaded.rememberCredentials, false)
  assert.equal(storage.getItem(providerStorageKeys.CREDENTIAL_KEY), null)
})

test('forget removes only saved credentials', () => {
  const storage = memoryStorage()
  saveProviderConfig({
    mode: 'openai',
    apiKey: 'secret',
    rememberCredentials: true,
  }, storage)
  forgetProviderCredentials(storage)
  assert.equal(loadProviderConfig({ mode: 'local' }, storage).mode, 'openai')
  assert.equal(loadProviderConfig({ mode: 'local' }, storage).apiKey, '')
})
