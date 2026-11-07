# Changelog

Each release of senfd has a section here, named by its version, such as
`## 0.3.0`. That section is the text of the release on GitHub.

A release is made by merging a pull request whose last commit is
`ver: bump to vX.Y.Z`. That commit sets `__version__` in
`src/senfd/__init__.py` and adds the `## X.Y.Z` section to this file. When it
lands on `main`, `.github/workflows/release.yml` checks both, takes the build
that the pull request's checks tested, publishes it to PyPI, tags it, and
creates the GitHub release. Release tags are not pushed by hand.

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
