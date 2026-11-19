"""Historical notebook regressions on the fixed incident and Appendix A examples."""

import json
from copy import deepcopy
from pathlib import Path
from unittest import TestCase

from globalforms import FormSpec
from globalforms.metrics import paired_pass, pool_a, track_a, track_b
from globalforms.metrics.track_a import choice_condition, in_section


INCIDENT = Path(__file__).resolve().parents[1] / "fixtures" / "incident"


def value(v):
    return {"value": v}


def status(s):
    return {"status": s}


def field_obligation(spec, key, facts):
    """Evaluate the pilot's single choice predicate per target and effect."""
    effects = {}
    for rule in spec["rules"]:
        if key not in rule.get("fields", ()) and not in_section(spec, spec["fields"][key], rule.get("sections", ())):
            continue
        effect = rule.get("effect", "applicable")
        if effect not in {"applicable", "required"} or effect in effects:
            raise ValueError("Expected at most one applicability and one requiredness rule per field")
        effects[effect] = choice_condition(rule, facts.get(rule["controller"]))
    active = effects.get("applicable", True)
    if active is None:
        return "unresolved", "unresolved"
    if not active:
        return "inactive", "inapplicable"
    if "required" not in effects:
        return "active", "undeclared"
    return "active", {True: "required", False: "not required", None: "unresolved"}[effects["required"]]


def fixture_completer(spec, facts):
    # Deterministic stand-in for a completer. Scenario facts are separate from the spec.
    typed = FormSpec.model_validate(spec)
    result = {}
    for key in spec["fields"]:
        if field_obligation(spec, key, facts)[0] != "active":
            continue
        entry = facts.get(key)
        if entry is None:
            result[key] = status("missing")
            continue
        if typed.failed_validations(key, entry):
            result[key] = status("invalid")
            continue
        result[key] = value(entry)
    return result


