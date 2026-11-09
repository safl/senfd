# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
A language model choosing the lookup, constrained by a JSON schema to a
query and its argument, as served by llama.cpp's llama-server
"""

import json
import urllib.request
from typing import Any, Dict, List, Optional

from senfd.sate.reading import Understood


QUERIES = {
    "command": "a command by name, with its dwords and opcode: 'write', 'zone append'",
    "feature": "a feature by identifier, '07h', or by name",
    "log_page": "a log page by identifier, '02h', or by name",
    "structure": "a data structure by name: 'identify controller'",
    "register": "a register by its acronym: 'CC', 'CSTS', 'CAP'",
    "search": "fields by acronym, 'FUA', or by name, and commands, features, "
    "log pages and structures by a word of their name",
    "section": "what a section describes, by number: '5.2.6'",
    "value": "an entry of a table of values: a status code, 'status code 82h' "
    "or 'status code zone boundary error', a status code type, or a CNS value, "
    "'CNS 05h' or 'CNS identify namespace'",
    "unknown": "the question is not about the NVMe specifications",
}


SYSTEM = (
    "You choose one lookup in a model of the NVMe specifications that answers "
    "the user's question. You never answer yourself. The lookups are:\n"
    + "\n".join(f"- {name}: {what}" for name, what in QUERIES.items())
    + "\n'dword' is for a command only, as 12 for CDW12, else null. Examples:\n"
    "- 'Which bit of CDW12 of Write is FUA?' -> command, 'write', 12\n"
    "- 'What is the opcode of Get Log Page?' -> command, 'get log page', null\n"
    "- 'Which feature is Number of Queues?' -> feature, 'number of queues', null\n"
    "- 'Which bits of CC select the arbitration mechanism?' -> register, 'CC', null\n"
    "- 'What does STC stand for?' -> search, 'STC', null\n"
    "- 'What is the status code of Zone Boundary Error?' -> value, "
    "'status code zone boundary error', null\n"
    "- 'What is the capital of France?' -> unknown, '', null\n"
    "If you are told a lookup found nothing, or nothing mentioning the "
    "question, choose another; if none fits, choose unknown."
)


SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"enum": list(QUERIES)},
        "argument": {"type": "string"},
        "dword": {"type": ["integer", "null"]},
    },
    "required": ["query", "argument", "dword"],
}


def choose(
    url: str, messages: List[Dict[str, str]], model: Optional[str] = None
) -> Understood:
    """The lookup a language model at 'url' chooses, constrained to SCHEMA;
    'model' names it, where the server has several to route between"""

    body: Dict[str, Any] = {
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_schema", "json_schema": {"schema": SCHEMA}},
    }
    if model:
        body["model"] = model
    request = urllib.request.Request(
        f"{url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        content = json.load(response)["choices"][0]["message"]["content"]
    chosen = json.loads(content)
    dword = chosen.get("dword")
    return Understood(
        chosen["query"],
        chosen.get("argument", ""),
        dword if chosen["query"] == "command" and dword else None,
    )
