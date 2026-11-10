# Changelog

Each release of senfd has a section here, named by its version, such as
`## 0.3.0`. That section is the text of the release on GitHub.

A release is made by merging a pull request whose last commit is
`ver: bump to vX.Y.Z`. That commit sets `__version__` in
`src/senfd/__init__.py` and adds the `## X.Y.Z` section to this file. When it
lands on `main`, `.github/workflows/release.yml` checks both, takes the build
that the pull request's checks tested, publishes it to PyPI, tags it, and
creates the GitHub release. Release tags are not pushed by hand.

## 0.14.0

senfd now requires Python 3.13 or later, and is tested on 3.13, 3.14 and
3.15. The container image is built on Python 3.15.

Two kinds of field name are read as the figures mean them. A name that only
begins with "Reserved", "Obsolete", "Vendor Specific" or "Ignored" is now a
field's name, so fields such as Vendor Specific Information Available no
longer get the role `vendor_specific`. A name followed by its acronym and an
aside in parentheses, without a colon, now keeps its acronym, so the last
entry of NVM 1.3, Figure 41, matches the entries before it.

Continuous integration now runs `sate --llm` in the container image against
a llama-server with a small language model, with and without
`--llm-model`.
A release pull request now fails its checks when it lacks commits of
`main`, since it could not be released once merged.

The benchmark was run again with Qwen 2.5 7B and 1.5B as the local language
models, and the documentation's recordings were made again. The
documentation says that sate answers instantly, and its copyright runs to
the year it is built.

## 0.13.0

A data model made by an earlier senfd no longer loads and must be made
again: a field now says what it is, by `role` and `kind`.

A figure's range is made by its type or reported. It is a span of numbers,
a formula of values the figure names, written plainly as `upper:lower`, or
left open; text that is none of these is a candidate erratum, as are
bounds whose upper is below the lower whatever the values they name. A
field is made with a name, or as what holds a place, reserved, obsolete,
vendor specific or ignored; a row giving neither is listed by `senfd lint`
as a row that names no field. A figure laying out a whole data structure,
log page or register is held to covering it, unless it leaves rows out
or gives a formula between. The eleven public PDFs go from 3 candidate
errata to 11.

The kinds of ranges, roles, captions, typed values and errata are in the
JSON schema, so a data model can be verified for its format by any JSON
Schema validator, with no part of senfd.

`sate --llm-model NAME` asks a server holding several language models for
that one. With verbose, a field's description is given whole. A value of a
typed column can be not applicable, with its footnotes. The PDF reader
joins the pages of a figure in the order of the pages, and no longer takes
the borders of a cell for those of a table nested in it.

The documentation says what `sate --llm` and `sate-mcp` are each for.

## 0.12.0

`senfd-query` is gone. What reading the documents found is senfd's to
list, as `senfd lint` and `senfd errata`; a lookup is the expert's, as
`sate command write 12`, `sate feature 07h` or `sate structure controller
status`, its name taking several words without quotes. A question in
quotes is still read as a question, whatever its first word.

A PDF published with its tracked changes shown is a document error,
listed once a document with how much is struck through and where it
starts: the published Base 2.4, Boot 1.4 and Management Interface 2.2
carry them. Only a filled rectangle strikes text through, as Word prints
one, so the labels of arrows and dimension lines in diagrams are no
longer dropped as deletions.

Bits nested in a range of bytes are held to the bits of those bytes, so
bits 15:3 under the one byte 362 of Base 2.4's Identify Controller are a
candidate erratum. The README's notices are four short ones, and sate is
introduced as an expert on the subject a data model describes.

## 0.11.0

A data structure laid out in both bytes and bits, a heading row naming each
byte range with the rows of its bits below it, is read as such: each byte
range is a field named by its heading, and its bits are a layout nested in
it. Before, the byte ranges were lost and the headings became fields of
their own. The files senfd writes are indented JSON, so that a diff of two
data models shows what changed.

The README says what senfd and sate are and what the data model is for,
with the cautions in a box, and points to the documentation for the rest.
The documentation shows the expert's session and its command line in tabs,
and tells where the names come from on a page of their own.

