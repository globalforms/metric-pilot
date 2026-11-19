"""Source-grounded validation contracts, scoring and execution."""

from copy import deepcopy
from pathlib import Path
from unittest import TestCase

from pydantic import ValidationError

from globalforms import FormSpec, PredictionFormSpec
from globalforms.fixtures import load_review
from globalforms.metrics import track_a
from globalforms.validations import Checksum, DateFormat, Length


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class ValidationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_review(FIXTURES / "length/review.json")
        cls.gold = cls.bundle.reference.model_dump(exclude_unset=True)

    def score(self, candidate):
        return track_a(candidate, self.gold)[1]["validation"]

    def test_three_visible_length_cues(self):
        reference = self.bundle.reference
        for field, expected in [
            ("plain", [True, True, True, True]),
            ("cells", [True, True, True, False]),
            ("digits", [False, False, True, False]),
        ]:
            with self.subTest(field=field):
                self.assertEqual([not reference.failed_validations(field, value)
                                  for value in self.bundle.validation_probes], expected)
        self.assertTrue(reference.failed_validations("digits", "１２３４５６"))
        self.assertEqual(self.score(self.bundle.track_a[0].spec.model_dump(exclude_unset=True)), (2, 1, 2))

    def test_parameter_identity_grouping_and_field_alignment(self):
        equivalent = deepcopy(self.gold)
        bounded, exact, digits = equivalent["validations"]
        # Same upper bound across two fields; lower bound and alphabet are independent claims.
        bounded["fields"].append("digits")
        del exact["max"]
        equivalent["fields"]["other_id"] = equivalent["fields"].pop("digits")
        for rule in equivalent["validations"]:
            rule["fields"] = ["other_id" if key == "digits" else key for key in rule["fields"]]
        self.assertEqual(self.score(equivalent), (4, 0, 0))
        exact["min"] = 5
        self.assertEqual(self.score(equivalent), (3, 1, 1))

    def test_formats_and_checksum_use_supplied_parameters(self):
        date = load_review(FIXTURES / "incident/review.json").reference
        self.assertFalse(date.failed_validations("review_date", "2024-02-29"))
        for invalid in ("2024-2-29", "2023-02-29", "29/02/2024"):
            self.assertTrue(date.failed_validations("review_date", invalid))
        args = dict(kind="date_format", fields=["date"], evidenceIds=["printed"])
        for mask, result in [("DD/MM/YYYY", True), ("MM/DD/YYYY", False)]:
            self.assertEqual(DateFormat(**args, format=mask).accepts("29/02/2024"), result)
        gold = deepcopy(self.gold)
        rule = dict(kind="checksum", algorithm="decimal_mod_97", remainder=1,
                    fields=["plain"], evidenceIds=["plain_label"])
        gold["validations"] = [rule]
        spec = PredictionFormSpec.model_validate(gold)
        self.assertFalse(spec.failed_validations("plain", "00098"))
        for invalid in ("97", "", "+98", "98A", "９８"):
            self.assertTrue(spec.failed_validations("plain", invalid))
        prediction = deepcopy(gold)
        prediction["validations"][0]["remainder"] = 0
        self.assertEqual(track_a(prediction, gold)[1]["validation"], (0, 1, 1))

    def test_version_evidence_and_parameter_boundaries(self):
        old = deepcopy(self.gold)
        old["schemaVersion"] = "pilot-1"
        with self.assertRaises(ValidationError):
            FormSpec.model_validate(old)
        schema = PredictionFormSpec.model_json_schema()
        kinds = schema["properties"]["validations"]["items"]["discriminator"]["mapping"]
        self.assertEqual(set(kinds), {"date_format", "length", "character_set", "checksum"})
        for data in ({}, {"min": 7, "max": 6}, {"max": -1}, {"min": True}):
            with self.assertRaises(ValidationError):
                Length(kind="length", fields=["cells"], evidenceIds=["six_cells"], **data)
        for algorithm, remainder in [("decimal_mod_97", 97), ("unknown", 0)]:
            with self.assertRaises(ValidationError):
                Checksum(kind="checksum", algorithm=algorithm, remainder=remainder,
                         fields=["cells"], evidenceIds=["six_cells"])
        for ids in ([], ["absent"]):
            candidate = deepcopy(self.gold)
            candidate["validations"][0]["evidenceIds"] = ids
            with self.assertRaises(ValidationError):
                FormSpec.model_validate(candidate)
