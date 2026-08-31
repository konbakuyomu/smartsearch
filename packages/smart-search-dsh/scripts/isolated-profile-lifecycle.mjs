import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SUPPORTED_DSH_VERSION } from '../src/config.js'

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const packageManifest = JSON.parse(fs.readFileSync(path.join(packageRoot, 'package.json'), 'utf8'))

function parseArgs(argv) {
  const values = { profile: 'smart-search-dsh-isolated' }
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index]
    const value = argv[index + 1]
    if (!flag?.startsWith('--') || value === undefined) {
      throw new Error('Usage: node isolated-profile-lifecycle.mjs --dsh-entry PATH --work-dir PATH [--profile NAME]')
    }
    values[flag.slice(2)] = value
  }
  return values
}

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

function scrubbedEnvironment(workDir) {
  const env = { ...process.env }
  for (const key of Object.keys(env)) {
    if (/(?:api[_-]?key|token|secret|password|credential|authorization)/i.test(key) || /^(?:npm_config_|pnpm_|corepack_)/i.test(key)) {
      delete env[key]
    }
  }

  const homeDir = path.join(workDir, 'home')
  const appDataDir = path.join(workDir, 'appdata')
  const localAppDataDir = path.join(workDir, 'local-appdata')
  return {
    ...env,
    DSH_HOME: path.join(workDir, 'dsh-home'),
    DSH_TELEMETRY_DISABLED: '1',
    HOME: homeDir,
    USERPROFILE: homeDir,
    APPDATA: appDataDir,
    LOCALAPPDATA: localAppDataDir,
    XDG_CONFIG_HOME: path.join(workDir, 'xdg-config'),
    XDG_CACHE_HOME: path.join(workDir, 'xdg-cache'),
    XDG_DATA_HOME: path.join(workDir, 'xdg-data'),
    NPM_CONFIG_CACHE: path.join(workDir, 'npm-cache'),
    NPM_CONFIG_USERCONFIG: path.join(workDir, 'npmrc'),
    NPM_CONFIG_GLOBALCONFIG: path.join(workDir, 'npm-globalrc'),
    PNPM_HOME: path.join(workDir, 'pnpm-home'),
    PNPM_STORE_DIR: path.join(workDir, 'pnpm-store'),
    PNPM_CONFIG_STORE_DIR: path.join(workDir, 'pnpm-store'),
    PNPM_CONFIG_UPDATE_NOTIFIER: 'false',
    COREPACK_HOME: path.join(workDir, 'corepack-home'),
    SMART_SEARCH_CONFIG_DIR: path.join(workDir, 'smart-search-config'),
  }
}

function runNode(entry, args, options) {
  const result = spawnSync(process.execPath, [entry, ...args], {
    cwd: options.cwd,
    env: options.env,
    encoding: 'utf8',
    shell: false,
    windowsHide: true,
    timeout: 120_000,
  })
  if (result.error) {
    throw result.error
  }
  if (result.status !== 0) {
    process.stdout.write(result.stdout || '')
    process.stderr.write(result.stderr || '')
    throw new Error(`${path.basename(entry)} ${args.join(' ')} exited with ${result.status ?? 1}`)
  }
  return result.stdout || ''
}

const args = parseArgs(process.argv.slice(2))
if (!args['dsh-entry'] || !args['work-dir']) {
  throw new Error('Usage: node isolated-profile-lifecycle.mjs --dsh-entry PATH --work-dir PATH [--profile NAME]')
}

const dshEntry = path.resolve(args['dsh-entry'])
const workDir = path.resolve(args['work-dir'])
const profile = args.profile
assert.match(profile, /^[a-z0-9][a-z0-9-]*$/i, 'profile must be a simple profile name')
assert.ok(fs.existsSync(dshEntry), `DSH entry was not found: ${dshEntry}`)
assert.equal(fs.existsSync(workDir), false, `Refusing to mutate an existing work directory: ${workDir}`)

const dshManifestPath = path.resolve(path.dirname(dshEntry), '..', 'package.json')
const dshManifest = JSON.parse(fs.readFileSync(dshManifestPath, 'utf8'))
assert.equal(dshManifest.name, '@deepseek-ai/dsh', `Unexpected DSH manifest at ${dshManifestPath}`)
assert.equal(dshManifest.version, SUPPORTED_DSH_VERSION, `Expected @deepseek-ai/dsh@${SUPPORTED_DSH_VERSION}`)

