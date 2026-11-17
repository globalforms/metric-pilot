# GlobalForms metric pilot

A small, executable pilot for Track A (form specification recovery) and Track B (form completion). The synthetic examples grow from a single field to a form with sections, multiple roles, date validation and a conditional branch.

## Run locally

Use Python 3.10 or later.

```sh
python -m pip install jupyterlab
jupyter lab GlobalForms-metric-pilot.ipynb
```

Run all cells in order. The scoring checks use Python's standard library. To generate the five blank PDFs and reference JSON files, install `reportlab`, set `WRITE_PDFS = True` in the optional notebook cell, and rerun it.

The notebook includes synthetic regression checks, a worked Track A example, and a protocol for a later pilot with model predictions and blinded human judgments. Track A weights and the real-file scoring policies remain open.
