.. _sec-install:

Install
-------

The tool is implemented in Python, distributed via `pypi
<https://pypi.org/project/senfd/>`_ and exercised from the 
:ref:`command-line <sec-usage>`, thus `pipx <https://pipx.pypa.io/stable/>`_ does a
great job at creating a virtual-environment for it and an entry-point to the
command-line utility.

Thus, install it, using `pipx <https://pipx.pypa.io/stable/>`_, using like so::

  pipx install senfd

.. note::
  ``pipx`` does not install the system libraries ``libxml2`` and ``libxslt``
  that the tool depends upon, so ensure that you have these installed.
