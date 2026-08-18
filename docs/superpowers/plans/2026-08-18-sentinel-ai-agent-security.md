# Sentinel AI Agent Security — Living Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, self-updating GitHub Pages brief on securing enterprise AI agents with Microsoft Sentinel, whose factual claims are continuously reconciled against authoritative Microsoft Learn pages, with model-generated diagrams and PDF/PPTX/PNG exports.

**Architecture:** A canonical model (`model/*.yaml`) plus a network-only evidence layer (`sources/`) that writes `state/reconciliation.json`. Pure generators (`build/`) consume model + reconciliation and emit `dist/` — HTML, SVG, PNG, PDF, PPTX. Generators never touch the network or the clock, so builds are byte-reproducible. Every gate is proven by a known-bad fixture that must fail first.

**Tech Stack:** Python 3.11, PyYAML, `jsonschema`, `pytest`, `python-pptx`, `rsvg-convert` (librsvg), `tesseract`, Playwright Chromium (PDF), GitHub Actions + Pages.

**Spec:** `docs/superpowers/specs/2026-08-18-sentinel-ai-agent-security-design.md`

## Global Constraints

- Python 3.11+. Standard library plus: `PyYAML`, `jsonschema`, `python-pptx`, `pytest`. No network libraries beyond `urllib.request`.
- **Generators are pure.** Nothing under `build/` may import `urllib`, `requests`, `socket`, or call `datetime.now()` / `time.time()` / `random`. Enforced by a test that greps the module source.
- **All timestamps** in output come from `reconciliation.json` `checked_at` fields. Never from render-time clock reads.
- **Fail closed.** Any unverifiable claim, unreachable source, or failed gate aborts the run and publishes nothing.
- **Exit codes:** `0` success · `2` drift needs review · `3` inconclusive/unreachable · `4` gate failure. `UNREACHABLE` is never counted as a pass.
- **No Microsoft-copyrighted prose or imagery** in the repo or published site. Diagrams are generated from our model; prose is our own synthesis with attribution and links.
- **Deterministic ordering.** Every iteration over a mapping in an output path sorts explicitly. No reliance on dict/set order.
- Repo work happens on branches in linked worktrees, merged via PR. Never commit on a primary checkout.
- Source article: TechCommunity message id `4542583`, author `SantoshPargi`, published `2026-07-31T02:30:39Z`.

---

## File Structure

| Path | Responsibility |
|---|---|
| `model/schema/entities.schema.json` | JSON Schema for the entity watchlist. |
| `model/schema/diagram.schema.json` | JSON Schema for figure definitions. |
| `model/entities.yaml` | The ~22 watched entities with pinned Learn URLs. |
| `model/diagram.yaml` | Node/column/edge definitions for all three figures. |
| `model/content.yaml` | Section narrative, each claim bound to entity ids. |
| `src/sasb/http_evidence.py` | The only network egress. Fetch, redirect capture, error classification. |
| `src/sasb/verdicts.py` | `Verdict` enum + exit-code mapping. Zero dependencies. |
| `src/sasb/learn_probe.py` | Learn page → verdict + extracted evidence. |
| `src/sasb/article.py` | Khoros API → normalised article record + body hash. |
| `src/sasb/feeds.py` | Azure Updates / M365 roadmap, filtered to entity names. |
| `src/sasb/reconcile.py` | Orchestrator → `state/reconciliation.json`. CLI entry. |
| `src/sasb/build/svg.py` | Model → standalone theme-aware SVG per figure. |
| `src/sasb/build/raster.py` | SVG → PNG at 1x/2x/4x via `rsvg-convert`. |
| `src/sasb/build/html.py` | Model + reconciliation → `dist/index.html`. |
| `src/sasb/build/pdf.py` | `index.html` → `dist/brief.pdf` via headless Chromium. |
| `src/sasb/build/pptx.py` | Model + reconciliation → `dist/brief.pptx`. |
| `src/sasb/gates/visual.py` | G4: render + OCR coverage check. |
| `src/sasb/gates/links.py` | G7: every cited URL resolves. |
| `tests/` | Unit tests + `tests/fixtures/` known-bad pages. |
| `.github/workflows/refresh.yml` | Daily cron: sweep → validate → generate → publish. |
| `docs/` | HLD, LLD, FR/NFR, ADRs. |

---

## Task 1: Repository genesis and CI baseline

**Files:**
- Create: `pyproject.toml`, `README.md`, `.gitignore`
- Create: `src/sasb/__init__.py`, `tests/test_smoke.py`
- Create: `docs/HLD.md`, `docs/LLD.md`, `docs/FR-NFR.md`, `docs/adr/0001-record-architecture-decisions.md`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: nothing.
- Produces: package `sasb` importable from `src/`; `pytest` runnable; green CI.

- [ ] **Step 1: Create the GitHub repo and a working branch**

```bash
cd ~/Projects/cybersecurity/sentinel-ai-agent-security
gh repo create thomaswillner/sentinel-ai-agent-security \
  --public --description "Self-updating brief: securing enterprise AI agents with Microsoft Sentinel" \
  --disable-wiki
git init -b main
git remote add origin https://github.com/thomaswillner/sentinel-ai-agent-security.git
printf 'dist/\n__pycache__/\n*.pyc\n.venv/\n.pytest_cache/\nstate/cache/\n' > .gitignore
git add .gitignore docs
git commit -m "chore: repository genesis with approved spec"
git push -u origin main
git checkout -b feat/reconciliation-engine
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "sasb"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["PyYAML>=6.0", "jsonschema>=4.21", "python-pptx>=1.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 3: Write the smoke test**

```python
# tests/test_smoke.py
import sasb


def test_package_imports():
    assert sasb.__name__ == "sasb"
```

- [ ] **Step 4: Run it and verify it passes**

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_smoke.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Write the docs contract**

`docs/HLD.md` — one page: purpose, the two update axes (article change vs Microsoft drift), the pure-generator boundary, the fail-closed rule.
`docs/LLD.md` — module table from the File Structure section above, plus the `reconciliation.json` schema (defined in Task 6).
`docs/FR-NFR.md` — copy FR-1..11 and NFR-1..7 verbatim from the spec.
`docs/adr/0001-record-architecture-decisions.md` — ADR-0001: we use ADRs. Then record ADR-0002 (rewrite-to-current-truth as a derived brief, not a reproduction), ADR-0003 (no LLM in the build path), ADR-0004 (fail closed on unreachable sources).

- [ ] **Step 6: Write CI**

```yaml
# .github/workflows/ci.yml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: sudo apt-get update && sudo apt-get install -y librsvg2-bin tesseract-ocr
      - run: pip install -e ".[dev]"
      - run: pytest -v
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: project skeleton, docs contract, CI baseline"
```

---

## Task 2: Entity model, schema, and the G1 schema gate

**Files:**
- Create: `model/schema/entities.schema.json`, `model/entities.yaml`
- Create: `src/sasb/model.py`
- Test: `tests/test_model_schema.py`, `tests/fixtures/bad_entities_unknown_key.yaml`, `tests/fixtures/bad_entities_dup_id.yaml`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_entities(path: Path) -> list[Entity]`; `Entity` dataclass with fields `id: str`, `name: str`, `kind: str`, `learn_url: str`, `expected_status: str`, `article_name: str | None`, `anchor: str | None`. Raises `ModelError` on any schema violation.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_schema.py
from pathlib import Path
import pytest
from sasb.model import load_entities, ModelError

FIX = Path(__file__).parent / "fixtures"


def test_real_model_loads_and_is_nonempty():
    ents = load_entities(Path("model/entities.yaml"))
    assert len(ents) >= 20
    assert all(e.learn_url.startswith("https://learn.microsoft.com/") for e in ents)


def test_unknown_key_is_rejected():
    with pytest.raises(ModelError, match="unknown"):
        load_entities(FIX / "bad_entities_unknown_key.yaml")


def test_duplicate_id_is_rejected():
    with pytest.raises(ModelError, match="duplicate"):
        load_entities(FIX / "bad_entities_dup_id.yaml")
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pytest tests/test_model_schema.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sasb.model'`.

