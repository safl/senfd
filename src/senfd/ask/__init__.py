# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Ask the data model questions, as of an expert who answers at once

    senfd-ask
    ask> opcode of zone append
    ask> Which bit of CDW12 of Write is FUA?
    ask> log page 1Fh

A question is read without a language model: by its words, as "opcode of",
"cdw12 of", "feature", "log page" or "section", by an identifier, as "1Fh",
or by an acronym or a name the data model has. Each answer says what the
question was read as, so a question read otherwise than meant shows, and is
the answer of a query of the data model, with the figures it cites. An
answer is shown only when it is about what the question asks of and
mentions every term of it that names something; otherwise it is not known.

With ``--llm URL``, a language model served there, as by llama.cpp's
``llama-server``, chooses the lookup instead, constrained by a JSON schema
to a query and its argument; it writes no part of the answer.

A question passes through the modules in this order:

* ``phrasing``: the words of questions, their forms and their terms
* ``vocabulary``: what the data model names
* ``reading``: a question read as the query answering it
* ``language_model``: or that query chosen by a language model
* ``lookup``: the query looked up in the data model
* ``grounding``: whether the answer is about what was asked
* ``answering``: all of it, the answer said, with where its fields are
* ``completion`` and ``session``: the interactive session, of the extra
  'ask'; ``cli``: the command line
"""

from senfd.ask.answering import exchange, reply, respond
from senfd.ask.cli import main
from senfd.ask.reading import Understood, understand
from senfd.ask.vocabulary import Vocabulary

__all__ = [
    "Understood",
    "Vocabulary",
    "exchange",
    "main",
    "reply",
    "respond",
    "understand",
]
