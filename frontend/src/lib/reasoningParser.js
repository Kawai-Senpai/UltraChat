export function removeToolBlocks(raw = '', toolPairs = []) {
  let out = raw || ''
  for (const pair of toolPairs || []) {
    if (!pair?.start || !pair?.end) continue
    const escapedStart = pair.start.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const escapedEnd = pair.end.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    out = out.replace(new RegExp(`${escapedStart}[\\s\\S]*?${escapedEnd}`, 'gi'), '')
    const openIdx = out.toLowerCase().indexOf(pair.start.toLowerCase())
    if (openIdx !== -1 && !out.toLowerCase().slice(openIdx).includes(pair.end.toLowerCase())) {
      out = out.slice(0, openIdx)
    }
  }
  return out.trim()
}

export function resolveReasoningFormat(registry, modelId = '', raw = '', preferredFormatId = null) {
  const formats = registry?.formats || []
  if (preferredFormatId) {
    const forced = formats.find(f => f.id === preferredFormatId)
    if (forced) return forced
  }

  const candidates = [...formats].sort((a, b) => (b.priority || 0) - (a.priority || 0))

  if (modelId) {
    for (const fmt of candidates) {
      if ((fmt.model_id_patterns || []).some(p => {
        try {
          return new RegExp(p, 'i').test(modelId)
        } catch {
          return false
        }
      })) {
        return fmt
      }
    }
  }

  const lowered = (raw || '').toLowerCase()
  for (const fmt of candidates) {
    const tags = [
      ...(fmt.reasoning_pairs || []).map(p => p.start?.toLowerCase()).filter(Boolean),
      ...(fmt.tool_pairs || []).map(p => p.start?.toLowerCase()).filter(Boolean),
    ]
    if (tags.some(tag => lowered.includes(tag))) return fmt
  }

  return formats.find(f => f.id === 'generic_fallback') || null
}

export function parseReasoningContent({
  raw = '',
  explicitThinking = '',
  modelId = '',
  registry = null,
  preferredFormatId = null,
}) {
  if (!raw && !explicitThinking) return { thinking: '', answer: '', formatId: null, toolPairs: [] }

  const fmt = resolveReasoningFormat(registry, modelId, raw, preferredFormatId)
  const toolPairs = fmt?.tool_pairs || []
  const reasoningPairs = fmt?.reasoning_pairs || []
  const withoutTools = removeToolBlocks(raw, toolPairs)

  if (explicitThinking?.trim()) {
    return {
      thinking: explicitThinking.trim(),
      answer: withoutTools,
      formatId: fmt?.id || null,
      toolPairs,
    }
  }

  for (const pair of reasoningPairs) {
    if (!pair?.start || !pair?.end) continue

    const escapedStart = pair.start.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const escapedEnd = pair.end.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const full = new RegExp(`${escapedStart}([\\s\\S]*?)${escapedEnd}`, 'gi')
    const matches = [...withoutTools.matchAll(full)]

    if (matches.length > 0) {
      const thinking = matches
        .map(m => (m[1] || '').trim())
        .filter(Boolean)
        .join('\n\n')
        .trim()

      const answer = withoutTools.replace(full, '').trim()
      return { thinking, answer, formatId: fmt?.id || null, toolPairs }
    }

    const openIdx = withoutTools.toLowerCase().indexOf(pair.start.toLowerCase())
    if (openIdx !== -1 && !withoutTools.toLowerCase().slice(openIdx).includes(pair.end.toLowerCase())) {
      return {
        thinking: withoutTools.slice(openIdx + pair.start.length).trim(),
        answer: withoutTools.slice(0, openIdx).trim(),
        formatId: fmt?.id || null,
        toolPairs,
      }
    }
  }

  const generic = withoutTools.match(/<(think|thinking|reasoning|analysis)>([\s\S]*?)<\/\1>/i)
  if (generic) {
    return {
      thinking: (generic[2] || '').trim(),
      answer: withoutTools.replace(/<(think|thinking|reasoning|analysis)>[\s\S]*?<\/\1>/gi, '').trim(),
      formatId: 'heuristic_generic_tag',
      toolPairs,
    }
  }

  return {
    thinking: '',
    answer: withoutTools.trim(),
    formatId: fmt?.id || null,
    toolPairs,
  }
}

export function parseToolCalls(toolCalls) {
  if (!toolCalls) return []
  if (Array.isArray(toolCalls)) return toolCalls
  try {
    const parsed = JSON.parse(toolCalls)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function buildAssistantParts(message, registry, preferredFormatId = null) {
  let raw = message.raw_content || message.content || ''
  // Older provider-lab messages stored adapter diagnostics here. They are not
  // model output, so prefer the persisted assistant content when encountered.
  try {
    const parsedRaw = JSON.parse(raw)
    if (parsedRaw && typeof parsedRaw === 'object' && (parsedRaw.protocol || parsedRaw._deltas)) {
      raw = message.content || ''
    }
  } catch {
    // Plain model output is expected not to be JSON.
  }
  const parsed = parseReasoningContent({
    raw,
    explicitThinking: message.thinking || '',
    modelId: message.model || '',
    registry,
    preferredFormatId,
  })

  const parts = []
  const toolCalls = parseToolCalls(message.tool_calls)

  if (parsed.thinking) {
    parts.push({ type: 'reasoning', content: parsed.thinking, formatId: parsed.formatId })
  }

  for (const call of toolCalls) {
    parts.push({
      type: 'tool_call',
      tool: call.name,
      arguments: call.arguments || {},
      result: call.result || '',
      round: call.round || 1,
    })
  }

  if (parsed.answer) {
    parts.push({ type: 'answer', content: parsed.answer })
  }

  if (parts.length === 0 && message.content) {
    parts.push({ type: 'answer', content: message.content })
  }

  return parts
}
