"""In-memory indexes over a validated dataset.

A "comparison" is a query, not stored data: ``products_by_capability`` is the
capability→providers pivot; ``children_by_parent`` is the hierarchy
(family→model, product→feature/sub-product). Build only after ``validate`` passes
— these accessors assume well-formed records.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Index:
    capabilities_by_id: dict[str, dict] = field(default_factory=dict)
    products_by_id: dict[str, dict] = field(default_factory=dict)
    products_by_capability: dict[str, list[dict]] = field(default_factory=dict)
    children_by_parent: dict[str, list[dict]] = field(default_factory=dict)
    providers: list[str] = field(default_factory=list)


def build_index(data: dict) -> Index:
    products = data.get("products", [])
    idx = Index(
        capabilities_by_id={c["id"]: c for c in data.get("capabilities", [])},
        products_by_id={p["id"]: p for p in products},
    )
    for p in products:
        for cap_id in p.get("capability_ids", []):
            idx.products_by_capability.setdefault(cap_id, []).append(p)
        parent = p.get("parent_id")
        if parent:
            idx.children_by_parent.setdefault(parent, []).append(p)
    idx.providers = sorted({p["provider"] for p in products if p.get("provider")})
    return idx
