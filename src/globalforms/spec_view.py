"""Paper-style FormSpec inspection for notebooks and HTML review interfaces."""

import json
from html import escape

from .spec import FormSpec


# Keep the serialized property names. Roles live on fields and sections in the pilot.
_GROUPS = {
    "schemaVersion": "#475569",
    "sections": "#475569",
    "fields": "#16549a",
    "regions": "#2b663f",
    "rules": "#8b5108",
    "validations": "#a12749",
    "evidence": "#475569",
}
_ROLE_COLOR = "#663e93"


def _json_value(value, path, depth=0):
    """Escape JSON as text. Keep short records compact and color inline role declarations."""
    compact = json.dumps(value, ensure_ascii=False, allow_nan=False)
    is_role_owner = len(path) == 2 and path[0] in ("sections", "fields")
    expand = isinstance(value, (dict, list)) and bool(value) and (
        len(compact) + 2 * depth > 72
        or len(path) == 1
        or (is_role_owner and isinstance(value, dict) and "role" in value)
    )
    if not expand:
        return escape(compact, quote=False)

    indent = "  " * depth
    items = []
    if isinstance(value, dict):
        left, right = "{", "}"
        for key, item in value.items():
            name = escape(json.dumps(key, ensure_ascii=False), quote=False)
            line = f"{name}: {_json_value(item, (*path, key), depth + 1)}"
            if is_role_owner and key == "role":
                line = f'<span style="color:{_ROLE_COLOR};font-weight:600">{line}</span>'
            items.append(line)
    else:
        left, right = "[", "]"
        items = [_json_value(item, (*path, i), depth + 1) for i, item in enumerate(value)]

    return left + "\n" + ",\n".join(indent + "  " + item for item in items) + "\n" + indent + right


def formspec_html(reference: FormSpec, prediction: FormSpec | None = None, *, changed_only=False) -> str:
    """Render one spec or compare two by serialized property. Return self-contained static HTML.

    changed_only omits equal groups and equal entries in ID-keyed maps. Lists retain
    their order and all their entries. Field correspondence belongs to the scorer.
    """
    if changed_only and prediction is None:
        raise ValueError("changed_only requires a prediction")
    specs = [reference] if prediction is None else [reference, prediction]
    data = [spec.model_dump(mode="json", exclude_unset=True) for spec in specs]
    names = ["FormSpec"] if prediction is None else ["Reference (GT)", "Prediction"]
    headers = "".join(f'<th scope="col" style="text-align:left">{name}</th>' for name in ("Spec group", *names))
    rows = []
    missing = object()
    keys = dict.fromkeys(key for spec in data for key in spec)
    ordered_keys = [key for key in _GROUPS if key in keys] + [key for key in keys if key not in _GROUPS]
    for key in ordered_keys:
        values = [spec.get(key, missing) for spec in data]
        if changed_only:
            left, right = values
            if left == right:
                continue
            if isinstance(left, dict) and isinstance(right, dict):
                values = [{k: v for k, v in left.items() if right.get(k, missing) != v},
                          {k: v for k, v in right.items() if left.get(k, missing) != v}]
        ink = _GROUPS.get(key, "#475569")
        label = (f'<th scope="row" style="text-align:left;vertical-align:top">'
                 f'<span aria-hidden="true" style="color:{ink}">■</span> <code>{escape(key)}</code></th>')
        cells = []
        for value in values:
            if value is missing:
                cells.append("<td><em>Absent</em></td>")
                continue
            content = _json_value(value, (key,))
            cells.append(
                f'<td style="vertical-align:top;border-left:3px solid {ink};background:#f6f8fa">'
                f'<pre style="margin:0;padding:0.4em;color:{ink};background:#f6f8fa;'
                f'font-family:ui-monospace,monospace;line-height:1.4;text-align:left;'
                f'white-space:pre-wrap;overflow-wrap:anywhere">{content}</pre></td>'
            )
        rows.append(f'<tr>{label}{"".join(cells)}</tr>')
    if not rows:
        rows.append('<tr><td colspan="3">No serialized groups differ.</td></tr>')
    width = "16%" if prediction is not None else "22%"
    return (f'<table style="width:100%;table-layout:fixed"><colgroup><col style="width:{width}"/>'
            + "<col/>" * len(data) + f"</colgroup><thead><tr>{headers}</tr></thead>"
            + "<tbody>" + "".join(rows) + "</tbody></table>")
