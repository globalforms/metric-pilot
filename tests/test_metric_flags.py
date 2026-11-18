"""The error flags describe measured outcomes and preserve their JSON keys."""

import json
from pathlib import Path
from unittest import TestCase

from globalforms.completions import answer_marks
from globalforms.fixtures import load_review
from globalforms.metrics import TrackAFlag, TrackBFlag, track_a, track_a_flags, track_b, track_b_flags


INCIDENT = Path(__file__).resolve().parents[1] / "fixtures/incident/review.json"


class MetricFlagTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = load_review(INCIDENT)
        cls.gold = cls.review.reference.model_dump(exclude_unset=True)

    def test_recovery_flags_include_alignment_and_diagnostic_errors(self):
        exact = track_a_flags(*track_a(self.gold, self.gold))
        self.assertEqual(set(exact), set(TrackAFlag))
        self.assertFalse(any(exact.values()))
        for case in self.review.track_a:
            flags = track_a_flags(*track_a(case.spec.model_dump(exclude_unset=True), self.gold,
                                          default_role=self.review.default_role))
            self.assertTrue(flags[TrackAFlag(case.layer)])
            if case.layer == "fields":
                active = {flag for flag, present in flags.items() if present}
                self.assertEqual(active, {TrackAFlag.JOINT_FIELDS, TrackAFlag.OPTION_OWNERSHIP})
                self.assertIs(json.loads(json.dumps(flags))["option ownership"], True)
            if case.layer == "geometry":
                self.assertTrue(flags[TrackAFlag.SECTIONS])
                self.assertTrue(flags[TrackAFlag.REQUIREDNESS])

    def test_completion_flags_match_all_five_matrix_columns(self):
        observed = []
        for case in self.review.track_b:
            spec = case.spec or self.review.reference
            recovered = case.spec.model_dump(exclude_unset=True) if case.spec is not None else None
            scores = track_b(case.submitted, case.expected, self.gold, recovered)
            drawn, _ = answer_marks(spec, case.submitted)
            flags = track_b_flags(scores, drawable_field_ids=(mark.field_id for mark in drawn))
            self.assertEqual(set(flags), set(TrackBFlag))
            self.assertTrue(all(isinstance(flag, TrackBFlag) for flag in flags))
            observed.append({flag for flag, present in flags.items() if present})
        f = TrackBFlag
        self.assertEqual(observed, [
            {f.OMITTED_EXPECTED_FIELD},
            {f.OMITTED_EXPECTED_FIELD, f.OMITTED_SUPPLIED_ANSWER, f.ANY_SCORING_ERROR},
            {f.INACTIVE_ENTRY, f.ANY_SCORING_ERROR},
            {f.UNKNOWN_ENTRY, f.DRAWABLE_UNKNOWN_ENTRY, f.ANY_SCORING_ERROR},
            {f.UNKNOWN_ENTRY, f.ANY_SCORING_ERROR},
        ])

    def test_wrong_value_still_sets_case_failure(self):
        case = self.review.track_b[1]
        submitted = dict(case.expected)
        submitted["name"] = {"value": "Someone else"}
        flags = track_b_flags(track_b(submitted, case.expected, self.gold), drawable_field_ids=())
        self.assertEqual([f for f in flags if flags[f]], [TrackBFlag.ANY_SCORING_ERROR])
