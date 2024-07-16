#!/usr/bin/env python3
"""
Set the project version in the various locations where it is "hardcoded"

* Using pyproject.toml[project.version] as the default bumping

Requirements
------------

* Python 3.11 (tomllib)
"""
import argparse
import re
import sys
from pathlib import Path

import tomllib as toml

REGEX = r"^(?P<before>.*?version.*?=.*?)(?P<version>\d\.\d\.\d)(?P<after>.*?)$"
FILES = [
    (Path("pyproject.toml"), REGEX),
    (Path("docs") / "pyproject.toml", REGEX),
    (Path("src") / "senfd" / "__init__.py", REGEX),
]


def get_project_version(toml_file):
    return toml.load(toml_file)["project"]["version"]


def bump_patch_version(version):
    major, minor, patch = map(int, version.split("."))
    patch += 1
    return f"{major}.{minor}.{patch}"


def main():

    parser = argparse.ArgumentParser(description="Update version info.")
    parser.add_argument(
        "version",
        nargs="?",
        help="version to set. If not provided, bump the patch level.",
    )
    args = parser.parse_args()

    version = (
        args.version
        if args.version
        else bump_patch_version(
            get_project_version((Path.cwd() / "pyproject.toml").open("rb"))
        )
    )

    for path, regex in FILES:
        lines = []
        for line in path.read_text().splitlines():
            match = re.match(regex, line)
            if match:
                data = match.groupdict()
                updated = f'{data["before"]}{version}{data["after"]}'
                lines.append(updated)
            else:
                lines.append(line)
        path.write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
