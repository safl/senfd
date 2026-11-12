# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
from pathlib import Path

RAW = "https://raw.githubusercontent.com/safl/senfd/main/"


def test_the_images_of_the_readme_are_files_of_the_repository():
    """PyPI shows the README away from the repository, so its images are
    addresses of main; each must name a file that is there"""

    readme = Path("README.md").read_text()
    paths = re.findall(re.escape(RAW) + r"([^\s)]+)", readme)
    assert paths
    for path in paths:
        assert Path(path).is_file(), path


def test_dependabot_watches_the_documentation_lock_and_the_actions():
    config = Path(".github/dependabot.yml").read_text()
    watched = re.findall(
        r'- package-ecosystem: "([\w-]+)"\n  directory: "([^"]+)"', config
    )

    assert watched == [("pip", "/docs"), ("github-actions", "/")]
    assert Path("docs/poetry.lock").is_file()
    assert sorted(Path(".github/workflows").glob("*.y*ml"))


def test_the_dependabot_badge_links_its_configuration():
    readme = Path("README.md").read_text()
    link = "https://github.com/safl/senfd/blob/main/.github/dependabot.yml"

    assert "[![Dependabot](" in readme
    assert f")]({link})" in readme
    assert Path(link.split("/blob/main/")[1]).is_file()
