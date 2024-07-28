from collections import namedtuple

TableCaptionError = namedtuple("TableCaptionError", ["table_nr", "caption", "message"])

TableOfFiguresError = namedtuple("TableOfFiguresError", ["caption", "message"])
