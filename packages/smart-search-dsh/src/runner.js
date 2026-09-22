import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const SUPPORTED_COMMANDS = new Set([
  'search', 'fetch', 'route', 'deep', 'research',
  'map', 'exa-search', 'zhipu-search', 'context7-docs', 'doctor',
])

function errorResult(command, code, message, details = undefined) {
  return {
    ok: false,
    command,
    error: {
      code,
      message,
      ...(details === undefined ? {} : { details }),
    },
  }
}

function processErrorDetails(error) {
  return error && typeof error === 'object' && typeof error.code === 'string' ? { errorCode: error.code } : {}
}

function formatSearchTimeout(timeoutMs) {
  const reservedForJsonOutput = Math.min(1_000, Math.max(100, Math.floor(timeoutMs / 10)))
  const budgetMs = Math.max(100, timeoutMs - reservedForJsonOutput)
  return String(budgetMs / 1_000)
}

function isRegularFile(candidate) {
  try {
    return fs.statSync(candidate).isFile()
  } catch {
    return false
  }
}

function windowsPathEntries() {
  const rawPath = process.env.Path ?? process.env.PATH ?? ''
  return rawPath.split(path.delimiter).filter(Boolean)
}

function windowsExtensions() {
  const rawExtensions = process.env.PATHEXT ?? '.COM;.EXE;.BAT;.CMD'
  return rawExtensions.split(';').filter(Boolean)
}

function resolveWindowsExecutable(executable) {
  if (process.platform !== 'win32') {
    return executable
  }

  const hasDirectory = path.dirname(executable) !== '.'
  const extension = path.extname(executable)
  const candidates = extension
    ? [
        ...(extension.toLowerCase() === '.cmd' || extension.toLowerCase() === '.bat'
          ? [`${executable.slice(0, -extension.length)}.ps1`]
          : []),
        executable,
      ]
    : [`${executable}.ps1`, ...windowsExtensions().map((suffix) => `${executable}${suffix}`), executable]

  if (hasDirectory) {
    for (const candidate of candidates) {
      const absoluteCandidate = path.resolve(candidate)
      if (isRegularFile(absoluteCandidate)) {
        return absoluteCandidate
      }
    }
    return executable
  }

  for (const directory of windowsPathEntries()) {
    for (const candidate of candidates) {
      const absoluteCandidate = path.join(directory, candidate)
      if (isRegularFile(absoluteCandidate)) {
        return absoluteCandidate
      }
    }
  }
  return executable
}

function createSpawnRequest(executable, args) {
  const resolvedExecutable = resolveWindowsExecutable(executable)
  if (process.platform === 'win32' && /\.ps1$/i.test(resolvedExecutable)) {
    return {
      file: 'pwsh.exe',
      args: ['-NoLogo', '-NoProfile', '-NonInteractive', '-File', resolvedExecutable, ...args],
      windowsVerbatimArguments: false,

    }
  }
  if (process.platform === 'win32' && /\.(?:cmd|bat)$/i.test(resolvedExecutable)) {
    return { unsupportedShell: true }
  }
  return { file: resolvedExecutable, args, windowsVerbatimArguments: false }
}

function terminateChild(child) {
  if (child.exitCode !== null || child.killed || child.pid === undefined) {
    return
  }

  if (process.platform === 'win32') {
    try {
      const killer = spawn('taskkill.exe', ['/pid', String(child.pid), '/t', '/f'], {
        windowsHide: true,
        stdio: 'ignore',
      })
      killer.unref()
    } catch {
      child.kill()
    }
    return
  }

  child.kill('SIGTERM')
}

function parseJsonResult(command, stdout) {
  const text = stdout.trim()
  if (!text) {
    return errorResult(command, 'SMART_SEARCH_INVALID_JSON', 'Smart Search wrote no JSON result.')
  }
  try {
    return { ok: true, value: JSON.parse(text) }
  } catch {
    return errorResult(command, 'SMART_SEARCH_INVALID_JSON', 'Smart Search wrote malformed JSON.')
  }
}

