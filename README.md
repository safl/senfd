<!--
SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>

SPDX-License-Identifier: LGPL-2.1-only
-->

# senfd and sate

[![Build and test](https://github.com/safl/senfd/actions/workflows/bd.yaml/badge.svg)](https://github.com/safl/senfd/actions/workflows/bd.yaml)
[![Coverage](https://coveralls.io/repos/github/safl/senfd/badge.svg?branch=main)](https://coveralls.io/github/safl/senfd?branch=main)
[![PyPI](https://img.shields.io/pypi/v/senfd)](https://pypi.org/project/senfd/)
[![Documentation](https://img.shields.io/badge/docs-safl.dk%2Fsenfd-blue)](https://safl.dk/senfd/)
[![License](https://img.shields.io/badge/license-LGPL--2.1--only-blue)](https://github.com/safl/senfd/blob/main/LICENSE)
[![Dependabot](https://img.shields.io/badge/dependabot-enabled-025E8C?logo=dependabot)](https://github.com/safl/senfd/blob/main/.github/dependabot.yml)
[![REUSE status](https://api.reuse.software/badge/github.com/safl/senfd)](https://api.reuse.software/info/github.com/safl/senfd)
[![MCP server](https://img.shields.io/badge/MCP-server-8A2BE2)](https://safl.dk/senfd/llm/)

> [!CAUTION]
> senfd is experimental and is not endorsed by NVM Express. Its data model
> is derived from the NVMe specifications, and you must be a member of NVM
> Express, Inc. to make it or use it. Read the [notices](#notices) first.

**senfd** reads the NVMe specifications and makes a data model of them.
senfd reads either the PDFs that NVM Express publishes or the `.docx` files
that its members hold. The data model holds every command with its dwords
and fields, and every data structure, register, feature, log page and
table of values. Each fact in the data model cites the document, section,
figure and page it comes from.

![The .pdf and .docx documents go through senfd's stages, read, normalise, define and merge, into one data model](https://raw.githubusercontent.com/safl/senfd/main/docs/_static/senfd.svg)

The data model is JSON, validated by a schema. The same documents give the
same data model every time.

**sate** answers questions from a data model. Here the data model is the
one senfd makes of the NVMe specifications. You can ask sate about a
command, a field, a register, a feature or a log page, in a session with
completion or on the command line. sate answers in milliseconds and cites
the figure, with a link to its page of the specification on
nvmexpress.org, so you can check the answer:

[![sate's session: a question put with completion, and answered with the figure it is from](https://raw.githubusercontent.com/safl/senfd/main/docs/_static/casts/session.svg)](https://safl.dk/senfd/sate/)

To try sate in the browser without installing senfd, run the wizard with
uvx:

```
uvx --from senfd@latest sate-preview-wizard
```

Or with pipx:

```
pipx run --no-cache --spec senfd sate-preview-wizard
```

The wizard lists the specifications it will download from nvmexpress.org.
The wizard asks before it makes the data model, because only members of
NVM Express may make and use the data model. The wizard then opens sate's
web page in the browser. The data model stays in `~/.cache/senfd`, so the
next run opens the page without making the data model again.

## What the data model is for

* Answers from the figures. `sate` answers a question about a command, a
  field, a register, a feature or a log page in milliseconds; see
  [the expert](https://safl.dk/senfd/sate/).
* Language models that take NVMe facts from the data model. `sate --llm`
  answers questions written in your own words. A small language model on
  your own CPU chooses the lookup, and writes no part of the answer.
  `sate-mcp` gives a coding agent the lookups as tools, so that the agent
  checks an opcode, a bit or an offset against its figure rather than
  recalling it; see [with a language model](https://safl.dk/senfd/llm/).
* Code generated from the figures. An early prototype writes xNVMe's
  specification headers from the data model, and every member cites its
  figure; see [code from the figures](https://safl.dk/senfd/codegen/).
* A lint of the documents. senfd lists what does not read as data, with
  its figure and page, for the authors to fix; see
  [the linter](https://safl.dk/senfd/linting/).

The [documentation](https://safl.dk/senfd/) covers the rest. It describes
how to [install](https://safl.dk/senfd/install/) senfd or run it from its
[container image](https://safl.dk/senfd/install/#in-a-container), how to
[make the data model](https://safl.dk/senfd/usage/) from the specifications
that NVM Express publishes, how to
[lint the documents](https://safl.dk/senfd/linting/), how to
[ask the expert](https://safl.dk/senfd/sate/), and how to use sate
[with a language model](https://safl.dk/senfd/llm/). The
[benchmark](https://safl.dk/senfd/benchmark/) compares sate's answers with
those of language models. [Prior art](https://safl.dk/senfd/prior-art/)
describes the tools senfd follows, and [the names](https://safl.dk/senfd/names/)
page explains what the names mean.

## Notices

**Not endorsed by NVM Express.** senfd is independent of NVM Express, Inc.
NVM Express and NVMe are its trademarks.

**Experimental.** What senfd says can be wrong. Every answer cites the
figure it is from; check it there before you rely on it.

**The data model is under the specifications' terms.** It is derived from
the NVMe specifications, so the notice printed in each governs it. Members
of NVM Express, Inc. may use it under their Participation Agreement and the
Company's Intellectual Property Policy and Bylaws; to anyone else, the
notice grants only the right to review, refer to or cite the
specification. **You must be a member of NVM Express, Inc. to make the data
model or use it.**

**Nothing made from the specifications is distributed.** senfd ships no
specification and no data model, and its CI job, which reads the public
PDFs, uploads nothing made from them. Make your own from the public PDFs,
as the documentation shows.
