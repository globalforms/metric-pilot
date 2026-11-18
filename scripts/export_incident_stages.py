"""Recreate the five historical synthetic PDFs and specs in globalforms-fixtures/."""

import json
from pathlib import Path


def main():
    fixture = Path(__file__).resolve().parents[1] / "fixtures/incident"
    stages = json.loads((fixture / "regressions/stages.json").read_text())
    incident_v1 = json.loads((fixture / "reference.json").read_text())
    from reportlab.pdfgen.canvas import Canvas

    folder = Path("globalforms-fixtures")
    folder.mkdir(exist_ok=True)
    for i, spec in enumerate(stages, 1):
        path = folder / f"stage-{i}.pdf"
        pdf = Canvas(str(path), pagesize=(612, 792))
        pdf.setTitle("Synthetic review form")
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawString(48, 760, "Synthetic review form")
        pdf.setFont("Helvetica-Bold", 11)
        for section in spec["sections"].values():
            x, y, _, _ = spec["evidence"][section["evidenceIds"][0]]["bbox"]
            pdf.drawString(x, 792 - y - 12, section["title"])
        pdf.setFont("Helvetica", 10)
        for field in spec["fields"].values():
            x, y, _, _ = spec["evidence"][field["evidenceIds"][0]]["bbox"]
            pdf.drawString(x, 792 - y - 12, field["label"])
            for region in field["regions"]:
                x, y, w, h = spec["regions"][region]["bbox"]
                pdf.rect(x, 792 - y - h, w, h)
            for option, region in field["options"].items():
                x, y, w, _ = spec["regions"][region]["bbox"]
                pdf.drawString(x+w+4, 792-y-12, option)
        pdf.save()
        (folder / f"stage-{i}.json").write_text(json.dumps(spec, indent=2))
        print(path)
    (folder / "stage-5-pilot-1.json").write_text(json.dumps(incident_v1, indent=2))


if __name__ == "__main__":
    main()
