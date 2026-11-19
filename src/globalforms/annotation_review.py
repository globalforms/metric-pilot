"""Private review of native draft annotations paired with a reason-aware omission case."""

import base64
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from html import escape
from pathlib import Path
from urllib.parse import quote

from .fixtures import load_review, pdf_page_png
from .source_pdf import cached_pdf_path


CATEGORIES = {
    "value": ("Expected value", "#15724c"),
    "status": ("Input status", "#1259a0"),
    "inactive": ("Inactive", "#596274"),
    "optional_omission": ("Optional omission", "#aa4b09"),
    "unoccupied": ("Unoccupied slot", "#804491"),
    "human_action": ("Pending human action", "#a32f4c"),
    "unassessed": ("Outside assessed inventory", "#525252"),
}


@dataclass
class OmissionAnnotation:
    pdf: Path
    annotation: dict
    case: dict
    scenario: str
    results: dict


def load_notebook_fixture(path: Path):
    """Load a standard metric bundle or an explicitly selected native annotation case."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "omission-annotation":
        return load_review(path)
    if manifest.get("version") != 1:
        raise ValueError("Unsupported annotation review manifest version")
    folder = path.parent
    native_bytes = (folder / manifest["annotation"]).read_bytes()
    native = json.loads(native_bytes)
    case = json.loads((folder / manifest["case"]).read_bytes())
    pdf = folder / manifest["pdf"] if manifest.get("pdf") else None
    if pdf is None or not pdf.exists():
        pdf = cached_pdf_path(case["sourcePdfSha256"])
        if not pdf.is_file():
            raise FileNotFoundError(f"Supply the original PDF in the manifest or populate the source cache at {pdf}")
    doc = native["document"]
    if (sha256(pdf.read_bytes()).hexdigest() != case["sourcePdfSha256"]
            or doc["source"]["sha256"] != case["sourcePdfSha256"]
            or sha256(native_bytes).hexdigest() != case["candidateAnnotationSha256"]
            or doc["id"] != case["documentId"]):
        raise ValueError("PDF, annotation and case identities must match")
    if (native["schemaVersion"] != "0.1.0-draft.1"
            or doc["coordinateFrame"] != "pdf_points_top_left_unrotated_crop_relative"
            or any(page["rotation"] != 0 for page in doc["pages"])):
        raise ValueError("Unsupported annotation version or page coordinate frame")
    expected, omissions = case["expected"], case["omissions"]
    assessed = expected.keys() | omissions.keys()
    if (expected.keys() & omissions.keys() or len(assessed) != case["assessedFieldCount"]
            or assessed - {field["id"] for field in native["fields"]}):
        raise ValueError("The case inventory must resolve to distinct native field IDs")
    return OmissionAnnotation(pdf, native, case,
                              (folder / manifest["scenario"]).read_text(encoding="utf-8"),
                              json.loads((folder / manifest["results"]).read_bytes()))


def notebook_report_url(path: Path) -> str:
    """Address a local HTML report through a Jupyter server serving this directory."""
    from jupyter_server.serverapp import list_running_servers

    absolute = path.resolve()
    for server in sorted(list_running_servers(), key=lambda item: len(item["root_dir"]), reverse=True):
        root = Path(server["root_dir"]).resolve()
        if absolute.is_relative_to(root):
            relative = quote(absolute.relative_to(root).as_posix())
            return f'{server["base_url"].rstrip("/")}/files/{relative}'
    return quote(path.as_posix())


def _outcome(case, key):
    if key in case["expected"]:
        kind, value = next(iter(case["expected"][key].items()))
        return kind, str(value)
    if key in case["omissions"]:
        item = case["omissions"][key]
        return item["reason"], item["rationale"]
    return "unassessed", "Outside this case’s assessed inventory."


def _recorded_scores(results):
    rows = []
    for name, record in results.items():
        old, revised = record["flattened_baseline"], record["reason_aware"]

        def ratio(count):
            return f'{count["numerator"]}/{count["denominator"]}' if count["denominator"] else "— (0 eligible)"

        extras = [f"{CATEGORIES[key][0]} ({count})"
                  for key, count in revised["unexpected_entries_by_omission_reason"].items() if count]
        cells = [name.replace("_", " "), ratio(revised["normalized_value_accuracy"]),
                 ratio(revised["expected_answer_coverage"]), ratio(old["inactive_entry_rate"]),
                 ratio(revised["inactive_entry_rate"]), ratio(revised["active_field_accuracy"]),
                 ", ".join(extras) or "—", "Pass" if revised["complete_form_success"] else "Fail"]
        rows.append("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in cells) + "</tr>")
    headings = ["Probe", "Value accuracy", "Coverage", "Inactive (flattened)", "Inactive (reason-aware)",
                "Active-field accuracy", "Unexpected entries", "Complete draft"]
    return ("<table><thead><tr>" + "".join(f"<th>{h}</th>" for h in headings)
            + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def write_annotation_review(review: OmissionAnnotation, destination: Path):
    """Write a standalone HTML review. Rectangles link the source page to its case ledger."""
    native, case = review.annotation, review.case
    regions = {region["id"]: region for region in native["regions"]}
    pages = {page["number"]: page for page in native["document"]["pages"]}
    evidence = {item["id"]: item for item in native["evidence"]}
    counts = Counter()
    boxes = defaultdict(list)
    ledger = []
    for field in native["fields"]:
        key = field["id"]
        kind, answer = _outcome(case, key)
        category, color = CATEGORIES[kind]
        counts[kind] += 1
        anchors = [(rid, None) for rid in field.get("regionIds", [])]
        for option in field.get("options", []):
            anchors.extend((rid, option) for rid in option.get("regionIds", []))
        links = []
        for rid, option in anchors:
            region = regions[rid]
            page = pages[region["page"]]
            x, y, width, height = region["bbox"]
            style = (f'left:{100*x/page["width"]:.5f}%;top:{100*y/page["height"]:.5f}%;'
                     f'width:{100*width/page["width"]:.5f}%;height:{100*height/page["height"]:.5f}%;'
                     f'--ink:{color}')
            unselected = option and kind == "value" and option["id"] != answer
            label = field["label"] + (f' · {option["label"]}' if option else "")
            hint = escape(f"{key} · {label} · {category} · {answer}")
            boxes[region["page"]].append(
                f'<a class="box{" unselected" if unselected else ""}" id="region-{escape(rid)}" '
                f'href="#field-{escape(key)}" style="{style}" title="{hint}" aria-label="{hint}"></a>'
            )
            link = f'Page {page["number"]}' + (f' · {option["label"]}' if option else "")
            links.append(f'<a href="#region-{escape(rid)}">{escape(link)}</a>')
        evidence_refs = (f'{eid} · {evidence[eid].get("quote", "")}' for eid in field["evidenceIds"])
        ledger.append(f'<article id="field-{escape(key)}"><strong>{escape(field["label"])}</strong> '
                      f'<code>{escape(key)}</code><p class="category" style="color:{color}">{category}</p>'
                      f'<p>{escape(answer)}</p><small>{escape(" / ".join(evidence_refs))}</small>'
                      f'<p>{" · ".join(links)}</p></article>')
    rendered_pages = []
    for number, page in pages.items():
        image, _ = pdf_page_png(review.pdf, number, (page["width"], page["height"]))
        encoded = base64.b64encode(image).decode("ascii")
        rendered_pages.append(f'<h3 id="page-{number}">Page {number} · {len(boxes[number])} answer regions</h3>'
                              f'<div class="page"><img alt="Source page {number}" src="data:image/png;base64,{encoded}">'
                              + "".join(boxes[number]) + "</div>")
    legend = "".join(f'<li style="--ink:{color}">{label} ({counts[kind]})</li>'
                     for kind, (label, color) in CATEGORIES.items() if counts[kind])
    scenario = "".join(f"<p>{escape(paragraph).replace('**', '')}</p>"
                       for paragraph in review.scenario.split("\n\n") if paragraph and not paragraph.startswith("# "))
    issues = "".join(f'<li>{escape(item["description"])}</li>' for item in native["unresolvedIssues"])
    doc_id = escape(case["documentId"])
    style = """
    * {box-sizing:border-box} html {font:16px/1.5 system-ui,sans-serif;color:#182638;background:#f7f9fb}
    body {max-width:1500px;margin:auto;padding:1.4rem 3vw} h1,h2,h3,p {margin:.5rem 0} h2 {margin-top:1.3rem}
    a {color:#185e8e} code,small {color:#475668} summary {cursor:pointer;font-weight:650}
    .legend {display:flex;flex-wrap:wrap;gap:1rem;padding:0;list-style:none}
    .legend li {border-left:5px solid var(--ink);padding-left:.4rem}
    .review {display:grid;grid-template-columns:minmax(0,1.6fr) minmax(18rem,1fr);gap:1rem}
    .pages,.ledger {height:79vh;overflow:auto;padding:.55rem 1rem;background:white;border:1px solid #d4dce2}
    .page {position:relative}.page img {width:100%;height:auto;display:block}
    .box {position:absolute;background:color-mix(in srgb,var(--ink) 25%,transparent);border:1.5px solid var(--ink)}
    .box.unselected {background:transparent;border-style:dashed}
    .box:focus,.box:target,.box:hover {outline:3px solid #101b28;z-index:1}
    article {border-bottom:1px solid #dce1e5;padding:.7rem .4rem;scroll-margin-top:.5rem}
    article:target {background:#fff2bf} .category {font-weight:650} table {border-collapse:collapse;background:white}
    th,td {text-align:left;padding:.4rem .6rem;border-bottom:1px solid #d4dce2}.scores {overflow:auto}
    @media(max-width:720px) {.review {display:block}.pages {height:60vh}.ledger {height:48vh}}
    """
    navigation = " · ".join(f'<a href="#page-{n}">Page {n}</a>' for n in pages)
    title = f"{doc_id} · Omission annotation"
    info = (f'{escape(native["state"].title())} annotation · revision {native["revision"]} · '
            f'{len(native["reviews"])} recorded reviews · {case["assessedFieldCount"]} assessed fields')
    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><title>{title}</title><style>{style}</style></head>'
            f'<body><h1>{title}</h1><p>{info}</p><details><summary>Fictional scenario</summary>{scenario}</details>'
            f'<ul class="legend">{legend}</ul><p>Select a box for its field, expected entry or reason for omission. '
            'Dashed boxes show the unselected alternatives of an answered choice.</p>'
            f'<nav aria-label="Source pages">{navigation}</nav><div class="review"><section class="pages">{"".join(rendered_pages)}</section>'
            f'<section class="ledger"><h2>Field ledger</h2>{"".join(ledger)}</section></div>'
            '<h2>Recorded omission-pilot scores</h2><p>The original pilot grades aligned fictional probes. '
            'The two inactive columns show how its denominator changes when omission reasons are retained.</p>'
            f'<div class="scores">{_recorded_scores(review.results)}</div>'
            f'<details><summary>Unresolved annotation issues ({len(native["unresolvedIssues"])})</summary>'
            f'<ul>{issues}</ul></details></body></html>')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return destination
