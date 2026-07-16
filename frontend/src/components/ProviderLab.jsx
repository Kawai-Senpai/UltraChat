import { useEffect, useState } from 'react'
import { Bug, ChevronDown, Eye, EyeOff, FlaskConical, RefreshCw } from 'lucide-react'
import { providersAPI } from '../lib/api'
import { forgetProviderCredentials } from '../lib/providerStorage'

const DEFAULT_SCHEMA = {
  type: 'object',
  properties: {
    answer: { type: 'string' },
    confidence: { type: 'number' },
    checks: { type: 'array', items: { type: 'string' } },
  },
  required: ['answer', 'confidence', 'checks'],
  additionalProperties: false,
}

export default function ProviderLab({ value, onChange, debugEvents, onClearDebug }) {
  const [providers, setProviders] = useState([])
  const [open, setOpen] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [modelOptions, setModelOptions] = useState([])
  const [discovering, setDiscovering] = useState(false)

  useEffect(() => {
    providersAPI.capabilities().then(data => setProviders(data.providers || [])).catch(() => setProviders([]))
  }, [])

  const patch = (changes) => onChange({ ...value, ...changes })
  const mode = value.mode || 'local'
  const remote = mode !== 'local'
  const current = providers.find(item => item.id === mode)
  const latestResponse = [...debugEvents].reverse().find(item => item.phase === 'response')
  const cache = latestResponse?.cache
  const discover = async () => {
    setDiscovering(true)
    try {
      const data = await providersAPI.discoverModels({ base_url: value.baseUrl, api_key: value.apiKey || undefined })
      setModelOptions(data.models || [])
    } finally { setDiscovering(false) }
  }

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className={`flex items-center gap-1.5 px-2 py-1 rounded-full border text-[10px] ${remote ? 'border-cyan-400/30 bg-cyan-500/10 text-cyan-300' : 'border-white/10 bg-white/5 text-neutral-400'}`}>
        <FlaskConical className="w-3 h-3" />
        {remote ? current?.label || mode : 'Local model'}
        {remote && <span className={`rounded px-1 py-px text-[8px] font-bold ${value.stream !== false ? 'bg-emerald-400/15 text-emerald-300' : 'bg-amber-400/15 text-amber-300'}`}>{value.stream !== false ? 'LIVE' : 'BUFFERED'}</span>}
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-2 z-[70] w-[min(92vw,500px)] max-h-[70vh] overflow-y-auto rounded-xl border border-white/10 bg-neutral-900 p-3 shadow-2xl">
          <div className="mb-2 text-[10px] font-bold uppercase tracking-wider text-neutral-500">Provider stress lab</div>
          <label className="block text-[10px] text-neutral-400">Transport mode
            <select value={mode} onChange={e => patch({ mode: e.target.value })} className="mt-1 w-full rounded bg-neutral-800 p-2 text-xs text-white">
              {providers.map(item => <option key={item.id} value={item.id} disabled={!item.available}>{item.label}{item.available ? '' : ' — unavailable'}</option>)}
            </select>
          </label>
          {remote && <>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="text-[10px] text-neutral-400">Gateway root URL
                <input value={value.baseUrl} onChange={e => patch({ baseUrl: e.target.value })} className="mt-1 w-full rounded bg-neutral-800 p-2 text-xs text-white" placeholder="http://localhost:8001" />
              </label>
              <label className="text-[10px] text-neutral-400">API key
                <div className="relative mt-1"><input type={showKey ? 'text' : 'password'} value={value.apiKey} onChange={e => patch({ apiKey: e.target.value })} className="w-full rounded bg-neutral-800 p-2 pr-8 text-xs text-white" />
                  <button onClick={() => setShowKey(!showKey)} className="absolute right-2 top-2 text-neutral-500">{showKey ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}</button>
                </div>
              </label>
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <label className="flex items-center gap-2 text-[10px] text-neutral-300">
                <input
                  type="checkbox"
                  checked={value.rememberCredentials !== false}
                  onChange={e => patch({ rememberCredentials: e.target.checked })}
                />
                Remember key in this browser
              </label>
              <button
                type="button"
                onClick={() => {
                  forgetProviderCredentials()
                  patch({ apiKey: '', rememberCredentials: false })
                }}
                className="text-[10px] text-red-300 hover:text-red-200"
              >
                Forget saved key
              </button>
            </div>
            <p className="mt-1 text-[9px] text-neutral-500">
              Stored only in this browser&apos;s local storage; never written to UltraChat&apos;s server database.
            </p>
            <label className="mt-2 block text-[10px] text-neutral-400">Model (custom names accepted)
              <div className="mt-1 flex gap-2"><input list="gateway-models" value={value.model} onChange={e => patch({ model: e.target.value })} className="min-w-0 flex-1 rounded bg-neutral-800 p-2 text-xs text-white" placeholder="openai-default" />
                <button onClick={discover} disabled={discovering || !value.baseUrl} className="rounded bg-cyan-500/15 px-2 text-cyan-300 disabled:opacity-50" title="Discover gateway models"><RefreshCw className={`w-3 h-3 ${discovering ? 'animate-spin' : ''}`} /></button>
              </div>
              <datalist id="gateway-models">{modelOptions.map(item => <option key={item} value={item} />)}</datalist>
            </label>
            <label className="mt-2 flex items-center gap-2 text-[10px] text-neutral-300"><input type="checkbox" checked={value.stream !== false} onChange={e => patch({ stream: e.target.checked })} /> Stream tokens live (turn off only to test buffered responses)</label>
            <label className="mt-1 flex items-center gap-2 text-[10px] text-neutral-300"><input type="checkbox" checked={value.structured} onChange={e => patch({ structured: e.target.checked })} /> Strict structured-output test</label>
            {value.structured && <textarea value={value.schemaText} onChange={e => patch({ schemaText: e.target.value })} rows="5" className="mt-1 w-full rounded bg-neutral-800 p-2 font-mono text-[10px] text-cyan-100" />}
            <div className={`mt-2 rounded border px-2 py-1.5 text-[10px] ${cache?.hit ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200' : 'border-white/10 bg-black/20 text-neutral-400'}`}>
              <span className="font-medium">Provider cache: </span>
              {cache ? `${cache.cached_tokens}/${cache.input_tokens} cached — ${cache.note}` : 'awaiting provider usage'}
            </div>
          </>}
          <div className="mt-3 border-t border-white/10 pt-2">
            <div className="flex items-center justify-between text-[10px] text-neutral-400"><span className="flex items-center gap-1"><Bug className="w-3 h-3" /> Debug timeline ({debugEvents.length})</span><button onClick={onClearDebug} className="text-red-300">clear</button></div>
            <pre className="mt-1 max-h-40 overflow-auto rounded bg-black/40 p-2 text-[9px] text-emerald-300">{debugEvents.slice(-20).map(item => JSON.stringify(item)).join('\n') || 'No provider events yet.'}</pre>
          </div>
        </div>
      )}
    </div>
  )
}

export { DEFAULT_SCHEMA }
