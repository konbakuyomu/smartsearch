export const SUPPORTED_DSH_VERSION = '0.1.1-rc.2'
// Leave the CLI its full 180-second default search budget plus one second to
// serialize the structured JSON result before the DSH tool deadline fires.
export const DEFAULT_TIMEOUT_MS = 181_000
export const DEFAULT_MAX_OUTPUT_BYTES = 262_144
export const MAX_INPUT_BYTES = 8_192
export const MIN_TIMEOUT_MS = 1_000
export const MAX_TIMEOUT_MS = 600_000
export const MIN_OUTPUT_BYTES = 4_096
export const MAX_OUTPUT_BYTES = 1_048_576
export const MAX_EXECUTABLE_ARGS = 16

const CONFIG_KEYS = new Set(['executable', 'executableArgs', 'timeoutMs', 'maxOutputBytes'])

function assertPlainObject(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('smart-search-dsh: config must be an object')
  }
}

function resolvePositiveInteger(value, fallback, name, minimum, maximum) {
  const resolved = value === undefined ? fallback : value
  if (!Number.isInteger(resolved) || resolved < minimum || resolved > maximum) {
    throw new RangeError(`smart-search-dsh: ${name} must be an integer from ${minimum} to ${maximum}`)
  }
  return resolved
}

function resolveExecutable(value) {
  const resolved = value === undefined ? 'smart-search' : value
  if (typeof resolved !== 'string' || !resolved.trim() || resolved.includes('\0')) {
    throw new TypeError('smart-search-dsh: executable must be a non-empty string without NUL bytes')
  }
  return resolved.trim()
}

function resolveExecutableArgs(value) {
  const resolved = value === undefined ? [] : value
  if (!Array.isArray(resolved) || resolved.length > MAX_EXECUTABLE_ARGS) {
    throw new TypeError(`smart-search-dsh: executableArgs must contain at most ${MAX_EXECUTABLE_ARGS} strings`)
  }
  return resolved.map((argument, index) => {
    if (typeof argument !== 'string' || argument.includes('\0')) {
      throw new TypeError(`smart-search-dsh: executableArgs[${index}] must be a string without NUL bytes`)
    }
    return argument
  })
}

export function normalizeConfig(input = {}) {
  assertPlainObject(input)
  for (const key of Object.keys(input)) {
    if (!CONFIG_KEYS.has(key)) {
      throw new TypeError(`smart-search-dsh: unsupported config key ${key}`)
    }
  }

  return Object.freeze({
    executable: resolveExecutable(input.executable),
    executableArgs: Object.freeze(resolveExecutableArgs(input.executableArgs)),
    timeoutMs: resolvePositiveInteger(input.timeoutMs, DEFAULT_TIMEOUT_MS, 'timeoutMs', MIN_TIMEOUT_MS, MAX_TIMEOUT_MS),
    maxOutputBytes: resolvePositiveInteger(
      input.maxOutputBytes,
      DEFAULT_MAX_OUTPUT_BYTES,
      'maxOutputBytes',
      MIN_OUTPUT_BYTES,
      MAX_OUTPUT_BYTES,
    ),
  })
}
