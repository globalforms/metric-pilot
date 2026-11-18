"""A display must preserve literal wire values even when the inputs contain markup."""

import json
from pathlib import Path
from unittest import TestCase
from xml.etree.ElementTree import fromstring

from globalforms.fixtures import load_review
from globalforms.spec_view import formspec_html


def table_rows(html):
    rows = fromstring(html).findall("tbody/tr")
    return {row.findtext("th/code"): [json.loads("".join(pre.itertext())) for pre in row.findall("td/pre")]
            for row in rows if row.find("th") is not None}


class FormSpecViewTests(TestCase):
    def setUp(self):
        manifest = Path(__file__).resolve().parents[1] / "fixtures/locker/review.json"
        review = load_review(manifest)
        self.reference = review.reference
        self.prediction = review.track_a[0].spec

    def test_notebook_view_preserves_json_and_escapes_markup(self):
        self.reference.fields["locker"].label = '<script> & "é"'
        html = self.reference._repr_html_()
        self.assertNotIn("<script>", html)
        rows = table_rows(html)
        self.assertEqual({key: values[0] for key, values in rows.items()},
                         self.reference.model_dump(mode="json", exclude_unset=True))
        self.assertIn('"role": "Custodian"', [span.text for span in fromstring(html).findall(".//pre/span")])

    def test_side_by_side_shows_exact_changed_groups(self):
        rows = table_rows(formspec_html(self.reference, self.prediction, changed_only=True))
        gold, pred = [s.model_dump(mode="json", exclude_unset=True) for s in (self.reference, self.prediction)]
        self.assertEqual(rows, {"fields": [{"locker": gold["fields"]["locker"]}, {"slot": pred["fields"]["slot"]}]})
        full = table_rows(formspec_html(self.reference, self.prediction))
        self.assertEqual(full, {k: [v, pred[k]] for k, v in gold.items()})
        self.assertIn("No serialized groups differ", formspec_html(self.reference, self.reference, changed_only=True))
