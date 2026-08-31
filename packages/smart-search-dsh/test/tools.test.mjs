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

test('registers only the narrow search and absolute-URL fetch tools', () => {
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
