.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-contributing:

Contributing
============

Fork the repository, make the change on a branch, check it as below, and
open a pull request against ``main``.

Set up
------

.. code-block:: console

   $ python3 -m venv .venv
   $ source .venv/bin/activate
   $ pip install -e ".[dev]" pre-commit

The tests run ``senfd`` and ``sate`` as commands, so the environment must
be active, or its ``bin`` first on ``PATH``. ``make`` does the same with
pipx, and also opens the coverage report.

Check a change
--------------

.. code-block:: console

   $ pre-commit run --all-files
   $ make test

pre-commit formats and lints with ruff, checks the types with mypy, and
checks every file's license with REUSE. ``make test`` runs the tests and
fails below 95% coverage. CI runs both, on Linux and macOS.

Some tests read the eleven specifications NVM Express publishes. They
download them from nvmexpress.org into a cache, ``~/.cache/senfd/public``
or ``$SENFD_PUBLIC_DOCUMENTS``, checked by their SHA-256, and are skipped
where the download fails. They check what senfd makes of each document
against ``tests/public/documents.toml``. A change that alters that, as
reading one more figure, updates the counts there in the same commit.

The specifications are not ours
-------------------------------

Never commit a specification, or anything made from one: no PDF, no
``.docx``, no data model, figure document or log of one, and no excerpt of
one in an issue or a pull request. Read :ref:`the notices <sec-notices>`
for why. A test needs a document of its own instead: ``example/example.docx``
is a synthetic specification with every kind of figure senfd reads, written
by ``toolbox/example_docx.py``. Add the figure a change is about there.

What a change carries
---------------------

A test that fails without the change. And, in the same commit, whatever is
made from what it changed, each kept so by a test:

* ``example/output``, what senfd makes of the example:
  ``senfd example/*.docx --output example/output``, without the
  ``.error.log`` files.
* ``src/senfd/schemas``, the schemas of the data model:
  ``senfd --dump-schema --output src/senfd/schemas``.
* ``docs/src/stages``, the stages of a figure the documentation shows:
  ``toolbox/example_stages.py docs/src/stages``.

The documentation is built with ``cd docs && make deps html``, and a
warning fails the build. The recordings in ``docs/_static/casts`` are made
by ``toolbox/record_cast.py`` and ``toolbox/record_session.py`` from the
scripts in ``docs/casts``; they need a data model of the public documents.
The README shows the session and the opening recording as animated SVGs,
rendered by ``toolbox/cast_svg.py``.
The diagram ``docs/_static/senfd.svg`` is drawn from ``senfd.mmd`` beside
it, in that directory by ``mmdc -i senfd.mmd -o senfd.svg -c
senfd.mmd.json -b white``.

Commits
-------

Commits follow `Conventional Commits
<https://www.conventionalcommits.org/en/v1.0.0/>`_: a type, as ``feat``,
``fix`` or ``docs``, and a summary in the imperative mood. The body says
why the change is made, not what it does; the diff shows that. Lines are at
most 78 characters. Refer to a commit by its hash and summary, not to an
issue or a pull request, which the history outlives.

Sign off each commit, ``git commit -s``, acknowledging the `Developer
Certificate of Origin <https://developercertificate.org/>`_: that you wrote
the change, or have the right to pass it on under the project's license. A
change a coding agent helped make says so in an ``Assisted-by:`` trailer
before the sign-off, naming the agent and the model, as ``Assisted-by:
Claude Code:claude-opus-5-5``. You answer for it as for any other.

A release is the last commit of its pull request, ``ver: bump to vX.Y.Z``
with its section of ``CHANGELOG.md``, and merging it publishes to PyPI.
That is the maintainer's.