- [ ] **Step 3: Write the schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["entities"],
  "properties": {
    "entities": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "name", "kind", "learn_url", "expected_status"],
        "properties": {
          "id": { "type": "string", "pattern": "^[a-z0-9-]+$" },
          "name": { "type": "string", "minLength": 1 },
          "kind": { "enum": ["platform", "table", "connector", "integration"] },
          "learn_url": { "type": "string", "pattern": "^https://learn\\.microsoft\\.com/" },
          "expected_status": { "enum": ["ga", "preview", "superseded"] },
          "article_name": { "type": "string" },
          "anchor": { "type": "string" }
        }
      }
    }
  }
}
```

- [ ] **Step 4: Write `model/entities.yaml`**

Every URL below was verified to return HTTP 200 on 2026-08-18. `article_name` is set only where the article's wording differs from Microsoft's current wording — that difference is itself a finding.

```yaml
entities:
  # --- platforms ---
  - id: agent-365
    name: Microsoft Agent 365
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability-concepts
    expected_status: ga
  - id: m365-copilot
    name: Microsoft 365 Copilot
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-overview
    expected_status: ga
  - id: copilot-studio
    name: Microsoft Copilot Studio
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/microsoft-copilot-studio/fundamentals-what-is-copilot-studio
    expected_status: ga
  - id: foundry
    name: Microsoft Foundry
    article_name: Azure AI Foundry Agents
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/azure/foundry/what-is-foundry
    expected_status: ga
  - id: security-copilot
    name: Microsoft Security Copilot
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/copilot/security/microsoft-security-copilot
    expected_status: ga
  - id: sentinel
    name: Microsoft Sentinel
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/azure/sentinel/overview
    expected_status: ga
  - id: sentinel-data-lake
    name: Microsoft Sentinel Data Lake
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/azure/sentinel/datalake/sentinel-lake-overview
    expected_status: ga
  - id: defender-xdr
    name: Microsoft Defender XDR
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/defender-xdr/microsoft-365-defender
    expected_status: ga
  - id: defender-for-ai
    name: Microsoft Defender for Cloud AI threat protection
    article_name: Defender for AI
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/azure/defender-for-cloud/ai-threat-protection
    expected_status: ga
  - id: defender-for-cloud
    name: Microsoft Defender for Cloud
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/azure/defender-for-cloud/defender-for-cloud-introduction
    expected_status: ga
  - id: purview
    name: Microsoft Purview
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/purview/purview
    expected_status: ga
  - id: entra-agent-id
    name: Microsoft Entra Agent ID
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/entra/agent-id/what-is-microsoft-entra-agent-id
    expected_status: preview

  # --- tables ---
  - id: unified-agent-observability
    name: UnifiedAgentObservability
    kind: table
    learn_url: https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference
    anchor: agent-365
    expected_status: preview
  - id: cloud-app-events
    name: CloudAppEvents
    kind: table
    learn_url: https://learn.microsoft.com/en-us/defender-xdr/advanced-hunting-cloudappevents-table
    expected_status: ga
  - id: copilot-activity
    name: CopilotActivity
    kind: table
    learn_url: https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference
    expected_status: preview
  - id: security-alert
    name: SecurityAlert
    kind: table
    learn_url: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/securityalert
    expected_status: ga
  - id: security-incident
    name: SecurityIncident
    kind: table
    learn_url: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/securityincident
    expected_status: ga

  # --- connectors ---
  - id: conn-agent-365
    name: Agent 365 data connector
    kind: connector
    learn_url: https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference
    anchor: agent-365
    expected_status: preview
  - id: conn-defender-xdr
    name: Microsoft Defender XDR connector
    kind: connector
    learn_url: https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference
    expected_status: ga
  - id: conn-defender-cloud
    name: Microsoft Defender for Cloud connector
    kind: connector
    learn_url: https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference
    expected_status: ga

  # --- integration surfaces ---
  - id: a365-observability-sdk
    name: Agent 365 Observability SDK
    kind: integration
    learn_url: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability
    expected_status: superseded
  - id: ms-otel-distro
    name: Microsoft OpenTelemetry Distro
    kind: integration
    learn_url: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/microsoft-opentelemetry
    expected_status: ga
  - id: a365-attribute-reference
    name: Agent 365 observability attribute reference
    kind: integration
    learn_url: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability-attribute-reference
    expected_status: ga
```

- [ ] **Step 5: Write the known-bad fixtures**

```yaml
# tests/fixtures/bad_entities_unknown_key.yaml
entities:
  - id: sentinel
    name: Microsoft Sentinel
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/azure/sentinel/overview
    expected_status: ga
    surprise_field: this key is not in the schema
```

```yaml
# tests/fixtures/bad_entities_dup_id.yaml
entities:
  - id: sentinel
    name: Microsoft Sentinel
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/azure/sentinel/overview
    expected_status: ga
  - id: sentinel
    name: Microsoft Sentinel Again
    kind: platform
    learn_url: https://learn.microsoft.com/en-us/azure/sentinel/overview
    expected_status: ga
```

- [ ] **Step 6: Implement `src/sasb/model.py`**

```python
"""Canonical model loading with strict schema validation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import yaml

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "model" / "schema"


class ModelError(Exception):
    """Raised when the canonical model violates its contract."""


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    kind: str
    learn_url: str
    expected_status: str
    article_name: str | None = None
    anchor: str | None = None


def _validate(doc: dict, schema_name: str) -> None:
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        kind = "unknown key" if "Additional properties" in first.message else first.message
        raise ModelError(f"{schema_name}: {kind} at {list(first.path)}")


def load_entities(path: Path) -> list[Entity]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    _validate(doc, "entities.schema.json")
    entities = [Entity(**item) for item in doc["entities"]]
    seen: set[str] = set()
    for e in entities:
        if e.id in seen:
            raise ModelError(f"duplicate entity id: {e.id}")
        seen.add(e.id)
    return sorted(entities, key=lambda e: e.id)
```

- [ ] **Step 7: Run the tests and verify they pass**

```bash
pytest tests/test_model_schema.py -v
```
Expected: 3 passed. The two fixture tests prove G1 rejects bad input — a schema gate that has only ever seen good input has not been shown to work.

- [ ] **Step 8: Commit**

```bash
git add model tests/test_model_schema.py tests/fixtures src/sasb/model.py
git commit -m "feat: entity watchlist model with strict schema gate (G1)"
```

---

## Task 3: HTTP evidence layer and the G3 inconclusive gate

**Files:**
- Create: `src/sasb/verdicts.py`, `src/sasb/http_evidence.py`
- Test: `tests/test_http_evidence.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Verdict` str-enum: `CURRENT`, `CHANGED`, `RENAMED`, `DEPRECATED`, `NOT_FOUND`, `UNREACHABLE`.
  - `exit_code_for(verdicts: list[Verdict]) -> int` returning `0|2|3`.
  - `FetchResult` dataclass: `url: str`, `final_url: str`, `status: int`, `body: str`, `error: str | None`, `redirected: bool`.
  - `fetch(url: str, *, timeout: int = 30) -> FetchResult`. Never raises on network failure; returns `status=0` with `error` set.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_http_evidence.py
from sasb.verdicts import Verdict, exit_code_for


def test_all_current_is_success():
    assert exit_code_for([Verdict.CURRENT, Verdict.CURRENT]) == 0


def test_drift_is_exit_two():
    assert exit_code_for([Verdict.CURRENT, Verdict.DEPRECATED]) == 2


def test_unreachable_outranks_drift_and_is_exit_three():
    # Inconclusive must never be laundered into a pass or a mere review flag.
    assert exit_code_for([Verdict.CURRENT, Verdict.DEPRECATED, Verdict.UNREACHABLE]) == 3


def test_unreachable_alone_is_never_success():
    assert exit_code_for([Verdict.UNREACHABLE]) != 0
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pytest tests/test_http_evidence.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sasb.verdicts'`.

- [ ] **Step 3: Implement `src/sasb/verdicts.py`**

```python
"""Verdict taxonomy and exit-code policy.

Exit codes: 0 success | 2 drift needs review | 3 inconclusive | 4 gate failure.
UNREACHABLE outranks every other verdict: a sweep that could not measure a
source reports inconclusive, never "nothing changed".
"""
from __future__ import annotations

from enum import StrEnum

EXIT_OK = 0
EXIT_DRIFT = 2
EXIT_INCONCLUSIVE = 3
EXIT_GATE_FAILURE = 4


class Verdict(StrEnum):
    CURRENT = "CURRENT"
    CHANGED = "CHANGED"
    RENAMED = "RENAMED"
    DEPRECATED = "DEPRECATED"
    NOT_FOUND = "NOT_FOUND"
    UNREACHABLE = "UNREACHABLE"


DRIFT_VERDICTS = frozenset(
    {Verdict.CHANGED, Verdict.RENAMED, Verdict.DEPRECATED, Verdict.NOT_FOUND}
)


def exit_code_for(verdicts: list[Verdict]) -> int:
    if Verdict.UNREACHABLE in verdicts:
        return EXIT_INCONCLUSIVE
    if any(v in DRIFT_VERDICTS for v in verdicts):
        return EXIT_DRIFT
    return EXIT_OK
```

- [ ] **Step 4: Implement `src/sasb/http_evidence.py`**

```python
"""The only network egress in the project.

