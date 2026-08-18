# Sentinel AI Agent Security — Living Brief

**Status:** approved design, pending implementation plan
**Date:** 2026-08-18
**Owner:** Thomas Willner

## 1. Purpose

Produce a self-updating, publicly hosted HTML brief on securing enterprise AI agents with
Microsoft Sentinel, derived from a Microsoft TechCommunity article, and continuously
reconciled against authoritative Microsoft sources so it always reads as current truth.

Source article: "Securing Enterprise AI Agents with Microsoft Sentinel", SantoshPargi,
published 2026-07-31T02:30:39Z, TechCommunity Core Infrastructure and Security Blog,
message id `4542583`. Labels: *Agent 365*, *AI Security*.

The page is a **derived living brief**, not a reproduction. It credits and links the source
article as its origin. Its factual assertions are bound to live Microsoft Learn evidence, so
rewriting a claim is a re-read, never an act of authorship attributed to the original author.

### 1.1 Non-goals

- Not a mirror of the article. No verbatim prose and no Microsoft-hosted images are
  committed or republished.
- Not a general Microsoft AI-security news feed. Scope is bounded by the entities the
  article names (§4).
- No LLM in the build path. Generation is deterministic (§3.3).

## 2. Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | Fetch the source article deterministically via the Khoros v1 REST API and record `post_time`, `last_edit_time`, and a body hash. |
| FR-2 | Maintain a watchlist of every Microsoft entity the article names, each pinned to an authoritative `learn.microsoft.com` URL. |
| FR-3 | On each run, re-measure every watched entity and emit a per-entity verdict with evidence, source URL, and `checked_at`. |
| FR-4 | Recreate all three article figures as generated SVG from a canonical model. No raster copying. |
| FR-5 | Render a single self-contained HTML page: recreated diagrams, full technical content, and a per-entity status strip. |
| FR-6 | Page content reflects current Microsoft truth. Machine-extractable facts render from live evidence; narrative claims are fingerprinted and fail closed when their source moves. |
| FR-7 | Publish to GitHub Pages on a daily schedule and on manual dispatch. |
| FR-8 | Export the brief as PDF, downloadable from the page. |
| FR-9 | Export the brief as an editable PowerPoint deck, downloadable from the page. |
| FR-10 | Each diagram is individually saveable as SVG and as PNG at 1x/2x/4x, via explicit download controls. |
| FR-11 | When a claim cannot be re-verified, fail closed and open a GitHub issue containing the before/after diff. |

## 3. Architecture

### 3.1 Repository

- GitHub: `thomaswillner/sentinel-ai-agent-security`
- Local clone: `~/Projects/cybersecurity/sentinel-ai-agent-security`
- Pages: `https://thomaswillner.github.io/sentinel-ai-agent-security/`
- All work happens on branches in linked worktrees, merged via PR. Never commit on a
  primary checkout.

### 3.2 Layout

```
model/        entities.yaml    watched entities: id, name, kind, learn_url, expected status
              diagram.yaml     nodes, columns, edges, labels for all three figures
              content.yaml     section narrative; each claim bound to an entity + source
sources/      article.py       Khoros API -> normalised JSON + hash
              learn.py         pinned Learn pages -> status, tables, banners, fingerprint
              feeds.py         Azure Updates + M365 roadmap, filtered to entity names
              guide.py         SCStelz/security-investigator hunting guide (raw)
state/        evidence/*.json  committed per-source snapshots (audit trail)
              reconciliation.json  per-entity verdicts for this run
build/        generate_svg.py  model -> dist/*.svg  (theme-aware, standalone)
              render_raster.py rsvg-convert -> dist/*.png at 1x/2x/4x
              generate_html.py model + reconciliation -> dist/index.html
              generate_pdf.py  headless Chromium -> dist/brief.pdf
              generate_pptx.py model + reconciliation -> dist/brief.pptx
validate/     validate_all.py  schema, model, generated-view drift
              test_negative.py known-bad fixtures that MUST fail
              visual_gate.py   rsvg-convert + tesseract OCR coverage check
.github/workflows/refresh.yml  cron + dispatch: sweep -> validate -> generate -> publish
docs/         HLD, LLD, FR/NFR, ADRs (repo onboarding contract)
```

### 3.3 Determinism

