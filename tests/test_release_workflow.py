import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
RESOLVER = ROOT / "npm" / "scripts" / "resolve-prerelease-version.js"
WORKFLOW = ROOT / ".github" / "workflows" / "publish-npm.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
TARBALL_SMOKE = ROOT / "npm" / "scripts" / "smoke-packed-install.js"
SKILL_PARITY_CHECK = ROOT / "npm" / "scripts" / "check-skill-parity.js"


def read_reference_tree(skill_dir: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((skill_dir / "references").rglob("*"))
        if p.is_file() and p.suffix == ".md"
    )


def read_workflow_events(workflow_text: str) -> dict[str, object]:
    # GitHub Actions follows YAML 1.2, where `on` is a string. BaseLoader keeps
    # that key intact while safe_load above remains the syntax validation gate.
    return yaml.load(workflow_text, Loader=yaml.BaseLoader)["on"]


def read_pyproject_version() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_section = pyproject.split("[project]", 1)[1].split("\n[", 1)[0]
    match = re.search(r'^version = "([^"]+)"$', project_section, flags=re.MULTILINE)
    assert match is not None
    return match.group(1)


def run_resolver(base_version: str, versions: list[str]) -> str:
    result = subprocess.run(
        [
            "node",
            str(RESOLVER),
            "--package",
            "@konbakuyomu/smart-search",
            "--base",
            base_version,
            "--id",
            "beta",
            "--versions-json",
            json.dumps(versions),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def test_resolver_counts_legacy_dev_slots_per_base_version():
    versions = [
        "0.1.9-dev.30",
        "0.1.9",
        "0.1.10-dev.32",
        "0.1.10-dev.34",
        "0.1.10",
    ]

    assert run_resolver("0.1.9", versions) == "0.1.9-beta.2"
    assert run_resolver("0.1.10", versions) == "0.1.10-beta.3"


def test_resolver_prefers_existing_beta_numbers_when_higher_than_legacy_count():
    versions = [
        "0.1.10-dev.32",
        "0.1.10-dev.34",
        "0.1.10-beta.5",
        "0.1.10",
    ]

    assert run_resolver("0.1.10", versions) == "0.1.10-beta.6"


def test_resolver_starts_at_beta_one_without_prior_versions():
    assert run_resolver("0.2.0", []) == "0.2.0-beta.1"


def test_publish_workflow_uses_beta_lane_and_prerelease_guardrails():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert isinstance(yaml.safe_load(workflow), dict)
    events = read_workflow_events(workflow)
    assert events["push"] == {"branches": ["main"], "tags": ["v*"]}
    assert set(events["workflow_dispatch"]["inputs"]) == {
        "target_ref",
        "version",
        "npm_tag",
        "create_github_release",
    }
    assert events["workflow_dispatch"]["inputs"]["target_ref"]["required"] == "true"
    assert events["workflow_dispatch"]["inputs"]["version"]["required"] == "true"
    assert events["workflow_dispatch"]["inputs"]["npm_tag"]["default"] == "next"

    assert "workflow_dispatch:" in workflow
    assert "github.event.inputs.target_ref" in workflow
    assert "github.event.inputs.version" in workflow
    assert "github.event.inputs.npm_tag" in workflow
    assert "resolve-prerelease-version.js" in workflow
    assert "Detect stable release bump commit" in workflow
    assert "chore\\(release\\)" in workflow
    assert "stable-bump.outputs.skip != 'true'" in workflow
    assert "-dev.${GITHUB_RUN_NUMBER}" not in workflow
    assert "&& inputs." not in workflow
    assert "|| inputs." not in workflow
    assert "tag=\"next\"" in workflow
    assert "tag=\"latest\"" in workflow
    assert "Refusing to publish prerelease version" in workflow
    assert "notes_file=\".github/releases/v${version}.md\"" in workflow
    assert "notes_footer=\"$(printf" in workflow
    assert "gh release create" in workflow
    assert "--prerelease" in workflow
    assert "concurrency:" in workflow
    assert "group: publish-npm-${{ github.repository }}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "fetch-depth: 2" in workflow
    assert "git cat-file -e HEAD^1:package.json" in workflow
    assert "git show HEAD^1:package.json" in workflow
    assert "current_version" in workflow
    assert "parent_version" in workflow
    assert "version_changed" in workflow
    assert "legacy_subject" in workflow
    assert 'version="${DISPATCH_VERSION}"' in workflow
    assert 'tag="${DISPATCH_NPM_TAG}"' in workflow
    assert 'version="${GITHUB_REF_NAME#v}"' in workflow


def test_ci_workflow_is_no_publish_and_covers_the_release_runtime_matrix():
    workflow_text = CI_WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)

    assert isinstance(workflow, dict)
    events = read_workflow_events(workflow_text)
    assert set(events) == {"pull_request", "push", "workflow_dispatch"}
    assert events["push"] == {"branches": ["main", "codex/release-*"]}
    assert workflow["permissions"] == {"contents": "read"}
    assert "npm publish" not in workflow_text
    assert "id-token: write" not in workflow_text
    assert "concurrency:" in workflow_text
    assert "cancel-in-progress: true" in workflow_text

    checkout = workflow["jobs"]["test"]["steps"][0]
    assert checkout["uses"] == "actions/checkout@v6"
    assert checkout["with"]["fetch-depth"] == 2

    whitespace_check = workflow["jobs"]["test"]["steps"][-1]
    assert whitespace_check["shell"] == "bash"
    assert "git diff --check HEAD^1 HEAD" in whitespace_check["run"]
    assert "git diff-tree --check --root -r --no-commit-id HEAD" in whitespace_check["run"]

    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]["include"]
    assert {
        (entry["os"], entry["node"], entry["python"])
        for entry in matrix
    } == {
        ("ubuntu-latest", "18", "3.10"),
        ("ubuntu-latest", "24", "3.12"),
        ("windows-latest", "22", "3.12"),
    }
    assert len(matrix) == 3

    for command in [
        "npm ci",
        "npm test",
        "node npm/bin/smart-search.js regression",
        "node npm/bin/smart-search.js smoke --mock --format json",
        "npm run check:skill-parity",
        "npm run pack:dry",
        "npm run smoke:tarball",
        "git diff --check HEAD^1 HEAD",
        "git diff-tree --check --root -r --no-commit-id HEAD",
    ]:
        assert command in workflow_text


