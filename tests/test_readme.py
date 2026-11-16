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


def test_the_readme_shows_how_to_try_sate_after_the_introductions():
    """The first command of the README runs the wizard of a script the
    package installs, after the introductions of senfd and sate and before
    the first section"""

    readme = Path("README.md").read_text()
    command = "uvx --from senfd@latest sate-preview-wizard"
    first = re.search(r"```\n(.*?)\n```", readme, re.DOTALL)

    assert first and first[1] == command
    assert readme.index("**senfd**") < readme.index("**sate**")
    assert readme.index("casts/session.svg") < readme.index(command)
    assert readme.index(command) < readme.index("\n## ")
    assert 'sate-preview-wizard = "' in Path("pyproject.toml").read_text()
