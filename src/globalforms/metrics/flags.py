"""Boolean review flags derived from the existing pilot scores."""

from collections.abc import Iterable, Mapping
from enum import Enum


class _ReviewFlag(str, Enum):
    """A string key for JSON and a separate label for display."""

    label: str

    def __new__(cls, key: str, label: str):
        member = str.__new__(cls, key)
        member._value_ = key
        member.label = label
        return member


class TrackAFlag(_ReviewFlag):
    """A ranked or diagnostic component with at least one FP or FN."""

    GEOMETRY = "geometry", "Geometry"
    JOINT_FIELDS = "fields", "Joint fields"
    SECTIONS = "sections", "Sections"
    ROLES = "roles", "Roles"
    APPLICABILITY = "rules", "Applicability"
    FIELD_TYPE = "type", "Field type"
    LABEL = "label", "Field label"
    OPTION_OWNERSHIP = "option ownership", "Option ownership"
    CARDINALITY = "cardinality", "Cardinality"
    REQUIREDNESS = "requiredness", "Requiredness"
    VALIDATION = "validation", "Validation"


class TrackBFlag(_ReviewFlag):
    """Scoring events, case failure, and the two observations in the completion matrix."""

    OMITTED_SUPPLIED_ANSWER = "omitted_supplied_answer", "Omitted a supplied answer"
    INACTIVE_ENTRY = "inactive_entry", "Filled an inactive field"
    UNKNOWN_ENTRY = "unknown_entry", "Submitted an unknown field"
    ANY_SCORING_ERROR = "any_scoring_error", "Any scoring error"
    OMITTED_EXPECTED_FIELD = "omitted_expected_field", "Left an expected field blank (observation)"
    DRAWABLE_UNKNOWN_ENTRY = "drawable_unknown_entry", "Unknown entry has a drawable box (observation)"


def track_a_flags(
    components: Mapping[str, tuple[int, int, int]],
    diagnostics: Mapping[str, tuple[int, int, int]],
) -> dict[TrackAFlag, bool]:
    """Read the ranked and diagnostic triples returned by track_a."""
    return {
        TrackAFlag(key): fp > 0 or fn > 0
        for group in (components, diagnostics)
        for key, (_, fp, fn) in group.items()
    }


def track_b_flags(scores: Mapping, *, drawable_field_ids: Iterable[str]) -> dict[TrackBFlag, bool]:
    """Read one track_b result and the submitted field IDs with drawable answers."""
    return {
        TrackBFlag.OMITTED_SUPPLIED_ANSWER: scores["omitted_supplied"] > 0,
        TrackBFlag.INACTIVE_ENTRY: scores["inactive"][0] > 0,
        TrackBFlag.UNKNOWN_ENTRY: scores["unmatched"] > 0,
        TrackBFlag.ANY_SCORING_ERROR: scores["complete"][0] == 0,
        TrackBFlag.OMITTED_EXPECTED_FIELD: scores["omitted_expected"] > 0,
        TrackBFlag.DRAWABLE_UNKNOWN_ENTRY: not set(scores["unmatched_ids"]).isdisjoint(drawable_field_ids),
    }
