# GlobalForms metric pilot

[Open the guiding notebook](GlobalForms-metric-pilot.ipynb) to compare Track A form recovery and Track B scenario completion. Its saved outputs cover all bundled fixtures. Each track shows the figures, scores and error matrix for each fixture that supplies cases.

| Fixture | Source page | Track A | Track B | What to look for |
|---|---:|---:|---:|---|
| [Incident](fixtures/incident/review.json) | 1 | 5 | 5 | Geometry, field ownership, sections, roles, rules, and when a blank earns credit |
| [Length](fixtures/length/review.json) | 1 | 1 | 0 | Three identifier fields with different evidence for length and digit constraints |
| [Locker](fixtures/locker/review.json) | 2 | 2 | 2 | Cached Flash-Lite boxes, matched-box IoUs, and role F1 with and without the Custodian default |

## Run the notebook

From the repository root, use Python 3.10 or later and uv. PDF-backed manifests also use Poppler’s `pdfinfo` and `pdftoppm` on PATH.

```sh
uv sync --locked --extra notebook
uv run --locked --extra notebook jupyter lab GlobalForms-metric-pilot.ipynb
```

To focus on one fixture, set `FIXTURE = "locker"` in the first code cell and run all cells. It also accepts a path to any review manifest. The default `"all"` discovers `fixtures/*/review.json` in folder-name order. Adding a bundle there makes it available to the same cells. The locker review reads the [cached prediction](fixtures/locker/predictions/flash-lite.json) and scores it locally.

You can also select a fixture when launching Jupyter:

```sh
GLOBALFORMS_FIXTURE=fixtures/locker/review.json uv run --locked --extra notebook jupyter lab GlobalForms-metric-pilot.ipynb
```

To refresh the saved walkthrough for GitHub, keep the first cell’s environment-based selector and run:

```sh
GLOBALFORMS_FIXTURE=all uv run --locked --extra notebook jupyter nbconvert \
  --to notebook --execute --inplace --ExecutePreprocessor.record_timing=False GlobalForms-metric-pilot.ipynb
```

### Preview the Aetna source locally

