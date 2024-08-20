"""
A model of the specification

This goes beyond that specifcation documents and the notions of various figures and
requirements to document formating and figure policies. The intent here is to provide a
rich and validated data model directly usable for implementers.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, root_validator


class Bits(BaseModel):
    """Representation of bits at least a single, and at most, 128 bits."""

    nbits: int
    lower: int
    upper: int

    name: str
    acronym: Optional[str]
    description: Optional[str]

    @root_validator(pre=True)
    def transform_input(cls, values):
        values["lower"] = int(values["lower"])
        values["upper"] = int(values["upper"] if values["upper"] else values["lower"])
        values["nbits"] = values["upper"] - values["lower"] + 1
        values["name"] = values["name"].strip()

        if values.get("acronym", None):
            values["acronym"] = values["acronym"].strip().lower()
        if values.get("description", None):
            values["description"] = values["description"].strip()

        return values


class CommandDwordLowerUpper(BaseModel):
    """
    Command DWORDS; the DWORD or DWORDS forming a "field" within a command

    Should be applicable to Submission Queue Entries (SQE) as well as Completion Queuey
    Entries (CQE) since validation of DWORDS "collections" is up the the container e.g.
    (Command.sqe / Command.cqe), as the rules such as the total amount etc. needs to
    verifying at that level.
    """

    command_alias: str
    nbytes: int
    lower: int
    upper: int
    fields: List[Bits] = Field(default_factory=list)


class Command(BaseModel):
    """Encapsulation of Command properties"""

    opcode: int
    alias: str
    name: str

    req: Optional[str] = None

    sqe: List[CommandDwordLowerUpper] = Field(default_factory=list)
    cqe: List[CommandDwordLowerUpper] = Field(default_factory=list)

    @staticmethod
    def opcode_from_hexstr(hexstr):
        return int(hexstr.lower().replace("h", ""), 16)

    @staticmethod
    def alias_from_name(text):
        return text.strip().lower().replace("/", "").replace(" ", "_")


class CommandSet(BaseModel):
    """Collection of entities encompassing a command-set"""

    alias: str
    name: str

    commands: Dict[str, Command] = Field(default_factory=dict)


class LogPage(BaseModel):
    """..."""

    alias: str
    name: str

    lpi: int
    fields: List[int] = Field(default_factory=list)
