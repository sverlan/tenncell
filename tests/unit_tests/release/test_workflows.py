"""Properties of the GitHub workflows that the public release relies on.

The files are read as text: the release starts only from a tag vX.Y.Z, checks the
tag before building, and uploads in a separate job behind the ``pypi`` environment
with trusted publishing (no stored secret). Third-party actions are pinned by commit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[3] / ".github" / "workflows"


def _text(name: str) -> str:
    path = WORKFLOWS / name
    if not path.is_file():
        pytest.skip("the workflows are not part of the source distribution")
    return path.read_text(encoding="utf-8")


def test_the_release_starts_only_from_a_version_tag() -> None:
    release = _text("release.yml")
    trigger = release[release.index("\non:") : release.index("\npermissions:")]
    assert 'tags: ["v[0-9]+.[0-9]+.[0-9]+"]' in trigger
    assert "branches" not in trigger and "workflow_dispatch" not in trigger


def test_the_release_checks_the_tag_and_the_package_before_uploading() -> None:
    release = _text("release.yml")
    build = release[release.index("\n  build:") : release.index("\n  publish:")]
    assert 'git merge-base --is-ancestor "${GITHUB_SHA}" origin/main' in build
    assert 'test "${GITHUB_REF_NAME}" = "v${version}"' in build
    assert 'grep -qx "## ${version}" CHANGELOG.md' in build
    assert build.index("src/nnc/_version.py") < build.index("pdm build")
    for step in ("pdm run lint", "pdm run typecheck", "pdm run test"):
        assert step in build


def test_the_upload_is_a_separate_job_with_trusted_publishing() -> None:
    release = _text("release.yml")
    publish = release[release.index("\n  publish:") :]
    assert "needs: build" in publish
    assert "name: pypi" in publish
    assert "id-token: write" in publish
    assert "pypa/gh-action-pypi-publish@" in publish
    assert "id-token" not in release[: release.index("\n  publish:")]
    assert "secrets." not in release and "password" not in release


def test_the_full_suite_starts_only_by_hand_with_the_tools() -> None:
    full = _text("full.yml")
    trigger = full[full.index("\non:") : full.index("\npermissions:")]
    assert trigger.strip() == "on:\n  workflow_dispatch:"
    assert 'sh scripts/ci_full_tools.sh "${HOME}/nnc-tools"' in full
    assert full.index("ci_full_tools.sh") < full.index("pdm run test")


@pytest.mark.parametrize("name", ["ci.yml", "release.yml", "full.yml"])
def test_actions_are_pinned_by_commit(name: str) -> None:
    uses = re.findall(r"uses:\s*(\S+)", _text(name))
    assert uses
    for action in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", action), action


@pytest.mark.parametrize("name", ["ci.yml", "release.yml", "full.yml"])
def test_workflows_only_read_the_repository(name: str) -> None:
    assert "permissions:\n  contents: read\n" in _text(name)