The benchmark's configuration runs on any machine, with the public PDFs,
llama-server from PATH and language models downloaded from Hugging Face,
rather than being that of one lab machine. senfd is type-checked against
its dependencies, pydantic among them, and ruff catches a name rebound over
an argument or its own loop variable.

## 0.10.0

`pipx install senfd` installs all of senfd: the PDF reader, and the
expert's prompt, rendering and MCP server, which were the extras `pdf` and
`sate`. The extras remain, empty, so `senfd[sate,pdf]` still installs.
Where installing these is the problem, a container image of senfd is
published with each release, as `ghcr.io/safl/senfd`; it holds no
specification, and the documents and the data model are mounted into it.

An answer about a field, made from the published PDFs, ended "is bits
29:26 of" and stopped; it says again where the field is, "of cdw12 of
Write", and the figure to read it in. `senfd --help` says what a skip list
is, without a heading of its own.

The README and the documentation open with what senfd and sate are: a
diagram of senfd making the data model, and a recording of sate answering
from it. The documentation has a page for each step of using them, in the
order they are taken, with no walk-through repeating them; the expert's
page leads with its links to the pages of the specifications, and tells
the session apart from the command line. The contributing guide says what
a change must carry, and that no specification goes into the repository.

## 0.9.2

The package is as in 0.9.1; this release brings its description on PyPI,
the README, up to date. The benchmark's report and tables give the
frontier language models the time they took beside their cost, the time
of the one call that answers every question and its share for each, and
the transcripts of the run of 2026-11-09, which the pages send a reader
to for every answer, are back in `benchmark/results/2026-11-09/bench`.

## 0.9.1

`sate` answers from the tables of values: `status code 82h`, `status code
type 1h`, `CNS 05h`, or `status code of zone boundary error`, each entry
with its table and the figure it is in; `senfd-query value` and the `value`
tool of `sate-mcp` do the same. A name asked as a log page's identifier,
"the log page identifier of Cross-Controller Reset", is the log page's, not
the command's of that name; a structure is named by what its command
qualifies, "Identify Namespace" of "Identify - Identify Namespace", and
where several documents define a structure of one name, the Base
specification's comes first. The opcode asked alone, "opcode of sanitize",
is answered with the opcode alone, and `describe` before a field asked by
its acronym adds its description. Completion offers only names of the
kind the question asks for.

The benchmark asks 71 questions, where it asked 30: the bits of the CAP,
CC, CSTS and CRTO registers, the byte offsets of fields of the Identify
data structures, the opcodes of the Key Value, Zoned Namespace, Subsystem
Local Memory, Computational Programs and NVMe-MI commands, the identifiers
of the features and log pages added in 2026, status codes and CNS values,
each checked against its figure. Its grader reads a closed-book answer by
the values it writes, so "1Fh (Namespace Admin Label)" is right and "82h
or 83h" is wrong, and a text answer by the line about the field asked, a
row marked in bold or not.

The documentation opens with a Get started page, from nothing to a data
model and an expert to ask, and the pages and the README are cut to what
they must say. Two recordings are new: the eleven published PDFs read into
one data model and linted, and a session that walks from completion to a
question the data model cannot answer. `senfd` says where it wrote from
the home directory, and counts the worked examples apart from the figures
it does not model.

## 0.9.0

senfd is a package of two tools: `senfd` makes the data model, and `sate`,
Senfd Ask The Expert, answers from it. `senfd-ask` is now `sate`, and
`senfd-mcp` is `sate-mcp`, both of the extra `sate`, which replaces the
extras `ask` and `mcp`; the package `senfd.ask` is `senfd.sate`.

senfd reads the specifications from the PDFs NVM Express publishes for
anyone, as well as from the .docx its members hold, and gives the same
data model of either: with the extra `pdf`, `senfd specification.pdf`. A
PDF must keep the structure of its tables, as NVM Express's do; one
without is refused. A CI job makes the data model of each of the eleven
published PDFs and compares it with what is expected, downloading them
into a cache and uploading nothing; it merges them into one data model,
and has `sate` answer the benchmark's questions from it, every one right.
The README and the documentation say that senfd is experimental, not
endorsed by NVM Express, that the data model is derived from the
specifications and under their terms, and how to make it.

