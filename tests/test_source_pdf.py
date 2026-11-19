"""The opt-in issuer download must preserve the pinned original and leave other files intact."""

from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from globalforms.source_pdf import AETNA_PDF_URL, cached_pdf_path, fetch_aetna_pdf


class SourcePdfTests(TestCase):
    def test_env_and_dotenv_override_the_platform_cache(self):
        digest = "a" * 64
        suffix = Path("pdfs") / digest / "source.pdf"
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            previous = Path.cwd()
            os.chdir(directory)
            try:
                with patch("globalforms.source_pdf.user_cache_path", return_value=Path(directory) / "os"):
                    self.assertEqual(cached_pdf_path(digest), Path(directory) / "os" / suffix)
                Path(".env").write_text("GLOBALFORMS_CACHE_DIR='from dotenv'\n")
                self.assertEqual(cached_pdf_path(digest), Path(directory) / "from dotenv" / suffix)
                os.environ["GLOBALFORMS_CACHE_DIR"] = "from-env"
                self.assertEqual(cached_pdf_path(digest), Path(directory) / "from-env" / suffix)
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    cached_pdf_path("../other")
            finally:
                os.chdir(previous)

    def test_download_and_offline_cache_hit(self):
        data = b"%PDF-synthetic fixture bytes"
        with TemporaryDirectory() as directory, patch("globalforms.source_pdf.AETNA_PDF_SHA256", sha256(data).hexdigest()):
            target = Path(directory) / "private/source.pdf"
            with patch("globalforms.source_pdf.urlopen", return_value=BytesIO(data)) as fetch:
                self.assertEqual(fetch_aetna_pdf(target), target)
                self.assertEqual(fetch_aetna_pdf(target), target)
                fetch.assert_called_once_with(AETNA_PDF_URL, timeout=30)
            self.assertEqual(target.read_bytes(), data)
            self.assertEqual(list(target.parent.iterdir()), [target])

    def test_changed_remote_or_local_file_is_rejected(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "source.pdf"
            with patch("globalforms.source_pdf.urlopen", return_value=BytesIO(b"unexpected content")) as fetch:
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    fetch_aetna_pdf(target)
                self.assertFalse(target.exists())
                target.write_bytes(b"existing file")
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    fetch_aetna_pdf(target)
                self.assertEqual(target.read_bytes(), b"existing file")
                fetch.assert_called_once()
