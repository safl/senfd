.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-contributing:

Contributing
============

Fork the repository, make the change on a branch, check it as below, and
open a pull request.

Commits follow `Conventional Commits v1.0.0
<https://www.conventionalcommits.org/en/v1.0.0/>`_: a type, as ``feat``,
``fix`` or ``refactor``, and a summary in the imperative mood, with lines
of at most 78 characters including the newline; the history of the
repository shows the form. Every commit is signed off, acknowledging the
Developer Certificate of Origin: that you wrote the change or have the
right to pass it on under the project's license.

``make format`` formats the code and runs the type checker, and says what
is left to fix by hand. ``make`` builds, installs and tests. Both need
pipx, which installs senfd and pytest into one virtual environment, so
that the tests can ``import senfd``, and installs pre-commit for the
formatting and type checks and twine for maintainers pushing a package by
hand; python-docx needs the system libraries ``libxml2`` and ``libxslt``
where its lxml is not a prebuilt wheel.
