const CONFIG_KEY = 'ultrachat.provider-lab.config.v1'
const CREDENTIAL_KEY = 'ultrachat.provider-lab.credentials.v1'

function parse(storage, key) {
  try {
    const value = JSON.parse(storage.getItem(key) || 'null')
    return value && typeof value === 'object' ? value : {}
  } catch {
    return {}
  }
}

export function loadProviderConfig(defaults, storage = globalThis.localStorage) {
  if (!storage) return defaults
  const config = parse(storage, CONFIG_KEY)
  const credentials = parse(storage, CREDENTIAL_KEY)
  return {
    ...defaults,
    ...config,
    apiKey: typeof credentials.apiKey === 'string' ? credentials.apiKey : '',
    rememberCredentials: config.rememberCredentials !== false,
  }
}

export function saveProviderConfig(config, storage = globalThis.localStorage) {
  if (!storage) return
  const { apiKey, ...nonSecretConfig } = config
  storage.setItem(CONFIG_KEY, JSON.stringify(nonSecretConfig))
  if (config.rememberCredentials !== false) {
    storage.setItem(CREDENTIAL_KEY, JSON.stringify({
      apiKey: apiKey || '',
    }))
  } else {
    storage.removeItem(CREDENTIAL_KEY)
  }
}

export function forgetProviderCredentials(storage = globalThis.localStorage) {
  if (storage) storage.removeItem(CREDENTIAL_KEY)
}

export const providerStorageKeys = { CONFIG_KEY, CREDENTIAL_KEY }