Same inputs produce byte-identical outputs. Guarantees:

- No LLM, no network calls, and no clock reads inside generators. Generators consume only
  `model/` and `state/reconciliation.json`.
- All network access is confined to `sources/`, which writes timestamped evidence to
  `state/evidence/` and nothing else.
- Timestamps enter generated artifacts only from `reconciliation.json`'s `checked_at`
  fields, never from `datetime.now()` at render time.
- Ordering is explicit everywhere. No set or dict iteration order in output paths.

### 3.4 Claim binding — how "rewrite to current truth" stays deterministic

Claims are split by extractability:

- **Extractable** — connector table lists, GA/preview status, deprecation banners, schema
  attribute names, page titles. The page renders the value extracted from the live page.
  Rewriting is a re-read; no judgment is involved.
- **Narrative** — architectural explanation and analysis. Held in `model/content.yaml`,
  each bound to one or more entities plus a source fingerprint. When a fingerprint moves,
  the build fails closed, opens an issue with the diff, and the model is updated by PR.

The page therefore never silently drifts and never silently freezes.

## 4. Watchlist

Every entity is pinned to an authoritative `learn.microsoft.com` URL.

**Platforms:** Microsoft 365 Copilot · Copilot Studio · Microsoft Foundry (article says
"Azure AI Foundry Agents") · Security Copilot · Agent 365 · Microsoft Sentinel · Sentinel
Data Lake · Defender XDR · Defender for AI · Defender for Cloud · Microsoft Purview ·
Microsoft Entra Agent ID

**Tables:** `UnifiedAgentObservability` · `CloudAppEvents` · `CopilotActivity` ·
`SecurityAlert` · `SecurityIncident`

**Connectors:** Agent 365 · Microsoft Agent Identities · Microsoft Copilot Logs ·
Microsoft Defender XDR · Microsoft Defender for Cloud

**Integration surfaces:** Agent 365 Observability SDK · Microsoft OpenTelemetry Distro ·
MCP tooling (`query_lake`, `RunAdvancedHuntingQuery`)

### 4.1 Verdict taxonomy

| Verdict | Meaning |
|---|---|
| `CURRENT` | Present at pinned URL; fingerprint matches expected. |
| `CHANGED` | Present; content fingerprint moved. Needs review. |
| `RENAMED` | Canonical URL redirects, or page title no longer matches expected name. |
| `DEPRECATED` | Deprecation, retirement, or supersession language detected. |
| `NOT_FOUND` | 404 or 410. |
| `UNREACHABLE` | Network failure or 5xx. **Inconclusive** — never counted as a pass, own exit code. |

`UNREACHABLE` is structurally distinct from `CURRENT`. A sweep that cannot reach a source
reports inconclusive and fails the run; it never reports "nothing changed".

### 4.2 Seed findings (day one)

Already evidenced during design; these ship as the first reconciliation results and double
as regression fixtures:

1. **`UnifiedAgentObservability`** — the article's central table claim. Learn's Agent 365
   connector reference currently lists no Log Analytics tables and describes data landing
   in the Sentinel data lake; the Agent 365 attribute reference maps attributes to
   `CloudAppEvents.RawEventData`. Requires verification, not reproduction.
2. **Agent 365 Observability SDK** — superseded. Learn directs new integrations to the
   Microsoft OpenTelemetry Distro.
3. **Azure AI Foundry → Microsoft Foundry** — rename; article uses the former.

## 5. Outputs

| Artifact | Path | Notes |
|---|---|---|
| Brief | `dist/index.html` | Self-contained, theme-aware, responsive, print-styled. |
| Diagrams | `dist/<fig>.svg` | Standalone, theme-aware, text as real `<text>` nodes. |
| Rasters | `dist/<fig>@{1x,2x,4x}.png` | Rendered by `rsvg-convert`. |
| PDF | `dist/brief.pdf` | Headless Chromium print of `index.html`. |
| Deck | `dist/brief.pptx` | `python-pptx`; diagrams embedded at 4x. |

### 5.1 Export requirements

**PDF (FR-8).** `@media print` rules give explicit page breaks, expand any collapsed
content, and print link URLs. CI additionally produces `dist/brief.pdf` via headless
Chromium so a deterministic PDF exists as a build artifact, not only as a browser action.
The page carries a direct download link to it.