Returns a FetchResult for every outcome. Network failures are data, not
exceptions, so callers must classify them explicitly rather than letting a
try/except swallow them into a pass.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass

USER_AGENT = "sentinel-ai-agent-security/0.1 (+https://github.com/thomaswillner/sentinel-ai-agent-security)"


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status: int
    body: str
    error: str | None = None

    @property
    def redirected(self) -> bool:
        return self.status != 0 and self.final_url.rstrip("/") != self.url.rstrip("/")

    @property
    def ok(self) -> bool:
        return self.status == 200


def fetch(url: str, *, timeout: int = 30) -> FetchResult:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return FetchResult(
                url=url,
                final_url=resp.geturl(),
                status=resp.status,
                body=raw.decode(charset, errors="replace"),
            )
    except urllib.error.HTTPError as exc:
        return FetchResult(url, url, exc.code, "", error=f"HTTP {exc.code}")
    except Exception as exc:  # network, DNS, TLS, timeout
        return FetchResult(url, url, 0, "", error=f"{type(exc).__name__}: {exc}")
```

- [ ] **Step 5: Run the tests and verify they pass**

```bash
pytest tests/test_http_evidence.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/sasb/verdicts.py src/sasb/http_evidence.py tests/test_http_evidence.py
git commit -m "feat: verdict taxonomy and network evidence layer (G3 inconclusive gate)"
```

---

## Task 4: Learn probe and the G2 negative-detection gate

**Files:**
- Create: `src/sasb/learn_probe.py`
- Test: `tests/test_learn_probe.py`
- Test fixtures: `tests/fixtures/learn_ok.html`, `tests/fixtures/learn_deprecated.html`, `tests/fixtures/learn_renamed_title.html`

**Interfaces:**
- Consumes: `Entity` (Task 2), `FetchResult`/`fetch` (Task 3), `Verdict` (Task 3).
- Produces:
  - `Probe` dataclass: `entity_id: str`, `verdict: Verdict`, `title: str | None`, `status_detected: str | None`, `evidence: list[str]`, `final_url: str`, `fingerprint: str`.
  - `classify(entity: Entity, result: FetchResult) -> Probe` — pure, no network. This is what the tests drive.
  - `probe(entity: Entity) -> Probe` — thin wrapper: `classify(entity, fetch(entity.learn_url))`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_learn_probe.py
from pathlib import Path

from sasb.http_evidence import FetchResult
from sasb.learn_probe import classify
from sasb.model import Entity
from sasb.verdicts import Verdict

FIX = Path(__file__).parent / "fixtures"
URL = "https://learn.microsoft.com/en-us/azure/sentinel/overview"


def _entity(**kw) -> Entity:
    base = dict(
        id="sentinel", name="Microsoft Sentinel", kind="platform",
        learn_url=URL, expected_status="ga",
    )
    base.update(kw)
    return Entity(**base)


def _result(fixture: str, status: int = 200, final: str | None = None) -> FetchResult:
    return FetchResult(URL, final or URL, status, (FIX / fixture).read_text())


def test_healthy_page_is_current():
    p = classify(_entity(), _result("learn_ok.html"))
    assert p.verdict is Verdict.CURRENT


def test_planted_deprecation_banner_is_detected():
    p = classify(_entity(), _result("learn_deprecated.html"))
    assert p.verdict is Verdict.DEPRECATED
    assert any("retire" in e.lower() or "deprecat" in e.lower() for e in p.evidence)


def test_title_change_is_renamed():
    p = classify(_entity(), _result("learn_renamed_title.html"))
    assert p.verdict is Verdict.RENAMED


def test_redirect_to_different_path_is_renamed():
    p = classify(
        _entity(),
        _result("learn_ok.html", final="https://learn.microsoft.com/en-us/azure/foundry/what-is-foundry"),
    )
    assert p.verdict is Verdict.RENAMED


def test_404_is_not_found():
    p = classify(_entity(), FetchResult(URL, URL, 404, "", error="HTTP 404"))
    assert p.verdict is Verdict.NOT_FOUND


def test_503_is_unreachable_not_current():
    p = classify(_entity(), FetchResult(URL, URL, 503, "", error="HTTP 503"))
    assert p.verdict is Verdict.UNREACHABLE


def test_network_failure_is_unreachable():
    p = classify(_entity(), FetchResult(URL, URL, 0, "", error="URLError: boom"))
    assert p.verdict is Verdict.UNREACHABLE
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pytest tests/test_learn_probe.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sasb.learn_probe'`.

- [ ] **Step 3: Write the fixtures**

```html
<!-- tests/fixtures/learn_ok.html -->
<html><head><title>Microsoft Sentinel | Microsoft Learn</title></head>
<body><main><h1>Microsoft Sentinel</h1>
<p>Microsoft Sentinel is a cloud-native SIEM and SOAR solution.</p></main></body></html>
```

```html
<!-- tests/fixtures/learn_deprecated.html -->
<html><head><title>Microsoft Sentinel | Microsoft Learn</title></head>
<body><main><h1>Microsoft Sentinel</h1>
<div class="alert"><p>This feature is deprecated and will be retired on 30 June 2027.</p></div>
</main></body></html>
```

```html
<!-- tests/fixtures/learn_renamed_title.html -->
<html><head><title>Contoso Threat Cloud | Microsoft Learn</title></head>
<body><main><h1>Contoso Threat Cloud</h1>
<p>Everything has been renamed.</p></main></body></html>
```

- [ ] **Step 4: Implement `src/sasb/learn_probe.py`**

```python
"""Classify a Microsoft Learn page into a drift verdict.

`classify` is pure so the detector can be driven by known-bad fixtures. A
detector that has only ever seen healthy pages has not been shown to work.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .http_evidence import FetchResult, fetch
from .model import Entity
from .verdicts import Verdict

DEPRECATION_PATTERNS = (
    r"\bdeprecat\w*",
    r"\bretir(?:e|ed|ement|ing)\b",
    r"\bwill be removed\b",
    r"\bno longer the recommended\b",
    r"\bsupersed\w*",
    r"\bend of support\b",
)
_DEPRECATION_RE = re.compile("|".join(DEPRECATION_PATTERNS), re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_PREVIEW_RE = re.compile(r"\bis currently in PREVIEW\b|\bin preview\b", re.IGNORECASE)


@dataclass(frozen=True)
class Probe:
    entity_id: str
    verdict: Verdict
    title: str | None
    status_detected: str | None
    final_url: str
    fingerprint: str
    evidence: list[str] = field(default_factory=list)


def _title(body: str) -> str | None:
    m = _TITLE_RE.search(body)
    if not m:
        return None
    return _TAG_RE.sub("", m.group(1)).split("|")[0].strip()


def _normalise(url: str) -> str:
    return url.rstrip("/").split("?")[0].removeprefix("https://learn.microsoft.com")


def _fingerprint(body: str) -> str:
    text = _TAG_RE.sub(" ", body)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def classify(entity: Entity, result: FetchResult) -> Probe:
    def mk(verdict: Verdict, evidence: list[str], title: str | None = None,
           status: str | None = None) -> Probe:
        return Probe(entity.id, verdict, title, status, result.final_url,
                     _fingerprint(result.body), evidence)

    if result.status in (404, 410):
        return mk(Verdict.NOT_FOUND, [f"HTTP {result.status} at {entity.learn_url}"])
    if not result.ok:
        return mk(Verdict.UNREACHABLE, [result.error or f"HTTP {result.status}"])

    title = _title(result.body)
    evidence: list[str] = []

    hits = [m.group(0) for m in _DEPRECATION_RE.finditer(result.body)]
    if hits:
        evidence.append(f"deprecation language: {sorted(set(h.lower() for h in hits))[:5]}")
        return mk(Verdict.DEPRECATED, evidence, title, "superseded")

    if _normalise(result.final_url) != _normalise(entity.learn_url):
        evidence.append(f"redirected to {result.final_url}")
        return mk(Verdict.RENAMED, evidence, title)

    expected_name = entity.name.lower()
    if title and expected_name not in title.lower() and title.lower() not in expected_name:
        evidence.append(f"title is {title!r}, expected to contain {entity.name!r}")
        return mk(Verdict.RENAMED, evidence, title)

    status = "preview" if _PREVIEW_RE.search(result.body) else "ga"
    if status != entity.expected_status:
        evidence.append(f"status is {status}, model expects {entity.expected_status}")
        return mk(Verdict.CHANGED, evidence, title, status)

    return mk(Verdict.CURRENT, ["page reachable, name and status as expected"], title, status)


def probe(entity: Entity) -> Probe:
    return classify(entity, fetch(entity.learn_url))
```

