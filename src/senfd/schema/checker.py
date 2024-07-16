"""

"""

import importlib.resources as pkg_resources
import json
from typing import Any, Dict

import senfd.schema


def get_schema() -> Dict[str, Any]:
    """
    Load the JSON Schema for the stage2 document from the package as a dict

    Returns:
        Dict[str, Any]: The JSON Schema as a dictionary.
    """

    with pkg_resources.open_text(senfd.schema, "enhanced.schema.json") as content:
        return json.load(content)
