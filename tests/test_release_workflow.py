import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESOLVER = ROOT / "npm" / "scripts" / "resolve-prerelease-version.js"
WORKFLOW = ROOT / ".github" / "workflows" / "publish-npm.yml"


def read_reference_tree(skill_dir: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((skill_dir / "references").rglob("*"))
        if p.is_file() and p.suffix == ".md"
    )


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


def test_release_docs_explain_beta_lane_and_npm_immutability():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
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
        assert marker in readme
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
        assert marker in readme_zh
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
