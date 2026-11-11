# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The specifications NVM Express publishes as PDF, by the SHA-256 of each
file, from published.toml beside this module: a data model made from one of
them knows the file it was read from by its hash, and so can cite it by a
link to the page.
"""

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import tomllib

TABLE = Path(__file__).with_name("published.toml")


@lru_cache(maxsize=1)
def documents() -> List[Dict[str, str]]:
    """The published documents: name, file, url and sha256 of each"""

    return list(tomllib.loads(TABLE.read_text(encoding="utf-8"))["document"])


def name_of(sha256: Optional[str]) -> Optional[str]:
    """The short name, such as "Base 2.4", of the published PDF with the
    SHA-256 'sha256', or None where no published PDF has it"""

    if not sha256:
        return None
    return next((d["name"] for d in documents() if d["sha256"] == sha256), None)


def url_of(sha256: Optional[str]) -> Optional[str]:
    """The URL of the published PDF whose SHA-256 is 'sha256'; None where
    none is"""

    if not sha256:
        return None
    return next((d["url"] for d in documents() if d["sha256"] == sha256), None)
