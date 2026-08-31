const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..", "..");
const packageJson = JSON.parse(fs.readFileSync(path.join(packageRoot, "package.json"), "utf8"));

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd || packageRoot,
    env: options.env || process.env,
    encoding: "utf8",
    shell: options.shell || false,
    stdio: options.capture ? "pipe" : "inherit",
    windowsHide: true
  });

  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    if (options.capture) {
      process.stdout.write(result.stdout || "");
      process.stderr.write(result.stderr || "");
    }
    throw new Error(`${command} ${args.join(" ")} exited with ${result.status || 1}.`);
  }

  return result.stdout || "";
}

function runNpm(args, options = {}) {
  if (process.env.npm_execpath) {
    return run(process.execPath, [process.env.npm_execpath, ...args], options);
  }
  return run("npm", args, { ...options, shell: process.platform === "win32" });
}

function assertPackContents(files) {
  assert.ok(Array.isArray(files), "npm pack --json must report the packed file list");
  const exactFiles = new Set([
    "LICENSE",
    "README.md",
    "README.zh-CN.md",
    "package.json",
    "pyproject.toml"
  ]);
  const allowedPrefixes = [
    "npm/",
    "skills/smart-search-cli/",
    "src/smart_search/assets/skills/smart-search-cli/"
  ];
  const unexpected = files
    .map((file) => file.path)
    .filter(
      (filePath) =>
        !exactFiles.has(filePath) &&
        !allowedPrefixes.some((prefix) => filePath.startsWith(prefix)) &&
        !(filePath.startsWith("src/smart_search/") && path.extname(filePath) === ".py")
    );

  assert.deepEqual(unexpected, [], "tarball contains files outside package.json files declarations");
  for (const requiredPath of ["package.json", "pyproject.toml", "npm/bin/smart-search.js", "src/smart_search/cli.py"]) {
    assert.ok(files.some((file) => file.path === requiredPath), `tarball is missing ${requiredPath}`);
  }
}

const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "smart-search-tarball-"));
const tarballDir = path.join(tempRoot, "tarball");
const installPrefix = path.join(tempRoot, "install");
const callerCwd = path.join(tempRoot, "caller");
const homeDir = path.join(tempRoot, "home");
fs.mkdirSync(tarballDir);
fs.mkdirSync(callerCwd);
fs.mkdirSync(homeDir);

const packed = JSON.parse(
  runNpm(["pack", "--json", "--pack-destination", tarballDir], { capture: true })
);
assert.equal(packed.length, 1, "npm pack must produce exactly one tarball");
assertPackContents(packed[0].files);

const tarballPath = path.join(tarballDir, packed[0].filename);
assert.ok(fs.existsSync(tarballPath), `npm pack did not create ${tarballPath}`);
runNpm(["install", "--no-audit", "--no-fund", "--prefix", installPrefix, tarballPath]);

const installedRoot = path.join(installPrefix, "node_modules", "@konbakuyomu", "smart-search");
const wrapperPath = path.join(installedRoot, "npm", "bin", "smart-search.js");
assert.ok(fs.existsSync(wrapperPath), "packed install is missing the smart-search wrapper");

const isolatedEnv = {
  ...process.env,
  HOME: homeDir,
  USERPROFILE: homeDir,
  INIT_CWD: callerCwd
};
const version = run(process.execPath, [wrapperPath, "--version"], {
  cwd: callerCwd,
  env: isolatedEnv,
  capture: true
});
assert.match(version, new RegExp(`smart-search ${packageJson.version.replaceAll(".", "\\.")}`));
run(process.execPath, [wrapperPath, "regression"], { cwd: callerCwd, env: isolatedEnv });
const smokeOutput = run(process.execPath, [wrapperPath, "smoke", "--mock", "--format", "json"], {
  cwd: callerCwd,
  env: isolatedEnv,
  capture: true
});
assert.equal(JSON.parse(smokeOutput).ok, true, "packed mock smoke must report ok=true");

const skillsUpdate = JSON.parse(
  run(
    process.execPath,
    [
      wrapperPath,
      "skills",
      "update",
      "--targets",
      "opencode",
      "--skills-root",
      homeDir,
      "--format",
      "json"
    ],
    { cwd: callerCwd, env: isolatedEnv, capture: true }
  )
);
assert.equal(skillsUpdate.ok, true, "packed OpenCode skill update must report ok=true");
assert.equal(skillsUpdate.installed_count, 1, "packed OpenCode skill update must install one target");
const opencodeSkill = path.join(homeDir, ".config", "opencode", "skills", "smart-search-cli", "SKILL.md");
assert.ok(fs.existsSync(opencodeSkill), "packed OpenCode skill update must use the canonical global path");

const skillsStatus = JSON.parse(
  run(
    process.execPath,
    [
      wrapperPath,
      "skills",
      "status",
      "--targets",
      "opencode",
      "--skills-root",
      homeDir,
      "--format",
      "json"
    ],
    { cwd: callerCwd, env: isolatedEnv, capture: true }
  )
);
assert.equal(skillsStatus.targets[0].status, "up_to_date", "packed OpenCode status must inspect the canonical global path");

console.log(`Packed tarball install smoke passed in temporary prefix ${installPrefix}.`);
