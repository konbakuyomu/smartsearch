import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'

function parseArgs(argv) {
  const values = {}
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index]
    const value = argv[index + 1]
    if (!flag?.startsWith('--') || value === undefined) {
      throw new Error('Usage: node verify-installed-bundle.mjs --profile-dir PATH --mock PATH')
    }
    values[flag.slice(2)] = value
  }
  return values
}

const args = parseArgs(process.argv.slice(2))
if (!args['profile-dir'] || !args.mock) {
  throw new Error('Usage: node verify-installed-bundle.mjs --profile-dir PATH --mock PATH')
}

const profileDir = path.resolve(args['profile-dir'])
const mockPath = path.resolve(args.mock)
const entryPath = path.join(profileDir, 'node_modules', '@konbakuyomu', 'smart-search-dsh', 'index.js')
assert.ok(fs.existsSync(entryPath), `Installed bundle entry was not found: ${entryPath}`)
assert.ok(fs.existsSync(mockPath), `Mock Smart Search program was not found: ${mockPath}`)

const bundle = await import(pathToFileURL(entryPath).href)
assert.equal(bundle.name, 'smart-search-dsh')
assert.deepEqual(bundle.inject, ['tools'])

const registered = []
await bundle.apply(
  { tools: { register: (tool) => registered.push(tool) } },
  {
    executable: process.execPath,
    executableArgs: [mockPath],
    timeoutMs: 3_000,
    maxOutputBytes: 65_536,
  },
)

assert.deepEqual(registered.map((tool) => tool.name), ['smart_search_search', 'smart_search_fetch'])
const searchTool = registered.find((tool) => tool.name === 'smart_search_search')
assert.ok(searchTool, 'Installed bundle did not register smart_search_search')
const result = await searchTool.execute({ query: 'isolated mock search' }, { signal: new AbortController().signal })
assert.equal(result.ok, true)
assert.equal(result.result.command, 'search')
assert.equal(result.result.input, 'isolated mock search')

console.log(JSON.stringify({ ok: true, registeredTools: registered.map((tool) => tool.name) }))
