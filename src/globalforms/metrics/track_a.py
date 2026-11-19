"""Pilot specification recovery metrics."""

from collections import Counter

from ..validations import DateValidation, wire_validation
from .alignment import align, matching, normalize


def counts(tp, predicted, reference):
    return tp, predicted - tp, reference - tp


def f1(triple):
    tp, fp, fn = triple
    return 2*tp / (2*tp+fp+fn) if tp or fp or fn else None


def inherited_role(spec, field, default_role):
    role = field.get("role")
    section = field.get("section")
    while not role and section is not None:
        node = spec["sections"][section]
        role = node.get("role")
        section = node.get("parent")
    return normalize(role or default_role or "")


def memberships(pred, ref, fields, identity=lambda p, r: True):
    shared = Counter((pred[p], ref[r]) for p, r in fields.items() if p in pred and r in ref)
    aligned = matching(set(pred.values()), set(ref.values()),
                       lambda p, r: shared[p, r] if identity(p, r) else 0)
    return counts(sum(shared[p, r] for p, r in aligned.items()), len(pred), len(ref))


def direct_sections(spec):
    return {k: f["section"] for k, f in spec["fields"].items() if f.get("section")}


def in_section(spec, field, targets):
    section = field.get("section")
    while section is not None:
        if section in targets:
            return True
        section = spec["sections"][section].get("parent")
    return False


def choice_condition(rule, answer):
    if rule["op"] not in {"eq", "ne"}:
        raise ValueError("Only choice equality and inequality are supported")
    if answer is None:
        return None
    return (answer == rule["option"]) == (rule["op"] == "eq")


# TODO: Define which compound rule encodings are equivalent to separate effect records.
# Test that a combined Yes -> details (applicable, required) and its two atomic records
# receive identical per-effect counts once compound syntax is supported.
# Today applicability is ranked and requiredness is diagnostic. Label both in rule plots:
# reversing only applicability gives 0% applicability F1 and 100% requiredness F1.
def rule_edges(spec, ref, alignment, effect="applicable"):
    # One edge per target, with the full truth table. Unmatched edges remain errors.
    result = Counter()
    for rule in spec["rules"]:
        if rule.get("effect", "applicable") != effect:
            continue
        source = rule["controller"]
        controller = alignment.get(source, ("unmatched", source))
        options = ref["fields"].get(controller, spec["fields"][source])["options"]
        state = (None,) + tuple(sorted(options))
        outputs = tuple(choice_condition(rule, v) for v in state)
        targets = set(rule.get("fields", ()))
        targets.update(k for k, f in spec["fields"].items()
                       if in_section(spec, f, rule.get("sections", ())))
        for target in targets:
            result[controller, alignment.get(target, ("unmatched", target)), outputs] += 1
    return result


def track_a(pred, ref, *, default_role=None):
    """Return ranked and diagnostic TP/FP/FN counts for the two specs.

    Both specs use the field role, then the nearest ancestor section role, then
    the evaluator's optional default_role.
    """
    regions, fields = align(pred, ref)
    pf, rf = pred["fields"], ref["fields"]

    def checks(p, r):
        a, b = pf[p], rf[r]
        return {
            "type": a["type"] == b["type"],
            "label": normalize(a["label"]) == normalize(b["label"]),
            "option ownership": {k: regions.get(v) for k, v in a["options"].items()} == b["options"],
            "cardinality": "cardinality" not in b or a.get("cardinality") == b["cardinality"],
        }

    checks_by_field = [checks(p, r) for p, r in fields.items()]
    p_rules = rule_edges(pred, ref, fields)
    r_rules = rule_edges(ref, ref, {r: r for r in rf})
    components = {
        "geometry": counts(len(regions), len(pred["regions"]), len(ref["regions"])),
        "fields": counts(sum(all(c.values()) for c in checks_by_field), len(pf), len(rf)),
        "sections": memberships(direct_sections(pred), direct_sections(ref), fields),
        "roles": memberships({k: inherited_role(pred, f, default_role) for k,f in pf.items()},
                             {k: inherited_role(ref, f, default_role) for k,f in rf.items()}, fields,
                             lambda p, r: p == r),
        "rules": counts(sum((p_rules & r_rules).values()), sum(p_rules.values()), sum(r_rules.values())),
    }
    local = {key: counts(sum(c[key] for c in checks_by_field), len(pf), len(rf))
             for key in ("type", "label", "option ownership", "cardinality")}

    def constraints(spec, ids):
        result = Counter()
        for record in spec["validations"]:
            rule = wire_validation.validate_python(record)
            if isinstance(rule, DateValidation):
                # Archived records applied to the entire target tuple.
                target = tuple(sorted(ids.get(k, f"unmatched:{k}") for k in rule.fields))
                result[target, rule.kind] += 1
                continue
            for field in set(rule.fields):
                target = ids.get(field, ("unmatched", field))
                for claim in rule.claims():
                    result[target, claim] = 1
        return result

    pv = constraints(pred, fields)
    rv = constraints(ref, {k: k for k in rf})
    local["validation"] = counts(sum((pv & rv).values()), sum(pv.values()), sum(rv.values()))
    pr = rule_edges(pred, ref, fields, "required")
    rr = rule_edges(ref, ref, {k: k for k in rf}, "required")
    local["requiredness"] = counts(sum((pr & rr).values()), sum(pr.values()), sum(rr.values()))
    return components, local


def pool_a(results):
    pooled = {}
    for result in results:
        for component, counts in result.items():
            previous = pooled.get(component, (0, 0, 0))
            pooled[component] = tuple(a + b for a, b in zip(previous, counts, strict=True))
    return pooled