- [ ] **Step 5: Run the tests and verify they pass**

```bash
pytest tests/test_learn_probe.py -v
```
Expected: 7 passed. Four of them are known-bad fixtures — G2 is proven to detect deprecation, rename-by-title, rename-by-redirect, 404, and to refuse to call a 503 a pass.

- [ ] **Step 6: Commit**

```bash
git add src/sasb/learn_probe.py tests/test_learn_probe.py tests/fixtures/learn_*.html
git commit -m "feat: Learn drift probe proven against known-bad fixtures (G2)"
```

---

## Task 5: Article source

**Files:**
- Create: `src/sasb/article.py`
- Test: `tests/test_article.py`, `tests/fixtures/khoros_message.json`

**Interfaces:**
- Consumes: `fetch` (Task 3).
- Produces:
  - `ArticleRecord` dataclass: `message_id: str`, `subject: str`, `author: str`, `post_time: str`, `last_edit_time: str`, `body_html: str`, `body_hash: str`, `labels: list[str]`, `source_url: str`.
  - `parse_article(payload: dict) -> ArticleRecord` — pure.
  - `ARTICLE_API` constant and `load_article() -> ArticleRecord | None` (None on unreachable).

- [ ] **Step 1: Capture the real payload as a fixture**

```bash
curl -sS "https://techcommunity.microsoft.com/t5/s/gxcuf89792/restapi/vc/messages/id/4542583?restapi.response_format=json" \
  -o tests/fixtures/khoros_message.json
python3 -c "import json;d=json.load(open('tests/fixtures/khoros_message.json'));print(d['response']['status'])"
```
Expected: `success`.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_article.py
import json
from pathlib import Path

from sasb.article import parse_article

FIX = Path(__file__).parent / "fixtures"


def test_parses_known_payload():
    payload = json.loads((FIX / "khoros_message.json").read_text())
    rec = parse_article(payload)
    assert rec.message_id == "4542583"
    assert rec.subject == "Securing Enterprise AI Agents with Microsoft Sentinel"
    assert rec.author == "SantoshPargi"
    assert rec.post_time.startswith("2026-07-31")
    assert len(rec.body_html) > 5000
    assert len(rec.body_hash) == 64
    assert "Agent 365" in rec.labels


def test_body_hash_is_stable():
    payload = json.loads((FIX / "khoros_message.json").read_text())
    assert parse_article(payload).body_hash == parse_article(payload).body_hash
```

- [ ] **Step 3: Run it to verify it fails**

```bash
pytest tests/test_article.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sasb.article'`.

- [ ] **Step 4: Implement `src/sasb/article.py`**

```python
"""Fetch the source article from the Khoros v1 REST API.

The rendered TechCommunity page is a client-rendered SPA, so its HTML is not a
usable source. This endpoint returns the message as structured JSON including
post_time and last_edit_time, which give exact change detection.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .http_evidence import fetch

MESSAGE_ID = "4542583"
ARTICLE_API = (
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/restapi/vc/messages/"
    f"id/{MESSAGE_ID}?restapi.response_format=json"
)
ARTICLE_URL = (
    "https://techcommunity.microsoft.com/blog/coreinfrastructureandsecurityblog/"
    f"securing-enterprise-ai-agents-with-microsoft-sentinel/{MESSAGE_ID}"
)


@dataclass(frozen=True)
class ArticleRecord:
    message_id: str
    subject: str
    author: str
    post_time: str
    last_edit_time: str
    body_html: str
    body_hash: str
    labels: list[str]
    source_url: str = ARTICLE_URL


def _scalar(node: object) -> str:
    if isinstance(node, dict):
        value = node.get("$")
        return "" if value is None else str(value)
    return "" if node is None else str(node)


def parse_article(payload: dict) -> ArticleRecord:
    msg = payload["response"]["message"]
    body = _scalar(msg.get("body"))
    labels = sorted(
        _scalar(item.get("text"))
        for item in (msg.get("labels") or {}).get("label", [])
    )
    return ArticleRecord(
        message_id=_scalar(msg.get("id")) or MESSAGE_ID,
        subject=_scalar(msg.get("subject")),
        author=_scalar((msg.get("author") or {}).get("login")),
        post_time=_scalar(msg.get("post_time")),
        last_edit_time=_scalar(msg.get("last_edit_time")),
        body_html=body,
        body_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        labels=labels,
    )


def load_article() -> ArticleRecord | None:
    result = fetch(ARTICLE_API)
    if not result.ok:
        return None
    try:
        return parse_article(json.loads(result.body))
    except (KeyError, json.JSONDecodeError):
        return None
```

- [ ] **Step 5: Run the tests and verify they pass**

```bash
pytest tests/test_article.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/sasb/article.py tests/test_article.py tests/fixtures/khoros_message.json
git commit -m "feat: article source via Khoros API with stable body hash"
```

---

## Task 6: Reconciliation orchestrator

**Files:**
- Create: `src/sasb/reconcile.py`, `model/schema/reconciliation.schema.json`
- Test: `tests/test_reconcile.py`

**Interfaces:**
- Consumes: `load_entities` (T2), `Probe`/`probe` (T4), `ArticleRecord`/`load_article` (T5), `Verdict`/`exit_code_for` (T3).
- Produces:
  - `build_reconciliation(entities, probes, article, checked_at) -> dict` — pure; the exact dict written to `state/reconciliation.json`.
  - `main(argv) -> int` — CLI entry returning the process exit code.
  - `reconciliation.json` shape: `{"schema_version": 1, "checked_at": ISO8601, "article": {...}, "entities": [{"id","name","kind","verdict","status_detected","final_url","fingerprint","evidence","checked_at"}], "summary": {"CURRENT": n, ...}}`. `entities` is sorted by `id`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reconcile.py
from sasb.article import ArticleRecord
from sasb.learn_probe import Probe
from sasb.model import Entity
from sasb.reconcile import build_reconciliation
from sasb.verdicts import Verdict

CHECKED = "2026-08-18T06:00:00Z"


def _ent(i: str) -> Entity:
    return Entity(i, i.title(), "platform", f"https://learn.microsoft.com/en-us/{i}", "ga")


def _probe(i: str, v: Verdict) -> Probe:
    return Probe(i, v, i.title(), "ga", f"https://learn.microsoft.com/en-us/{i}", "abc123", ["e"])


def _article() -> ArticleRecord:
    return ArticleRecord("4542583", "S", "SantoshPargi", "2026-07-31T02:30:39+00:00",
                         "2026-07-31T02:30:39+00:00", "<p>x</p>", "h" * 64, ["Agent 365"])


def test_entities_are_sorted_and_summarised():
    ents = [_ent("zulu"), _ent("alpha")]
    probes = [_probe("zulu", Verdict.CURRENT), _probe("alpha", Verdict.DEPRECATED)]
    doc = build_reconciliation(ents, probes, _article(), CHECKED)
    assert [e["id"] for e in doc["entities"]] == ["alpha", "zulu"]
    assert doc["summary"]["DEPRECATED"] == 1
    assert doc["checked_at"] == CHECKED


def test_every_entity_carries_source_and_timestamp():
    ents = [_ent("alpha")]
    doc = build_reconciliation(ents, [_probe("alpha", Verdict.CURRENT)], _article(), CHECKED)
    row = doc["entities"][0]
    assert row["final_url"].startswith("https://learn.microsoft.com/")
    assert row["checked_at"] == CHECKED


def test_output_is_byte_identical_for_identical_input():
    import json
    ents, probes = [_ent("alpha")], [_probe("alpha", Verdict.CURRENT)]
    a = json.dumps(build_reconciliation(ents, probes, _article(), CHECKED), sort_keys=True)
    b = json.dumps(build_reconciliation(ents, probes, _article(), CHECKED), sort_keys=True)
    assert a == b
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pytest tests/test_reconcile.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sasb.reconcile'`.

