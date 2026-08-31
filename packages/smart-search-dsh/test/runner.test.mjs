import assert from 'node:assert/strict'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { normalizeConfig } from '../src/config.js'
import { runSmartSearchCli } from '../src/runner.js'

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const mockSmartSearch = path.join(packageRoot, 'scripts', 'mock-smart-search.mjs')
const mockSmartSearchCmd = path.join(packageRoot, 'test', 'mock-cmd-only.cmd')
const mockSmartSearchPowerShell = path.join(packageRoot, 'test', 'mock-smart-search.ps1')

function mockConfig(overrides = {}) {
  return normalizeConfig({
    executable: process.execPath,
    executableArgs: [mockSmartSearch],
    timeoutMs: 3_000,
    maxOutputBytes: 65_536,
    ...overrides,
  })
}

test('runs the public Smart Search JSON command with a bounded search timeout', async () => {
  const result = await runSmartSearchCli({
    command: 'search',
    input: 'focused query',
    config: mockConfig(),
  })

  assert.equal(result.ok, true)
  assert.equal(result.command, 'search')
  assert.deepEqual(result.result, {
    ok: true,
    command: 'search',
    input: 'focused query',
    args: ['--timeout', '2.7', '--format', 'json'],
  })
})

test('uses the fetch public CLI shape without exposing a configurable shell', async () => {
  const result = await runSmartSearchCli({
    command: 'fetch',
    input: 'https://example.com/',
    config: mockConfig(),
  })

  assert.equal(result.ok, true)
  assert.deepEqual(result.result.args, ['--format', 'json'])
})

test('runs a Windows PowerShell npm shim without treating model input as shell syntax', async (context) => {
  if (process.platform !== 'win32') {
    context.skip('Windows-only PowerShell shim coverage')
    return
  }

  const query = 'literal & | < > ( ) ^ %PATH% !value!'
  const result = await runSmartSearchCli({
    command: 'search',
    input: query,
    config: normalizeConfig({
      executable: mockSmartSearchPowerShell,
      executableArgs: [],
      timeoutMs: 3_000,
      maxOutputBytes: 65_536,
    }),
  })

  assert.equal(result.ok, true)
  assert.equal(result.result.input, query)
})

test('rejects command-processor metacharacters when only a cmd shim is available', async (context) => {
  if (process.platform !== 'win32') {
    context.skip('Windows-only cmd shim coverage')
    return
  }

  const result = await runSmartSearchCli({
    command: 'search',
    input: 'unsafe & query',
    config: normalizeConfig({
      executable: mockSmartSearchCmd,
      executableArgs: [],
      timeoutMs: 3_000,
      maxOutputBytes: 65_536,
    }),
  })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_UNSUPPORTED_INPUT')
})

test('runs ordinary input through a cmd-only shim', async (context) => {
  if (process.platform !== 'win32') {
    context.skip('Windows-only cmd shim coverage')
    return
  }

  const result = await runSmartSearchCli({
    command: 'search',
    input: 'safe cmd query',
    config: normalizeConfig({
      executable: mockSmartSearchCmd,
      executableArgs: [],
      timeoutMs: 3_000,
      maxOutputBytes: 65_536,
    }),
  })

  assert.equal(result.ok, true)
  assert.equal(result.result.input, 'safe cmd query')
})

test('preserves a public JSON CLI failure in a structured error envelope', async () => {
  const result = await runSmartSearchCli({
    command: 'search',
    input: '__cli_error__',
    config: mockConfig(),
  })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_CLI_ERROR')
  assert.equal(result.error.details.exitCode, 2)
  assert.equal(result.error.details.smartSearchErrorType, 'config_error')
  assert.deepEqual(result.result, { ok: false, error_type: 'config_error', error: 'mock CLI failure' })
})

test('reports malformed JSON without forwarding raw process output', async () => {
  const result = await runSmartSearchCli({
    command: 'fetch',
    input: '__invalid_json__',
    config: mockConfig(),
  })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_INVALID_JSON')
  assert.equal(Object.hasOwn(result.error.details, 'stderr'), false)
})

test('counts but never forwards child stderr into the structured result', async () => {
  const result = await runSmartSearchCli({
    command: 'fetch',
    input: '__stderr__',
    config: mockConfig(),
  })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_INVALID_JSON')
  assert.ok(result.error.details.stderrBytes > 0)
  assert.equal(Object.hasOwn(result.error.details, 'stderr'), false)
  assert.doesNotMatch(JSON.stringify(result), /untrusted-stderr-payload/)
})

test('terminates a mock command that exceeds the bundle output cap', async () => {
  const result = await runSmartSearchCli({
    command: 'search',
    input: '__large_output__',
    config: mockConfig({ maxOutputBytes: 4_096 }),
  })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_OUTPUT_TOO_LARGE')
  assert.equal(result.error.details.maxOutputBytes, 4_096)
})

test('terminates a mock command at the configured tool budget', async () => {
  const result = await runSmartSearchCli({
    command: 'search',
    input: '__slow__',
    config: mockConfig({ timeoutMs: 1_000 }),
  })

  assert.equal(result.ok, false)
  assert.equal(result.error.code, 'SMART_SEARCH_TIMEOUT')
  assert.equal(result.error.details.timeoutMs, 1_000)
})

test('terminates a running command when the DSH execution signal is cancelled', async () => {
  const controller = new AbortController()
  const cancellation = setTimeout(() => controller.abort(), 100)
  try {
    const result = await runSmartSearchCli({
      command: 'search',
      input: '__slow__',
      config: mockConfig(),
      signal: controller.signal,
    })

    assert.equal(result.ok, false)
    assert.equal(result.error.code, 'SMART_SEARCH_CANCELLED')
  } finally {
    clearTimeout(cancellation)
  }
})