Read from the PDFs, a figure going on past a page break keeps one copy of
its header and a row broken across the page whole; a table's columns are
found where its rules meet its borders, so a border far from centred text
is no longer lost, which brings twelve more figures of the Base
specification and the features of the Management Interface into the data
model; the deletions a specification published with its tracked changes
shows struck through are left out, as they are of a `.docx`; and text Word
tags into a cell but prints below the table is left out of the cell. Read
from the `.docx`, a paragraph of a list is led by the label Word shows,
"1.", "a)" or a bullet, so the notes of a figure keep their numbers and
read as the PDF does.

Each fact cites its document, section, figure and page, and where the
document is one NVM Express publishes as PDF, the citation of `senfd-query
--markdown`, `sate` and `sate-mcp` links to that page of the PDF: the data
model carries the SHA-256 of the file each document was made from, and the
page of the PDF each figure is on, as "page 213, PDF page 238". `sate` opens
each answer with a rule naming the question and pages an answer taller than
the terminal from its top; `describe` or `explain` before a question answers
it with the descriptions of the fields; and the bits of a byte in a data
structure stand in a column of their own beside the bytes. The PDF reader
reads a header turned by 90 degrees the way it runs, places a figure in its
section by the outline's destinations, carries a table nested in a cell past
a page break, and makes one again a range wrapped by a narrow column; and a
field named with a range in brackets, as `KV Key[63:00]`, keeps its name
whole. senfd needs Python 3.11 or later.

`senfd-query lint` lists what an author acts on first: the candidate errata,
and the document errors, which were only in each document's error log and
are now in the data model, each by its document and the figure it follows.
Every line of the lint cites as the errata do, names read as words, and a
range of identifiers giving the "h" once, or a column of sentences, is read
as what it is rather than as an erratum. A run of `senfd` names the command
listing what it found for the data model it wrote, and a missing document is
an error.

Every type and field of the data model is described in its schema.

`senfd-query command` finds a command by its opcode, as "8Ch", and errata
in an annex no longer stop `senfd-query errata`. `sate-mcp`
says what it is with `--help`, and its tools' descriptions are without the
indentation of their docstrings.

## 0.8.0

`senfd-query lint`, and the MCP tool `lint`, list what reading the figures as
data found, for the authors apart from for senfd: candidate errata, figures of
no shape senfd models with worked examples apart, and dwords no command,
feature or operation claims. An erratum found in many rows of a figure is said
once, with the number of rows, and columns and kinds read as words. A run of
`senfd` ends by saying what it made and what to look at, the document errors
say what they found, and the error logs are named as the other outputs.

`senfd-ask` answers which feature or log page holds a field, as "Which log page
reports sanitize progress?", and a feature or log page by identifier whatever
command carries it, as "feature 02h of Set Features".

The documentation describes the parts of the data model and how stable its
schema is, and says that the xNVMe generator is proposed to xNVMe.
`senfd-query` without a data model says how to make one, and the package says
it needs Python 3.10 or later.

## 0.7.0

The data model says what each value is rather than its text, and holds the
structure behind the fields. The values of requirement, yes/no and
identifier columns are typed, as a level, a flag, an identifier or a range,
with their footnotes, or as a note, a reference, reserved or vendor specific,
and a value of no form its column holds is an erratum. Fields sharing bits
are the alternatives of a union. A field has the values it takes, and a field
selecting operations, as the select field of Migration Send, gives each
operation its dwords. A table of values has the scope its caption confines it
to, so the status codes of I/O commands and of Fabrics commands are told
apart. A register whose layout is a format it shares with others, as the
version register, is named by the section describing it.

`senfd-query --markdown` gives the fields of a command, feature, log page or
structure as a Markdown table, for an answer shown to a person, and a command
found by a search says its opcode.

`senfd-ask` answers a question as an expert would, at once: names, acronyms
and the words of questions complete as they are typed, from where a name
starts in the question and with its kind shown, each answer is a table
citing its figure, and an answer not mentioning every term of the question
that names something is withheld as not known. With `--llm URL`, a language
model served by llama.cpp reads the question and chooses the lookup,
constrained by a schema to a query and its argument, and writes nothing of
the answer. It is the extra `ask`.

