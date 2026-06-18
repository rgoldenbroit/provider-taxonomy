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

## Enabling the self-maintaining loop (`.github/workflows/maintain.yml`)

The loop re-verifies every record against its source weekly (and on demand), captures fresh
evidence, proves the rebuild is reproducible (`verify`), writes a changelog, commits the diff,
and optionally redeploys. It runs **keyless** via GCP Workload Identity Federation — no
service-account JSON in the repo. Until the secrets below exist it **skips cleanly** (no red CI).

One-time setup (`PROJECT`, `REPO=rgoldenbroit/provider-taxonomy`):

```sh
# 1. A service account the loop runs as (Vertex calls; add run.admin if AUTO_DEPLOY).
gcloud iam service-accounts create taxo-maintainer --project "$PROJECT"
SA="taxo-maintainer@$PROJECT.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role="roles/aiplatform.user"

# 2. A Workload Identity pool + GitHub provider, restricted to this repo.
gcloud iam workload-identity-pools create github --project "$PROJECT" --location global
gcloud iam workload-identity-pools providers create-oidc github --project "$PROJECT" \
  --location global --workload-identity-pool github \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='$REPO'"
POOL=$(gcloud iam workload-identity-pools describe github --project "$PROJECT" --location global --format="value(name)")

# 3. Let the GitHub repo impersonate the SA.
gcloud iam service-accounts add-iam-policy-binding "$SA" --project "$PROJECT" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/$POOL/attribute.repository/$REPO"
```

Then in the GitHub repo (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `<POOL>/providers/github` (from step 2) |
| `GCP_SERVICE_ACCOUNT` | `taxo-maintainer@<PROJECT>.iam.gserviceaccount.com` |
| `TAVILY_API_KEY` | your Tavily key |

| Variable | Value |
|---|---|
| `GCP_PROJECT_ID` | `<PROJECT>` |
| `CLOUD_ML_REGION` | `global` |
| `VERTEX_MODEL` | `claude-opus-4-8` |
| `AUTO_DEPLOY` | `true` to redeploy each run (SA also needs `roles/run.admin`), else omit |

Trigger it from the **Actions** tab (workflow_dispatch) to test, or wait for the weekly cron.
