# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
from pathlib import Path

RAW = "https://raw.githubusercontent.com/safl/senfd/main/"


def test_the_images_of_the_readme_are_files_of_the_repository():
    """PyPI shows the README away from the repository, so its images are
    addresses of main; each must name a file that is there"""

    readme = Path("README.rst").read_text()
    paths = re.findall(re.escape(RAW) + r"(\S+)", readme)
    assert paths
    for path in paths:
        assert Path(path).is_file(), path
