# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
from pathlib import Path

import pytest

WORKFLOWS = sorted((Path(__file__).parents[1] / ".github" / "workflows").glob("*.y*ml"))


def jobs_of(text: str) -> dict:
    """The text of each job of a workflow, by the job's name"""

    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([A-Za-z][\w-]*):\s*$", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_every_job_of_a_workflow_states_the_permissions_of_its_token(workflow):
    text = workflow.read_text()
    if re.search(r"^permissions:", text, re.M):
        return
    for name, job in jobs_of(text).items():
        assert re.search(r"^    permissions:", job, re.M), f"{workflow.name}: {name}"
