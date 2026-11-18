"""Page overlays in one-based, top-left PDF points. No plotting dependency."""

from dataclasses import asdict, dataclass
from typing import Iterable, Literal

from .spec import FormSpec

Layer = Literal["geometry", "fields", "sections", "roles", "rules"]
Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class Mark:
    layer: Layer
    page: int
    field_id: str
    region_id: str
    box: Box
    label: str = ""
    source_id: str | None = None
    source_page: int | None = None
    source_box: Box | None = None

    option: str | None = None
    field_type: str | None = None

    def to_dict(self):
        """JSON-compatible values for a browser canvas or SVG renderer."""
        return asdict(self)


def page_marks(spec: FormSpec, page: int, *, default_role: str | None = None) -> list[Mark]:
    """Describe each answer region and its relationships, retaining off-page sources."""
    if page < 1:
        raise ValueError("Pages start at 1")
    marks = []
    for field_id, field in spec.fields.items():
        ancestors = []
        section_id = field.section
        while section_id is not None:
            ancestors.append(section_id)
            section_id = spec.sections[section_id].parent
        for region_id in field.regions:
            region = spec.regions[region_id]
            if region.page != page:
                continue
            box = tuple(region.bbox)

            def add(layer, label="", source_id=None, source=None, *, option=None):
                marks.append(Mark(layer, page, field_id, region_id, box, label, source_id,
                                  source.page if source else None, tuple(source.bbox) if source else None,
                                  option=option, field_type=field.type))

            def evidence(ids):
                anchors = [spec.evidence[key] for key in ids]
                return next((a for a in anchors if a.page == page), next(iter(anchors), None))

            add("geometry")
            option = next((k for k, v in field.options.items() if v == region_id), None)
            label = field.label if option is None else option
            add("fields", label, field_id, evidence(field.evidenceIds), option=option)
            if field.section is not None:
                section = spec.sections[field.section]
                add("sections", section.title, field.section, evidence(section.evidenceIds))
            role_section = next((k for k in ancestors if spec.sections[k].role), None)
            if field.role:
                add("roles", field.role, field_id, evidence(field.evidenceIds))
            elif role_section is not None:
                section = spec.sections[role_section]
                add("roles", section.role, role_section, evidence(section.evidenceIds))
            elif default_role is not None:
                add("roles", default_role)
            for rule in spec.rules:
                if field_id not in rule.fields and not any(s in rule.sections for s in ancestors):
                    continue
                control = spec.fields[rule.controller]
                widget = control.options[rule.option]
                op = "=" if rule.op == "eq" else "≠"
                add("rules", f"{control.label} {op} {rule.option} → {rule.effect}",
                    widget, spec.regions[widget])
    return marks


def draw_layer(ax, marks: Iterable[Mark], layer: Layer, *, color="#256281", linestyle="-",
               show_labels=True):
    """Draw into caller-owned axes already set to top-left PDF coordinates."""
    from matplotlib.patches import Rectangle

    rows = {}
    for mark in marks:
        if mark.layer != layer:
            continue
        x, y, w, h = mark.box
        ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor=color, linestyle=linestyle))
        if mark.source_box and mark.source_page == mark.page:
            sx, sy, sw, sh = mark.source_box
            ax.annotate("", xy=(x, y + h / 2), xytext=(sx + sw / 2, sy + sh / 2),
                        arrowprops={"arrowstyle": "->", "color": color, "lw": 0.9})
        if show_labels and mark.label:
            row = rows.get(mark.box, 0)
            label = mark.label
            if mark.source_page is not None and mark.source_page != mark.page:
                label += f" (from p. {mark.source_page})"
            ax.annotate(label, (x, y), xytext=(0, 3 + row * 10), textcoords="offset points",
                        fontsize=8, color=color, bbox={"facecolor": "white", "edgecolor": "none", "alpha": .85})
            rows[mark.box] = row + 1


def page_axes(ax, page_size, *, image=None, crop=None):
    """Place a full-page raster and optional (x, y, width, height) viewport."""
    width, height = page_size
    if image is not None:
        ax.imshow(image, extent=(0, width, height, 0), origin="upper")
    x, y, w, h = crop if crop is not None else (0, 0, width, height)
    ax.set(xlim=(x, x + w), ylim=(y + h, y), aspect="equal")
    ax.axis("off")


def draw_region_pair(ax, reference: Mark, prediction: Mark):
    """Overlay one caller-selected pair and report both directional overlap ratios."""
    from matplotlib.patches import Rectangle

    if reference.page != prediction.page or reference.layer != "geometry" or prediction.layer != "geometry":
        raise ValueError("Expected two geometry marks on the same page")
    draw_layer(ax, [reference], "geometry")
    draw_layer(ax, [prediction], "geometry", color="#ae4935", linestyle="--")
    x, y, w, h = reference.box
    px, py, pw, ph = prediction.box
    left, top = max(x, px), max(y, py)
    iw = max(0, min(x + w, px + pw) - left)
    ih = max(0, min(y + h, py + ph) - top)
    area = iw * ih
    if area:
        ax.add_patch(Rectangle((left, top), iw, ih, color="#457b64", alpha=.25))
    return area / (w * h), area / (pw * ph)


def compare_layer(reference, prediction, layer: Layer, page_size, *, image=None, crop=None):
    """Return a Matplotlib figure comparing page_marks outputs on identical viewports."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    for ax, marks, title, color in zip(axes, (reference, prediction), ("Reference", "Prediction"),
                                       ("#256281", "#ae4935")):
        page_axes(ax, page_size, image=image, crop=crop)
        draw_layer(ax, marks, layer, color=color)
        ax.set_title(title, loc="left", fontsize=11, color=color)
    return fig
