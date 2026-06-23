# Plan — Detail pop-out redesign (understand-first, then compare)

**Problem:** clicking a feature/category opens a right-side drawer dominated by methodology —
metadata table, "Why we believe this" evidence, history timeline, sub-feature breakdown. A user
can't quickly answer "what *is* this, and how does it stack up against the others?"

**Goal:** a centered **pop-out** that leads with a plain-language explanation, then a clean
cross-provider comparison. Drop the justification/provenance/history/breakdown.

## Layout (centered modal, not side drawer)
```
┌───────────────────────────────────────────────┐
│  Code Review                                ✕  │   name
│  Anthropic · active · Managed agent runtime    │   provider · status · capability (one line)
│ ─────────────────────────────────────────────  │
│  Provides automated PR reviews on GitHub        │   WHAT IT IS  — the plain explanation
│  Enterprise Server repos — the same automated   │   (scope_note; fallback to capability desc)
│  reviews as github.com.                         │
│                                                 │
│  How it compares — Managed agent runtime        │   HOW IT COMPARES (cross-provider)
│  Anthropic, OpenAI and Google differ here:      │   the "how they differ" synthesis (if present)
│  Anthropic is sandbox-native…                   │
│   OpenAI   → Responses API · Built-in tools …   │   each other provider's offerings on this axis
│   Google   → Agent Runtime · Sessions …         │   (or "none" / "not verified", honestly)
│ ─────────────────────────────────────────────  │
│  Official docs ↗                                │   one quiet first-party link (not justification)
└───────────────────────────────────────────────┘
```

## Changes (all in `viewer/template.html`)
1. **Drawer → modal.** `#drawer` becomes a centered card: `max-width:600px`, `max-height:86vh`,
   internal scroll, fade+scale in, dim overlay behind. Close on ✕, overlay click, or **Esc**.
2. **`openDrawer` content** — keep only:
   - **header**: name; one compact meta line (provider · status · capability). No kv table.
   - **What it is**: `scope_note` rendered prominently; if empty, fall back to the primary
     capability's description so there's always an explanation.
   - **How it compares**: reuse `axisCompareSection` logic, restyled and renamed "How it compares —
     <capability>", leading with `comparison_note` ("how they differ"), then the other providers'
     features on that axis (present / none / not-verified, unchanged honesty).
   - **Official docs ↗**: a single quiet link to `source.url`.
   - **Removed**: the kv metadata table, `receiptSection` ("Why we believe this"), `lineage`,
     `history` timeline, and `featuresSection` (Breakdown / sub-features).
3. **Categories become clickable.** Axis/category row labels (`capname` on Overview + Explore) get
   an `openCapability(capId)` handler → same modal: capability **name + description** (what it is)
   then the per-provider comparison grid + `comparison_note`. Today only products/features are
   clickable; this makes "click a category" work as asked.

## Notes / non-goals
- `receiptSection`/`featuresSection`/history stay defined but unused by the modal (harmless). The
  breakdown/evidence still live in the data + ledger; just not in this user-facing view.
- Viewer-only; no data/engine changes. Rebuild + redeploy after.

## Open choices
1. **Sub-features**: fully removed (per your note), or a light one-line "Includes: a, b, c" under
   "what it is"? (They're arguably "what it is," but you listed breakdown as out.)
2. **Official-docs link**: keep the single quiet link, or zero links?
