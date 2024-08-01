Contributors Guide
==================

Thank you for your interest in contributing to **senfd**! Please follow the
guidelines below to ensure a smooth and effective collaboration.

Commit Message Guidelines
-------------------------

**senfd** follow the
`Conventional Commits v1.0.0 <https://www.conventionalcommits.org/en/v1.0.0/>`_ 
specification for commit messages. A clear and consistent commit message format
helps us understand the history of **senfd**. Each commit message should:

- Start with a type (e.g., feat, fix, refactor) and a brief summary.
- Be written in the imperative mood.
- Have a line-width of at most 78 characters, including newline.

For examples, please refer to the structure of the current git commit messages
in our repository.

Sign Off Your Commits / DCO
~~~~~~~~~~~~~~~~~~~~~~~~~~~

All commits must be signed off to acknowledge the Developer Certificate of
Origin (DCO). This certifies that you wrote the patch or have the right to pass
it on as an open-source patch.

Code Formatting
---------------

To ensure all code adheres to senfd's formatting and type-info guidelines, run:

.. code-block:: sh

    make format

This will perform code auto-formatting where possible and guide you to fix what
needs to be addressed manually.


Building and Testing
--------------------

To build, install, and test the project, run:

.. code-block:: sh

    make

Prerequisites
~~~~~~~~~~~~~

On your system you need a couple of tools and libraries:

* On the system

  - pipx, to install ``senfd`` and dependencies
  - libxml2, library needed by ``python-docx``
  - libxslt, library needed by ``python-docx``

* The install of ``senfd`` itself is done via ``pipx`` with dependencies

  - This installs ``senfd`` and **pytest** into the same pipx-managed virtual
    environment, ensuring that test written in **pytest** can ``import senfd``

  - Notice that ``pipx`` makes the executable endpoints that ``senfd`` provides,
    and its dependencies, available. That is, your system ``pytest`` will with
    this point to the one install here
  
* The ``Makefile`` will install the following via ``pipx``

  - pre-commit (for formating and type-checking)
  - twine (only for maintainers needing to push packages manually)


Contributing Process
--------------------

1. Fork the repository.

2. Make your changes in your forked repository.

3. Check the items above (Commits, DCO, Format)

3. Create a pull request with your changes.


Thank you for contributing!
