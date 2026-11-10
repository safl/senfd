# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / ".github" / "scripts" / "release_ready.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="needs git and bash",
)


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repos(tmp_path):
    """A base repository and a clone of it with a pull request's branch"""

    base, pr = tmp_path / "base", tmp_path / "pr"
    base.mkdir()
    git(base, "init", "-q", "-b", "main")
    git(base, "commit", "-q", "--allow-empty", "-m", "first")
    git(tmp_path, "clone", "-q", str(base), str(pr))
    return base, pr


def ready(pr):
    return subprocess.run(
        ["bash", str(SCRIPT), "main"], cwd=pr, capture_output=True, text=True
    )


def test_a_release_pull_request_behind_its_base_fails(repos):
    base, pr = repos
    git(pr, "commit", "-q", "--allow-empty", "-m", "ver: bump to v1.2.3")
    git(base, "commit", "-q", "--allow-empty", "-m", "landed meanwhile")

    proc = ready(pr)
    assert proc.returncode == 1
    assert "Rebase on main" in proc.stdout


def test_a_release_pull_request_holding_its_base_passes(repos):
    base, pr = repos
    git(base, "commit", "-q", "--allow-empty", "-m", "landed meanwhile")
    git(pr, "pull", "-q", "--ff-only")
    git(pr, "commit", "-q", "--allow-empty", "-m", "ver: bump to v1.2.3")

    assert ready(pr).returncode == 0


def test_another_pull_request_behind_its_base_passes(repos):
    base, pr = repos
    git(pr, "commit", "-q", "--allow-empty", "-m", "fix: something")
    git(base, "commit", "-q", "--allow-empty", "-m", "landed meanwhile")

    proc = ready(pr)
    assert proc.returncode == 0
    assert "Not a release pull request" in proc.stdout
