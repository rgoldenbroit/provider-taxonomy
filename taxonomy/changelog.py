"""Diff two catalogs → a "what changed" changelog (human Markdown + machine JSON).

Used by the scheduled maintenance loop so every automated update is legible: which
offerings were added/removed and which changed lifecycle status, review state, or
confidence — the audit trail of a self-maintaining catalog.
"""

from __future__ import annotations

_WATCH = ("status", "review_status")


def diff_catalogs(old: dict, new: dict) -> dict:
    o = {p["id"]: p for p in old.get("products", [])}
    n = {p["id"]: p for p in new.get("products", [])}
    added = [{"id": i, "name": n[i]["name"], "provider": n[i]["provider"]} for i in n if i not in o]
    removed = [{"id": i, "name": o[i]["name"], "provider": o[i]["provider"]} for i in o if i not in n]
    changed = []
    for i in n:
        if i not in o:
            continue
        a, b = o[i], n[i]
        fields = {f: [a.get(f), b.get(f)] for f in _WATCH if a.get(f) != b.get(f)}
        ac, bc = (a.get("source") or {}).get("confidence"), (b.get("source") or {}).get("confidence")
        if ac != bc:
            fields["confidence"] = [ac, bc]
        if fields:
            changed.append({"id": i, "name": b["name"], "provider": b["provider"], "fields": fields})
    return {"added": added, "removed": removed, "changed": changed}


def is_empty(diff: dict) -> bool:
    return not (diff["added"] or diff["removed"] or diff["changed"])


def to_markdown(diff: dict, date: str) -> str:
    lines = [f"## {date}"]
    for a in diff["added"]:
        lines.append(f"- ➕ **{a['name']}** ({a['provider']}) — added")
    for r in diff["removed"]:
        lines.append(f"- ➖ **{r['name']}** ({r['provider']}) — removed")
    for c in diff["changed"]:
        ch = ", ".join(f"{k} {v[0]}→{v[1]}" for k, v in c["fields"].items())
        lines.append(f"- ✏️ **{c['name']}** ({c['provider']}) — {ch}")
    return "\n".join(lines) + "\n"


_HEADER = "# Changelog\n\n_What the self-maintaining loop changed, newest first._\n"


def prepend_markdown(existing: str | None, entry_md: str) -> str:
    body = (existing or _HEADER)
    body = body[len(_HEADER):] if body.startswith(_HEADER) else body
    return _HEADER + "\n" + entry_md + "\n" + body.lstrip()
