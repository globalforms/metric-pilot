"""Acceptance checks at the fixture-loader and metric-package boundaries."""

import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from globalforms.fixtures import load_review
from globalforms.metrics import pool_a, track_a, track_b
from globalforms.metrics.alignment import align, matching, region_iou
from globalforms.overlays import page_marks
from globalforms.spec import FormSpec


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def wire(spec):
    return spec.model_dump(exclude_unset=True)


class BundleTests(TestCase):
    def test_full_incident_scores_match_published_notebook(self):
        folder = FIXTURES / "incident"
        bundle = load_review(folder / "review.json")
        baseline = json.loads((folder / "regressions/published-scores.json").read_text())
        ref = wire(bundle.reference)
        actual_a = {case.layer: track_a(wire(case.spec), ref, default_role=bundle.default_role)
                    for case in bundle.track_a}
        actual_b = {case.title: track_b(case.submitted, case.expected, ref,
                                         wire(case.spec) if case.spec else None)
                    for case in bundle.track_b}
        self.assertEqual(json.loads(json.dumps(actual_a)), baseline["track_a"])
        self.assertEqual(json.loads(json.dumps(actual_b)), baseline["track_b"])

    def test_independent_locker_fixture(self):
        bundle = load_review(FIXTURES / "locker/review.json")
        self.assertEqual(bundle.page, 2)
        ref = wire(bundle.reference)
        ranked, _ = track_a(wire(bundle.track_a[0].spec), ref)
        self.assertEqual(ranked["sections"], (1, 0, 1))
        renamed, omitted = bundle.track_b
        end_to_end = track_b(renamed.submitted, renamed.expected, ref, wire(renamed.spec))
        oracle = track_b(omitted.submitted, omitted.expected, ref)
        self.assertEqual((end_to_end["value"], end_to_end["complete"]), ((2, 2), (1, 1)))
        self.assertEqual((oracle["value"], oracle["complete"]), ((1, 2), (0, 1)))

    def test_cached_locker_prediction(self):
        bundle = load_review(FIXTURES / "locker/review.json")
        case, = [case for case in bundle.track_a if case.model == "gemini-3.5-flash-lite"]
        pred, ref = wire(case.spec), wire(bundle.reference)
        regions, _ = align(pred, ref)
        overlaps = {r: round(region_iou(pred["regions"][p], ref["regions"][r]), 4)
                    for p, r in regions.items()}
        self.assertEqual(overlaps, {"locker_box": .8033, "date_box": .8114})

        scores, diagnostics = track_a(pred, ref, default_role=bundle.default_role)
        self.assertEqual(scores, {"geometry": (2, 0, 0), "fields": (2, 0, 0), "sections": (2, 0, 0),
                                  "roles": (2, 0, 0), "rules": (0, 0, 0)})
        self.assertEqual(track_a(pred, ref)[0]["roles"], (0, 2, 2))
        self.assertEqual(diagnostics["validation"], (0, 0, 1))
        self.assertEqual(diagnostics["requiredness"], (0, 0, 0))

    def test_locker_omitted_and_explicit_roles(self):
        bundle = load_review(FIXTURES / "locker/review.json")
        self.assertEqual(bundle.default_role, "Custodian")
        ref = wire(bundle.reference)
        candidate = deepcopy(ref)
        del candidate["sections"]["receipt"]["role"]

        def roles():
            return track_a(candidate, ref, default_role=bundle.default_role)[0]["roles"]

        self.assertEqual(track_a(candidate, ref)[0]["roles"], (0, 2, 2))
        self.assertEqual(roles(), (2, 0, 0))
        marks = page_marks(FormSpec.model_validate(candidate), bundle.page,
                           default_role=bundle.default_role)
        self.assertEqual([(m.label, m.source_id) for m in marks if m.layer == "roles"],
                         [("Custodian", None), ("Custodian", None)])

        candidate["sections"]["receipt"]["role"] = "Reviewer"
        self.assertEqual(roles(), (0, 2, 2))
        candidate["fields"]["locker"]["role"] = "Custodian"
        self.assertEqual(roles(), (1, 1, 1))

    def test_legacy_inline_case_and_invalid_reference(self):
        empty = dict(schemaVersion="pilot-1", fields={}, regions={}, rules=[],
                     sections={}, evidence={}, validations=[])
        manifest = dict(reference="ref.json", image="page.png", page=1, page_size=[100, 200],
                        track_b=[dict(title="Empty", scenario="No entries", expected={}, submitted={})])
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "ref.json").write_text(json.dumps(empty))
            path = root / "review.json"
            path.write_text(json.dumps(manifest))
            self.assertEqual(load_review(path).track_b[0].scenario, "No entries")
            manifest["track_b"][0]["expected"] = {"unknown": {"status": "missing"}}
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "unknown"):
                load_review(path)

    def test_matching_disjoint_and_competing_fields(self):
        keys = range(40)
        self.assertEqual(matching(keys, keys, lambda p, r: p == r), {i: i for i in keys})
        weights = [[3, 2], [2, 0]]
        self.assertEqual(matching(range(2), range(2), lambda p, r: weights[p][r]), {0: 1, 1: 0})

    def test_pooling(self):
        self.assertEqual(pool_a([]), {})
        self.assertEqual(pool_a([{"rules": (1, 0, 1)}, {"rules": (0, 2, 0)}]),
                         {"rules": (1, 2, 1)})
