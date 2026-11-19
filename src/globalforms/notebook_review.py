"""Display and export scored review cases in Jupyter. Requires the notebook extra."""

import json
import re
from html import escape
from pathlib import Path
from textwrap import fill

import matplotlib.pyplot as plt
from IPython.display import HTML, Markdown, display

from .completions import answer_marks, compare_completions
from .metrics import SCORER_VERSION, TrackAFlag, f1, track_a, track_a_flags, track_b, track_b_flags
from .metrics.alignment import align, region_iou
from .metrics.track_a import choice_condition
from .overlays import compare_layer, draw_layer, draw_region_pair, page_axes, page_marks
from .spec_view import formspec_html
from .validations import describe


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def show_spec_changes(reference_spec, predicted_spec):
    comparison = formspec_html(reference_spec, predicted_spec, changed_only=True)
    display(HTML(f"<details><summary>Compare changed FormSpec entries</summary>{comparison}</details>"))


def show_flag_matrix(flag_type, cases, *, accuracy=()):
    if not cases:
        return
    titles = [title.replace("|", "&#124;") for title, _ in cases]
    rows = [["Flag", *titles], ["---"] * (len(titles) + 1)]
    for flag in flag_type:
        rows.append([flag.label, *(str(int(flags[flag])) for _, flags in cases)])
    if accuracy:
        rows.append(["Answer accuracy", *accuracy])
    display(Markdown("\n".join("| " + " | ".join(row) + " |" for row in rows)))


def show_reference_page(review, paper, page_size):
    """Overlay the reference rules or answer regions on the selected page."""
    gold_marks = page_marks(review.reference, review.page, default_role=review.default_role)
    _, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    page_axes(ax, page_size, image=paper, crop=review.crop)
    layer = "rules" if any(mark.layer == "rules" for mark in gold_marks) else "geometry"
    draw_layer(ax, gold_marks, layer)
    ax.set_title("Conditional rules" if layer == "rules" else "Answer regions", loc="left")
    plt.show()


