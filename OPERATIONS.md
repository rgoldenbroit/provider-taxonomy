# Operations runbook

How the catalog is built, verified, and reproduced. The guiding idea: the catalog is
**derived** from a committed evidence ledger, not hand-asserted — so it is replay-reproducible
and every fact carries a receipt.

## Modes (`TAXO_LEDGER`)

| Mode | What happens | Needs |
|---|---|---|
| `off` (default) | legacy path; nothing stored or required | — |
| `record` | live calls run; every page + LLM response + receipt is written to `evidence/` | `TAXO_OFFLINE=0`, ADC, Tavily key |
| `replay` | **no live calls**; pages and LLM responses come from `evidence/` (a miss is an error) | nothing (works in CI) |

## Common tasks

```sh
# Offline dev/test — deterministic, no creds (stub LLM + fixtures)
TAXO_OFFLINE=1 python tests/run_all.py

# Reproducible-build check — replay the committed evidence; assert the catalog matches
python -m taxonomy.cli verify            # PASS ⇒ catalog == replay(evidence); no creds needed

# Re-verify + re-grade the catalog, capturing evidence (live, records the ledger)
TAXO_OFFLINE=0 TAXO_LEDGER=record .venv/bin/python scripts/reverify.py

# Re-derive the catalog from the ledger with zero live calls (e.g. after a grading-logic change)
TAXO_OFFLINE=0 TAXO_LEDGER=replay .venv/bin/python scripts/reverify.py
```

## What "reproducible" means here

**Replay-determinism**, not bit-reproducibility on re-derivation. The web and the models drift,
so a *fresh* discovery run is non-deterministic — that's expected. The evidence ledger pins a run:
`taxo verify` replays it and asserts the published `data/taxonomy.json` is byte-identical to what
the evidence re-derives. It's the same contract as `npm ci` reproducing from a lockfile.

CI (`.github/workflows/ci.yml`) runs the offline test suite **and** `taxo verify` on every push.

## Trust receipts

Each record's derivation is recorded in `evidence/provenance/<id>.json`: the verbatim judge quote,
the source + tier (official > reputable > low), every gate's pass/score, the decision, the model,
and the page content-hash. Confidence is **derived** from source tier; a lone low-quality source
cannot reach `confirmed`.

## Deploy

```sh
python -m taxonomy.cli build     # data/taxonomy.json → viewer/taxonomy.html
gcloud run deploy provider-seed-viewer --source viewer --region us-east5 --allow-unauthenticated --quiet
```
