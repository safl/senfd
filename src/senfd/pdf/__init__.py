# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Reading a specification from its tagged PDF, as NVM Express publishes it,
into the figure document senfd otherwise reads from the .docx; what follows
is the same for either. pikepdf reads the structure tree and the outline,
pdfplumber the characters and the borders.

* ``tree``: the structure tree's tables, rows, cells and headings
* ``pages``: the characters of marked content, and the borders drawn
* ``tables``: a tagged table as rows of cells, merged cells placed
* ``reader``: the figures, their sections and pages
"""
