import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import { createSmartSearchTools } from '../src/tools.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const python = process.env.SMART_SEARCH_TEST_PYTHON

test('all tool argument vectors match the real repository CLI parser', { skip: !python && 'Set SMART_SEARCH_TEST_PYTHON to enable real CLI contract tests' }, async () => {
  const tools = createSmartSearchTools({
    executable: process.execPath,
    executableArgs: [path.join(root, 'packages/smart-search-dsh/scripts/mock-smart-search.mjs')],
    timeoutMs: 5000,
  }, d => d)
  const vectors = []
  for (const tool of tools) {
    const args = tool.name.endsWith('_doctor') ? {}
      : /_(fetch|map)$/.test(tool.name) ? { url: 'https://example.com/docs' }
      : { query: 'Python async 中文', ...(tool.name.endsWith('_context7_docs') ? { library_id: '/python/cpython' } : {}) }
    for (const budget of /_(deep|research)$/.test(tool.name) ? [undefined, 'quick', 'standard', 'deep'] : [undefined]) {
      const result = await tool.execute({ ...args, ...(budget ? { budget } : {}) }, {})
      assert.equal(result.ok, true, tool.name)
      vectors.push([result.command, ...(result.result.input === '' ? [] : [result.result.input]), ...result.result.args])
    }
  }
  const code = `import json,sys\nfrom smart_search.cli import build_parser\np=build_parser()\nrows=[vars(p.parse_args(a)) for a in json.load(sys.stdin)]\nprint(json.dumps(rows))`.replaceAll('\\n', '\n')
  const result = spawnSync(python, ['-c', code], {
    input: JSON.stringify(vectors), encoding: 'utf8', shell: false, windowsHide: true,
    timeout: 30000, env: { ...process.env, PYTHONPATH: path.join(root, 'src'), PYTHONUTF8: '1' },
  })
  assert.ifError(result.error)
  assert.equal(result.status, 0, result.stderr)
  const parsed = JSON.parse(result.stdout)
  assert.equal(parsed.length, 16)
  const docs = parsed.find(row => row.command === 'context7-docs')
  assert.equal(docs.library_id, '/python/cpython')
  assert.equal(docs.query, 'Python async 中文')
  for (const command of ['deep', 'research']) {
    assert.deepEqual(parsed.filter(row => row.command === command).slice(1).map(row => row.budget), ['quick', 'standard', 'deep'])
  }
})
