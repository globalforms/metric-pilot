"""Fetch the issuer's blank form on request and preview a local PDF in Jupyter."""

import base64
import os
import re
import subprocess
from hashlib import sha256
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

from dotenv import dotenv_values
from platformdirs import user_cache_path

from .fixtures import pdf_page_png


AETNA_PDF_URL = (
    "https://www.aetna.com/content/dam/aetna/pdfs/aetnacom/"
    "individuals-families-health-insurance/document-library/medical-claim-form-spanish.pdf"
)
AETNA_PDF_SHA256 = "4db1ae400b793177ae4a95c5af57bb4a3f88ad7bbd54490f591cdc81de19390a"


def cached_pdf_path(digest: str) -> Path:
    """Address an immutable PDF by hash in the configured per-user cache."""
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Expected a lowercase SHA-256 for the cached PDF")
    override = os.environ.get("GLOBALFORMS_CACHE_DIR") or dotenv_values(".env").get("GLOBALFORMS_CACHE_DIR")
    root = Path(override).expanduser().resolve() if override else user_cache_path("globalforms", appauthor=False)
    return root / "pdfs" / digest / "source.pdf"


def _check_pdf(data: bytes) -> None:
    if sha256(data).hexdigest() != AETNA_PDF_SHA256:
        raise ValueError("The PDF does not match the recorded SHA-256 for the Aetna source.")


def fetch_aetna_pdf(destination: Path | None = None) -> Path:
    """Fetch the hash-pinned blank PDF, or reuse a verified local copy. Leave existing files intact."""
    destination = cached_pdf_path(AETNA_PDF_SHA256) if destination is None else Path(destination)
    if destination.exists():
        _check_pdf(destination.read_bytes())
        return destination
    with urlopen(AETNA_PDF_URL, timeout=30) as response:
        data = response.read()
    _check_pdf(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = NamedTemporaryFile(dir=destination.parent, delete=False)
    pending = Path(temp.name)
    try:
        with temp:
            temp.write(data)
        try:
            os.link(pending, destination)
        except FileExistsError:
            # A concurrent fetch may have already installed the verified bytes.
            _check_pdf(destination.read_bytes())
    finally:
        pending.unlink(missing_ok=True)
    return destination


def write_pdf_preview(pdf: Path, destination: Path) -> Path:
    """Render source pages for a local review when no annotation manifest is available."""
    result = subprocess.run(["pdfinfo", str(pdf)], check=True, capture_output=True, text=True,
                            env={**os.environ, "LC_ALL": "C"})
    count = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    if count is None:
        raise ValueError(f"Cannot determine page count for {pdf}")
    pages = []
    for page in range(1, int(count[1]) + 1):
        image, _ = pdf_page_png(pdf, page)
        encoded = base64.b64encode(image).decode("ascii")
        pages.append(f'<section><h2>Page {page}</h2><img alt="Source page {page}" '
                     f'src="data:image/png;base64,{encoded}"></section>')
    title = escape(pdf.name)
    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>'
            '<style>body{max-width:64rem;margin:1rem auto;padding:0 1rem;font:1rem/1.5 system-ui}'
            'img{width:100%;height:auto}h2{font-size:1.2rem}</style></head>'
            f'<body><h1>{title}</h1><p>Blank source PDF · {len(pages)} pages</p>'
            + "".join(pages) + '</body></html>')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return destination