class IncidentRegressionTests(TestCase):
    def test_stages_and_correspondence(self):
        stages = json.loads((INCIDENT / "regressions/stages.json").read_text())
        for stage in stages:
            assert FormSpec.model_validate(stage).model_dump(exclude_unset=True) == stage
        mistakes = []
        for i, ref in enumerate(stages, 1):
            pred = deepcopy(ref)
            if i == 1:
                pred["regions"]["name_0"]["bbox"][0] += 180
            if i == 2:
                pred["fields"]["name"]["section"] = None
            if i == 3:
                del pred["sections"]["office"]["role"]
            if i == 4:
                pred["validations"].clear()
            if i == 5:
                pred["rules"][0]["option"] = "No"
            perfect, _ = track_a(ref, ref)
            assert all(fp == fn == 0 for tp, fp, fn in perfect.values())
            mistakes.append(track_a(pred, ref))

        assert mistakes[0][0]["geometry"] == (0, 1, 1)
        assert mistakes[1][0]["sections"] == (0, 0, 1)
        assert mistakes[2][0]["roles"] == (1, 1, 1)
        assert all(fp == fn == 0 for tp, fp, fn in mistakes[3][0].values())
        assert mistakes[3][1]["validation"] == (0, 0, 1)
        assert mistakes[4][0]["rules"] == (0, 1, 1)

        ref = stages[-1]
        equivalent = deepcopy(ref)
        equivalent["rules"][0].update(op="ne", option="No")
        del equivalent["sections"]["office"]["role"]
        for f in equivalent["fields"].values():
            if f["section"] == "office":
                f["role"] = "Business Office"
        assert track_a(equivalent, ref) == track_a(ref, ref)

        wrong = deepcopy(ref)
        wrong["fields"]["incident"]["options"] = {"No": "incident_1", "Yes": "incident_0"}
        a, _ = track_a(wrong, ref)
        assert a["geometry"] == (6, 0, 0) and a["fields"] == (4, 1, 1)

        wrong = deepcopy(ref)
        wrong["fields"]["incident"]["cardinality"] = [0, 2]
        assert track_a(wrong, ref)[0]["fields"] == (4, 1, 1)

        # Section aggregation is intentionally blind to a wholesale swap of section titles.
        wrong = deepcopy(ref)
        wrong["sections"]["office"]["title"], wrong["sections"]["applicant"]["title"] = (
            wrong["sections"]["applicant"]["title"], wrong["sections"]["office"]["title"]
        )
        assert track_a(wrong, ref)[0] == track_a(ref, ref)[0]

        # Confirmed-negative reference for rules adds no TP; a hallucination adds a pooled FP.
        ref_no_rule = deepcopy(ref)
        ref_no_rule["rules"].clear()
        clean_negative = track_a(ref_no_rule, ref_no_rule)[0]
        bad_negative = track_a(ref, ref_no_rule)[0]
        assert clean_negative["rules"] == (0, 0, 0)
        assert bad_negative["rules"] == (0, 1, 0)
        pooled = pool_a([track_a(ref, ref)[0], bad_negative])
        assert pooled["rules"] == (1, 1, 0)

    def test_appendix_counts(self):
        appendix_case = json.loads((INCIDENT / "regressions/appendix.json").read_text())
        appendix, imperfect = appendix_case["reference"], appendix_case["prediction"]
        expected_counts = dict(geometry=(3,2,1), fields=(1,3,2), sections=(2,2,1),
                               roles=(2,2,1), rules=(0,1,2))
        assert track_a(imperfect, appendix)[0] == expected_counts

    def test_completion_pairs_and_obligations(self):
        stages = json.loads((INCIDENT / "regressions/stages.json").read_text())
        ref = stages[-1]
        incident_v1 = json.loads((INCIDENT / "reference.json").read_text())
        facts = dict(name="Alex", reviewer="Sam", review_date="2004-02-29",
                     incident="Yes", details="Broken latch")
        gold = {k: value(v) for k,v in facts.items()}
        assert fixture_completer(ref, facts) == gold

        no_facts = dict(facts, incident="No")  # deliberately retains the detail
        no_gold = dict(gold, incident=value("No"))
        del no_gold["details"]
        invalid_facts = dict(facts, review_date="2004-02-30")
        invalid_gold = dict(gold, review_date=status("invalid"))

        assert fixture_completer(incident_v1, invalid_facts) == invalid_gold
        date_outputs = (fixture_completer(ref, facts), fixture_completer(ref, invalid_facts))
        branch_outputs = (fixture_completer(ref, facts), fixture_completer(ref, no_facts))


        assert paired_pass(date_outputs, (gold, invalid_gold), ["review_date"])
        assert paired_pass(branch_outputs, (gold, no_gold), ["incident", "details"])

        no_constraint = deepcopy(ref)
        no_constraint["validations"].clear()
        unsafe = fixture_completer(no_constraint, invalid_facts)
        assert track_a(no_constraint, ref)[0] == track_a(ref, ref)[0]
        assert not paired_pass((date_outputs[0], unsafe), (gold, invalid_gold), ["review_date"])
        assert track_b(unsafe, invalid_gold, ref, no_constraint)["value"] == (4, 5)

        leak = dict(no_gold, details=value("Broken latch"))
        assert track_b(leak, no_gold, ref)["inactive"] == (1, 1)
        assert track_b(leak, no_gold, ref)["complete"] == (0, 1)
        assert track_b(leak, no_gold, ref)["value"] == (4, 5)

        swap = dict(gold, name=gold["reviewer"], reviewer=gold["name"])
        assert track_b(swap, gold, ref)["value"] == (3, 5)
        assert track_b(swap, gold, ref)["coverage"] == (5, 5)
        assert track_b(swap, gold, ref)["activity"] == (5, 5)

        for input_status in ("missing", "conflicting"):
            answer = dict(gold, reviewer=status(input_status))
            assert track_b(answer, answer, ref)["complete"] == (1, 1)
            assert track_b(gold, answer, ref)["complete"] == (0, 1)

        renamed = deepcopy(ref)
        renamed["fields"]["applicant_full_name"] = renamed["fields"].pop("name")
        renamed_answer = {("applicant_full_name" if k == "name" else k): v for k,v in gold.items()}
        assert track_b(renamed_answer, gold, ref, renamed)["complete"] == (1, 1)
        assert track_b(renamed_answer, gold, ref)["unmatched"] == 1

        missing = dict(gold)
        del missing["reviewer"]
        extra = dict(gold, extra=value("extra"))

        clean_score = track_b(gold, gold, ref)
        assert clean_score["value"] == (5, 5) and clean_score["complete"] == (1, 1)

        # Use the same output for two scenarios with different reference answers.
        missing_gold = dict(gold, reviewer=status("missing"))
        valid_omission = track_b(missing, missing_gold, ref)
        assert valid_omission["value"] == valid_omission["activity"] == (5, 5)
        assert valid_omission["complete"] == (1, 1) and valid_omission["coverage"] == (4, 5)
        assert track_b(dict(missing, reviewer=None), missing_gold, ref)["complete"] == (0, 1)
        assert track_b(gold, missing_gold, ref)["value"] == (4, 5)

        missing_score = track_b(missing, gold, ref)
        assert missing_score["value"] == missing_score["coverage"] == (4, 5)
        assert missing_score["complete"] == (0, 1) and missing_score["unmatched"] == 0

        extra_score = track_b(extra, gold, ref)
        assert extra_score["value"] == (5, 6) and extra_score["complete"] == (0, 1)
        assert extra_score["coverage"] == (5, 5) and extra_score["unmatched"] == 1
        assert track_b(dict(leak, extra=value("extra")), no_gold, ref)["value"] == (4, 6)

        for controller, expected_state in [
            ("Yes", ("active", "required")),
            ("No", ("inactive", "inapplicable")),
            (None, ("unresolved", "unresolved")),
        ]:
            scenario = dict(facts, incident=controller)
            state = field_obligation(incident_v1, "details", scenario)
            assert state == expected_state
            assert ("details" in fixture_completer(incident_v1, scenario)) == (controller == "Yes")


        # Removing only the applicability gate leaves an active, conditionally required field.
        always_active = deepcopy(incident_v1)
        always_active["rules"].pop(0)
        assert field_obligation(always_active, "details", no_facts) == ("active", "not required")
        assert fixture_completer(always_active, no_facts)["details"] == gold["details"]

        assert track_a(incident_v1, incident_v1)[1]["requiredness"] == (1, 0, 0)
        ranked, diagnostics = track_a(ref, incident_v1)
        assert ranked == track_a(ref, ref)[0] and diagnostics["requiredness"] == (0, 0, 1)

        # The form still requires details when Yes, even if the narrative gives none.
        without_details = dict(facts)
        del without_details["details"]
        assert field_obligation(incident_v1, "details", without_details) == ("active", "required")
        submitted = fixture_completer(incident_v1, without_details)
        assert submitted.pop("details") == status("missing")
        assert track_b(submitted, dict(gold, details=status("missing")), incident_v1)["complete"] == (1, 1)
        assert track_b(submitted, gold, incident_v1)["complete"] == (0, 1)