Set `FIXTURE = fetch_aetna_pdf()` in the notebook’s first code cell and run all cells. This downloads the issuer’s three-page blank form into the user cache and displays a local page preview. The helper verifies the recorded SHA-256 on download and on cache hits. Selecting an existing PDF path also opens the source preview. [Issuer PDF](https://www.aetna.com/content/dam/aetna/pdfs/aetnacom/individuals-families-health-insurance/document-library/medical-claim-form-spanish.pdf)

Set `GLOBALFORMS_CACHE_DIR` in the environment or in a local `.env` where you launch Jupyter. An exported value takes precedence. For example:

```dotenv
GLOBALFORMS_CACHE_DIR=~/.cache/globalforms
```

The default follows the OS user-cache convention, such as `$XDG_CACHE_HOME/globalforms` or `~/.cache/globalforms` on Linux. PDFs live at `<cache>/pdfs/<sha256>/source.pdf`. A private manifest with an absent or missing local PDF reuses its source hash from this cache. Selecting a manifest never triggers a download. Local HTML previews are written under ignored `output/`.

If you have the private Aetna annotation bundle, select its `review.json` to view clickable answer regions, case rationales and recorded scores. The default rendered notebook runs offline with the bundled synthetic fixtures.

### Review a native omission annotation

Select the path to a private manifest in the same first cell. The notebook opens a standalone HTML review with clickable answer regions, the field ledger, the scenario and the original pilot’s saved probe scores. Each printed option retains its own geometry. The review distinguishes expected values and statuses from inactive fields, optional omissions, unoccupied slots and pending human actions. The native annotation retains its evidence, draft state and unresolved issues.

Keep the manifest and its inputs together under ignored `output/private-fixtures/<name>/`. Use `version: 1`, `kind: "omission-annotation"` and these paths relative to the manifest.

| Key | Input |
|---|---|
| `pdf` | Optional local path to the original blank PDF. The source hash also identifies the cached copy. |
| `annotation` | Native `0.1.0-draft.1` annotation with top-left unrotated CropBox coordinates |
| `case` | Omission reference with source and candidate hashes, expected entries, and reason-tagged omissions |
| `scenario` | Fictional scenario text |
| `results` | Original flattened and reason-aware probe reports |

The loader verifies both hashes and checks that assessed field IDs resolve. This mode displays the pilot’s historical scores. The public default discovers only bundles under `fixtures/`. Private reports are written to `output/<name>/annotation.html`.

## Fixture and metric subspecs

| # | Operation | Inputs | Outputs |
|---|---|---|---|
| 1 | Load review | Manifest, raw reference and prediction JSON, scenario text, evaluator expectations, submissions | Validated form specs and resolved cases, independent of the notebook |
| 2a | Score recovery | Candidate and reference specs, optional default completion role | Five ranked TP/FP/FN triples and diagnostic counts, including requiredness and validation |
| 2b | Grade completion | Submitted entries, reviewed expected entries, reference spec and optional recovered spec | Correct/denominator, case pass, coverage, active-field accuracy, inactive and unmatched entries, omissions |
| 3 | Render review | Selected page, its geometry, scores and case records | Side-by-side PNGs, per-case JSON, shared gold specs and an error matrix |
| 4 | Verify outputs | Published incident counts and an independent two-page PDF | Exact incident parity and an end-to-end field-ID alignment check on the locker fixture |

The current scorer version is `pilot-metrics-2`. Exports record it separately from each spec's `schemaVersion`.

### 1. Supply a bundle

Give each document its own folder and `review.json`. File references resolve from that manifest. See [incident](fixtures/incident) for separate narratives, expected entries, submissions and candidate specs. One scenario and one expected-answer file can serve multiple model submissions.

- Set `version: 1`, `reference` and the one-based `page`. A PDF source uses `pdf` and derives its size from the unrotated CropBox. A raster source uses `image` plus `page_size` in PDF points. Optional `crop` and `completion_crop` select top-left x/y/width/height viewports. The pilot renders one selected page per manifest. Scores cover all fields in the specs.
- Each Track A case specifies a `layer` and candidate `spec`. A geometry case can include `inspect_regions` with one reference and one candidate region ID. For a cached model comparison, set `model` to the model ID and point `spec` to its normalized prediction. The notebook then includes a table of matched boxes and a full score breakdown.
- Each Track B case specifies `title`, `scenario_file` (UTF-8 text), `expected` and `submitted` (JSON files). Set `spec` for end-to-end grounding. Omit it for oracle mode. The grader accepts the reviewed reference separately from the submission. A prior manifest with inline `scenario`, `expected` and `submitted` still loads.
- Titles and explanations describe planted errors. Scoring functions use the spec and entry values.

### Role defaults

For a form with a single completion role, declare it once in the review manifest, for example `"default_role": "Custodian"` on the locker receipt. Track A resolves each aligned field’s role on both sides by checking the field first, then its enclosing sections from nearest to farthest, then the configured default. An explicit conflicting assignment still counts as an error. In the incident fixture, business-office fields inherit their section role and the other fields can fall back to Applicant.

The default is evaluator input. The CLI accepts it with `--default-role` when using `--reference`. An omitted argument leaves the scorer without a fallback. The role overlay adds `(default)` when a field uses it. The saved FormSpecs preserve the original declarations.

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

### Predicting document constraints

The producer contract is `PredictionFormSpec.model_json_schema()`. Its `pilot-2` validation records name the target fields, cite at least one evidence anchor and select one of the following kinds. A document can support an empty validation list.

| Kind | Parameters shown to the model | Python check on a supplied string |
|---|---|---|
| `date_format` | `format` of `YYYY-MM-DD`, `DD/MM/YYYY` or `MM/DD/YYYY` | Match the exact widths and separators and verify the calendar date. |
| `length` | Inclusive integer `min`, `max`, or both | Count Unicode code points in the original string, including leading zeroes and spaces. Equal bounds express exact length. |
| `character_set` | `alphabet="ascii_digits"` | A nonempty sequence of ASCII digits 0–9. |
| `checksum` | `algorithm="decimal_mod_97"`, integer `remainder` from 0 to 96 | Read the entire ASCII digit string as a decimal number and compare its remainder modulo 97. |

Only record a constraint when the supplied document supports its parameters. The incident label prints its date mask. The locker receipt simply asks for a date. The [length reference](fixtures/length/reference.json) distinguishes an ordinary box, six character cells, and a printed six-digit instruction. A field’s type and the accepted interchange format for Track B answers are separate from its document constraints.

Track A first aligns fields, then compares distinct `(field, predicate, parameters)` claims. Lower and upper length bounds score independently, and regrouping equivalent predicates in separate records gives the same score. A wrong parameter gives a false positive and a false negative. Citing the correct claim with a different evidence ID preserves the semantic score. Evidence location and relevance are available for review. With no claims on either side, validation F1 is undefined.

```python
from pathlib import Path
from globalforms import PredictionFormSpec

menu = PredictionFormSpec.model_json_schema()
spec = PredictionFormSpec.model_validate_json(Path("fixtures/length/reference.json").read_bytes())
spec.failed_validations("digits", "001234")  # []
spec.failed_validations("digits", "ABCDEF")  # character_set
```

`failed_validations` checks a supplied value. Track B grades missing, conflicting or omitted entries using the scenario. To add a new algorithm, define its precise input normalization and parameters in the typed vocabulary, implement its predicate in Python, and add passing and failing vectors. A bank-specific check-digit scheme with letter conversion or rearrangement needs its own algorithm identifier. An unsupported check can be flagged for annotation review outside the prediction. The historical reader accepts `pilot-0` and `pilot-1` records, including their original `iso_calendar_date` semantics. The current scorer retains that distinct legacy claim when comparing old predictions.

### Error flags

Both matrices use string enums from `globalforms.metrics`. Each member has a stable JSON key (`.value`) and a display label (`.label`). `track_a_flags(*track_a(candidate, gold))` returns booleans keyed by `TrackAFlag`. For example, `flags[TrackAFlag.OPTION_OWNERSHIP]` is true when that diagnostic has a false positive or false negative, including downstream alignment errors.

`track_b_flags(grade, drawable_field_ids=ids)` returns booleans keyed by `TrackBFlag`. Supply the submitted IDs with drawable answer marks to distinguish an unknown entry on the PDF from one without a box. An accepted blank sets `OMITTED_EXPECTED_FIELD`. Omitting a supplied answer also sets `OMITTED_SUPPLIED_ANSWER` and `ANY_SCORING_ERROR`. Each saved case exports the flags as JSON booleans alongside its counts.

### 3. Inspect results

Displaying a `FormSpec` in Jupyter shows its serialized groups with the paper’s colors. For a review UI, import `formspec_html` from `globalforms.spec_view`. Pass one validated spec for a full view, or call `formspec_html(reference, prediction, changed_only=True)` to see changed entries side by side. The static HTML preserves the original IDs, roles and evidence links. Text labels identify each group in viewers that strip inline colors.

Answer regions locate writable space. Evidence anchors locate the source that supports a field, section, rule or validation. For example, the locker fixture’s `date_box` is where the date goes and `date_label` cites the printed label. The pilot validates evidence references and uses them in review overlays. Track A scores the geometry of answer regions. Evidence localization and the relevance of a citation to its claim have no metric in the current suite.

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
