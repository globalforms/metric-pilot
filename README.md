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
