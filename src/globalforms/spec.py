"""Wire format of the staged synthetic fixtures. Coordinates are top-left PDF points."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, PositiveInt, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Anchor(Model):
    page: PositiveInt
    bbox: Annotated[list[FiniteFloat], Field(min_length=4, max_length=4)]

    @model_validator(mode="after")
    def check_rectangle(self):
        x, y, width, height = self.bbox
        if min(x, y) < 0 or min(width, height) <= 0:
            raise ValueError("Expected nonnegative origin and positive dimensions")
        return self


class Section(Model):
    title: str
    evidenceIds: list[str]
    role: str | None = None
    parent: str | None = None


class FieldSpec(Model):
    label: str
    section: str | None
    role: str | None = None
    evidenceIds: list[str]
    regions: Annotated[list[str], Field(min_length=1)]


class EntryField(FieldSpec):
    type: Literal["text", "date"]
    options: Annotated[dict[str, str], Field(max_length=0)]


class ChoiceField(FieldSpec):
    type: Literal["choice"]
    options: Annotated[dict[str, str], Field(min_length=1)]
    cardinality: list[int] | None = None

    @model_validator(mode="after")
    def check_options(self):
        if sorted(self.options.values()) != sorted(set(self.regions)):
            raise ValueError("Each option must own exactly one distinct field region")
        if self.cardinality is not None:
            if len(self.cardinality) != 2 or not 0 <= self.cardinality[0] <= self.cardinality[1] <= len(self.options):
                raise ValueError("Invalid selection cardinality")
        return self


class ChoiceRule(Model):
    effect: Literal["applicable", "required"] = "applicable"
    controller: str
    op: Literal["eq", "ne"]
    option: str
    fields: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    evidenceIds: list[str] = Field(default_factory=list)


class DateValidation(Model):
    kind: Literal["iso_calendar_date"]
    fields: Annotated[list[str], Field(min_length=1)]
    evidenceIds: list[str]


class FormSpec(Model):
    schemaVersion: Literal["pilot-0", "pilot-1"]
    fields: dict[str, Annotated[EntryField | ChoiceField, Field(discriminator="type")]]
    sections: dict[str, Section]
    regions: dict[str, Anchor]
    evidence: dict[str, Anchor]
    rules: list[ChoiceRule]
    validations: list[DateValidation]

    def _repr_html_(self) -> str:
        """Show the semantic JSON groups when a notebook displays a FormSpec."""
        from .spec_view import formspec_html

        return formspec_html(self)

    @model_validator(mode="after")
    def check_references(self):
        owned = set()
        for field in self.fields.values():
            if field.section is not None and field.section not in self.sections:
                raise ValueError(f"Unknown section {field.section!r}")
            for region in field.regions:
                if region not in self.regions or region in owned:
                    raise ValueError(f"Unknown or multiply owned region {region!r}")
                owned.add(region)
        for start in self.sections:
            section = start
            seen = set()
            while section is not None:
                if section in seen or section not in self.sections:
                    raise ValueError(f"Cyclic or unknown section {section!r}")
                seen.add(section)
                section = self.sections[section].parent
        for rule in self.rules:
            controller = self.fields.get(rule.controller)
            if not isinstance(controller, ChoiceField) or rule.option not in controller.options:
                raise ValueError(f"Unknown controller or option in rule for {rule.controller!r}")
            if (not rule.fields and not rule.sections or set(rule.fields) - self.fields.keys()
                    or set(rule.sections) - self.sections.keys()):
                raise ValueError("Missing or unknown rule target")
        for validation in self.validations:
            for key in validation.fields:
                if key not in self.fields or self.fields[key].type != "date":
                    raise ValueError(f"Calendar validator requires a date field at {key!r}")
        for item in [*self.fields.values(), *self.sections.values(), *self.rules, *self.validations]:
            if set(item.evidenceIds) - self.evidence.keys():
                raise ValueError("Unknown source evidence ID")
        return self
