"""Validate a taxonomy dataset against ``schema.json`` and fail loudly.

Two layers:

1. **Schema-subset walk** — interprets exactly the JSON-Schema (draft 2020-12)
   constructs ``schema.json`` actually uses: ``type``, ``required``,
   ``additionalProperties: false``, ``enum``, ``properties``, ``array``/``items``,
   ``$ref`` into ``$defs``, and ``format: date``. A focused ~150-line walker, not a
   general JSON-Schema engine (deliberately — keep it tied to this schema).

2. **Referential integrity** — invariants JSON Schema cannot express, which is
   where real data bugs hide: every ``capability_ids`` / ``primary_capability_id`` /
   ``parent_id`` / ``predecessor_id`` / ``successor_id`` resolves to an existing id;
   ``primary_capability_id`` is one of ``capability_ids``; ``status: "absent"`` implies
   ``relation_within_capability: "none"``; ids are unique; ``capability_ids`` is non-empty.

``validate(data)`` returns a flat list of :class:`Issue`; an empty list means valid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import load_schema

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Cross-record reference fields on a product → the id space they must resolve into.
_PRODUCT_REF_FIELDS = ("parent_id", "predecessor_id", "successor_id")


@dataclass(frozen=True)
class Issue:
    """A single validation failure. ``kind`` is 'schema' or 'integrity'."""

    kind: str
    rule: str
    path: str
    message: str
    record_id: str | None = None

    def __str__(self) -> str:
        loc = self.path or "<root>"
        rid = f" [{self.record_id}]" if self.record_id else ""
        return f"{self.kind}:{self.rule}{rid} at {loc} — {self.message}"


def _type_name(value: object) -> str:
    return {
        dict: "object",
        list: "array",
        str: "string",
        bool: "boolean",
        int: "integer",
        float: "number",
        type(None): "null",
    }.get(type(value), type(value).__name__)


class _SchemaWalker:
    """Walks a value against the supported JSON-Schema subset, collecting issues."""

    def __init__(self, root_schema: dict):
        self.root = root_schema
        self.issues: list[Issue] = []

    def _add(self, rule: str, path: str, message: str) -> None:
        self.issues.append(Issue("schema", rule, path, message))

    def _resolve(self, schema: dict) -> dict:
        seen = 0
        while isinstance(schema, dict) and "$ref" in schema:
            schema = self._lookup_ref(schema["$ref"])
            seen += 1
            if seen > 32:  # guard against a pathological $ref cycle in the schema
                break
        return schema

    def _lookup_ref(self, ref: str) -> dict:
        if not ref.startswith("#/"):
            raise ValueError(f"unsupported $ref (only local refs handled): {ref!r}")
        node: object = self.root
        for part in ref[2:].split("/"):
            node = node[part]  # KeyError here is a real bug in schema.json — surface it
        return node  # type: ignore[return-value]

    def walk(self, value: object, schema: dict, path: str) -> None:
        schema = self._resolve(schema)
        t = schema.get("type")

        if t == "object":
            if not isinstance(value, dict):
                self._add("type", path, f"expected object, got {_type_name(value)}")
                return
            self._object(value, schema, path)
        elif t == "array":
            if not isinstance(value, list):
                self._add("type", path, f"expected array, got {_type_name(value)}")
                return
            items = schema.get("items")
            if items is not None:
                for i, item in enumerate(value):
                    self.walk(item, items, f"{path}[{i}]")
        elif t == "string":
            if not isinstance(value, str):
                self._add("type", path, f"expected string, got {_type_name(value)}")
                return
            if schema.get("format") == "date" and not _DATE_RE.match(value):
                self._add("format", path, f"{value!r} is not an ISO date (YYYY-MM-DD)")

        # enum applies to leaf values regardless of declared type.
        if "enum" in schema and value not in schema["enum"]:
            self._add("enum", path, f"{value!r} is not one of {schema['enum']}")

    def _object(self, value: dict, schema: dict, path: str) -> None:
        props: dict = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                self._add("required", path, f"missing required property {key!r}")
        if schema.get("additionalProperties", True) is False:
            for key in value:
                if key not in props:
                    child = f"{path}.{key}" if path else key
                    self._add("additionalProperties", child, f"unexpected property {key!r}")
        for key, subschema in props.items():
            if key in value:
                child = f"{path}.{key}" if path else key
                self.walk(value[key], subschema, child)


def _check_integrity(data: dict) -> list[Issue]:
    """Referential-integrity checks the JSON Schema can't express."""
    issues: list[Issue] = []
    capabilities = data.get("capabilities", [])
    products = data.get("products", [])
    if not isinstance(capabilities, list) or not isinstance(products, list):
        return issues  # schema layer already flagged the shape problem

    cap_ids: set[str] = set()
    for i, cap in enumerate(capabilities):
        if not isinstance(cap, dict):
            continue
        cid = cap.get("id")
        if isinstance(cid, str):
            if cid in cap_ids:
                issues.append(Issue("integrity", "uniqueness", f"capabilities[{i}].id",
                                    f"duplicate capability id {cid!r}", cid))
            cap_ids.add(cid)

    prod_ids: set[str] = set()
    for i, prod in enumerate(products):
        if not isinstance(prod, dict):
            continue
        pid = prod.get("id")
        if isinstance(pid, str):
            if pid in prod_ids:
                issues.append(Issue("integrity", "uniqueness", f"products[{i}].id",
                                    f"duplicate product id {pid!r}", pid))
            prod_ids.add(pid)

    for i, prod in enumerate(products):
        if not isinstance(prod, dict):
            continue
        pid = prod.get("id")
        path = f"products[{i}]"

        cap_list = prod.get("capability_ids")
        if isinstance(cap_list, list):
            if not cap_list:
                issues.append(Issue("integrity", "invariant", f"{path}.capability_ids",
                                    "capability_ids is empty; a product must touch ≥1 capability", pid))
            for cid in cap_list:
                if cid not in cap_ids:
                    issues.append(Issue("integrity", "ref_resolution", f"{path}.capability_ids",
                                        f"references unknown capability {cid!r}", pid))

        primary = prod.get("primary_capability_id")
        if isinstance(primary, str):
            if primary not in cap_ids:
                issues.append(Issue("integrity", "ref_resolution", f"{path}.primary_capability_id",
                                    f"references unknown capability {primary!r}", pid))
            elif isinstance(cap_list, list) and primary not in cap_list:
                issues.append(Issue("integrity", "invariant", f"{path}.primary_capability_id",
                                    f"primary_capability_id {primary!r} is not in capability_ids", pid))

        for field in _PRODUCT_REF_FIELDS:
            ref = prod.get(field)
            if isinstance(ref, str) and ref not in prod_ids:
                issues.append(Issue("integrity", "ref_resolution", f"{path}.{field}",
                                    f"references unknown product {ref!r}", pid))

        if prod.get("status") == "absent" and prod.get("relation_within_capability") != "none":
            issues.append(Issue("integrity", "invariant", f"{path}.relation_within_capability",
                                "status 'absent' requires relation_within_capability 'none'", pid))

    return issues


def validate(data: object, schema: dict | None = None) -> list[Issue]:
    """Validate a dataset; return all issues (empty list ⇒ valid)."""
    if not isinstance(data, dict):
        return [Issue("schema", "type", "", f"top-level value must be an object, got {_type_name(data)}")]
    walker = _SchemaWalker(schema or load_schema())
    walker.walk(data, walker.root, "")
    return walker.issues + _check_integrity(data)


def validate_instance(instance: object, schema: dict, root: dict | None = None) -> list[Issue]:
    """Validate one value against an arbitrary schema (schema-subset walk only).

    Reused to check a triage agent's structured output conforms before it is
    admitted, and to check the stub LLM emits schema-valid objects. ``root`` is the
    document ``$ref`` resolves against (defaults to ``schema`` itself).
    """
    walker = _SchemaWalker(root or schema)
    walker.walk(instance, schema, "")
    return walker.issues
