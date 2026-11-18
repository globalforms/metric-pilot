"""Pilot scenario completion metrics."""

from datetime import date

from .alignment import align, normalize


def valid_entry(entry):
    if not isinstance(entry, dict) or len(entry) != 1:
        return False
    if "status" in entry:
        return entry["status"] in ("missing", "conflicting", "invalid")
    return "value" in entry and type(entry["value"]) in (str, int, float, bool) and (
        not isinstance(entry["value"], str) or bool(entry["value"].strip())
    )


def same_answer(pred, ref, field):
    if not valid_entry(pred) or pred.keys() != ref.keys():
        return False
    if "status" in ref:
        return pred["status"] == ref["status"]
    a, b = pred["value"], ref["value"]
    if field["type"] == "date":
        try:
            return date.fromisoformat(a) == date.fromisoformat(b)
        except (TypeError, ValueError):
            return False
    if field["options"]:
        return a == b
    return normalize(a) == normalize(b)


def track_b(output, expected, ref, recovered=None):
    """Grade one case. Omit recovered for oracle mode; otherwise align by grounding."""
    bound = {k: k for k in ref["fields"]} if recovered is None else align(recovered, ref)[1]
    submitted = {bound[k]: v for k, v in output.items() if k in bound}
    unmatched_ids = [key for key in output if key not in bound]
    unmatched = len(unmatched_ids)
    omissions = expected.keys() - submitted.keys()
    inactive = set(ref["fields"]) - expected.keys()
    # Only an absent key can stand in for the reference's missing status.
    accepted_omissions = {k for k, answer in expected.items()
                          if k not in submitted and answer == {"status": "missing"}}
    correct = accepted_omissions | {
        k for k, answer in expected.items()
        if same_answer(submitted.get(k), answer, ref["fields"][k])
    }
    covered = sum(valid_entry(submitted.get(k)) for k in expected)
    inactive_written = len(inactive & submitted.keys())
    extra_entries = inactive_written + unmatched
    success = len(correct) == len(expected) and extra_entries == 0
    return dict(value=(len(correct), len(expected) + extra_entries),
                coverage=(covered, len(expected)),
                inactive=(inactive_written, len(inactive)),
                activity=(covered + len(accepted_omissions) + len(inactive) - inactive_written,
                          len(ref["fields"])),
                complete=(int(success), 1), unmatched=unmatched,
                unmatched_ids=unmatched_ids, omitted_expected=len(omissions),
                omitted_supplied=sum("value" in expected[key] for key in omissions))


def paired_pass(outputs, references, targets):
    """Check exact recorded outputs on the specified fields in each paired scenario."""
    return all(all(output.get(k) == reference.get(k) for k in targets)
               for output, reference in zip(outputs, references, strict=True))
