# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
from pathlib import Path

STATIC = re.compile(r"_static/[\w./-]+\.(?:png|svg|cast)")


def test_each_static_file_the_documentation_shows_exists():
    pages = sorted(Path("docs/src").rglob("*.rst"))
    shown = {name for page in pages for name in STATIC.findall(page.read_text())}

    assert "_static/web-light.png" in shown
    assert [name for name in sorted(shown) if not (Path("docs") / name).is_file()] == []
