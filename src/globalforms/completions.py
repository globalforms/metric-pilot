"""Render completion entries in the widgets of the supplied form specification."""

from dataclasses import dataclass

from .overlays import Box, page_axes
from .spec import FormSpec


@dataclass(frozen=True)
class AnswerMark:
    field_id: str
    region_id: str
    page: int
    box: Box
    text: str


def answer_marks(spec: FormSpec, entries):
    """Return grounded answers and entries without a unique drawable destination."""
    marks = []
    unplaced = {}
    for key, entry in entries.items():
        field = spec.fields.get(key)
        if field is None or not isinstance(entry, dict):
            unplaced[key] = entry
            continue
        if field.options and "value" in entry:
            option = entry["value"]
            region_id = field.options.get(option) if isinstance(option, str) else None
            text = "✓"
        elif len(field.regions) == 1 and ("value" in entry or "status" in entry):
            region_id = field.regions[0]
            text = str(entry["value"]) if "value" in entry else f"[{entry['status']}]"
        else:
            region_id = None
        if region_id is None:
            unplaced[key] = entry
            continue
        region = spec.regions[region_id]
        marks.append(AnswerMark(key, region_id, region.page, tuple(region.bbox), text))
    return marks, unplaced


def draw_answers(ax, marks, page, *, color):
    """Fill text and choice marks inside their own region in PDF coordinates."""
    from matplotlib.patches import Rectangle

    for mark in marks:
        if mark.page != page:
            continue
        x, y, w, h = mark.box
        patch = Rectangle((x, y), w, h, facecolor=color, edgecolor=color, alpha=.16)
        ax.add_patch(patch)
        text = ax.text(x + min(3, w / 5), y + h / 2, mark.text, va="center", color=color,
                       weight="semibold", fontsize=10, clip_on=True, parse_math=False)
        text.set_clip_path(patch)


def compare_completions(reference_spec, expected, predicted_spec, submitted, *,
                        page, page_size, image, crop=None):
    """Render both sides on the same source raster, using each side's own grounding."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3), layout="constrained")
    sides = ((reference_spec, expected, "Expected", "#006c69"),
             (predicted_spec, submitted, "Predicted", "#754098"))
    for ax, (spec, entries, title, color) in zip(axes, sides):
        page_axes(ax, page_size, image=image, crop=crop)
        marks, unplaced = answer_marks(spec, entries)
        draw_answers(ax, marks, page, color=color)
        ax.set_title(title, loc="left", color=color, fontweight="bold")
        if unplaced:
            lines = [f"{key}: {value}" for key, value in unplaced.items()]
            ax.text(0, -.04, "Without a grounded region: " + ", ".join(lines),
                    transform=ax.transAxes, va="top", color=color, fontsize=9, parse_math=False)
    return fig
