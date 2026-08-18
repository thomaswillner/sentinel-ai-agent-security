# Sentinel AI Agent Security — Living Brief

A self-updating brief on securing enterprise AI agents with Microsoft Sentinel.

Derived from ["Securing Enterprise AI Agents with Microsoft Sentinel"](https://techcommunity.microsoft.com/blog/coreinfrastructureandsecurityblog/securing-enterprise-ai-agents-with-microsoft-sentinel/4542583)
by SantoshPargi (2026-07-31), and continuously reconciled against Microsoft Learn.

**Live page:** https://thomaswillner.github.io/sentinel-ai-agent-security/

## How it works

Two independent update axes:

1. **The source article changes** — detected exactly via the Khoros REST API (`last_edit_time` + body hash).
2. **Microsoft reality drifts away from the article** — every named entity is pinned to an
   authoritative `learn.microsoft.com` URL and re-measured on each run.

A daily GitHub Action sweeps both, writes `state/reconciliation.json`, regenerates the page,
diagrams and exports, and publishes to Pages. Generators never touch the network or the clock,
so builds are byte-reproducible.

## Design rules

- **Fail closed.** Unreachable source, unverifiable claim or failed gate aborts the run and
  publishes nothing. `UNREACHABLE` is never counted as a pass.
- **No LLM in the build path.** Facts are extracted from live pages; narrative is fingerprinted
  and flagged for review when its source moves.
- **Derived brief, not a reproduction.** No Microsoft prose or imagery is republished. Diagrams
  are generated from `model/diagram.yaml`; prose is our own synthesis, with attribution and links.

## Exit codes

`0` success · `2` drift needs review · `3` inconclusive/unreachable · `4` gate failure

## Layout

| Path | Role |
|---|---|
| `model/` | Canonical model: watched entities, figures, content |
| `src/sasb/` | Sources (network), generators (pure), gates |
| `state/reconciliation.json` | Per-entity verdicts with evidence and timestamps |
| `dist/` | Generated site: HTML, SVG, PNG, PDF, PPTX |

Spec: `docs/superpowers/specs/2026-08-18-sentinel-ai-agent-security-design.md`
