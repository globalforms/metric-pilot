"""Load one page and its evaluator inputs from a review manifest."""

import json
import os
import re
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, PositiveInt, model_validator

from .metrics.track_b import valid_entry
from .overlays import Layer
from .spec import FormSpec


class BundleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecoveryCase(BundleModel):
    layer: Layer
    spec: FormSpec
    title: str | None = None
    explanation: str = ""
    inspect_regions: tuple[str, str] | None = None


class CompletionCase(BundleModel):
    title: str
    scenario: str
    expected: dict[str, dict]
    submitted: dict[str, object]
    explanation: str = ""
    spec: FormSpec | None = None


class ReviewBundle(BundleModel):
    version: Literal[1] = 1
    reference: FormSpec
    page: PositiveInt
    image: Path | None = None
    pdf: Path | None = None
    page_size: tuple[FiniteFloat, FiniteFloat] | None = None
    crop: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat] | None = None
    completion_crop: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat] | None = None
    default_role: str | None = None
    track_a: list[RecoveryCase] = Field(default_factory=list)
    track_b: list[CompletionCase] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_inputs(self):
        if (self.image is None) == (self.pdf is None):
            raise ValueError("Select one page source: image or pdf")
        if self.image is not None and self.page_size is None:
            raise ValueError("A raster page requires page_size in PDF points")
        if self.page_size and min(self.page_size) <= 0:
            raise ValueError("Page dimensions must be positive")
        for crop in (self.crop, self.completion_crop):
            if crop and min(crop[2:]) <= 0:
                raise ValueError("The viewport must have positive width and height")
        for case in self.track_b:
            for key, entry in case.expected.items():
                if key not in self.reference.fields or not valid_entry(entry):
                    raise ValueError(f"{case.title}: invalid expected field or entry {key!r}")
        for case in self.track_a:
            if case.inspect_regions:
                for spec, key in zip((self.reference, case.spec), case.inspect_regions):
                    if case.layer != "geometry" or key not in spec.regions or spec.regions[key].page != self.page:
                        raise ValueError(f"Geometry inspection requires a region on page {self.page}: {key!r}")
        return self


def load_review(path: str | Path) -> ReviewBundle:
    """Resolve all fixture paths relative to the manifest. Accept existing inline cases."""
    path = Path(path).resolve()

    def read_json(name):
        source = path.parent / name
        try:
            return json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {source}: {exc}") from exc

    data = read_json(path.name)
    data["reference"] = read_json(data["reference"])
    for key in ("pdf", "image"):
        if key in data:
            data[key] = path.parent / data[key]
    for case in data.get("track_a", []):
        case["spec"] = read_json(case["spec"])
    for case in data.get("track_b", []):
        if "scenario_file" in case:
            if "scenario" in case:
                raise ValueError(f"{case['title']}: select scenario_file or inline scenario")
            case["scenario"] = (path.parent / case.pop("scenario_file")).read_text(encoding="utf-8").strip()
        for key in ("expected", "submitted", "spec"):
            if isinstance(case.get(key), str):
                case[key] = read_json(case[key])
    return ReviewBundle.model_validate(data)


def read_page(bundle: ReviewBundle):
    """Return the page raster and its unrotated CropBox extent in PDF points."""
    from matplotlib.image import imread

    if bundle.image is not None:
        return imread(bundle.image), bundle.page_size

    page = str(bundle.page)
    selection = ["-f", page, "-l", page]
    info = subprocess.run(
        ["pdfinfo", *selection, "-box", str(bundle.pdf)], check=True,
        capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"},
    ).stdout
    box = re.search(rf"^Page\s+{page} CropBox:\s*(.+)$", info, re.MULTILINE)
    if box is None or not re.search(rf"^Page\s+{page} rot:\s*0\s*$", info, re.MULTILINE):
        raise ValueError(f"Expected an unrotated CropBox on page {page} of {bundle.pdf}")
    x0, y0, x1, y1 = map(float, box[1].split())
    size = (x1 - x0, y1 - y0)
    if bundle.page_size and any(abs(a - b) > .02 for a, b in zip(size, bundle.page_size)):
        raise ValueError(f"Declared page_size {bundle.page_size} differs from the PDF CropBox {size}")
    result = subprocess.run(
        ["pdftoppm", *selection, "-singlefile", "-cropbox", "-scale-to", "1200", "-png", str(bundle.pdf)],
        check=True, capture_output=True,
    )
    return imread(BytesIO(result.stdout), format="png"), size