- [ ] **Step 3: Implement `src/sasb/reconcile.py`**

```python
"""Orchestrate the sweep and emit state/reconciliation.json.

This module owns the only clock read in the project. Generators receive the
timestamp through the reconciliation document so their output stays
byte-reproducible.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .article import ArticleRecord, load_article
from .learn_probe import Probe, probe
from .model import Entity, load_entities
from .verdicts import EXIT_GATE_FAILURE, EXIT_INCONCLUSIVE, Verdict, exit_code_for

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / "model" / "entities.yaml"
DEFAULT_OUT = ROOT / "state" / "reconciliation.json"
SCHEMA_VERSION = 1


def build_reconciliation(
    entities: list[Entity],
    probes: list[Probe],
    article: ArticleRecord,
    checked_at: str,
) -> dict:
    by_id = {p.entity_id: p for p in probes}
    rows = []
    for entity in sorted(entities, key=lambda e: e.id):
        p = by_id[entity.id]
        rows.append({
            "id": entity.id,
            "name": entity.name,
            "article_name": entity.article_name,
            "kind": entity.kind,
            "verdict": str(p.verdict),
            "status_detected": p.status_detected,
            "final_url": p.final_url,
            "fingerprint": p.fingerprint,
            "evidence": list(p.evidence),
            "checked_at": checked_at,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "checked_at": checked_at,
        "article": {
            "message_id": article.message_id,
            "subject": article.subject,
            "author": article.author,
            "post_time": article.post_time,
            "last_edit_time": article.last_edit_time,
            "body_hash": article.body_hash,
            "labels": list(article.labels),
            "source_url": article.source_url,
        },
        "entities": rows,
        "summary": dict(sorted(Counter(r["verdict"] for r in rows).items())),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reconcile the brief against Microsoft Learn.")
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    entities = load_entities(args.model)
    article = load_article()
    if article is None:
        print("FATAL: article source unreachable; refusing to report currency",
              file=sys.stderr)
        return EXIT_INCONCLUSIVE

    probes = [probe(e) for e in entities]
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_reconciliation(entities, probes, article, checked_at)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for row in doc["entities"]:
        if row["verdict"] != Verdict.CURRENT:
            print(f"{row['verdict']:<12} {row['id']:<28} {'; '.join(row['evidence'])}")
    print(f"summary: {doc['summary']}")

    code = exit_code_for([Verdict(r["verdict"]) for r in doc["entities"]])
    if not doc["entities"]:
        return EXIT_GATE_FAILURE
    return code


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests and verify they pass**

```bash
pytest tests/test_reconcile.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Run the real sweep and inspect the findings**

```bash
python3 -m sasb.reconcile; echo "exit=$?"
```
Expected: exit `2` (drift present). The output must include non-`CURRENT` rows for `foundry` (redirect rename), `a365-observability-sdk` (superseded), and the Agent 365 table entities. Record what it reports in `docs/LLD.md`.

- [ ] **Step 6: Commit**

```bash
git add src/sasb/reconcile.py state/reconciliation.json tests/test_reconcile.py
git commit -m "feat: reconciliation orchestrator with fail-closed exit policy"
```

---

## Task 7: Diagram model, SVG generator, and the G4 visual gate

**Files:**
- Create: `model/schema/diagram.schema.json`, `model/diagram.yaml`
- Create: `src/sasb/build/__init__.py`, `src/sasb/build/svg.py`, `src/sasb/gates/__init__.py`, `src/sasb/gates/visual.py`
- Test: `tests/test_svg.py`, `tests/test_visual_gate.py`

**Interfaces:**
- Consumes: `load_entities` (T2), `ModelError` (T2).
- Produces:
  - `load_diagrams(path) -> list[Figure]`; `Figure` has `id`, `title`, `subtitle`, `width`, `height`, `columns: list[Column]`, `bands: list[Band]`, `steps: list[str]`.
  - `render_svg(figure: Figure) -> str` — standalone SVG string. Pure.
  - `gates.visual.check(svg_path: Path, expect_tokens: list[str], *, scale: int = 4) -> tuple[bool, list[str]]` — renders via `rsvg-convert`, OCRs via `tesseract`, returns (passed, missing_tokens).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_svg.py
from pathlib import Path
from sasb.build.svg import load_diagrams, render_svg


def test_three_figures_defined():
    figs = load_diagrams(Path("model/diagram.yaml"))
    assert {f.id for f in figs} == {"reference-architecture", "prompt-injection-flow", "session-reconstruction"}


def test_svg_is_standalone_and_has_real_text_nodes():
    fig = next(f for f in load_diagrams(Path("model/diagram.yaml")) if f.id == "reference-architecture")
    svg = render_svg(fig)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "<tspan" not in svg          # importer-unsafe; collapses in vector editors
    assert "UnifiedAgentObservability" in svg
    assert 'prefers-color-scheme' in svg  # theme-aware


def test_render_is_deterministic():
    fig = load_diagrams(Path("model/diagram.yaml"))[0]
    assert render_svg(fig) == render_svg(fig)
```

```python
# tests/test_visual_gate.py
from pathlib import Path
import pytest
from sasb.build.svg import load_diagrams, render_svg
from sasb.gates.visual import check

