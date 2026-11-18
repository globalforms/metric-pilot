# GlobalForms metric pilot

A small, executable pilot for Track A (form specification recovery) and Track B (form completion). The synthetic examples grow from a single field to a form with sections, multiple roles, date validation and a conditional branch.

## Run locally

Use Python 3.10 or later.

```sh
uv sync --locked --extra notebook
uv run --locked --extra notebook jupyter lab GlobalForms-metric-pilot.ipynb
```

Run all cells in order. The notebook imports the local Pydantic v2 package and renders the validated incident fixture. To generate the five blank PDFs and reference JSON files, include `--extra pdf` in both uv commands, set `WRITE_PDFS = True` in the optional notebook cell, and rerun it.

The notebook includes synthetic regression checks, a worked Track A example, and a protocol for a later pilot with model predictions and blinded human judgments. Track A weights and the real-file scoring policies remain open.

## Python API

```python
from globalforms import FormSpec

spec = FormSpec.model_validate_json(raw_json)
schema = FormSpec.model_json_schema()
```

The package models the pilot-0 and pilot-1 notebook formats. Document page bounds and full competition conformance are future work.

## Review overlays

`globalforms.overlays.page_marks(spec, page)` returns the marks for one page.
Each mark identifies its field and answer region. A relationship can also point to a
source on another page. Coordinates are top-left PDF points. Pass the scorer's default
role explicitly if it should appear on unassigned fields.

```python
from globalforms.overlays import page_marks

payload = [mark.to_dict() for mark in page_marks(spec, page=1)]
```

A browser can group marks by layer, use field and region IDs for selection, and apply
the PDF viewer's page-to-viewport transform when zooming or rotating. Translated
labels can be supplied through the input spec. The notebook uses the optional
Matplotlib adapters `page_axes`, `draw_layer`, `draw_region_pair` and `compare_layer`.
Matching and scoring belong to the evaluator. A displayed pair of regions can be
inspected even when it fails matching.

The notebook background in `fixtures/incident-page-1.png` is a rendering of the
synthetic stage-5 PDF embedded in the scoring explainer.

## Review a different fixture

Set `review_path` in the notebook to the new fixture's manifest. The [incident manifest](fixtures/incident/review.json) is a worked example. It selects one page image, its dimensions in PDF points, optional viewports and default role, and a [reference specification](fixtures/incident/reference.json). Relative paths resolve from the manifest's directory.

Track A cases supply a layer and a saved candidate spec. A geometry case can also name a reference/prediction region pair to inspect. Track B cases supply the narrative, expected entries, submitted entries and a caption. An optional candidate spec enables grounding-based alignment. The scorer computes the results from these inputs.

The incident reference stores the union of each heading's page-1 word boxes measured with Poppler on the embedded stage-5 PDF. Historical stages and Appendix A examples live under `fixtures/incident/regressions/`. Those fixed regression checks run independently of the selected review fixture.
