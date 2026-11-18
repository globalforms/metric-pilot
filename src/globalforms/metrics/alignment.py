"""One-to-one grounded correspondence used by both evaluation tracks."""

from functools import lru_cache


def normalize(value):
    return " ".join(str(value).casefold().split())


def matching(pred_ids, ref_ids, weight):
    refs = sorted(ref_ids)
    preds = sorted(pred_ids)
    edges = [[(j, w) for j, r in enumerate(refs) if (w := weight(p, r)) > 0]
             for p in preds]

    # An earlier assignment matters only if a remaining prediction could claim it.
    # Dropping irrelevant bits keeps forms with disjoint boxes on a single search path.
    available = [0] * (len(preds) + 1)
    for i in reversed(range(len(preds))):
        available[i] = available[i + 1]
        for j, _ in edges[i]:
            available[i] |= 1 << j

    @lru_cache(None)
    def best(i, used):
        if i == len(preds):
            return 0, ()
        remaining = available[i + 1]
        result = best(i + 1, used & remaining)
        for j, w in edges[i]:
            if not used & (1 << j):
                score, pairs = best(i + 1, (used | (1 << j)) & remaining)
                result = max(result, (score+w, ((preds[i], refs[j]),) + pairs))
        return result

    return dict(best(0, 0)[1])


def hit(pred, ref):
    if pred["page"] != ref["page"]:
        return False
    x, y, w, h = pred["bbox"]
    X, Y, W, H = ref["bbox"]
    if min(w, h, W, H) <= 0:
        return False
    intersection = max(0, min(x+w, X+W)-max(x, X)) * max(0, min(y+h, Y+H)-max(y, Y))
    return intersection >= .50 * W * H and intersection >= .20 * w * h


def align(pred, ref):
    pr, rr = pred["regions"], ref["regions"]
    regions = matching(pr, rr, lambda p, r: hit(pr[p], rr[r]))
    pf, rf = pred["fields"], ref["fields"]

    def same_grounding(p, r):
        owned = pf[p]["regions"]
        return bool(owned) and len(owned) == len(rf[r]["regions"]) and (
            {regions.get(k) for k in owned} == set(rf[r]["regions"])
        )

    return regions, matching(pf, rf, same_grounding)