OFFCANVAS = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="120" viewBox="0 0 400 120">
<rect width="400" height="120" fill="#fff"/>
<text x="-9000" y="60" font-size="16" fill="#000">UnifiedAgentObservability</text></svg>"""


def test_healthy_diagram_passes_ocr(tmp_path):
    fig = next(f for f in load_diagrams(Path("model/diagram.yaml")) if f.id == "reference-architecture")
    p = tmp_path / "fig.svg"
    p.write_text(render_svg(fig))
    passed, missing = check(p, ["UnifiedAgentObservability", "CloudAppEvents", "Microsoft Sentinel"])
    assert passed, f"missing from OCR: {missing}"


def test_offcanvas_text_fails_the_gate(tmp_path):
    p = tmp_path / "bad.svg"
    p.write_text(OFFCANVAS)
    passed, missing = check(p, ["UnifiedAgentObservability"])
    assert not passed
    assert "UnifiedAgentObservability" in missing
```

- [ ] **Step 2: Run them to verify they fail**

```bash
pytest tests/test_svg.py tests/test_visual_gate.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sasb.build.svg'`.

- [ ] **Step 3: Write `model/diagram.yaml`**

Recreate the article's three figures from our own model. Figure 1 is a four-column flow with a data-lake band, a SOC-operations band, and a key-benefits band; figures 2 and 3 are linear step chains.

```yaml
figures:
  - id: reference-architecture
    title: Reference Architecture
    subtitle: AI Agent Telemetry Integration with Microsoft Sentinel
    width: 1200
    height: 820
    columns:
      - id: platforms
        heading: AI Platforms
        subheading: Telemetry Sources
        items:
          - { title: Microsoft 365 Copilot, entity: m365-copilot }
          - { title: Copilot Studio Agents, entity: copilot-studio }
          - { title: Microsoft Foundry Agents, entity: foundry }
          - { title: Security Copilot, entity: security-copilot }
          - { title: Third-Party / Custom AI Agents }
      - id: observability
        heading: Security & Observability Layer
        items:
          - { title: Agent 365 Observability, entity: agent-365,
              body: Collects runtime telemetry from Agent 365, Copilot Studio, Foundry and other agents }
          - { title: Microsoft Entra Agent ID, entity: entra-agent-id,
              body: Inventory, ownership, relationships and governance for agents and blueprints }
          - { title: Defender for Cloud AI threat protection, entity: defender-for-ai,
              body: Prompt Shield, XPIA and jailbreak detection }
          - { title: Defender XDR, entity: defender-xdr,
              body: Security detections, incidents, alerts and advanced hunting }
          - { title: Defender for Cloud, entity: defender-for-cloud,
              body: Cloud workload protection and AI related security alerts }
      - id: sentinel
        heading: Microsoft Sentinel
        subheading: Data Layer
        items:
          - { title: UnifiedAgentObservability, entity: unified-agent-observability,
              body: Agent runtime telemetry: prompts, sessions, tool calls, connector invocations, arguments, responses, errors }
          - { title: CloudAppEvents, entity: cloud-app-events,
              body: AI safety signals: Prompt Shield, prompt injection, XPIA, jailbreak verdicts, risk indicators }
          - { title: CopilotActivity, entity: copilot-activity,
              body: Copilot usage and audit logs }
          - { title: SecurityAlert, entity: security-alert,
              body: AI related security alerts from Defender XDR and Defender for Cloud }
          - { title: SecurityIncident, entity: security-incident,
              body: Correlated incidents for investigation and response }
      - id: connectors
        heading: Data Connectors
        items:
          - { title: Agent 365 data connector, entity: conn-agent-365,
              body: Ingests agent runtime telemetry }
          - { title: Microsoft Defender XDR connector, entity: conn-defender-xdr,
              body: Ingests CloudAppEvents, alerts and incidents }
          - { title: Microsoft Defender for Cloud connector, entity: conn-defender-cloud,
              body: Ingests cloud and AI security alerts }
    bands:
      - id: data-lake
        heading: Microsoft Sentinel Data Lake
        entity: sentinel-data-lake
        body: Long-term retention for AI telemetry and security data, for hunting, analytics and investigations
      - id: soc-operations
        heading: SOC Operations & Outcomes
        items:
          - { title: Threat Hunting, body: Hunt malicious prompts, tool usage, data access and agent behavior }
          - { title: Detection Engineering, body: Build analytics rules for prompt injection, jailbreaks and excessive access }
          - { title: Investigations, body: Pivot across prompts, tools, identities and alerts }
          - { title: Incident Response, body: Respond to AI related threats with full context }
          - { title: Governance & Risk, body: Monitor agent inventory, ownership and permissions }
          - { title: Analytics & Reporting, body: Dashboards for AI adoption, usage and security posture }
      - id: key-benefits
        heading: Key Benefits
        items:
          - { title: Unified visibility across all AI agents and platforms }
          - { title: End-to-end correlation of prompts, actions and alerts }
          - { title: Improved security posture and data protection }
          - { title: Stronger governance and agent lifecycle management }
          - { title: Scalable analytics with Sentinel Data Lake }

  - id: prompt-injection-flow
    title: Prompt Injection Investigation
    subtitle: Pivot from a safety signal to agent runtime behavior
    width: 560
    height: 420
    steps:
      - CloudAppEvents
      - Identify Malicious Prompt
      - Obtain Session ID
      - Pivot to Agent Runtime Telemetry
      - Review Tool Activity

  - id: session-reconstruction
    title: Session Reconstruction
    subtitle: Correlate a complete forensic timeline
    width: 560
    height: 420
    steps:
      - User Prompt
      - Agent Invocation
      - Tool Calls
      - Connector Activity
      - Agent Responses
```

- [ ] **Step 4: Write `model/schema/diagram.schema.json`**

Mirror the YAML above: top-level `figures` array, `additionalProperties: false` throughout, `id` pattern `^[a-z0-9-]+$`, `width`/`height` integers with `minimum: 100`, `columns` items requiring `id`/`heading`/`items`, `bands` items requiring `id`/`heading`, `steps` an array of strings with `minItems: 2`. Each figure must have either `columns` or `steps`.

- [ ] **Step 5: Implement `src/sasb/build/svg.py`**

Requirements the tests pin down:
- Emits a standalone `<svg>` with `xmlns`, `viewBox`, `role="img"` and a `<title>`/`<desc>` pair for accessibility.
- Every visible line is one `<text>` element with a numeric absolute `y`. **Never** emit `<tspan>` or relative line offsets — those collapse on import into vector editors.
- Embeds a `<style>` block defining CSS custom properties for the light palette on `:root`, then redefines only those properties inside `@media (prefers-color-scheme: dark)`. All fills reference the variables.
- Long `body` strings are wrapped by a pure helper `wrap(text: str, width_chars: int) -> list[str]`, each line emitted as its own `<text>` at `y + i * line_height`.
- Iterates columns, items and bands in their declared list order (lists, so order is already deterministic); any dict iteration sorts by key.
- No clock, no network, no randomness.

Layout: columns laid out left-to-right with equal width and a fixed gutter; each column is a rounded `rect` with a heading, then item cards stacked vertically; arrows between adjacent columns as `<path>` with a shared `<marker>` arrowhead defined once in `<defs>`. Bands are full-width rounded rects below the columns. For `steps` figures, render a vertical chain of rounded rects joined by arrows.

- [ ] **Step 6: Implement `src/sasb/gates/visual.py`**

```python
"""G4: prove the generated diagram is legible, not merely well-formed."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class ToolMissing(RuntimeError):
    """A required external renderer is unavailable — inconclusive, not a pass."""


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise ToolMissing(f"{tool} not found; cannot verify rendering")
    return path


def check(svg_path: Path, expect_tokens: list[str], *, scale: int = 4) -> tuple[bool, list[str]]:
    rsvg, tess = _require("rsvg-convert"), _require("tesseract")
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "render.png"
        subprocess.run(
            [rsvg, "-z", str(scale), "-o", str(png), str(svg_path)],
            check=True, capture_output=True,
        )
        out = subprocess.run(
            [tess, str(png), "stdout"], check=True, capture_output=True, text=True
        ).stdout
    normalised = " ".join(out.split()).lower()
    missing = [t for t in expect_tokens if t.lower() not in normalised]
    return (not missing), missing
```

- [ ] **Step 7: Run the tests and verify they pass**

```bash
pytest tests/test_svg.py tests/test_visual_gate.py -v
```
Expected: 5 passed. The off-canvas fixture proves G4 actually fails on an illegible diagram.

- [ ] **Step 8: Commit**

```bash
git add model/diagram.yaml model/schema/diagram.schema.json src/sasb/build src/sasb/gates tests/test_svg.py tests/test_visual_gate.py
git commit -m "feat: model-driven SVG figures with OCR legibility gate (G4)"
```

---

## Task 8: Raster export at 1x/2x/4x

**Files:**
- Create: `src/sasb/build/raster.py`
- Test: `tests/test_raster.py`

**Interfaces:**
- Consumes: `render_svg` (T7).
- Produces: `render_pngs(svg_path: Path, out_dir: Path, stem: str, scales=(1,2,4)) -> list[Path]` writing `<stem>@1x.png`, `<stem>@2x.png`, `<stem>@4x.png`. Raises `ToolMissing` if `rsvg-convert` is absent.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_raster.py
import struct
from pathlib import Path

from sasb.build.raster import render_pngs
from sasb.build.svg import load_diagrams, render_svg


def _png_size(p: Path) -> tuple[int, int]:
    data = p.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_three_scales_written_and_sizes_multiply(tmp_path):
    fig = next(f for f in load_diagrams(Path("model/diagram.yaml")) if f.id == "session-reconstruction")
    svg = tmp_path / "f.svg"
    svg.write_text(render_svg(fig))
    outs = render_pngs(svg, tmp_path, "f")
    assert [p.name for p in outs] == ["f@1x.png", "f@2x.png", "f@4x.png"]
    w1, h1 = _png_size(outs[0])
    w4, h4 = _png_size(outs[2])
    assert (w4, h4) == (w1 * 4, h1 * 4)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pytest tests/test_raster.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sasb.build.raster'`.

- [ ] **Step 3: Implement `src/sasb/build/raster.py`**

```python
"""Render generated SVG figures to PNG at multiple scales."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..gates.visual import ToolMissing, _require

DEFAULT_SCALES = (1, 2, 4)


def render_pngs(svg_path: Path, out_dir: Path, stem: str,
                scales: tuple[int, ...] = DEFAULT_SCALES) -> list[Path]:
    rsvg = _require("rsvg-convert")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for scale in scales:
        target = out_dir / f"{stem}@{scale}x.png"
        subprocess.run(
            [rsvg, "-z", str(scale), "-o", str(target), str(svg_path)],
            check=True, capture_output=True,
        )
        written.append(target)
    return written
```

- [ ] **Step 4: Run the test and verify it passes**

```bash
pytest tests/test_raster.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sasb/build/raster.py tests/test_raster.py
git commit -m "feat: PNG export at 1x/2x/4x for saveable diagrams"
```

---

## Task 9: HTML generator, print styles, and the G5 determinism gate

**Files:**
- Create: `model/content.yaml`, `src/sasb/build/html.py`
- Test: `tests/test_html.py`, `tests/test_purity.py`

**Interfaces:**
- Consumes: `load_entities` (T2), `load_diagrams`/`render_svg` (T7), `reconciliation.json` (T6).
- Produces: `render_html(content: dict, entities: list[Entity], figures: list[Figure], recon: dict) -> str` — pure; and `main(argv) -> int` writing `dist/index.html` plus the figure SVG/PNG assets.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_html.py
import json
from pathlib import Path

