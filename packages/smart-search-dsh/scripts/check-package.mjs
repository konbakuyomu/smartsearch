import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SUPPORTED_DSH_VERSION } from '../src/config.js'

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const manifest = JSON.parse(fs.readFileSync(path.join(packageRoot, 'package.json'), 'utf8'))

function npmCliPath() {
  const candidates = [
    process.env.npm_execpath,
    path.resolve(process.execPath, '..', 'node_modules', 'npm', 'bin', 'npm-cli.js'),
  ].filter(Boolean)
  const npmCli = candidates.find((candidate) => fs.existsSync(candidate))
  if (!npmCli) {
    throw new Error('Unable to locate npm-cli.js. Run this through npm or a Node installation with npm.')
  }
  return npmCli
}

function runNpm(args) {
  const result = spawnSync(process.execPath, [npmCliPath(), ...args], {
    cwd: packageRoot,
    encoding: 'utf8',
    shell: false,
    windowsHide: true,
  })
  if (result.error) {
    throw result.error
  }
  if (result.status !== 0) {
    process.stdout.write(result.stdout || '')
    process.stderr.write(result.stderr || '')
    throw new Error(`npm ${args.join(' ')} exited with ${result.status ?? 1}`)
  }
  return result.stdout
}

const packed = JSON.parse(runNpm(['pack', '--dry-run', '--json']))
assert.equal(packed.length, 1, 'npm pack must produce one archive description')
const archivePaths = new Set(packed[0].files.map((file) => file.path))
const requiredPaths = [
  'LICENSE',
  'README.md',
  'package.json',
  'index.js',
  'cordis.patch.yml',
  'src/config.js',
  'src/runner.js',
  'src/tools.js',
  'scripts/check-package.mjs',
  'scripts/isolated-profile-lifecycle.mjs',
  'scripts/mock-smart-search.mjs',
  'scripts/verify-installed-bundle.mjs',
]
for (const requiredPath of requiredPaths) {
  assert.ok(archivePaths.has(requiredPath), `archive is missing ${requiredPath}`)
}
assert.equal([...archivePaths].some((filePath) => filePath.startsWith('test/')), false, 'archive must not publish test sources')

assert.equal(manifest.dsh?.bundle?.patch, './cordis.patch.yml')
assert.equal(manifest.peerDependencies?.['@deepseek-ai/dsh'], SUPPORTED_DSH_VERSION)
assert.equal(manifest.peerDependencies?.['@deepseek-ai/dsh-tools'], SUPPORTED_DSH_VERSION)
assert.equal(manifest.peerDependenciesMeta?.['@deepseek-ai/dsh']?.optional, true)
assert.equal(manifest.peerDependenciesMeta?.['@deepseek-ai/dsh-tools']?.optional, true)
for (const lifecycleScript of ['preinstall', 'install', 'postinstall', 'prepare']) {
  assert.equal(manifest.scripts?.[lifecycleScript], undefined, `bundle must not declare ${lifecycleScript}`)
}

const patch = fs.readFileSync(path.join(packageRoot, 'cordis.patch.yml'), 'utf8')
assert.match(patch, /id: smart-search-dsh/)
assert.match(patch, /name: '@konbakuyomu\/smart-search-dsh'/)

console.log(`Package archive contract passed for ${manifest.name}@${manifest.version}.`)
