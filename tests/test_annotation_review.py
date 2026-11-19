"""A native review must bind case IDs and both original file hashes before display."""

import json
import os
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from globalforms.annotation_review import OmissionAnnotation, load_notebook_fixture


class NativeReviewTests(TestCase):
    def test_case_is_bound_to_pdf_and_candidate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = b"source PDF identity"
            (root / "form.pdf").write_bytes(pdf)
            digest = sha256(pdf).hexdigest()
            candidate = {"schemaVersion": "0.1.0-draft.1", "fields": [{"id": "sign"}],
                         "document": {"id": "sample", "source": {"sha256": digest}, "pages": [],
                                      "coordinateFrame": "pdf_points_top_left_unrotated_crop_relative"}}
            native = json.dumps(candidate).encode()
            (root / "native.json").write_bytes(native)
            case = {"documentId": "sample", "sourcePdfSha256": digest,
                    "candidateAnnotationSha256": sha256(native).hexdigest(), "assessedFieldCount": 1,
                    "expected": {}, "omissions": {"sign": {"reason": "human_action", "rationale": "Awaiting signer"}}}
            case_path = root / "case.json"
            case_path.write_text(json.dumps(case))
            (root / "story.md").write_text("Draft for signature.")
            (root / "scores.json").write_text("{}")
            path = root / "review.json"
            path.write_text(json.dumps(dict(version=1, kind="omission-annotation", pdf="form.pdf",
                                            annotation="native.json", case="case.json", scenario="story.md",
                                            results="scores.json")))
            self.assertIsInstance(load_notebook_fixture(path), OmissionAnnotation)
            for source, contents in [(root / "form.pdf", pdf), (root / "native.json", native)]:
                source.write_bytes(contents + b" ")
                with self.assertRaisesRegex(ValueError, "identities"):
                    load_notebook_fixture(path)
                source.write_bytes(contents)
            with patch.dict(os.environ, {"GLOBALFORMS_CACHE_DIR": str(root / "cache")}):
                cached = root / "cache" / "pdfs" / digest / "source.pdf"
                cached.parent.mkdir(parents=True)
                (root / "form.pdf").rename(cached)
                self.assertEqual(load_notebook_fixture(path).pdf, cached)
                manifest = json.loads(path.read_bytes())
                del manifest["pdf"]
                path.write_text(json.dumps(manifest))
                self.assertEqual(load_notebook_fixture(path).pdf, cached)
                cached.rename(root / "form.pdf")
                manifest["pdf"] = "form.pdf"
                path.write_text(json.dumps(manifest))
            case["expected"] = {"sign": {"status": "missing"}}
            case_path.write_text(json.dumps(case))
            with self.assertRaisesRegex(ValueError, "inventory"):
                load_notebook_fixture(path)
