"""
A model of the specification

This goes beyond that specifcation documents and the notions of various figures and
requirements to document formating and figure policies. The intent here is to provide a
rich and validated data model directly usable for implementers.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class Bits(BaseModel):
    """Representation of bits at least a single, and at most, 128 bits."""

    nbits: int
    lower: int
    upper: int
    acronym: str
    name: str
    description: str


class CommandDwords(BaseModel):
    """
    Command DWORDS; the DWORD or DWORDS forming a "field" within a command

    Should be applicable to Submission Queue Entries (SQE) as well as Completion Queuey
    Entries (CQE) since validation of DWORDS "collections" is up the the container e.g.
    (Command.sqe / Command.cqe), as the rules such as the total amount etc. needs to
    verifying at that level.
    """

    nbytes: int
    lower: int
    upper: int
    acronym: str
    name: str
    description: str

    bits: List[Bits] = Field(default_factory=list)


class Command(BaseModel):
    """Encapsulation of Command properties"""

    opcode: int
    alias: str
    name: str

    req: Optional[str]  # I/O Controller Requirement

    sqe: List[CommandDwords] = Field(default_factory=list)
    cqe: List[CommandDwords] = Field(default_factory=list)

    def is_optional(self):
        return self.requirement == "O"

    def is_mandatory(self):
        return self.requirement == "M"

    def is_prohibited(self):
        return self.requirement == "P"
