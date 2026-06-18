"""``taxo`` command-line entrypoint.

Phase 0 commands:
  taxo validate [path]   Validate a dataset against schema.json (fail loudly).
  taxo config            Show the resolved GCP / Vertex configuration.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .config import settings
from .index import build_index
from .schema import DEFAULT_DATA_PATH, load_dataset, load_schema
from .validate import validate


def cmd_validate(args: argparse.Namespace) -> int:
    path = args.path or DEFAULT_DATA_PATH
    try:
        data = load_dataset(path)
    except FileNotFoundError:
        print(f"error: dataset not found: {path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:  # malformed JSON: cannot validate, fail loudly
        print(f"error: {path} is not valid JSON: {exc}", file=sys.stderr)
        return 2

    issues = validate(data, load_schema())
    n_caps = len(data.get("capabilities", [])) if isinstance(data, dict) else 0
    n_prods = len(data.get("products", [])) if isinstance(data, dict) else 0

    if not issues:
        idx = build_index(data)
        print(f"✓ valid — {n_caps} capabilities / {n_prods} products / {len(idx.providers)} providers")
        return 0

    schema_issues = [i for i in issues if i.kind == "schema"]
    integ_issues = [i for i in issues if i.kind == "integrity"]
    print(
        f"✗ invalid — {len(schema_issues)} schema, {len(integ_issues)} integrity "
        f"issue(s) in {path}",
        file=sys.stderr,
    )
    for issue in issues:
        print(f"  - {issue}", file=sys.stderr)
    return 1


_PING_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ok", "tier"],
    "properties": {
        "ok": {"type": "boolean"},
        "tier": {"type": "string", "enum": ["model", "product", "feature"]},
    },
}


def cmd_ping(args: argparse.Namespace) -> int:
    from .retrieval import get_retrieval
    from .retrieval.base import RetrievalMissing
    from .validate import validate_instance
    from .vertex_client import LLMError, get_llm

    cfg = settings()
    print(f"mode: {cfg.mode}")

    try:
        llm = get_llm(cfg)
    except LLMError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if cfg.offline:
        out = llm.structured(system="You are a taxonomy classifier.",
                             prompt="Return a stub classification.", schema=_PING_SCHEMA)
        issues = validate_instance(out, _PING_SCHEMA)
        verdict = "valid" if not issues else "INVALID: " + "; ".join(str(i) for i in issues)
        print(f"  LLM   stub.structured → {out}  [{verdict}]")
        retrieval = get_retrieval(cfg)
        query = "Anthropic agentic-coding products 2026-06"
        try:
            results = retrieval.search(query)
            page = retrieval.fetch(results[0].url)
            print(f"  retrieval  search({query!r}) → {len(results)} result(s); "
                  f"fetch → {len(page.text)} chars, hash {page.content_hash[:12]}")
        except RetrievalMissing as exc:
            print(f"  retrieval  fixture missing: {exc}", file=sys.stderr)
            return 1
        return 0 if not issues else 1

    # Live: confirm Vertex credentials + model reachability.
    try:
        reply = llm.ping()
    except Exception as exc:  # surface the Vertex/ADC failure rather than a stack trace
        print(f"error: Vertex ping failed: {exc}", file=sys.stderr)
        print("  hint: run `gcloud auth application-default login` and check `taxo config`.",
              file=sys.stderr)
        return 1
    print(f"  LLM   Vertex {cfg.model} → {reply!r}")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    import json as _json

    from .discover import candidates_to_doc, discover
    from .fixtures import load_llm_fixtures
    from .retrieval import get_retrieval
    from .schema import REPO_ROOT
    from .vertex_client import get_llm

    cfg = settings()
    dataset = load_dataset(args.dataset)
    responses = load_llm_fixtures() if cfg.offline else None
    llm = get_llm(cfg, responses=responses)
    retrieval = get_retrieval(cfg)

    candidates = discover(args.capability, llm=llm, retrieval=retrieval, dataset=dataset)
    print(f"discover {args.capability} ({cfg.mode.split()[0]}) → {len(candidates)} new candidate(s)")
    for c in candidates:
        print(f"  + {c.record['id']}  ({c.record['provider']}: {c.record['name']})")

    out_path = REPO_ROOT / "data" / "candidates.json"
    out_path.write_text(_json.dumps(candidates_to_doc(args.capability, candidates), indent=2),
                        encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


def cmd_triage(args: argparse.Namespace) -> int:
    import json as _json
    from collections import Counter

    from .fixtures import load_llm_fixtures
    from .retrieval import get_retrieval
    from .schema import REPO_ROOT
    from .triage import triage_dataset
    from .validate import validate
    from .vertex_client import get_llm

    cfg = settings()
    dataset = load_dataset(args.dataset)
    responses = load_llm_fixtures() if cfg.offline else None
    llm = get_llm(cfg, responses=responses)
    retrieval = get_retrieval(cfg)

    proposed, outcomes = triage_dataset(dataset, llm=llm, retrieval=retrieval)
    counts = Counter(o.decision for o in outcomes)
    print(f"triage ({cfg.mode.split()[0]}) → {len(outcomes)} reviewable record(s): "
          f"{dict(counts)}")
    for o in outcomes:
        r = o.report
        print(f"  {o.decision:12} {o.record['id']}  "
              f"[schema {r.schema.score:.0f} · grounding {r.grounding.score:.2f} · "
              f"classification {r.classification.score:.2f}]")

    issues = validate(proposed)
    print(f"proposed dataset: {'✓ valid' if not issues else f'✗ {len(issues)} issue(s)'}")
    for it in issues:
        print(f"    - {it}", file=sys.stderr)

    out_path = REPO_ROOT / "data" / "proposed.json"
    out_path.write_text(_json.dumps(proposed, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    if args.apply and not issues:
        DEFAULT_DATA_PATH.write_text(_json.dumps(proposed, indent=2), encoding="utf-8")
        print(f"applied → {DEFAULT_DATA_PATH}")
    elif args.apply:
        print("not applied: proposed dataset has issues", file=sys.stderr)
        return 1
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    import json as _json
    from datetime import datetime, timezone

    from .evals import run_all
    from .schema import REPO_ROOT, load_seed

    seed = load_seed()
    dataset = load_dataset(args.dataset)
    report = run_all(seed, dataset)

    gold, adv, m = report["gold"], report["adversarial"], report["dataset_metrics"]
    print("gold-set reconstruction (held out: " + ", ".join(gold["holdout"]) + ")")
    print(f"  discovery recall            {gold['discovery_recall']:.2f}   "
          f"precision {gold['discovery_precision']:.2f}")
    print(f"  classification primary acc  {gold['classification_primary_accuracy']}   "
          f"relation acc {gold['classification_relation_accuracy']}  (n={gold['scored']})")
    print("adversarial grounding")
    print(f"  false-admit rate            {adv['false_admit_rate']:.2f}  "
          f"({adv['false_admits']}/{adv['cases']} fakes admitted)")
    print("dataset metrics")
    print(f"  schema conformance          {m['schema_conformance']:.2f}  ({m['schema_issues']} issues)")
    print(f"  provenance completeness     {m['provenance_completeness']:.2f}")
    print(f"  staleness coverage (fresh)  {m['staleness_coverage']:.2f}  ({m['stale_count']} stale)")
    print(f"  review_status               {m['review_status']}")
    print("gates")
    for name, ok in report["gates"].items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "passed": report["passed"], "gold": gold, "adversarial": adv,
              "dataset_metrics": m, "gates": report["gates"]}
    metrics_path = REPO_ROOT / "ops" / "metrics.jsonl"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(record) + "\n")
    print(f"\n{'✓ all gates passed' if report['passed'] else '✗ gate(s) failed'} "
          f"— appended to {metrics_path}")
    return 0 if report["passed"] else 1


def cmd_build(args: argparse.Namespace) -> int:
    import importlib.util

    from .schema import REPO_ROOT

    spec = importlib.util.spec_from_file_location("viewer_build", REPO_ROOT / "viewer" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    out, issues = module.build(args.dataset)
    print(f"wrote {out}  ({'valid' if not issues else f'{len(issues)} validation issue(s)'})")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from .retrieval import get_retrieval
    from .retrieval.base import RetrievalError

    cfg = settings()
    try:
        results = get_retrieval(cfg).search(args.query, max_results=args.n)
    except RetrievalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except NotImplementedError:
        print("error: live search not configured. Set TAVILY_API_KEY and TAXO_OFFLINE=0 "
              "(offline mode uses fixtures).", file=sys.stderr)
        return 1
    print(f"{len(results)} result(s) for {args.query!r}:")
    for r in results:
        print(f"  {r.url}\n      {r.title}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    import json as _json
    from collections import Counter

    from .audit import audit_catalog, findings_to_dicts
    from .retrieval import get_retrieval
    from .schema import REPO_ROOT
    from .vertex_client import get_llm

    cfg = settings()
    dataset = load_dataset(args.dataset)
    live = not cfg.offline and not args.mechanical
    llm = get_llm(cfg) if live else None
    retrieval = get_retrieval(cfg) if live else None
    findings = audit_catalog(dataset, llm, retrieval, triangulate=live, completeness=live)

    by_sev = Counter(f.severity for f in findings)
    print(f"audit ({'live' if live else 'mechanical-only'}) → {dict(by_sev)}")
    for f in findings:
        print(f"  [{f.severity:8}] {f.kind:12} {f.record_id or '-':34} {f.message}")
    out = REPO_ROOT / "ops" / "audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(findings_to_dicts(findings), indent=2), encoding="utf-8")
    print(f"wrote {out}")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    from .audit import audit_catalog, gate
    from .evals import run_all
    from .retrieval import get_retrieval
    from .schema import load_seed
    from .vertex_client import get_llm

    cfg = settings()
    dataset = load_dataset(args.dataset)
    eval_report = run_all(load_seed(), dataset)
    live = not cfg.offline
    findings = audit_catalog(dataset, get_llm(cfg) if live else None,
                             get_retrieval(cfg) if live else None,
                             triangulate=live, completeness=live)
    passed, reasons = gate(dataset, findings, eval_report)
    print(f"GATE: {'PASS — clear to ship' if passed else 'BLOCK'}")
    for r in reasons:
        print(f"  ✗ {r}")
    for f in findings:
        if f.severity == "critical":
            print(f"  ! critical/{f.kind} {f.record_id}: {f.message}")
    return 0 if passed else 1


def cmd_autobuild(args: argparse.Namespace) -> int:
    import json as _json

    from .autobuild import autobuild
    from .retrieval import get_retrieval
    from .schema import REPO_ROOT, load_seed
    from .validate import validate
    from .vertex_client import get_llm

    cfg = settings()
    if cfg.offline:
        print("autobuild needs live search + LLM: set TAXO_OFFLINE=0 and TAVILY_API_KEY.", file=sys.stderr)
        return 1
    catalog = autobuild(get_llm(cfg), get_retrieval(cfg), load_seed(),
                        capabilities=args.capabilities or None, max_rounds=args.rounds)
    issues = validate(catalog)
    print(f"\nautobuild → {len(catalog['products'])} products; "
          f"{'✓ valid' if not issues else f'✗ {len(issues)} issue(s)'}")
    # write to a proposal file (review before promoting to data/taxonomy.json)
    out = REPO_ROOT / "data" / "auto.json"
    out.write_text(_json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"wrote {out}  (review, then audit/gate it; promote to data/taxonomy.json when satisfied)")
    return 0 if not issues else 1


def cmd_config(args: argparse.Namespace) -> int:
    cfg = settings()
    print("GCP / Vertex AI Claude configuration")
    print(f"  project_id : {cfg.project_id or '(unset — set ANTHROPIC_VERTEX_PROJECT_ID)'}")
    print(f"  region     : {cfg.region}")
    print(f"  model      : {cfg.model}")
    print(f"  search     : {'Tavily (configured)' if cfg.tavily_api_key else 'not configured — operator-seeded'}")
    print(f"  mode       : {cfg.mode}")
    if not cfg.offline:
        print("\nLive runs need Application Default Credentials:")
        print("  gcloud auth application-default login")
        if cfg.project_id:
            print(f"  gcloud auth application-default set-quota-project {cfg.project_id}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Reproducible-build check: replay the committed evidence ledger and assert the
    published catalog is byte-identical to what the evidence re-derives. No creds needed."""
    import copy

    from .config import _LEDGER_DIR
    from .ledger import REPLAY, Ledger, LedgerMiss
    from .replay import catalog_hash, reverify_catalog
    from .retrieval.http_fetch import HttpFetch
    from .vertex_client import ReplayLLM

    catalog = load_dataset(args.dataset)
    h_committed = catalog_hash(catalog)
    ledger = Ledger(_LEDGER_DIR, REPLAY)
    if not ledger.root.exists():
        print("VERIFY: FAIL — no evidence/ ledger found to replay.")
        return 1
    llm, retrieval = ReplayLLM(ledger, settings().model), HttpFetch(ledger=ledger)
    try:
        replayed = copy.deepcopy(catalog)
        reverify_catalog(replayed, llm, retrieval, ledger)
    except LedgerMiss as exc:
        print(f"VERIFY: FAIL — evidence missing from the ledger ({exc}).")
        return 1
    h_replay = catalog_hash(replayed)
    print(f"committed catalog : {h_committed}")
    print(f"replayed catalog  : {h_replay}")
    print(f"evidence ledger   : {ledger.stats()}")
    if h_committed == h_replay:
        print("VERIFY: PASS — the published catalog is exactly what the committed evidence reproduces.")
        return 0
    print("VERIFY: FAIL — catalog does not match a replay of the evidence (hand-edited or stale).")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taxo", description="AI-provider taxonomy engine.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a dataset against schema.json")
    p_validate.add_argument("path", nargs="?", default=None,
                            help="dataset path (default: data/taxonomy.json)")
    p_validate.set_defaults(func=cmd_validate)

    p_config = sub.add_parser("config", help="show resolved GCP / Vertex configuration")
    p_config.set_defaults(func=cmd_config)

    p_ping = sub.add_parser("ping", help="smoke-test the LLM + retrieval (offline stub or live Vertex)")
    p_ping.set_defaults(func=cmd_ping)

    p_search = sub.add_parser("search", help="run a live web search (Tavily) — smoke-test the search backend")
    p_search.add_argument("query")
    p_search.add_argument("-n", type=int, default=8, help="max results")
    p_search.set_defaults(func=cmd_search)

    p_discover = sub.add_parser("discover", help="sweep providers for a capability → candidate records")
    p_discover.add_argument("capability", help="capability id, e.g. agentic-coding")
    p_discover.add_argument("--dataset", default=None, help="dataset to dedup against (default: data/taxonomy.json)")
    p_discover.set_defaults(func=cmd_discover)

    p_triage = sub.add_parser("triage", help="triage reviewable records through the trust gates")
    p_triage.add_argument("--dataset", default=None, help="dataset to triage (default: data/taxonomy.json)")
    p_triage.add_argument("--apply", action="store_true", help="write the proposed dataset to data/taxonomy.json if valid")
    p_triage.set_defaults(func=cmd_triage)

    p_eval = sub.add_parser("eval", help="run gold-set + adversarial evals; gate on thresholds")
    p_eval.add_argument("--dataset", default=None, help="dataset for metrics (default: data/taxonomy.json)")
    p_eval.set_defaults(func=cmd_eval)

    p_build = sub.add_parser("build", help="generate the single-file viewer (viewer/taxonomy.html)")
    p_build.add_argument("--dataset", default=None, help="dataset to render (default: data/taxonomy.json)")
    p_build.set_defaults(func=cmd_build)

    p_audit = sub.add_parser("audit", help="red-team the catalog (mechanical + triangulation + completeness)")
    p_audit.add_argument("--dataset", default=None)
    p_audit.add_argument("--mechanical", action="store_true", help="skip LLM checks (deterministic only)")
    p_audit.set_defaults(func=cmd_audit)

    p_gate = sub.add_parser("gate", help="deploy gate: block unless schema+evals+audit pass (exit 1 on block)")
    p_gate.add_argument("--dataset", default=None)
    p_gate.set_defaults(func=cmd_gate)

    p_verify = sub.add_parser("verify", help="reproducible-build check: replay the evidence ledger and assert the catalog matches")
    p_verify.add_argument("--dataset", default=None)
    p_verify.set_defaults(func=cmd_verify)

    p_auto = sub.add_parser("autobuild", help="autonomously build the catalog (Tavily discovery, loop-until-dry)")
    p_auto.add_argument("--capabilities", nargs="*", default=None, help="subset of capability ids (default: all)")
    p_auto.add_argument("--rounds", type=int, default=2, help="max completeness rounds per capability")
    p_auto.set_defaults(func=cmd_autobuild)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
