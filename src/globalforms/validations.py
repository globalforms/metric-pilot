"""Executable unary constraints on a supplied field value, independent of requiredness."""

from datetime import date
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, TypeAdapter, model_validator


class ValidationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    fields: Annotated[list[str], Field(min_length=1)]
    evidenceIds: list[str]


class DateValidation(ValidationRecord):
    """Historical pilot-0/1 predicate, retained for replay."""
    kind: Literal["iso_calendar_date"]

    def accepts(self, value: str) -> bool:
        return matches_date_format(value, "YYYY-MM-DD")


class GroundedValidation(ValidationRecord):
    evidenceIds: Annotated[list[str], Field(min_length=1)]

    def claims(self):
        """Hashable semantic predicates, independent of target IDs and evidence anchors."""
        parameters = self.model_dump(exclude={"kind", "fields", "evidenceIds"})
        return [(self.kind, *sorted(parameters.items()))]


def matches_date_format(value, mask):
    parts = re.fullmatch(mask.replace("YYYY", "([0-9]{4})")
                         .replace("MM", "([0-9]{2})").replace("DD", "([0-9]{2})"), value)
    if parts is None:
        return False
    components = dict(zip(re.findall("YYYY|MM|DD", mask), map(int, parts.groups())))
    try:
        date(components["YYYY"], components["MM"], components["DD"])
    except ValueError:
        return False
    return True


class DateFormat(GroundedValidation):
    kind: Literal["date_format"]
    format: Literal["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"]

    def accepts(self, value: str) -> bool:
        return matches_date_format(value, self.format)


class Length(GroundedValidation):
    kind: Literal["length"]
    min: NonNegativeInt | None = None
    max: NonNegativeInt | None = None

    @model_validator(mode="after")
    def check_bounds(self):
        if self.min is None and self.max is None:
            raise ValueError("Supply at least one length bound")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("Minimum length exceeds maximum length")
        return self

    def claims(self):
        return [(self.kind, name, bound) for name, bound in (("min", self.min), ("max", self.max))
                if bound is not None]

    def accepts(self, value: str) -> bool:
        return ((self.min is None or self.min <= len(value)) and
                (self.max is None or len(value) <= self.max))


class CharacterSet(GroundedValidation):
    kind: Literal["character_set"]
    alphabet: Literal["ascii_digits"]

    def accepts(self, value: str) -> bool:
        return value.isascii() and value.isdigit()


class Checksum(GroundedValidation):
    kind: Literal["checksum"]
    algorithm: Literal["decimal_mod_97"]
    remainder: Annotated[int, Field(ge=0, le=96)]

    def accepts(self, value: str) -> bool:
        if not (value.isascii() and value.isdigit()):
            return False
        remainder = 0
        for digit in value:
            remainder = (10 * remainder + int(digit)) % 97
        return remainder == self.remainder


Constraint = Annotated[DateFormat | Length | CharacterSet | Checksum, Field(discriminator="kind")]
ReadableConstraint = Annotated[DateValidation | DateFormat | Length | CharacterSet | Checksum,
                               Field(discriminator="kind")]
wire_validation = TypeAdapter(ReadableConstraint)


def describe(rule):
    """Compact labels for a review of the supplied constraints."""
    if isinstance(rule, DateValidation):
        return "ISO calendar date (legacy)"
    if isinstance(rule, DateFormat):
        return rule.format
    if isinstance(rule, Length):
        if rule.min == rule.max:
            return f"exactly {rule.min} chars"
        return ", ".join(f"{op} {n} chars" for op, n in (("≥", rule.min), ("≤", rule.max)) if n is not None)
    if isinstance(rule, CharacterSet):
        return "digits 0–9"
    return f"decimal mod 97 = {rule.remainder}"
