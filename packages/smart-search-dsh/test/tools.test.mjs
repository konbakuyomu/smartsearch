import assert from 'node:assert/strict'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { createSmartSearchTools, registerSmartSearchTools, SMART_SEARCH_TOOL_NAMES } from '../src/tools.js'

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const mockSmartSearch = path.join(packageRoot, 'scripts', 'mock-smart-search.mjs')

function config() {
  return {
    executable: process.execPath,
    executableArgs: [mockSmartSearch],
    timeoutMs: 3_000,
    maxOutputBytes: 65_536,
  }
}

function toolByName(tools, name) {
  const tool = tools.find((candidate) => candidate.name === name)
  assert.ok(tool, `expected ${name} tool`)
  return tool
}

test('registers all ten tools in the correct order', () => {
  const registered = []
  registerSmartSearchTools({ tools: { register: (tool) => registered.push(tool) } }, config(), (definition) => definition)

  assert.deepEqual(registered.map((tool) => tool.name), SMART_SEARCH_TOOL_NAMES)
  for (const tool of registered) {
    assert.equal(tool.timeoutMs, 3_000)
    assert.equal(tool.output.schema.oneOf.length, 2)
  }
})

test('default tool budget preserves the Smart Search 180-second search budget', () => {
  const tools = createSmartSearchTools({}, (definition) => definition)

  for (const tool of tools) {
    assert.equal(tool.timeoutMs, 181_000)
  }
})

test('search validates empty input before spawning the CLI', async () => {
  const search = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_search')
  const result = await search.execute({ query: '   ' }, { signal: new AbortController().signal })

  assert.deepEqual(result, {
    ok: false,
    command: 'search',
    error: {
      code: 'SMART_SEARCH_INVALID_INPUT',
      message: 'query must not be empty.',
    },
  })
})

test('fetch rejects non-HTTP schemes and URL credentials before spawning the CLI', async () => {
  const fetch = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_fetch')
  const fileResult = await fetch.execute({ url: 'file:///private.txt' }, { signal: new AbortController().signal })
  const credentialResult = await fetch.execute({ url: 'https://user:password@example.com/' }, { signal: new AbortController().signal })

  assert.equal(fileResult.error.code, 'SMART_SEARCH_INVALID_INPUT')
  assert.equal(credentialResult.error.code, 'SMART_SEARCH_INVALID_INPUT')
})

test('the registered tool invokes the mock CLI through the structured JSON bridge', async () => {
  const search = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_search')
  const result = await search.execute({ query: 'test query' }, { signal: new AbortController().signal })

  assert.equal(result.ok, true)
  assert.equal(result.result.command, 'search')
  assert.equal(result.result.input, 'test query')
})

// --- New tool tests ---

test('route tool validates empty input', async () => {
  const route = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_route')
  const result = await route.execute({ query: '' }, { signal: new AbortController().signal })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_INVALID_INPUT')
})

test('route tool invokes the mock CLI', async () => {
  const route = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_route')
  const result = await route.execute({ query: 'React useEffect API docs' }, { signal: new AbortController().signal })

  assert.equal(result.ok, true)
  assert.equal(result.result.command, 'route')
  assert.equal(result.result.input, 'React useEffect API docs')
})

test('deep tool validates empty input', async () => {
  const deep = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_deep')
  const result = await deep.execute({ query: '  ' }, { signal: new AbortController().signal })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_INVALID_INPUT')
})

test('deep tool passes --budget when provided', async () => {
  const deep = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_deep')
  const result = await deep.execute({ query: 'bitcoin market', budget: 'standard' }, { signal: new AbortController().signal })

  assert.equal(result.ok, true)
  assert.equal(result.result.command, 'deep')
  assert.equal(result.result.input, 'bitcoin market')
  assert.deepEqual(result.result.args, ['--budget', 'standard', '--format', 'json'])
})

test('deep tool rejects invalid budget enum', async () => {
  const deep = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_deep')
  const result = await deep.execute({ query: 'bitcoin', budget: 'invalid' }, { signal: new AbortController().signal })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_INVALID_INPUT')
})