def test_release_version_metadata_and_tarball_support_are_synchronized():
    package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))

    version = package_json["version"]
    assert version
    assert package_lock["version"] == version
    assert package_lock["packages"][""]["version"] == version
    assert read_pyproject_version() == version
    assert package_json["scripts"]["check:skill-parity"] == "node npm/scripts/check-skill-parity.js"
    assert package_json["scripts"]["smoke:tarball"] == "node npm/scripts/smoke-packed-install.js"

    tarball_smoke = TARBALL_SMOKE.read_text(encoding="utf-8")
    assert SKILL_PARITY_CHECK.exists()
    for marker in [
        "--pack-destination",
        "--prefix",
        "smart-search-tarball-",
        "--version",
        "regression",
        "smoke",
        "--mock",
        "assertPackContents",
        "src/smart_search/assets/skills/smart-search-cli/",
        'path.extname(filePath) === ".py"',
    ]:
        assert marker in tarball_smoke


def test_release_docs_explain_beta_lane_and_npm_immutability():
    reference = (ROOT / "docs" / "reference.md").read_text(encoding="utf-8")
    reference_zh = (ROOT / "docs" / "reference.zh-CN.md").read_text(encoding="utf-8")
    public_contract = read_reference_tree(ROOT / "skills" / "smart-search-cli")
    packaged_contract = read_reference_tree(
        ROOT / "src" / "smart_search" / "assets" / "skills" / "smart-search-cli"
    )

    required_markers = [
        "Release lanes",
        "<package.json version>-beta.N",
        "dist-tag `next`",
        "0.1.10-beta.3",
        "chore(release): bump version to X.Y.Z",
        ".github/releases/vX.Y.Z.md",
        "vX.Y.Z",
        "workflow_dispatch",
        "target_ref",
        "npm versions are immutable",
        "cannot be renamed in place",
        "Release closeout checklist",
        "create_github_release=false",
        "gh release create vX.Y.Z-beta.N",
        "npm `E409`",
        "machine-readable gap check",
        "mise use -g",
        "non-ASCII JSON",
        "ConvertFrom-Json",
    ]
    for marker in required_markers:
        assert marker in reference
    zh_required_markers = [
        "发布通道",
        "<package.json version>-beta.N",
        "npm `next`",
        "0.1.10-beta.3",
        ".github/releases/vX.Y.Z.md",
        "npm 版本不可变",
        "gh release list",
        "npm `E409`",
        "smart-search regression",
        "smart-search smoke --mock --format json",
        "ConvertFrom-Json",
    ]
    for marker in zh_required_markers:
        assert marker in reference_zh
    contract_markers = [
        "Release Lanes",
        "<package.json version>-beta.N",
        "chore(release): bump version to X.Y.Z",
        ".github/releases/vX.Y.Z.md",
        "npm versions are immutable",
        "Release Closeout Lessons",
        "GitHub release creation fails",
        "npm `E409`",
        "diff-style gap check",
        "smart-search smoke --mock --format json",
        "Windows npm/mise wrapper is emitting UTF-8 JSON",
    ]
    for marker in contract_markers:
        assert marker in public_contract
        assert marker in packaged_contract


