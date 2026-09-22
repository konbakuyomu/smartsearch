// One-time local setup for npm packages CI has never published. npm trusted
// publishing (OIDC) can only be configured on a package that already exists,
// so reserve each missing platform package with a 0.0.0 placeholder, then
// trust the release workflow. Run while logged in to npm; add --dry-run to
// print the npm commands without running them.
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const WORKFLOW = "publish-npm.yml";
const TRUST_MIN_NPM = [11, 15, 0];
const MANIFEST_URL = "https://raw.githubusercontent.com/konbakuyomu/smartsearch/main/package.json";
const dryRun = process.argv.includes("--dry-run");

function npmCommand(args) {
  // Reuse the repo helper when running from a checkout; a downloaded copy
  // falls back to the npm that ships with this Node.
  try { return require("./npm-command")(args); } catch {}
  const directory = path.dirname(process.execPath);
  const script = [process.env.npm_execpath,
    path.join(directory, "node_modules/npm/bin/npm-cli.js"),
    path.resolve(directory, "../lib/node_modules/npm/bin/npm-cli.js")].filter(Boolean)
    .find(file => fs.existsSync(file));
  if (!script) throw new Error("找不到 npm，请确认 Node.js 安装完整");
  return [process.execPath, [fs.realpathSync(script), ...args]];
}

function npm(args, { interactive = false, cwd } = {}) {
  const [node, argv] = npmCommand(args);
  const result = spawnSync(node, argv, {
    cwd, encoding: "utf8", windowsHide: true, stdio: interactive ? "inherit" : "pipe"
  });
  if (result.error) throw result.error;
  return result;
}

function run(args, options) {
  console.log(`\n> npm ${args.join(" ")}`);
  if (dryRun) return { status: 0 };
  return npm(args, { ...options, interactive: true });
}

async function loadManifest() {
  const local = path.resolve(__dirname, "../../package.json");
  if (fs.existsSync(local)) return JSON.parse(fs.readFileSync(local, "utf8"));
  const response = await fetch(MANIFEST_URL);
  if (!response.ok) throw new Error(`读取 ${MANIFEST_URL} 失败：HTTP ${response.status}`);
  return response.json();
}

function exists(name) {
  const result = npm(["view", name, "name", "--json"]);
  if (result.status === 0) return true;
  if ((result.stderr + result.stdout).includes("E404")) return false;
  throw new Error(result.stderr || result.stdout);
}

function npmSupportsTrust() {
  const version = npm(["--version"]).stdout.trim().split(".").map(Number);
  for (let i = 0; i < TRUST_MIN_NPM.length; i++) {
    if (version[i] !== TRUST_MIN_NPM[i]) return version[i] > TRUST_MIN_NPM[i];
  }
  return true;
}

function publishPlaceholder(manifest, name) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "smart-search-placeholder-"));
  try {
    fs.writeFileSync(path.join(directory, "package.json"), JSON.stringify({
      name,
      version: "0.0.0",
      description: `Placeholder reserving the ${manifest.name} native runtime package name. Install ${manifest.name} instead.`,
      license: manifest.license,
      repository: manifest.repository
    }, null, 2) + "\n");
    fs.writeFileSync(path.join(directory, "README.md"),
      `# ${name}\n\nPlaceholder. Install \`${manifest.name}\` instead; it selects the right native package.\n`);
    const args = ["publish", "--access", "public", ...(dryRun ? ["--dry-run"] : [])];
    console.log(`\n发布占位版本 ${name}@0.0.0\n> npm ${args.join(" ")}`);
    return npm(args, { cwd: directory, interactive: true }).status === 0;
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

async function main() {
  const manifest = await loadManifest();
  const repository = String(manifest.repository?.url || manifest.repository || "")
    .match(/github\.com[/:]([^/]+\/[^/.]+)/)?.[1];
  if (!repository) throw new Error("package.json 缺少 GitHub repository 地址");
  const packages = Object.keys(manifest.optionalDependencies || {});
  if (!packages.length) throw new Error("package.json 里没有平台包（optionalDependencies）");

  if (!dryRun) {
    let whoami = npm(["whoami"]);
    if (whoami.status !== 0) {
      console.log("还没有登录 npm，接下来按提示在浏览器里登录（需要两步验证）。");
      if (npm(["login"], { interactive: true }).status !== 0) throw new Error("npm 登录失败");
      whoami = npm(["whoami"]);
      if (whoami.status !== 0) throw new Error("npm 登录失败");
    }
    console.log(`已登录 npm：${whoami.stdout.trim()}`);
  }

  const failed = [];
  for (const name of packages) {
    if (exists(name)) {
      console.log(`已存在，跳过占位发布：${name}`);
    } else if (!publishPlaceholder(manifest, name)) {
      failed.push(`${name}：占位版本发布失败`);
    }
  }

  // trust needs npm >= 11.15; borrow the latest npm when the local one is older.
  const trustPrefix = dryRun || npmSupportsTrust() ? [] : ["exec", "--yes", "--package=npm@latest", "--", "npm"];
  console.log(`\n配置可信发布：${repository} 的 .github/workflows/${WORKFLOW}`);
  console.log("第一次会要求两步验证；可以在网页上勾选 5 分钟内跳过，后面几个包就不用再验证。");
  for (const name of packages) {
    if (failed.some(entry => entry.startsWith(`${name}：`))) continue;
    const args = [...trustPrefix, "trust", "github", name,
      "--file", WORKFLOW, "--repo", repository, "--allow-publish", "--yes"];
    if (run(args).status !== 0) failed.push(`${name}：可信发布配置失败（如果提示已存在配置，说明之前已配好，可忽略）`);
  }

  console.log("");
  if (failed.length) {
    console.log("以下包没有完成：");
    for (const entry of failed) console.log(`  - ${entry}`);
    process.exitCode = 1;
  } else {
    console.log("全部完成。回到 GitHub Actions 重新运行失败的 Publish npm package 即可。");
  }
}

main().catch(error => {
  console.error(error.message || error);
  process.exitCode = 1;
});
