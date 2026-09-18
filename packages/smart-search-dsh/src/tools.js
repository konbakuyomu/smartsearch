import { MAX_INPUT_BYTES, normalizeConfig } from './config.js'
import { runSmartSearchCli } from './runner.js'

export const SMART_SEARCH_TOOL_NAMES = Object.freeze([
  'smart_search_search',
  'smart_search_fetch',
  'smart_search_route',
  'smart_search_deep',
  'smart_search_research',
  'smart_search_map',
  'smart_search_exa_search',
  'smart_search_zhipu_search',
  'smart_search_context7_docs',
  'smart_search_doctor',
])

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

function normalizeFetchUrl(value, command = 'fetch') {
  const normalized = normalizeText(value, command, 'url')
  if (typeof normalized !== 'string') {
    return normalized
  }
  try {
    const parsed = new URL(normalized)
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return invalidInput(command, 'url must use the http or https protocol.')
    }
    if (parsed.username || parsed.password) {
      return invalidInput(command, 'url must not include credentials.')
    }
    return parsed.href
  } catch {
    return invalidInput(command, 'url must be a valid absolute URL.')
  }
}

function normalizeOptionalEnum(value, command, label, allowed) {
  if (value === undefined || value === null) {
    return undefined
  }
  if (typeof value !== 'string') {
    return invalidInput(command, `${label} must be a string.`)
  }
  const trimmed = value.trim()
  if (!trimmed) {
    return undefined
  }
  if (!allowed.includes(trimmed)) {
    return invalidInput(command, `${label} must be one of: ${allowed.join(', ')}.`)
  }
  return trimmed
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

function makeRouteTool(config, defineTool) {
  return defineTool({
    name: 'smart_search_route',
    description: 'Explain Smart Search intent routing for a query without calling any search provider. Returns routing metadata as JSON.',
    parameters: {
      query: { type: 'string', required: true, description: 'Query to analyze for routing.' },
    },
    timeoutMs: config.timeoutMs,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: (_args, value) => renderJson(value),
    },
    async execute(args, exec) {
      const query = normalizeText(args.query, 'route', 'query')
      if (typeof query !== 'string') {
        return query
      }
      return runSmartSearchCli({ command: 'route', input: query, config, signal: exec.signal })
    },
  })
}

function makeDeepTool(config, defineTool) {
  return defineTool({
    name: 'smart_search_deep',
    description: 'Plan Deep Research offline: generate a research_plan JSON with staged steps. Does not call providers, fetch pages, or run doctor.',
    parameters: {
      query: { type: 'string', required: true, description: 'Deep research query to plan.' },
      budget: { type: 'string', enum: ['quick', 'standard', 'deep'], description: 'Research budget level: quick, standard, or deep.' },
    },
    timeoutMs: config.timeoutMs,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: (_args, value) => renderJson(value),
    },
    async execute(args, exec) {
      const query = normalizeText(args.query, 'deep', 'query')
      if (typeof query !== 'string') {
        return query
      }
      const budget = normalizeOptionalEnum(args.budget, 'deep', 'budget', ['quick', 'standard', 'deep'])
      if (budget !== undefined && typeof budget !== 'string') {
        return budget
      }
      return runSmartSearchCli({ command: 'deep', input: query, config, signal: exec.signal, extraArgs: budget ? ['--budget', budget] : [] })
    },
  })
}

function makeResearchTool(config, defineTool) {
  return defineTool({
    name: 'smart_search_research',
    description: 'Execute live Deep Research: plan, discover, fetch/read, gap check, and evidence-only synthesis. Returns markdown or JSON result.',
    parameters: {
      query: { type: 'string', required: true, description: 'Deep research query to execute.' },
      budget: { type: 'string', enum: ['quick', 'standard', 'deep'], description: 'Research budget level: quick, standard, or deep.' },
    },
    timeoutMs: config.timeoutMs,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: (_args, value) => renderJson(value),
    },
    async execute(args, exec) {
      const query = normalizeText(args.query, 'research', 'query')
      if (typeof query !== 'string') {
        return query
      }
      const budget = normalizeOptionalEnum(args.budget, 'research', 'budget', ['quick', 'standard', 'deep'])
      if (budget !== undefined && typeof budget !== 'string') {
        return budget
      }
      return runSmartSearchCli({ command: 'research', input: query, config, signal: exec.signal, extraArgs: budget ? ['--budget', budget] : [] })
    },
  })
}