test('research tool passes --budget when provided', async () => {
  const research = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_research')
  const result = await research.execute({ query: 'AI news', budget: 'deep' }, { signal: new AbortController().signal })

  assert.equal(result.ok, true)
  assert.equal(result.result.command, 'research')
  assert.deepEqual(result.result.args, ['--budget', 'deep', '--format', 'json'])
})

test('map tool rejects non-HTTP URLs', async () => {
  const map = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_map')
  const result = await map.execute({ url: 'ftp://example.com' }, { signal: new AbortController().signal })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_INVALID_INPUT')
})

test('map tool invokes the mock CLI with a valid URL', async () => {
  const map = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_map')
  const result = await map.execute({ url: 'https://example.com/docs' }, { signal: new AbortController().signal })

  assert.equal(result.ok, true)
  assert.equal(result.result.command, 'map')
  assert.equal(result.result.input, 'https://example.com/docs')
})

test('exa-search tool validates empty input', async () => {
  const exa = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_exa_search')
  const result = await exa.execute({ query: '' }, { signal: new AbortController().signal })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_INVALID_INPUT')
})

test('exa-search tool invokes the mock CLI', async () => {
  const exa = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_exa_search')
  const result = await exa.execute({ query: 'OpenAI Responses API' }, { signal: new AbortController().signal })

  assert.equal(result.ok, true)
  assert.equal(result.result.command, 'exa-search')
})

test('zhipu-search tool invokes the mock CLI', async () => {
  const zhipu = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_zhipu_search')
  const result = await zhipu.execute({ query: '中国AI政策' }, { signal: new AbortController().signal })

  assert.equal(result.ok, true)
  assert.equal(result.result.command, 'zhipu-search')
  assert.equal(result.result.input, '中国AI政策')
})

test('context7-docs tool invokes the mock CLI', async () => {
  const c7 = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_context7_docs')
  const result = await c7.execute({ library_id: '/facebook/react', query: 'React hooks' }, { signal: new AbortController().signal })

  assert.equal(result.ok, true)
  assert.equal(result.result.command, 'context7-docs')
})

test('doctor tool invokes the mock CLI without input', async () => {
  const doctor = toolByName(createSmartSearchTools(config(), (definition) => definition), 'smart_search_doctor')
  const result = await doctor.execute({}, { signal: new AbortController().signal })

  assert.equal(result.ok, true)
  assert.equal(result.result.command, 'doctor')
  assert.equal(result.result.input, '')
})


for (const command of ['deep', 'research']) {
  test(`${command} accepts all CLI budgets and rejects light`, async () => {
    const tool = toolByName(createSmartSearchTools(config(), d => d), `smart_search_${command}`)
    for (const budget of ['quick', 'standard', 'deep']) {
      const result = await tool.execute({ query: 'Python async', budget }, {})
      assert.equal(result.ok, true)
      assert.deepEqual(result.result.args, ['--budget', budget, '--format', 'json'])
    }
    const result = await tool.execute({ query: 'Python async', budget: 'light' }, {})
    assert.equal(result.error.code, 'SMART_SEARCH_INVALID_INPUT')
  })
}

test('context7 requires both arguments and preserves their argv boundaries', async () => {
  const tool = toolByName(createSmartSearchTools(config(), d => d), 'smart_search_context7_docs')
  for (const args of [{ query: 'hooks' }, { library_id: ' ', query: 'hooks' }, { library_id: '/facebook/react' }]) {
    const result = await tool.execute(args, {})
    assert.equal(result.error.code, 'SMART_SEARCH_INVALID_INPUT')
  }
  const result = await tool.execute({ library_id: '/facebook/react', query: 'hooks & effects 中文' }, {})
  assert.equal(result.ok, true)
  assert.equal(result.result.input, '/facebook/react')
  assert.deepEqual(result.result.args, ['hooks & effects 中文', '--format', 'json'])
})

test('map validation always identifies the map command', async () => {
  const tool = toolByName(createSmartSearchTools(config(), d => d), 'smart_search_map')
  for (const url of ['', 'bad URL', 'ftp://example.com', 'https://user:pass@example.com']) {
    const result = await tool.execute({ url }, {})
    assert.equal(result.command, 'map')
    assert.equal(result.error.code, 'SMART_SEARCH_INVALID_INPUT')
  }
})
