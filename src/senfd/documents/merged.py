import json
from pathlib import Path
from typing import List, Tuple

import senfd.errors
import senfd.models
from senfd.documents.base import Converter, Document
from senfd.documents.model import ModelDocument


class FromFolder(Converter):

    @staticmethod
    def is_applicable(path: Path) -> bool:
        return path.is_dir() and all(path.glob(f"*{ModelDocument.SUFFIX_JSON}"))

    @staticmethod
    def convert(path: Path) -> Tuple[Document, List[senfd.errors.Error]]:
        """Instantiate an 'organized' Document from a 'figure' document"""

        errors: List[senfd.errors.Error] = []

        merged = ModelDocument()
        merged.meta.stem = "merged"

        for path in path.glob(f"*{ModelDocument.SUFFIX_JSON}"):
            model = ModelDocument(**json.loads(path.read_text()))
            for cmdset_alias, cmdset in model.command_sets.items():
                if not cmdset.commands:
                    continue

                merged.command_sets[cmdset_alias] = cmdset

        return merged, errors