function makeMapTool(config, defineTool) {
  return defineTool({
    name: 'smart_search_map',
    description: 'Map the structure of a documentation site or domain. Returns a site map as JSON.',
    parameters: {
      url: { type: 'string', required: true, description: 'Absolute HTTP(S) URL of the site to map.' },
    },
    timeoutMs: config.timeoutMs,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: (_args, value) => renderJson(value),
    },
    async execute(args, exec) {
      const url = normalizeFetchUrl(args.url, 'map')
      if (typeof url !== 'string') {
        return url
      }
      return runSmartSearchCli({ command: 'map', input: url, config, signal: exec.signal })
    },
  })
}

function makeExaSearchTool(config, defineTool) {
  return defineTool({
    name: 'smart_search_exa_search',
    description: 'Search with Exa for official domains, papers, product pages, and trusted-site discovery. Returns JSON results.',
    parameters: {
      query: { type: 'string', required: true, description: 'Exa search query.' },
    },
    timeoutMs: config.timeoutMs,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: (_args, value) => renderJson(value),
    },
    async execute(args, exec) {
      const query = normalizeText(args.query, 'exa-search', 'query')
      if (typeof query !== 'string') {
        return query
      }
      return runSmartSearchCli({ command: 'exa-search', input: query, config, signal: exec.signal })
    },
  })
}

function makeZhipuSearchTool(config, defineTool) {
  return defineTool({
    name: 'smart_search_zhipu_search',
    description: 'Search with Zhipu for Chinese-language, domestic China, policy/regulatory, announcements, and current news. Returns JSON results.',
    parameters: {
      query: { type: 'string', required: true, description: 'Zhipu search query.' },
    },
    timeoutMs: config.timeoutMs,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: (_args, value) => renderJson(value),
    },
    async execute(args, exec) {
      const query = normalizeText(args.query, 'zhipu-search', 'query')
      if (typeof query !== 'string') {
        return query
      }
      return runSmartSearchCli({ command: 'zhipu-search', input: query, config, signal: exec.signal })
    },
  })
}

function makeContext7DocsTool(config, defineTool) {
  return defineTool({
    name: 'smart_search_context7_docs',
    description: 'Search Context7 for library, SDK, API, framework, or documentation. Returns JSON results.',
    parameters: {
      library_id: { type: 'string', required: true, description: 'Resolved Context7 library ID, for example /python/cpython.' },
      query: { type: 'string', required: true, description: 'Context7 docs query.' },
    },
    timeoutMs: config.timeoutMs,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: (_args, value) => renderJson(value),
    },
    async execute(args, exec) {
      const libraryId = normalizeText(args.library_id, 'context7-docs', 'library_id')
      if (typeof libraryId !== 'string') return libraryId
      const query = normalizeText(args.query, 'context7-docs', 'query')
      if (typeof query !== 'string') {
        return query
      }
      return runSmartSearchCli({ command: 'context7-docs', input: libraryId, config, signal: exec.signal, extraArgs: [query] })
    },
  })
}

function makeDoctorTool(config, defineTool) {
  return defineTool({
    name: 'smart_search_doctor',
    description: 'Run Smart Search configuration diagnostics. Returns JSON with provider health, missing keys, and setup status.',
    parameters: {},
    timeoutMs: config.timeoutMs,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: (_args, value) => renderJson(value),
    },
    async execute(_args, exec) {
      return runSmartSearchCli({ command: 'doctor', input: '', config, signal: exec.signal })
    },
  })
}

export function createSmartSearchTools(configInput, defineTool) {
  if (typeof defineTool !== 'function') {
    throw new TypeError('smart-search-dsh: defineTool must be a function')
  }
  const config = normalizeConfig(configInput)
  return [
    makeSearchTool(config, defineTool),
    makeFetchTool(config, defineTool),
    makeRouteTool(config, defineTool),
    makeDeepTool(config, defineTool),
    makeResearchTool(config, defineTool),
    makeMapTool(config, defineTool),
    makeExaSearchTool(config, defineTool),
    makeZhipuSearchTool(config, defineTool),
    makeContext7DocsTool(config, defineTool),
    makeDoctorTool(config, defineTool),
  ]
}

export function registerSmartSearchTools(ctx, configInput, defineTool) {
  if (!ctx || !ctx.tools || typeof ctx.tools.register !== 'function') {
    throw new TypeError('smart-search-dsh: the DSH tools service is required')
  }
  for (const tool of createSmartSearchTools(configInput, defineTool)) {
    ctx.tools.register(tool)
  }
}
