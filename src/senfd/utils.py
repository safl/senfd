import re


def pascal_to_snake(name):
    """Convert a PascalCase to snake_case"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def snake_to_pascal(name):
    """Convert snake_case to PascalCase"""

    return "".join(word.capitalize() for word in name.split("_"))
