import { MAX_INPUT_BYTES, normalizeConfig } from './config.js'
import { runSmartSearchCli } from './runner.js'

export const SMART_SEARCH_TOOL_NAMES = Object.freeze(['smart_search_search', 'smart_search_fetch'])

const ERROR_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    code: { type: 'string', required: true },
    message: { type: 'string', required: true },
    details: { type: 'json' },
  },
}

const TOOL_OUTPUT_SCHEMA = {
  oneOf: [
    {
      type: 'object',
      additionalProperties: false,
      properties: {
        ok: { type: 'boolean', const: true, required: true },
        command: { type: 'string', required: true },
        result: { type: 'json', required: true },
      },
    },
    {
      type: 'object',
      additionalProperties: false,
      properties: {
        ok: { type: 'boolean', const: false, required: true },
        command: { type: 'string', required: true },
        error: { ...ERROR_SCHEMA, required: true },
        result: { type: 'json' },
      },
    },
  ],
}

function renderJson(value) {
  return [{ type: 'text', text: JSON.stringify(value) }]
}

function invalidInput(command, message) {
  return {
    ok: false,
    command,
    error: {
      code: 'SMART_SEARCH_INVALID_INPUT',
      message,
    },
  }
}

function normalizeText(value, command, label) {
  if (typeof value !== 'string') {
    return invalidInput(command, `${label} must be a string.`)
  }
  const normalized = value.trim()
  if (!normalized) {
    return invalidInput(command, `${label} must not be empty.`)
  }
  if (Buffer.byteLength(normalized, 'utf8') > MAX_INPUT_BYTES) {
    return invalidInput(command, `${label} exceeds the ${MAX_INPUT_BYTES} byte limit.`)
  }
  return normalized
}

function normalizeFetchUrl(value) {
  const normalized = normalizeText(value, 'fetch', 'url')
  if (typeof normalized !== 'string') {
    return normalized
  }
  try {
    const parsed = new URL(normalized)
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return invalidInput('fetch', 'url must use the http or https protocol.')
    }
    if (parsed.username || parsed.password) {
      return invalidInput('fetch', 'url must not include credentials.')
    }
    return parsed.href
  } catch {
    return invalidInput('fetch', 'url must be a valid absolute URL.')
  }
}

function makeSearchTool(config, defineTool) {
  return defineTool({
    name: 'smart_search_search',
    description: 'Run Smart Search for one focused query and return its public JSON result. Provider configuration remains owned by Smart Search.',
    parameters: {
      query: { type: 'string', required: true, description: 'Focused search query.' },
    },
    timeoutMs: config.timeoutMs,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: (_args, value) => renderJson(value),
    },
    async execute(args, exec) {
      const query = normalizeText(args.query, 'search', 'query')
      if (typeof query !== 'string') {
        return query
      }
      return runSmartSearchCli({ command: 'search', input: query, config, signal: exec.signal })
    },
  })
}

function makeFetchTool(config, defineTool) {
  return defineTool({
    name: 'smart_search_fetch',
    description: 'Fetch one absolute HTTP(S) URL through Smart Search and return its public JSON result.',
    parameters: {
      url: { type: 'string', required: true, description: 'Absolute HTTP(S) URL to fetch.' },
    },
    timeoutMs: config.timeoutMs,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: (_args, value) => renderJson(value),
    },
    async execute(args, exec) {
      const url = normalizeFetchUrl(args.url)
      if (typeof url !== 'string') {
        return url
      }
      return runSmartSearchCli({ command: 'fetch', input: url, config, signal: exec.signal })
    },
  })
}

export function createSmartSearchTools(configInput, defineTool) {
  if (typeof defineTool !== 'function') {
    throw new TypeError('smart-search-dsh: defineTool must be a function')
  }
  const config = normalizeConfig(configInput)
  return [makeSearchTool(config, defineTool), makeFetchTool(config, defineTool)]
}

export function registerSmartSearchTools(ctx, configInput, defineTool) {
  if (!ctx || !ctx.tools || typeof ctx.tools.register !== 'function') {
    throw new TypeError('smart-search-dsh: the DSH tools service is required')
  }
  for (const tool of createSmartSearchTools(configInput, defineTool)) {
    ctx.tools.register(tool)
  }
}
