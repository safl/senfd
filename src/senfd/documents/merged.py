import json
from argparse import Namespace
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
    def convert(
        path: Path, args: Namespace
    ) -> Tuple[Document, List[senfd.errors.Error]]:
        """Instantiate an 'organized' Document from a 'figure' document"""

        errors: List[senfd.errors.Error] = []

        merged = ModelDocument()
        merged.meta.stem = "merged"

        for path in path.glob(f"*{ModelDocument.SUFFIX_JSON}"):
            if path.name == merged.json_filename():
                continue
            model = ModelDocument(**json.loads(path.read_text(encoding="utf-8")))
            for cmdset_alias, cmdset in model.command_sets.items():
                if not cmdset.commands:
                    continue

                merged.command_sets[cmdset_alias] = cmdset

        return merged, errors
