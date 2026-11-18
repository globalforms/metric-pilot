# GlobalForms metric pilot

The [notebook](GlobalForms-metric-pilot.ipynb) reviews PDF specification recovery (Track A) and scenario completion (Track B). It imports the scoring suite from `globalforms.metrics`. The incident and locker bundles contain synthetic reference data and deliberately perturbed submissions.

## Run a fixture

Use Python 3.10 or later and uv. Run from the repository root.

```sh
uv sync --locked --extra notebook
uv run --locked --extra notebook jupyter lab GlobalForms-metric-pilot.ipynb
```

The default is the [incident review](fixtures/incident/review.json). To switch to [page two of the locker receipt](fixtures/locker/review.json), set the manifest in the environment used to launch Jupyter.

```sh
GLOBALFORMS_FIXTURE=fixtures/locker/review.json uv run --locked --extra notebook jupyter lab GlobalForms-metric-pilot.ipynb
```

For a fully executed notebook from the shell:

```sh
mkdir -p output/locker
GLOBALFORMS_FIXTURE=fixtures/locker/review.json uv run --locked --extra notebook jupyter nbconvert \
  --execute --to notebook --output-dir output/locker GlobalForms-metric-pilot.ipynb
```

A PDF-backed bundle uses Poppler's `pdfinfo` and `pdftoppm` on PATH. The incident bundle uses a pre-rendered page and runs with the uv environment alone.

## Fixture and metric subspecs

| # | Operation | Inputs | Outputs |
|---|---|---|---|
| 1 | Load review | Manifest, raw reference and prediction JSON, scenario text, evaluator expectations, submissions | Validated form specs and resolved cases, independent of the notebook |
| 2a | Score recovery | Candidate and reference specs, optional default completion role | Five ranked TP/FP/FN triples and diagnostic counts, including requiredness and validation |
| 2b | Grade completion | Submitted entries, reviewed expected entries, reference spec and optional recovered spec | Correct/denominator, case pass, coverage, active-field accuracy, inactive and unmatched entries, omissions |
| 3 | Render review | Selected page, its geometry, scores and case records | Side-by-side PNGs, per-case JSON, shared gold specs and an error matrix |
| 4 | Verify outputs | Published incident counts and an independent two-page PDF | Exact incident parity and an end-to-end field-ID alignment check on the locker fixture |

The current scorer version is `pilot-metrics-1`. Exports record it separately from each spec's `schemaVersion`.

### 1. Supply a bundle

Give each document its own folder and `review.json`. File references resolve from that manifest. See [incident](fixtures/incident) for separate narratives, expected entries, submissions and candidate specs. One scenario and one expected-answer file can serve multiple model submissions.

- Set `version: 1`, `reference` and the one-based `page`. A PDF source uses `pdf` and derives its size from the unrotated CropBox. A raster source uses `image` plus `page_size` in PDF points. Optional `crop` and `completion_crop` select top-left x/y/width/height viewports. The pilot renders one selected page per manifest. Scores cover all fields in the specs.
- Each Track A case specifies a `layer` and candidate `spec`. A geometry case can include `inspect_regions` with one reference and one candidate region ID. The optional default role belongs to the bundle.
- Each Track B case specifies `title`, `scenario_file` (UTF-8 text), `expected` and `submitted` (JSON files). Set `spec` for end-to-end grounding. Omit it for oracle mode. The grader accepts the reviewed reference separately from the submission. A prior manifest with inline `scenario`, `expected` and `submitted` still loads.
- Titles and explanations describe planted errors. Scoring functions use the spec and entry values.

### 2. Import the scorers

```python
from globalforms.fixtures import load_review
from globalforms.metrics import f1, track_a, track_b

review = load_review("fixtures/locker/review.json")
gold = review.reference.model_dump(exclude_unset=True)
candidate = review.track_a[0].spec.model_dump(exclude_unset=True)
counts, diagnostics = track_a(candidate, gold, default_role=review.default_role)
section_f1 = f1(counts["sections"])

case = review.track_b[0]
recovered = case.spec.model_dump(exclude_unset=True) if case.spec is not None else None
grade = track_b(case.submitted, case.expected, gold, recovered)
```

The scoring API takes dictionaries in the pilot form format. `FormSpec.model_validate_json` validates a producer's spec and `FormSpec.model_json_schema()` exports the current schema. `pool_a` sums component counts before F1. `paired_pass` checks exact entries on selected fields across paired scenarios. The one-to-one matcher is intended for small pilot forms.

### 3. Inspect results

The notebook writes to `output/<fixture-folder>/track-a/` and `track-b/`. Both include the shared reference and one PNG and predicted spec per comparison. Track A also writes ranked and diagnostic counts. Track B writes each narrative, expected and submitted entries, mode and grade. The matrix is embedded in the notebook.

For a browser reviewer, `globalforms.overlays.page_marks(spec, page)` returns field and region IDs, coordinates, labels and relationship sources. Serialize each mark with `to_dict()`. The Matplotlib adapters use the same geometry; callers supply the page raster and viewport. The incident heading rectangles are the unions of the corresponding source PDF words.

### 4. Regression checks

```sh
uv run --locked python -m unittest discover -s tests -v
```

The [incident baseline](fixtures/incident/regressions/published-scores.json) records counts from the published notebook at `2541662`. Tests also cover the five historical stages, Appendix A, paired completion, requiredness and legacy inline manifests. The [published incident walkthrough](https://github.com/globalforms/metric-pilot/blob/25416629a9bf765127320a988a39a27f91605ce0/GlobalForms-metric-pilot.ipynb) retains the original staged demonstrations. The independent locker receipt uses different fields, page dimensions and a recovered ID. Its expected section counts are one TP and one FN. Its two completion cases score 2/2 and 1/2.

To regenerate the five historical blank incident PDFs and JSON files:

```sh
uv run --locked --extra pdf python scripts/export_incident_stages.py
```