from sasb.build.html import render_html, load_content
from sasb.build.svg import load_diagrams
from sasb.model import load_entities

RECON = json.loads(Path("state/reconciliation.json").read_text())


def _render() -> str:
    return render_html(load_content(Path("model/content.yaml")),
                       load_entities(Path("model/entities.yaml")),
                       load_diagrams(Path("model/diagram.yaml")), RECON)


def test_is_deterministic():
    assert _render() == _render()


def test_carries_provenance_and_attribution():
    html = _render()
    assert "SantoshPargi" in html
    assert RECON["checked_at"] in html
    assert "techcommunity.microsoft.com" in html


def test_every_entity_has_a_status_row_with_source_link():
    html = _render()
    for row in RECON["entities"]:
        assert row["name"] in html
        assert row["verdict"] in html
        assert row["final_url"] in html


def test_has_print_styles_and_export_links():
    html = _render()
    assert "@media print" in html
    assert 'href="brief.pdf"' in html and 'href="brief.pptx"' in html
    assert 'download' in html


def test_no_render_time_clock_leaks_into_output():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    html = _render()
    # The only timestamps present must come from reconciliation.json.
    assert today not in html or RECON["checked_at"].startswith(today)
```

```python
# tests/test_purity.py
"""Generators must never touch the network or the clock."""
from pathlib import Path
import pytest

BUILD = Path("src/sasb/build")
FORBIDDEN = ("urllib", "requests", "socket", "datetime.now", "time.time", "random")


@pytest.mark.parametrize("module", sorted(BUILD.glob("*.py")), ids=lambda p: p.name)
def test_generator_is_pure(module):
    src = module.read_text()
    hits = [t for t in FORBIDDEN if t in src]
    assert not hits, f"{module.name} must not use {hits}; builds must be reproducible"
```

- [ ] **Step 2: Run them to verify they fail**

```bash
pytest tests/test_html.py tests/test_purity.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sasb.build.html'`.

- [ ] **Step 3: Write `model/content.yaml`**

Our own synthesis, never the article's prose. Each section is `{id, heading, body: [paragraphs], bullets: [...], entities: [ids]}`, mirroring the article's structure: Introduction and the new attack surface; Reference Architecture; Telemetry Integration (runtime, governance, Copilot audit, safety, alerts); The Two Central Tables; Threat Hunting Scenarios; Detection Engineering; Long-Term Analytics; Summary. Bind every factual claim to the `entities` it depends on, so a `DEPRECATED`/`RENAMED` verdict on an entity marks its sections for review.

- [ ] **Step 4: Implement `src/sasb/build/html.py`**

Requirements the tests pin down:
- Single self-contained HTML: inline `<style>`, inline SVG figures, no external requests.
- Theme-aware: full light palette as custom properties on bare `:root`; only those properties redefined under `@media (prefers-color-scheme: dark)`; explicit `background` on `body`.
- Responsive: relative units, `max-width: 100%` on figures, wide tables in an `overflow-x: auto` wrapper so the body never scrolls horizontally.
- Header block: title, the derived-brief provenance line naming `SantoshPargi` and linking the source article, and `Reconciled against Microsoft Learn as of {recon["checked_at"]}`.
- A reconciliation table: one row per entity — name, kind, verdict badge, detected status, evidence, and a link to `final_url`. Rows iterate `recon["entities"]`, already sorted by `id`.
- Where `article_name` differs from `name`, render both so the rename is visible.
- Export bar: `<a href="brief.pdf" download>`, `<a href="brief.pptx" download>`, and per-figure `<a href="<fig>.svg" download>` / `<a href="<fig>@4x.png" download>` controls (FR-10).
- `@media print`: hide the export bar and nav, force `figure { break-inside: avoid }`, set `a[href^="http"]::after { content: " (" attr(href) ")" }` so links survive on paper.
- Escape all interpolated text with `html.escape`.

- [ ] **Step 5: Run the tests and verify they pass**

```bash
pytest tests/test_html.py tests/test_purity.py -v
```
Expected: all passed.

- [ ] **Step 6: Prove the build is byte-reproducible (G5)**

```bash
python3 -m sasb.build.html && cp dist/index.html /tmp/a.html
python3 -m sasb.build.html && diff -q /tmp/a.html dist/index.html && echo "G5 PASS: byte-identical"
```
Expected: `G5 PASS`. Then prove the gate can fail: temporarily insert `datetime.now()` into a generator, confirm `tests/test_purity.py` fails, and revert.

- [ ] **Step 7: Commit**

```bash
git add model/content.yaml src/sasb/build/html.py tests/test_html.py tests/test_purity.py
git commit -m "feat: deterministic HTML brief with reconciliation table and print styles (G5)"
```

---

## Task 10: PDF and PPTX exports with the G6 integrity gate

**Files:**
- Create: `src/sasb/build/pdf.py`, `src/sasb/build/pptx.py`
- Test: `tests/test_exports.py`

**Interfaces:**
- Consumes: `dist/index.html` (T9), figures + rasters (T7/T8), `reconciliation.json` (T6).
- Produces:
  - `pdf.render(html_path: Path, out: Path) -> Path` via headless Chromium.
  - `pptx.render(content, entities, figures, recon, out: Path) -> Path`.
  - `pptx.slide_titles(path: Path) -> list[str]` helper used by tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_exports.py
import json
from pathlib import Path

import pytest
from pptx import Presentation

RECON = json.loads(Path("state/reconciliation.json").read_text())


def _texts(prs) -> str:
    out = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                out.append(shape.text_frame.text)
    return "\n".join(out)


def test_pptx_has_editable_text_and_expected_slides(tmp_path):
    from sasb.build.pptx import render
    from sasb.build.html import load_content
    from sasb.build.svg import load_diagrams
    from sasb.model import load_entities

    out = render(load_content(Path("model/content.yaml")),
                 load_entities(Path("model/entities.yaml")),
                 load_diagrams(Path("model/diagram.yaml")), RECON, tmp_path / "b.pptx")
    prs = Presentation(str(out))
    assert len(prs.slides) >= 8
    text = _texts(prs)
    assert "Microsoft Sentinel" in text
    assert "SantoshPargi" in text            # attribution survives export
    assert RECON["checked_at"] in text       # provenance survives export
    # diagrams embedded as pictures, not as a flat image-only deck
    pics = sum(1 for s in prs.slides for sh in s.shapes if sh.shape_type == 13)
    assert pics >= 3


def test_pptx_reconciliation_slide_lists_every_entity(tmp_path):
    from sasb.build.pptx import render
    from sasb.build.html import load_content
    from sasb.build.svg import load_diagrams
    from sasb.model import load_entities

    out = render(load_content(Path("model/content.yaml")),
                 load_entities(Path("model/entities.yaml")),
                 load_diagrams(Path("model/diagram.yaml")), RECON, tmp_path / "b.pptx")
    text = _texts(Presentation(str(out)))
    for row in RECON["entities"]:
        assert row["name"] in text


@pytest.mark.skipif(not Path("dist/index.html").exists(), reason="build HTML first")
def test_pdf_has_pages_and_text(tmp_path):
    from sasb.build.pdf import render
    out = render(Path("dist/index.html"), tmp_path / "b.pdf")
    data = out.read_bytes()
    assert data[:5] == b"%PDF-"
    assert data.count(b"/Type /Page") >= 3 or data.count(b"/Type/Page") >= 3
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pytest tests/test_exports.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sasb.build.pptx'`.

- [ ] **Step 3: Implement `src/sasb/build/pdf.py`**

Shell out to headless Chromium (`--headless --disable-gpu --no-pdf-header-footer --print-to-pdf=<out> <file-url>`). Resolve the binary from, in order: `$CHROME_BIN`, `chromium`, `chromium-browser`, `google-chrome`, then the macOS bundle path `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`. Raise `ToolMissing` if none is found — a missing renderer is inconclusive, never a silent skip. Assert the output exists and is non-trivial (`> 1024` bytes) before returning.

- [ ] **Step 4: Implement `src/sasb/build/pptx.py`**