The session of `senfd-ask` is made for someone who does not yet know how to
ask: it opens with the questions it answers in a menu, completes each part
of one by what comes next, the fields of the very dword asked of after
"is", colours what it recognises, says at the bottom how the question is
read so far above the keys that do something at that moment, ends an
answer asked of a field by saying where the field is, and keeps the
questions asked for the next session. `senfd.ask` is a package of one
module a step a question passes through.

The documentation says what the data model is for, with recordings of
`senfd-ask` and a benchmark against frontier language models. The
benchmark is kept in `benchmark/`, a cijoe workflow with the record of its
run, for anyone holding the documents to repeat. The sources follow the
REUSE specification, checked by pre-commit, and the tests fail below 95%
coverage.

Writing headers from the data model is left to the project consuming it, as
xNVMe does with a generator run by yace; senfd makes the data model.

## 0.6.0

The model holds only values that are what their kind must be. An acronym that
is not one is left out, and a field whose bounds are reversed or lie beyond the
dwords it is of is left out whole; those, the bits of a command's dwords that
no figure gives a field, and an opcode that is not a value, are errata, each
saying the document, section, figure and page it is in. `senfd-query errata`
and the MCP tool `errata` list them, for the documents to be corrected.

## 0.5.0

senfd makes a model of the specification to generate code from and to
answer questions with. Each figure is normalised by the shape of its table,
decided by its header with columns matched by name, and by the subject its
caption names, and every normalisation is a diagnostic, which makes senfd a
linter of the documents too. From that, the specification document holds the
command sets with each command's dwords and directive operations, the features
and log pages by identifier, the structures and the tables of values, each
citing its document, section, figure and page. `senfd-query` answers from the
merged model, and `senfd-mcp`, with `senfd[mcp]`, serves the same answers to an
agent over MCP, by command, feature, log page, structure, field and section.

The enriched figure document, its 49 caption categories, the model document and
merged.model.document.json are gone; merged.spec.document.json takes the place
of the last. The skip lists apply to the normalised stage.

The plain stage reads the text of Word's fields, the number of a figure among
them, and finds the tables of figures that it missed, among them a caption
after an empty cell, a table wrapped in another, and two figures in one table.

## 0.4.0

The example document is written by `toolbox/example_docx.py` and holds a
figure of every category, and a test fails when a category has none. The
general command status category is dropped, as no figure could land in it.

The model gives a command its dword pairs, its data and metadata pointers,
and the condition a dword is described for, and the dwords that another
document describes. The merged model combines a command set listed by more
than one document, and no longer merges in a merged model left in the output
folder by an earlier run.

## 0.3.0

Figures are enriched by their table's grid as well as by their caption: a
category whose grid does not match the table is passed over, columns the grid
does not name are allowed, and rows of uneven length are an error. A figure
matching several categories is left uncategorized, with an error naming them,
and the categories are written so that no figure of the Base, NVM, ZNS and KV
specifications matches two; the data structures are split into log pages,
PRP entries, create queue and management operation specific fields, and
command data.

New categories cover status values and status codes, formats, data types,
descriptors, parameter fields, completion and submission queue entries,
asynchronous event information, requirements, log specific identifiers, the
RPMB flow, dword 0, state transition conditions, responses, attribute
entries, additional hardware error information, message fields, NVMe
management and PCIe request dwords, PDUs and mapping tables.

`--skip-figures` takes a TOML list of figure captions to leave out, with a
description of why; `skiplists/` has such lists for the Base, Boot,
Management Interface, NVM and Computational Programs specifications. The enriched figure document records
the figures skipped, and counts those categorized, uncategorized, nontabular
and skipped, with the highest figure number. A skip element matching other
than the number of figures it states names both counts.

A model document, and one merged from several documents, is written from the
enriched figure documents. The output files of each document are named by it
in the `--output` directory rather than put in a folder of their own.

The documents are written and read as UTF-8 on every platform; on Windows
they were written in the platform's encoding, which a JSON reader elsewhere
does not read.

A release is made by merging a version bump, as described above, rather than
by pushing a tag. The package version is read from `senfd.__version__`.
