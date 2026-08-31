const [command, input, ...args] = process.argv.slice(2)

if (input === '__invalid_json__') {
  process.stdout.write('not json')
  process.exit(0)
}

if (input === '__stderr__') {
  process.stderr.write('untrusted-stderr-payload')
  process.stdout.write('not json')
  process.exit(1)
}

if (input === '__cli_error__') {
  process.stdout.write(JSON.stringify({ ok: false, error_type: 'config_error', error: 'mock CLI failure' }))
  process.exit(2)
}

if (input === '__large_output__') {
  process.stdout.write(JSON.stringify({ ok: true, payload: 'x'.repeat(16_384) }))
  process.exit(0)
}

if (input === '__slow__') {
  setTimeout(() => {
    process.stdout.write(JSON.stringify({ ok: true, command, input, args }))
  }, 10_000)
} else {
  process.stdout.write(JSON.stringify({ ok: true, command, input, args }))
}