export async function runSmartSearchCli({ command, input, config, signal, extraArgs = [] }) {
  if (!SUPPORTED_COMMANDS.has(command)) {
    throw new TypeError(`smart-search-dsh: unsupported Smart Search command ${command}`)
  }

  const cliArgs = [...config.executableArgs, command]
  // Commands that accept a positional input argument
  const hasPositionalInput = input !== ''
  if (hasPositionalInput) {
    cliArgs.push(input)
  }
  // Add search-specific timeout budget
  if (command === 'search') {
    cliArgs.push('--timeout', formatSearchTimeout(config.timeoutMs))
  }
  // Add any extra arguments from the tool definition (e.g. --budget)
  for (const arg of extraArgs) {
    cliArgs.push(arg)
  }
  cliArgs.push('--format', 'json')

  const request = createSpawnRequest(config.executable, cliArgs)
  if (request.unsupportedShell) {
    return errorResult(
      command,
      'SMART_SEARCH_UNSUPPORTED_INPUT',
      'CMD/BAT launchers are disabled. Configure a trusted executable or PowerShell 7 shim instead.',
    )
  }
  return new Promise((resolve) => {
    let child
    try {
      child = spawn(request.file, request.args, {
        shell: false,
        windowsHide: true,
        windowsVerbatimArguments: request.windowsVerbatimArguments,
        stdio: ['ignore', 'pipe', 'pipe'],
      })
    } catch (error) {
      resolve(errorResult(command, 'SMART_SEARCH_EXECUTABLE_NOT_FOUND', 'Unable to start the Smart Search executable.', {
        ...processErrorDetails(error),
      }))
      return
    }

    let settled = false
    let termination = null
    let outputExceeded = false
    let stdoutBytes = 0
    let stderrBytes = 0
    const stdoutChunks = []

    const cleanup = () => {
      clearTimeout(timeout)
      if (signal) {
        signal.removeEventListener('abort', abortFromCaller)
      }
    }

    const finish = (result) => {
      if (settled) {
        return
      }
      settled = true
      cleanup()
      resolve(result)
    }

    const abortFromCaller = () => {
      if (!termination) {
        termination = 'cancelled'
      }
      terminateChild(child)
    }

    const timeout = setTimeout(() => {
      if (!termination) {
        termination = 'timeout'
      }
      terminateChild(child)
    }, config.timeoutMs)

    if (signal) {
      if (signal.aborted) {
        abortFromCaller()
      } else {
        signal.addEventListener('abort', abortFromCaller, { once: true })
      }
    }

    child.stdout.on('data', (chunk) => {
      const bytes = Buffer.byteLength(chunk)
      stdoutBytes += bytes
      if (stdoutBytes > config.maxOutputBytes) {
        outputExceeded = true
        terminateChild(child)
        return
      }
      stdoutChunks.push(Buffer.from(chunk))
    })

    child.stderr.on('data', (chunk) => {
      stderrBytes += Buffer.byteLength(chunk)
    })

    child.once('error', (error) => {
      if (termination === 'timeout') {
        finish(errorResult(command, 'SMART_SEARCH_TIMEOUT', `Smart Search exceeded the ${config.timeoutMs} ms tool budget.`, {
          timeoutMs: config.timeoutMs,
          stdoutBytes,
          stderrBytes,
        }))
        return
      }
      if (termination === 'cancelled') {
        finish(errorResult(command, 'SMART_SEARCH_CANCELLED', 'The Smart Search tool call was cancelled.', {
          stdoutBytes,
          stderrBytes,
        }))
        return
      }
      finish(errorResult(command, 'SMART_SEARCH_EXECUTABLE_NOT_FOUND', 'Unable to start the Smart Search executable.', {
        ...processErrorDetails(error),
      }))
    })

    child.once('close', (exitCode, exitSignal) => {
      if (termination === 'timeout') {
        finish(errorResult(command, 'SMART_SEARCH_TIMEOUT', `Smart Search exceeded the ${config.timeoutMs} ms tool budget.`, {
          timeoutMs: config.timeoutMs,
          stdoutBytes,
          stderrBytes,
        }))
        return
      }
      if (termination === 'cancelled') {
        finish(errorResult(command, 'SMART_SEARCH_CANCELLED', 'The Smart Search tool call was cancelled.', {
          stdoutBytes,
          stderrBytes,
        }))
        return
      }
      if (outputExceeded) {
        finish(errorResult(command, 'SMART_SEARCH_OUTPUT_TOO_LARGE', `Smart Search exceeded the ${config.maxOutputBytes} byte output limit.`, {
          maxOutputBytes: config.maxOutputBytes,
          stdoutBytes,
          stderrBytes,
        }))
        return
      }

      const parsed = parseJsonResult(command, Buffer.concat(stdoutChunks).toString('utf8'))
      if (!parsed.ok) {
        finish({
          ...parsed,
          error: {
            ...parsed.error,
            details: { stdoutBytes, stderrBytes, exitCode, exitSignal },
          },
        })
        return
      }

      if (exitCode !== 0 || (parsed.value && typeof parsed.value === 'object' && parsed.value.ok === false)) {
        const result = {
          ok: false,
          command,
          error: {
            code: 'SMART_SEARCH_CLI_ERROR',
            message: exitCode === 0 ? 'Smart Search reported an unsuccessful JSON result.' : `Smart Search exited with code ${exitCode}.`,
            details: {
              ...(exitCode === null ? {} : { exitCode }),
              ...(exitSignal === null ? {} : { exitSignal }),
              stdoutBytes,
              stderrBytes,
              ...(parsed.value && typeof parsed.value === 'object' && typeof parsed.value.error_type === 'string'
                ? { smartSearchErrorType: parsed.value.error_type }
                : {}),
            },
          },
          result: parsed.value,
        }
        finish(result)
        return
      }

      finish({ ok: true, command, result: parsed.value })
    })
  })
}
