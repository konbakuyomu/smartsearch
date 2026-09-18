// The mock simulates the smart-search CLI's public JSON contract.
// argv layout: [node, script, command, (optional positional input), ...flags]
const argv = process.argv.slice(2)
const command = argv[0]
const commandExpectsInput = command !== 'doctor'
const input = commandExpectsInput ? argv[1] : ''
const args = commandExpectsInput ? argv.slice(2) : argv.slice(1)

// Validate the contract that an echo-only mock previously failed to enforce.
if (command === 'context7-docs' && (!args[0] || args[0].startsWith('--'))) {
  process.stderr.write('context7-docs requires library_id and query')
  process.exit(2)
}
const budgetIndex = args.indexOf('--budget')
if (budgetIndex >= 0 && !['quick', 'standard', 'deep'].includes(args[budgetIndex + 1])) {
  process.stderr.write('invalid research budget')
  process.exit(2)
}
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
