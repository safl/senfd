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

The tests run ``senfd`` and ``sate`` as commands, so the virtual
environment must be active, or its ``bin`` directory first on ``PATH``.
Running ``make`` instead installs senfd in editable mode with pipx, runs the
tests and opens the coverage report.

Check a change
--------------

.. code-block:: console

   $ pre-commit run --all-files
   $ make test

pre-commit formats and lints with ruff, checks the types with mypy, and
checks every file's license with REUSE. ``make test`` runs the tests and
fails below 95% coverage. CI runs both, on Linux and macOS.

Some tests read the eleven specifications that NVM Express publishes.
These tests download the PDFs from nvmexpress.org into a cache,
``~/.cache/senfd/public`` or ``$SENFD_PUBLIC_DOCUMENTS``, check each PDF by
its SHA-256, and are skipped when the download fails. The tests check what
senfd makes of each document against ``tests/public/documents.toml``. A
change that alters what senfd makes of a document, such as reading one
more figure, updates the counts in that file in the same commit.

The specifications are not ours
-------------------------------

Never commit a specification, or anything made from one: no PDF, no
``.docx``, no data model, figure document or log of one, and no excerpt of
one in an issue or a pull request. Read :ref:`the notices <sec-notices>`
for why. A test uses senfd's own document instead. ``example/example.docx``
is a synthetic specification with every kind of figure senfd reads, and
``toolbox/example_docx.py`` writes it. Add the figure that a change is
about to that document.

What a change carries
---------------------

A change carries a test that fails without the change. The same commit also
updates each file that is generated from what the change touched, and a
test checks each of these files:

* ``example/output``, what senfd makes of the example:
  ``senfd example/*.docx --output example/output``, without the
  ``.error.log`` files.
* ``src/senfd/schemas``, the schemas of the data model:
  ``senfd --dump-schema --output src/senfd/schemas``.
* ``docs/src/stages``, the stages of a figure the documentation shows:
  ``toolbox/example_stages.py docs/src/stages``.

``cd docs && make deps html`` builds the documentation, and a warning fails
the build. ``make refresh`` makes again what the README and the
documentation show of senfd at work: the recordings in
``docs/_static/casts``, from the scripts in ``docs/casts``, the animated SVG
of the session that the README shows, and the screenshots of sate's web
page. It runs the senfd of the checkout, on the PDFs in ``~/specs``, and
the recording of ``sate --llm`` needs llama-server on port 8088. Run it
before a release, so that the documentation shows the release.
``make benchmark`` runs the :ref:`benchmark <sec-benchmark>` of the release
that the checkout is. The diagram ``docs/_static/senfd.svg`` is
drawn from ``senfd.mmd`` in the same directory, by running ``mmdc -i
senfd.mmd -o senfd.svg -c senfd.mmd.json -b white`` in that directory.

Commits
-------

Commits follow `Conventional Commits
<https://www.conventionalcommits.org/en/v1.0.0/>`_: a type, as ``feat``,
``fix`` or ``docs``, and a summary in the imperative mood. The body says
why the change is made, not what it does; the diff shows that. Lines are at
most 78 characters. Refer to a commit by its hash and summary, not to an
issue or a pull request, because the history outlives the hosting service.

Sign off each commit with ``git commit -s``. The sign-off acknowledges the
`Developer Certificate of Origin <https://developercertificate.org/>`_:
that you wrote the change, or have the right to pass it on under the
project's license. When a coding agent helped make a change, the commit
says so in an ``Assisted-by:`` trailer before the sign-off, naming the
agent and the language model, as ``Assisted-by: Claude
Code:claude-opus-5-5``. You
answer for such a change as for any other.

A release is the last commit of its pull request: ``ver: bump to vX.Y.Z``
with its section of ``CHANGELOG.md``. Merging that pull request publishes
the release to PyPI. The maintainer makes the releases.
