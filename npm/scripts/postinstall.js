const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const https = require("node:https");
const os = require("node:os");

const packageRoot = path.resolve(__dirname, "..", "..");
const venvDir = path.join(packageRoot, ".smart-search-python");

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: packageRoot,
    stdio: options.stdio || "inherit",
    encoding: "utf8",
    windowsHide: true
  });

  if (result.error) {
    return { ok: false, error: result.error };
  }
  return { ok: result.status === 0, status: result.status, stdout: result.stdout || "", stderr: result.stderr || "" };
}

function pythonCandidates() {
  if (process.platform === "win32") {
    return [
      { command: "py", args: ["-3"] },
      { command: "python", args: [] },
      { command: "python3", args: [] }
    ];
  }
  return [
    { command: "python3", args: [] },
    { command: "python", args: [] }
  ];
}

function findPython() {
  const probe = [
    "-c",
    "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
  ];

  for (const candidate of pythonCandidates()) {
    const result = run(candidate.command, [...candidate.args, ...probe], { stdio: "pipe" });
    if (result.ok) {
      return candidate;
    }
  }
  return null;
}

function venvPython() {
  return process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");
}

/**
 * Download a URL to a temporary file and return the file path.
 */
function downloadToTempFile(url) {
  return new Promise((resolve, reject) => {
    const tmpFile = path.join(os.tmpdir(), `smart-search-get-pip-${Date.now()}.py`);
    const file = fs.createWriteStream(tmpFile);
    https.get(url, (response) => {
      if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
        file.close();
        fs.unlinkSync(tmpFile);
        downloadToTempFile(response.headers.location).then(resolve).catch(reject);
        return;
      }
      if (response.statusCode !== 200) {
        file.close();
        fs.unlinkSync(tmpFile);
        reject(new Error(`HTTP ${response.statusCode} downloading ${url}`));
        return;
      }
      response.pipe(file);
      file.on("finish", () => {
        file.close();
        resolve(tmpFile);
      });
    }).on("error", (err) => {
      file.close();
      if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
      reject(err);
    });
  });
}

/**
 * Strategy 1: python3 -m venv (works on most systems)
 */
function tryVenv(python) {
  console.log("  Trying: python3 -m venv ...");
  const result = run(python.command, [...python.args, "-m", "venv", venvDir], { stdio: "pipe" });
  if (result.ok) return true;

  const stderr = result.stderr || result.stdout || "";
  if (stderr.includes("ensurepip") || stderr.includes("pip") || stderr.includes("venv")) {
    console.log("  venv creation failed (likely missing ensurepip/python3-venv).");
  } else {
    console.log("  venv creation failed.");
  }
  return false;
}

/**
 * Strategy 2: install virtualenv via pip --user, then use it
 */
function tryVirtualenv(python) {
  console.log("  Trying: virtualenv fallback ...");

  // Check if virtualenv is already available
  let hasVirtualenv = run(python.command, [...python.args, "-m", "virtualenv", "--version"], { stdio: "pipe" });

  if (!hasVirtualenv.ok) {
    console.log("  virtualenv not found, installing via pip --user ...");
    const installVenv = run(python.command, [...python.args, "-m", "pip", "install", "--user", "virtualenv"], { stdio: "pipe" });
    if (!installVenv.ok) {
      console.log("  Failed to install virtualenv.");
      return false;
    }
  }

  const result = run(python.command, [...python.args, "-m", "virtualenv", venvDir], { stdio: "pipe" });
  if (result.ok) return true;

  console.log("  virtualenv failed to create the environment.");
  return false;
}

/**
 * Strategy 3: python3 -m venv --without-pip, then bootstrap pip
 */
async function tryVenvWithoutPipAsync(python) {
  console.log("  Trying: venv --without-pip + pip bootstrap ...");

  // Remove any partial venv from earlier attempts
  if (fs.existsSync(venvDir)) {
    fs.rmSync(venvDir, { recursive: true, force: true });
  }

  const result = run(python.command, [...python.args, "-m", "venv", "--without-pip", venvDir], { stdio: "pipe" });
  if (!result.ok) {
    console.log("  venv --without-pip also failed.");
    return false;
  }

  const py = venvPython();

  // Try ensurepip.bootstrap() first
  console.log("  Bootstrapping pip via ensurepip ...");
  const bootstrap = run(py, ["-m", "ensurepip", "--upgrade"], { stdio: "pipe" });
  if (bootstrap.ok) return true;

  // Fall back to get-pip.py
  console.log("  ensurepip unavailable, downloading get-pip.py ...");
  let tmpFile;
  try {
    tmpFile = await downloadToTempFile("https://bootstrap.pypa.io/get-pip.py");
  } catch (err) {
    console.log(`  Failed to download get-pip.py: ${err.message}`);
    return false;
  }

  try {
    const getPipResult = run(py, [tmpFile], { stdio: "pipe" });
    if (getPipResult.ok) return true;
    console.log("  get-pip.py failed to install pip.");
    return false;
  } finally {
    if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
  }
}

/**
 * Create a virtual environment using the best available method.
 * Tries: venv -> virtualenv -> venv --without-pip + pip bootstrap
 */
async function createVenv(python) {
  if (tryVenv(python)) return true;

  // Clean up failed attempt
  if (fs.existsSync(venvDir)) {
    fs.rmSync(venvDir, { recursive: true, force: true });
  }

  if (tryVirtualenv(python)) return true;

  // Clean up failed attempt
  if (fs.existsSync(venvDir)) {
    fs.rmSync(venvDir, { recursive: true, force: true });
  }

  if (await tryVenvWithoutPipAsync(python)) return true;

  return false;
}

// --- Main ---

async function main() {
  const python = findPython();
  if (!python) {
    console.error("smart-search requires Python 3.10 or newer.");
    console.error("Install Python, then run: npm install -g @konbakuyomu/smart-search@latest");
    process.exit(1);
  }

  if (!fs.existsSync(venvPython())) {
    console.log("Creating smart-search Python runtime...");
    const created = await createVenv(python);
    if (!created) {
      console.error("");
      console.error("Failed to create the smart-search Python virtual environment.");
      console.error("");
      console.error("On Debian/Ubuntu, install the required package:");
      console.error("  sudo apt install python3-venv");
      console.error("");
      console.error("Then retry: npm install -g @konbakuyomu/smart-search@latest");
      process.exit(1);
    }
  }

  const py = venvPython();

  console.log("Installing smart-search Python package...");
  const install = run(py, [
    "-m",
    "pip",
    "install",
    "--disable-pip-version-check",
    packageRoot
  ]);

  if (!install.ok) {
    console.error("Failed to install the bundled smart-search Python package.");
    process.exit(install.status || 1);
  }
}

main().catch((err) => {
  console.error("Unexpected error during postinstall:", err.message);
  process.exit(1);
});