def test_current_stable_release_notes_describe_user_visible_changes():
    notes = (ROOT / ".github" / "releases" / "v0.1.14.md").read_text(encoding="utf-8")

    required_markers = [
        "GitHub issue #7",
        "smart-search skills status",
        "smart-search skills update",
        "smart-search diagnose openai-compatible",
        "Context7",
        "Exa",
        "Validation",
    ]
    for marker in required_markers:
        assert marker in notes


def test_v015_release_notes_cover_beta_and_stable_lanes():
    beta_notes = (ROOT / ".github" / "releases" / "v0.1.15-beta.1.md").read_text(encoding="utf-8")
    stable_notes = (ROOT / ".github" / "releases" / "v0.1.15.md").read_text(encoding="utf-8")

    for marker in ["v0.1.15-beta.1", "npm `next`", "tarball", "smart-search regression", "mock smoke"]:
        assert marker in beta_notes
    for marker in ["v0.1.15", "npm `latest`", "Context7", "AnySearch", "Validation"]:
        assert marker in stable_notes


@pytest.mark.skipif(sys.version_info < (3, 11), reason="The release runner uses Python 3.11+ file_digest")
def test_desktop_release_accepts_nested_artifact_paths(tmp_path, monkeypatch):
    workflow = yaml.safe_load((ROOT / ".github/workflows/desktop-build.yml").read_text())
    step = next(step for step in workflow["jobs"]["release-assets"]["steps"]
                if step.get("name") == "Validate version, platforms and checksums")
    script = step["run"].split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    names = [f"SmartSearch-0.1.20-win-{arch}-Setup-unsigned-test.exe" for arch in ("x64", "arm64")]
    names += [f"SmartSearch-0.1.20-macos-{arch}-unsigned-test.dmg" for arch in ("x86_64", "arm64")]
    (tmp_path / "package.json").write_text('{"version":"0.1.20"}')
    for index, name in enumerate(names):
        package = tmp_path / "release-packages" / f"build-{index}" / "installer" / name
        package.parent.mkdir(parents=True)
        package.write_bytes(name.encode())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RELEASE_TAG", "v0.1.20")
    exec(compile(script, "desktop-release-validation", "exec"), {})
    root = tmp_path / "release-packages"
    assert {path.name for path in root.iterdir() if path.is_file()} == set(names) | {"SHA256SUMS.txt"}
    assert all((root / name).read_bytes() == name.encode() for name in names)
    assert len((root / "SHA256SUMS.txt").read_text().splitlines()) == 4
