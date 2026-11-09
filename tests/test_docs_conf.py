# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import datetime
import runpy


def test_the_copyright_of_the_documentation_runs_to_the_year_it_is_built():
    conf = runpy.run_path("docs/conf.py")
    year = datetime.date.today().year
    assert conf["copyright"] == f"2024-{year}, Simon A. F. Lund"