fs.mkdirSync(workDir, { recursive: true })
const env = scrubbedEnvironment(workDir)
const dshHome = env.DSH_HOME
const profileDir = path.join(dshHome, 'profiles', profile)
const tarballDir = path.join(workDir, 'tarball')
fs.mkdirSync(tarballDir, { recursive: true })

const runDsh = (dshArgs) => runNode(dshEntry, dshArgs, { cwd: packageRoot, env })

runDsh(['plugin', '--profile', profile, 'list'])
const profilePatchPath = path.join(profileDir, 'cordis.patch.yml')
assert.ok(fs.existsSync(profilePatchPath), 'DSH did not create the profile patch file')
const profilePatchBefore = fs.readFileSync(profilePatchPath)
const sentinelPath = path.join(profileDir, 'unrelated-profile-sentinel.txt')
const sentinel = Buffer.from('smart-search-dsh isolated lifecycle sentinel\n', 'utf8')
fs.writeFileSync(sentinelPath, sentinel, { flag: 'wx' })

const packed = JSON.parse(
  runNode(npmCliPath(), ['pack', '--json', '--pack-destination', tarballDir], { cwd: packageRoot, env }),
)
assert.equal(packed.length, 1, 'npm pack must emit one tarball')
const tarballPath = path.join(tarballDir, packed[0].filename)
assert.ok(fs.existsSync(tarballPath), `npm pack did not create ${tarballPath}`)

runDsh(['plugin', '--profile', profile, 'add', tarballPath])
const installedDump = runDsh(['--profile', profile, '--dump-config'])
assert.match(installedDump, /@konbakuyomu\/smart-search-dsh/)
assert.match(installedDump, /id: smart-search-dsh/)

const mockPath = path.join(packageRoot, 'scripts', 'mock-smart-search.mjs')
const installedVerification = runNode(
  path.join(packageRoot, 'scripts', 'verify-installed-bundle.mjs'),
  ['--profile-dir', profileDir, '--mock', mockPath],
  { cwd: packageRoot, env },
)
assert.equal(JSON.parse(installedVerification).ok, true, 'installed bundle mock call did not pass')

runDsh(['plugin', '--profile', profile, 'remove', packageManifest.name])
const removedDump = runDsh(['--profile', profile, '--dump-config'])
assert.doesNotMatch(removedDump, /@konbakuyomu\/smart-search-dsh/)

// Re-adding the exact packed version exercises the documented rollback path.
runDsh(['plugin', '--profile', profile, 'add', tarballPath])
const rollbackDump = runDsh(['--profile', profile, '--dump-config'])
assert.match(rollbackDump, /@konbakuyomu\/smart-search-dsh/)
assert.match(rollbackDump, /id: smart-search-dsh/)

runDsh(['plugin', '--profile', profile, 'remove', packageManifest.name])
const finalDump = runDsh(['--profile', profile, '--dump-config'])
assert.doesNotMatch(finalDump, /@konbakuyomu\/smart-search-dsh/)

const profileManifest = JSON.parse(fs.readFileSync(path.join(profileDir, 'package.json'), 'utf8'))
assert.equal(profileManifest.dependencies?.[packageManifest.name], undefined, 'removed bundle remains in profile dependencies')
assert.equal(profileManifest.dsh?.profile?.bundles?.includes(packageManifest.name), false, 'removed bundle remains in profile order')
assert.deepEqual(fs.readFileSync(profilePatchPath), profilePatchBefore, 'DSH changed the unrelated profile patch layer')
assert.deepEqual(fs.readFileSync(sentinelPath), sentinel, 'DSH changed an unrelated profile file')

console.log(JSON.stringify({
  ok: true,
  dshVersion: dshManifest.version,
  profile,
  bundle: packageManifest.name,
  workDir,
  lifecycle: ['add', 'remove', 're-add-packed-version', 'remove'],
  preservedFiles: ['cordis.patch.yml', 'unrelated-profile-sentinel.txt'],
}, null, 2))
