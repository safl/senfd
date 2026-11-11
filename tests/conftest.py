# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
from typing import Callable

import pytest

SOURCED = re.compile(r'"(senfd_sha256|combined_sha256)": "[0-9a-f]{64}"')


@pytest.fixture
def unsourced() -> Callable[[str], str]:
    """The JSON text of a document with the hashes that change with senfd's
    source emptied. The committed example outputs are made at each release,
    so between releases their senfd hash is that of an older source."""

    return lambda text: SOURCED.sub(r'"\1": ""', text)