def show_constraints(review):
    """Show the evidence and probe results for document constraints."""
    review_spec = review.reference

    def cell(value):
        return "<td>" + escape(value) + "</td>"

    header = ["Field", "Constraint", "Evidence", *review.validation_probes]
    rows = []
    for field_id, field in review_spec.fields.items():
        rules = [rule for rule in review_spec.validations if field_id in rule.fields]
        checks = ", ".join(describe(rule) for rule in rules) or "None"
        citations = ", ".join(dict.fromkeys(key for rule in rules for key in rule.evidenceIds))
        outcomes = ["Fail" if review_spec.failed_validations(field_id, value) else "Pass"
                    for value in review.validation_probes]
        rows.append("<tr>" + "".join(map(cell, [field.label, checks, citations, *outcomes])) + "</tr>")
    display(HTML("<table><thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in header)
                 + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"))


def show_rule_effects(spec):
    """Explain the effect of each reference rule for every controller answer."""
    reference = spec.model_dump()
    outcomes = {
        "applicable": {True: "active", False: "inactive", None: "unresolved"},
        "required": {True: "required when active", False: "no requirement from this rule", None: "unresolved"},
    }
    for rule in reference["rules"]:
        controller = reference["fields"][rule["controller"]]
        effect = rule.get("effect", "applicable")
        targets = [reference["fields"][key]["label"] for key in rule.get("fields", ())]
        targets.extend(reference["sections"][key]["title"] for key in rule.get("sections", ()))
        print(f"{controller['label']} → {', '.join(targets)} ({effect})")
        for answer in [*controller["options"], None]:
            print(f"  {answer if answer is not None else 'Unanswered'} → {outcomes[effect][choice_condition(rule, answer)]}")
    if not reference["rules"]:
        print("The reference declares no conditional rules.")


def format_score(label, counts):
    value = f1(counts)
    return f"{label} {value:.1%}" if value is not None else f"{label} —"


def show_model_results(candidate, reference, page, scores, diagnostics, default_role):
    pairs, _ = align(candidate, reference)
    box_rows = ["| Reference region | Reference box | Predicted box | IoU |", "|---|---|---|---:|"]
    for pred_id, ref_id in pairs.items():
        pred = candidate["regions"][pred_id]
        ref = reference["regions"][ref_id]
        if ref["page"] == page:
            boxes = [" · ".join(f"{v:g}" for v in region["bbox"]) for region in (ref, pred)]
            box_rows.append(f"| `{ref_id}` | {boxes[0]} | {boxes[1]} | {region_iou(pred, ref):.1%} |")
    display(Markdown(f"**Matched boxes on page {page}**  \nPDF points in x, y, width, height order.\n\n" +
                     "\n".join(box_rows)))

    score_rows = ["| Track A | Component | TP | FP | FN | F1 |", "|---|---|---:|---:|---:|---:|"]
    for group, counts in (("Ranked", scores), ("Diagnostic", diagnostics)):
        for key, (tp, fp, fn) in counts.items():
            score = f1((tp, fp, fn))
            value = f"{score:.1%}" if score is not None else "No support"
            score_rows.append(f"| {group} | {TrackAFlag(key).label} | {tp} | {fp} | {fn} | {value} |")
    display(Markdown("\n".join(score_rows)))
    if default_role is not None:
        without_default = track_a(candidate, reference)[0]["roles"]
        print(format_score("Role F1 without a default", without_default), " · ",
              format_score(f"with {default_role} as default", scores["roles"]))


def show_track_a(review, paper, page_size, plot_dir):
    """Score, display and export each recovery case. Return the flags for the error matrix."""
    review_spec = review.reference
    reference = review_spec.model_dump(exclude_unset=True)
    page, default_role = review.page, review.default_role
    gold_marks = page_marks(review_spec, page, default_role=default_role)
    plot_dir.mkdir(parents=True, exist_ok=True)
    write_json(plot_dir / "ground-truth.json", reference)
    recovery_flags = []
    for index, case in enumerate(review.track_a, start=1):
        layer = case.layer
        prediction = case.spec
        candidate = prediction.model_dump(exclude_unset=True)
        predicted = page_marks(prediction, page, default_role=default_role)
        figure = compare_layer(gold_marks, predicted, layer, page_size, image=paper, crop=review.crop)
        if case.model:
            display(Markdown(f"### {case.title or case.model}"))
            draw_layer(figure.axes[1], gold_marks, "geometry", color="#256281", linestyle="--")
            figure.axes[1].set_title("Prediction · dashed outlines show reference boxes", loc="left",
                                     fontsize=11, color="#ae4935")
        if case.inspect_regions:
            ref_region, pred_region = case.inspect_regions
            original = next(m for m in gold_marks if m.region_id == ref_region and m.layer == layer)
            shifted = next(m for m in predicted if m.region_id == pred_region and m.layer == layer)
            ref_ioa, pred_ioa = draw_region_pair(figure.axes[1], original, shifted)
            figure.axes[1].set_xlabel(f"Coverage: reference {ref_ioa:.0%}, prediction {pred_ioa:.0%}")
            print(f"Region coverage: reference {ref_ioa:.0%}, prediction {pred_ioa:.0%}")
        scores, diagnostics = track_a(candidate, reference, default_role=default_role)
        tp, fp, fn = (scores | diagnostics)[layer]
        title = case.title or layer.title()
        flags = track_a_flags(scores, diagnostics)
        recovery_flags.append((title, flags))
        figure.suptitle(f"{title}   ·   {tp} TP, {fp} FP, {fn} FN ({TrackAFlag(layer).label})")

        ranked = "   ·   ".join(format_score(TrackAFlag(key).label, counts) for key, counts in scores.items())
        diagnostic = "   ·   ".join(format_score(flag.label, diagnostics[flag])
                                  for flag in (TrackAFlag.REQUIREDNESS, TrackAFlag.VALIDATION))
        caption = fill(case.explanation, width=108)
        role_note = f"Default role: {default_role}" if default_role is not None else "No default role"
        figure.supxlabel(f"{caption}\n\nRanked F1    {ranked}\nDiagnostic F1    {diagnostic}   ·   {role_note}", fontsize=10)
        stem = f"{index:02d}-{layer}"
        figure.savefig(plot_dir / f"{stem}.png", dpi=160, facecolor="white", bbox_inches="tight")
        write_json(plot_dir / f"{stem}.predicted.json", candidate)
        report = {"scorer_version": SCORER_VERSION, "default_role": default_role,
                  "components": scores, "diagnostics": diagnostics, "flags": flags}
        if case.model:
            report["model"] = case.model
        write_json(plot_dir / f"{stem}.scores.json", report)
        plt.show()
        if case.model:
            show_model_results(candidate, reference, page, scores, diagnostics, default_role)
        show_spec_changes(review_spec, prediction)
    return recovery_flags


def show_track_b(review, paper, page_size, completion_dir):
    """Grade, display and export each completion. Return flags and answer accuracies."""
    review_spec = review.reference
    reference = review_spec.model_dump(exclude_unset=True)
    page = review.page
    completion_dir.mkdir(parents=True, exist_ok=True)
    write_json(completion_dir / "ground-truth.json", reference)
    completion_flags = []
    answer_accuracies = []
    for index, case in enumerate(review.track_b, start=1):
        title, story, explanation = case.title, case.scenario, case.explanation
        expected, submitted = case.expected, case.submitted
        predicted_spec = case.spec or review_spec
        spec_data = predicted_spec.model_dump(exclude_unset=True)
        recovered = spec_data if case.spec is not None else None
        result = track_b(submitted, expected, reference, recovered)
        drawn, _ = answer_marks(predicted_spec, submitted)
        flags = track_b_flags(result, drawable_field_ids=(mark.field_id for mark in drawn))
        completion_flags.append((title, flags))
        figure = compare_completions(review_spec, expected, predicted_spec, submitted, page=page,
                                     page_size=page_size, image=paper, crop=review.completion_crop or review.crop)
        correct, denominator = result["value"]
        answer_accuracies.append(f"{correct}/{denominator}")
        extras = result["inactive"][0] + result["unmatched"]
        outcome = "Pass" if result["complete"][0] else "Fail"
        accuracy = f"{correct / denominator:.1%}" if denominator else "—"
        figure.suptitle(f"{title} · {outcome} · Answer accuracy {accuracy}\n{fill(story, width=100)}", fontsize=12)
        diagnostics = []
        for key, label in (("coverage", "Coverage"), ("activity", "Active-field accuracy"),
                           ("inactive", "Inactive-entry rate")):
            hits, total = result[key]
            ratio = f"{hits}/{total}" if total else "— (0 eligible)"
            diagnostics.append(f"{label} {ratio}")
        diagnostics.append(f"Unmatched entries {result['unmatched']}")
        formula = f"{correct} correct / ({len(expected)} expected + {extras} extra)"
        figure.supxlabel("\n".join([fill(explanation, width=105), formula, "   ·   ".join(diagnostics)]), fontsize=10)
        stem = f"{index:02d}-" + re.sub(r"[^\w-]+", "-", title.casefold()).strip("-")
        figure.savefig(completion_dir / f"{stem}.png", dpi=160, facecolor="white", bbox_inches="tight")
        write_json(completion_dir / f"{stem}.predicted.json", spec_data)
        report = {
            "scorer_version": SCORER_VERSION,
            "title": title,
            "scenario": story,
            "explanation": explanation,
            "mode": "B-end-to-end" if recovered is not None else "B-oracle",
            "expected": expected,
            "submitted": submitted,
            "scores": result,
            "flags": flags,
        }
        write_json(completion_dir / f"{stem}.case.json", report)
        plt.show()
        if case.spec is not None:
            show_spec_changes(review_spec, case.spec)
    return completion_flags, answer_accuracies