Build the deck from the canonical model with `python-pptx`, not by converting HTML:
- Title slide: brief title, the provenance line naming `SantoshPargi` and the source URL, and `Reconciled as of {recon["checked_at"]}`.
- One content slide per section in `content.yaml`: heading as the title placeholder, bullets as a real text frame.
- One full-bleed slide per figure, inserting `dist/<fig>@4x.png` via `add_picture`, scaled to fit the slide while preserving aspect ratio.
- A reconciliation slide (or slides, chunked at ~12 rows) with a real table: name, kind, verdict, status.
- Use `Presentation()` default 4:3 unless the model sets 16:9 — set `prs.slide_width/slide_height` explicitly to 13.333in × 7.5in for 16:9.
- Iterate `recon["entities"]` in given order; sort any dict.

- [ ] **Step 5: Run the tests and verify they pass**

```bash
python3 -m sasb.build.html          # ensure dist/ assets exist
pytest tests/test_exports.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Prove G6 can fail**

Temporarily truncate `content.yaml` to a single section, rebuild, and confirm `test_pptx_has_editable_text_and_expected_slides` fails on the `>= 8` slide assertion. Revert.

- [ ] **Step 7: Commit**

```bash
git add src/sasb/build/pdf.py src/sasb/build/pptx.py tests/test_exports.py
git commit -m "feat: PDF and editable PPTX exports with integrity assertions (G6)"
```

---

## Task 11: Link integrity, the refresh workflow, and Pages

**Files:**
- Create: `src/sasb/gates/links.py`, `.github/workflows/refresh.yml`
- Modify: `.github/workflows/ci.yml` (add the gate suite)
- Test: `tests/test_links.py`

**Interfaces:**
- Consumes: `fetch` (T3), `load_entities` (T2), `reconciliation.json` (T6).
- Produces: `gates.links.check(urls: list[str]) -> tuple[bool, list[tuple[str, int]]]` returning (passed, failures as `(url, status)`), and `main(argv) -> int` exiting `4` on failure.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_links.py
from sasb.gates.links import classify_statuses


def test_all_ok_passes():
    passed, bad = classify_statuses({"https://a": 200, "https://b": 200})
    assert passed and bad == []


def test_dead_link_fails_the_gate():
    passed, bad = classify_statuses({"https://a": 200, "https://dead": 404})
    assert not passed
    assert ("https://dead", 404) in bad


def test_unreachable_also_fails():
    passed, bad = classify_statuses({"https://x": 0})
    assert not passed
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pytest tests/test_links.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sasb.gates.links'`.

- [ ] **Step 3: Implement `src/sasb/gates/links.py`**

```python
"""G7: every URL the brief cites must resolve."""
from __future__ import annotations

import sys

from ..http_evidence import fetch
from ..verdicts import EXIT_GATE_FAILURE, EXIT_OK


def classify_statuses(statuses: dict[str, int]) -> tuple[bool, list[tuple[str, int]]]:
    bad = sorted((url, code) for url, code in statuses.items() if code != 200)
    return (not bad), bad


def check(urls: list[str]) -> tuple[bool, list[tuple[str, int]]]:
    return classify_statuses({u: fetch(u).status for u in sorted(set(urls))})


def main(argv: list[str] | None = None) -> int:
    import json
    from pathlib import Path

    recon = json.loads(Path("state/reconciliation.json").read_text(encoding="utf-8"))
    urls = [r["final_url"] for r in recon["entities"]] + [recon["article"]["source_url"]]
    passed, bad = check(urls)
    for url, code in bad:
        print(f"DEAD {code} {url}", file=sys.stderr)
    return EXIT_OK if passed else EXIT_GATE_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests and verify they pass**

```bash
pytest tests/test_links.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Write the refresh workflow**

```yaml
# .github/workflows/refresh.yml
name: refresh
on:
  schedule: [{ cron: "0 6 * * *" }]
  workflow_dispatch:

permissions:
  contents: write
  pages: write
  id-token: write
  issues: write

concurrency:
  group: refresh
  cancel-in-progress: false

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: sudo apt-get update && sudo apt-get install -y librsvg2-bin tesseract-ocr chromium-browser
      - run: pip install -e ".[dev]"

      - name: Sweep Microsoft sources
        id: sweep
        run: |
          set +e
          python3 -m sasb.reconcile | tee sweep.log
          echo "code=$?" >> "$GITHUB_OUTPUT"

      - name: Fail closed on inconclusive sweep
        if: steps.sweep.outputs.code == '3'
        run: echo "::error::Sources unreachable; refusing to publish a currency claim" && exit 1

      - name: Build
        run: |
          python3 -m sasb.build.html
          python3 -m sasb.build.pdf
          python3 -m sasb.build.pptx

      - name: Gates
        run: |
          pytest -v
          python3 -m sasb.gates.links

      - name: Commit refreshed state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add state/
          git diff --cached --quiet || git commit -m "chore: refresh reconciliation $(date -u +%Y-%m-%d)"
          git push

      - uses: actions/upload-pages-artifact@v3
        with: { path: dist }
      - uses: actions/deploy-pages@v4

      - name: Open an issue when drift needs review
        if: steps.sweep.outputs.code == '2'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const log = fs.readFileSync('sweep.log', 'utf8');
            await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `Drift detected ${new Date().toISOString().slice(0,10)}`,
              body: "Reconciliation reported drift. Review and update the model.\n\n```\n" + log + "\n```",
              labels: ['drift'],
            });
```

- [ ] **Step 6: Enable Pages and run the workflow**

```bash
gh api -X POST repos/thomaswillner/sentinel-ai-agent-security/pages \
  -f build_type=workflow || true
git add -A && git commit -m "feat: link gate (G7) and daily refresh workflow with Pages deploy"
git push -u origin feat/reconciliation-engine
gh pr create --fill --title "feat: self-updating Sentinel AI agent security brief"
```

- [ ] **Step 7: Verify the published result**

After merge, confirm the run is green, then check the live site:

```bash
gh run watch
curl -sS -o /dev/null -w "site=%{http_code}\n" https://thomaswillner.github.io/sentinel-ai-agent-security/
curl -sS -o /dev/null -w "pdf=%{http_code}\n"  https://thomaswillner.github.io/sentinel-ai-agent-security/brief.pdf
curl -sS -o /dev/null -w "pptx=%{http_code}\n" https://thomaswillner.github.io/sentinel-ai-agent-security/brief.pptx
curl -sS -o /dev/null -w "svg=%{http_code}\n"  https://thomaswillner.github.io/sentinel-ai-agent-security/reference-architecture.svg
```
Expected: all `200`.

---

## Self-Review

**Spec coverage.** FR-1 → T5. FR-2 → T2. FR-3 → T4/T6. FR-4 → T7. FR-5 → T9. FR-6 → T4 extraction + T9 rendering + T6 binding. FR-7 → T11. FR-8 → T10. FR-9 → T10. FR-10 → T8/T9. FR-11 → T6 exit codes + T11 issue step. NFR-1 → T9 Step 6. NFR-2 → T3/T6/T11. NFR-3 → no secrets used. NFR-4 → T9 Step 3 (own synthesis) + T7 (generated figures). NFR-5 → T7/T9. NFR-6 → single job. NFR-7 → T6 per-row `checked_at` + `final_url`. Gates G1→T2, G2→T4, G3→T3, G4→T7, G5→T9, G6→T10, G7→T11.

**Deferred with reason.** The spec's `sources/feeds.py` (Azure Updates / M365 roadmap early warning) is **not** in Tasks 1–11. Watchlist re-measurement is the primary detector and is fully covered; feeds are a secondary early-warning path. Adding them is a self-contained follow-up task once the pipeline is green — it produces `feed_hits` in `reconciliation.json` and a "Recent Microsoft changes" section in the HTML. Track as issue `feeds: add filtered Azure Updates / M365 roadmap early warning`.

**Type consistency.** `Entity` fields are used identically in T2/T4/T6/T9/T10. `Probe` fields (`entity_id`, `verdict`, `title`, `status_detected`, `final_url`, `fingerprint`, `evidence`) match between T4 and T6. `FetchResult` (`url`, `final_url`, `status`, `body`, `error`) matches T3/T4/T5/T11. `_require`/`ToolMissing` are defined in `gates/visual.py` (T7) and imported by `build/raster.py` (T8) and `build/pdf.py` (T10). `load_content` is defined in `build/html.py` (T9) and imported by tests in T10. `render_svg`/`load_diagrams` are defined in T7 and used in T8/T9/T10.

**Purity caveat.** `build/raster.py` and `build/pdf.py` shell out to external renderers, which `tests/test_purity.py` permits — the forbidden list covers network and clock modules, not `subprocess`. Both are deterministic given identical input.