**PowerPoint (FR-9).** Generated from the same canonical model by `python-pptx`, not
converted from HTML. One slide per content section, a full-bleed diagram slide per figure,
and a reconciliation-status slide. Text is real text boxes and diagrams are embedded 4x
PNGs, so the deck is editable in PowerPoint rather than a flat image dump.

**Image saving (FR-10).** Inline SVG is not reliably right-click-saveable, so each figure
carries explicit download controls for SVG and PNG at 1x/2x/4x. All are real files in
`dist/`, served by Pages, linked with `<a download>` — which works on Pages (unlike inside
a sandboxed artifact viewer). A standalone PNG is also present so right-click → Save image
behaves as users expect.

## 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Deterministic build: identical inputs produce byte-identical `dist/`. Enforced by a re-run-and-diff check in CI. |
| NFR-2 | Fail closed. Any unverifiable claim, unreachable source, or failed gate fails the run and publishes nothing. |
| NFR-3 | No secrets. All sources are unauthenticated public endpoints. |
| NFR-4 | No Microsoft-copyrighted prose or imagery in the repository or the published site. |
| NFR-5 | Page is responsive, theme-aware (light/dark), and accessible: real text in SVG, alt text, WCAG AA contrast. |
| NFR-6 | Full refresh completes within the GitHub-hosted runner default timeout. |
| NFR-7 | Every published claim carries a source URL and a `checked_at` timestamp. |

## 7. Reliability gates

Approval was conditional on proven reliability. These gates are the proof, and each must be
demonstrated failing before it is trusted.

| Gate | Proves | Known-bad fixture that must FAIL |
|---|---|---|
| G1 schema | Model conforms; no unknown keys, no dangling edges. | Model with a dangling edge and an unknown key. |
| G2 negative sweep | Drift is actually detected. | Fixture pages: a planted deprecation banner, a renamed table, a 404. Each must produce `DEPRECATED` / `RENAMED` / `NOT_FOUND`, never `CURRENT`. |
| G3 inconclusive | Unreachable ≠ pass. | Source stubbed to 503 must exit `UNREACHABLE` with its own exit code. |
| G4 visual OCR | The generated diagram is legible, not merely well-formed. | SVG with text moved off-canvas or shrunk below threshold must fail OCR coverage. |
| G5 determinism | No hidden nondeterminism. | Two consecutive builds from identical inputs must diff clean; a `datetime.now()` in a generator must break it. |
| G6 export integrity | Exports actually contain the content. | PPTX with expected slide count and per-slide text assertions; PDF page count and text-extraction assertions; PNG dimensions and OCR. A truncated diagram must fail. |
| G7 link integrity | Every cited source resolves. | A planted dead link must fail the run. |

Verification order is mandatory: **each gate is run against its known-bad fixture and
required to fail before any passing result from it is trusted.** A gate that has never
failed has not been shown to work.

## 8. Scheduling

GitHub Actions, `cron: '0 6 * * *'` (06:00 UTC daily) plus `workflow_dispatch`. Drift in
this domain moves in days. Each run: sweep → validate → generate → diff → commit only if
changed → deploy Pages. On gate failure: no publish, open an issue with evidence.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Khoros API is undocumented and may change or restrict. | Treated as one source among several; failure is `UNREACHABLE`, not silent. Article body is already captured in `state/evidence/`. Rendered-page fallback documented in the LLD. |
| Learn page restructuring produces false `CHANGED` noise. | Fingerprint targets extracted semantic fields, not whole-page hashes. Section anchors pinned per entity. |
| Feed filtering misses a sundown announced only in a blog. | Watchlist re-measurement is the primary detector; feeds are a secondary early-warning path. Documented limitation. |
| Rename detection via title match is brittle. | Combine redirect-chain inspection with title comparison; ambiguous results are `CHANGED` and reviewed, never auto-applied. |
| Copyright. | No verbatim prose, no Microsoft imagery. Own synthesis and own recreated diagrams, with attribution and links. |

## 10. Open decisions

None. Runtime (GitHub Actions → Pages), drift policy (rewrite to current truth, as a
derived brief), and watch scope (watchlist + filtered feeds) are settled. Cron at 06:00 UTC
and the no-verbatim/no-Microsoft-imagery constraint are design decisions recorded here.
