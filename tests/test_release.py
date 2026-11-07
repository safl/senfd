# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / ".github" / "scripts" / "release.py"
spec = importlib.util.spec_from_file_location("release", SCRIPT)
assert spec and spec.loader
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def tree(tmp_path, version, changelog):
    (tmp_path / "src" / "senfd").mkdir(parents=True)
    (tmp_path / "src" / "senfd" / "__init__.py").write_text(
        f'__version__ = "{version}"\n'
    )
    (tmp_path / "CHANGELOG.md").write_text(changelog)
    return tmp_path


CHANGELOG = "# Changelog\n\n## 1.2.3\n\nThe notes.\n\n## 1.2.2\n\nOlder.\n"


def test_a_bump_releases_its_section(tmp_path):
    root = tree(tmp_path, "1.2.3", CHANGELOG)
    assert release.check("ver: bump to v1.2.3", root) == ("1.2.3", "The notes.")


@pytest.mark.parametrize(
    "subject, version, changelog, why",
    [
        ("feat: something", "1.2.3", CHANGELOG, "not a version bump"),
        ("ver: bump to v1.2.4", "1.2.3", CHANGELOG, "__version__ is 1.2.3"),
        ("ver: bump to v1.2.4", "1.2.4", CHANGELOG, "no '## 1.2.4' section"),
    ],
)
def test_what_does_not_release_says_why(tmp_path, subject, version, changelog, why):
    root = tree(tmp_path, version, changelog)
    with pytest.raises(ValueError, match=why):
        release.check(subject, root)


def test_the_repository_releases_its_version_once_bumped():
    """The script reads the files of this repository as they are laid out"""

    root = Path(__file__).parent.parent
    version = release.VERSION.search(
        (root / "src" / "senfd" / "__init__.py").read_text()
    ).group(1)
    if release.notes_for((root / "CHANGELOG.md").read_text(), version):
        assert release.check(f"ver: bump to v{version}", root)[0] == version
    else:
        with pytest.raises(ValueError, match="CHANGELOG.md has no"):
            release.check(f"ver: bump to v{version}", root)
