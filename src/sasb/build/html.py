"""Render the living brief as one self-contained bilingual page.

Pure by contract: this module reads the model and state/reconciliation.json and
nothing else. It never touches the network and never reads the clock -- every
timestamp on the page comes from the reconciliation document, which is what
makes the build byte-reproducible.

Both languages are rendered into the document and switched client-side, so the
page keeps one URL and one set of exports per locale.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import yaml

from ..i18n import DEFAULT_LOCALE, LOCALES, load_locale, summary_for
from ..model import Entity, load_entities
from ..verdicts import Verdict, assert_publishable
from .svg import Figure, load_diagrams, render_svg

ROOT = Path(__file__).resolve().parents[3]
VERDICT_LABEL = {
    "CURRENT": "status_current", "CHANGED": "status_changed",
    "RENAMED": "status_renamed", "DEPRECATED": "status_deprecated",
}
AVAIL_LABEL = {
    "ga": "avail_ga", "preview": "avail_preview", "superseded": "avail_superseded",
    "documented-differently": "avail_documented_differently",
    "review-needed": "avail_review_needed",
}


def load_content(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _e(text: object) -> str:
    return html.escape(str(text), quote=True)


def _ui(loc: dict, key: str) -> str:
    return (loc.get("ui") or {}).get(key, key)


def _section(loc: dict, sid: str) -> dict:
    return (loc.get("sections") or {}).get(sid, {})


_TOKEN_RE = re.compile(r"\{([a-z0-9-]+)\}")


def resolve_tokens(text: str, entities: dict[str, Entity]) -> str:
    """Replace {entity-id} with the entity's current name.

    Prose is bound to the model for the same reason the diagram is: when
    Microsoft renames something, the sentences have to move with it. Writing
    "Azure AI Foundry" into a paragraph would leave the text stale while the
    figure and the status table had already updated.
    """
    def sub(match: re.Match) -> str:
        entity = entities.get(match.group(1))
        return entity.name if entity else match.group(0)

    return _TOKEN_RE.sub(sub, text)


def _linked(text: str, entities: dict[str, Entity]) -> str:
    """Escape prose, then make each {entity-id} token open its lightbox."""
    parts, last = [], 0
    for match in _TOKEN_RE.finditer(text):
        parts.append(_e(text[last:match.start()]))
        entity = entities.get(match.group(1))
        if entity is None:
            parts.append(_e(match.group(0)))
        else:
            parts.append(f'<a class="ent" role="button" tabindex="0" '
                         f'data-entity="{_e(entity.id)}">{_e(entity.name)}</a>')
        last = match.end()
    parts.append(_e(text[last:]))
    return "".join(parts)


def _entity_payload(entities: dict[str, Entity], recon: dict,
                    locales: dict[str, dict]) -> dict:
    """Per-locale detail for the lightbox, keyed by entity id."""
    rows = {r["id"]: r for r in recon["entities"]}
    payload: dict[str, dict] = {}
    for eid, entity in sorted(entities.items()):
        row = rows.get(eid)
        if row is None:
            continue
        per_locale = {}
        for loc_name in LOCALES:
            loc = locales[loc_name]
            url = row["source_urls"].get(loc_name, row["final_url"])
            # No silent locale substitution: if the localized page does not
            # exist the reader is told the link is English, never redirected
            # to it without notice.
            localized = f"/{ 'de-de' if loc_name == 'de' else 'en-us' }/" in url
            per_locale[loc_name] = {
                "name": entity.name,
                "articleName": entity.article_name,
                "kind": _ui(loc, f"kind_{entity.kind}"),
                "status": _ui(loc, VERDICT_LABEL.get(row["verdict"], "status_current")),
                "avail": _ui(loc, AVAIL_LABEL.get(row["status_detected"], "avail_ga")),
                "summary": summary_for(entity, loc_name, locales),
                "evidence": row["evidence"][0] if row["evidence"] else "",
                "url": url,
                "urlIsLocalized": localized,
                "checkedAt": row["checked_at"],
                "verdict": row["verdict"],
            }
        payload[eid] = per_locale
    return payload


def _figure_block(fig: Figure, entities: dict[str, Entity], loc: dict,
                  loc_name: str) -> str:
    svg = render_svg(fig, entities, loc)
    stem = f"{fig.id}.{loc_name}"
    return (
        f'<figure class="fig" data-figure="{_e(fig.id)}">'
        f'<div class="fig-canvas" role="group" aria-label="{_e(_ui(loc, "enlarge"))}">'
        f"{svg}</div>"
        f'<figcaption class="fig-tools">'
        f'<span class="hint">{_e(_ui(loc, "figure_hint"))}</span>'
        f'<span class="fig-dl">'
        f'<a href="{stem}.svg" download>{_e(_ui(loc, "download_svg"))}</a>'
        f'<a href="{stem}@4x.png" download>{_e(_ui(loc, "download_png"))}</a>'
        f'<button type="button" class="enlarge">{_e(_ui(loc, "enlarge"))}</button>'
        f"</span></figcaption></figure>"
    )


def _sections_html(content: dict, entities: dict[str, Entity], figures: dict[str, Figure],
                   loc: dict, loc_name: str) -> str:
    out = []
    for spec in content["sections"]:
        sid = spec["id"]
        sec = _section(loc, sid)
        parts = [f'<section id="{_e(sid)}-{loc_name}"><h2>{_e(sec.get("heading", sid))}</h2>']
        for paragraph in sec.get("body", []):
            parts.append(f"<p>{_linked(paragraph, entities)}</p>")
        if sec.get("bullets"):
            parts.append("<ul>" + "".join(
                f"<li>{_linked(item, entities)}</li>" for item in sec["bullets"]) + "</ul>")
        if sec.get("links"):
            parts.append('<ul class="refs">' + "".join(
                f'<li><a href="{_e(link["url"])}" target="_blank" rel="noopener">'
                f'{_e(link["label"])}</a></li>' for link in sec["links"]) + "</ul>")
        if spec.get("figure"):
            parts.append(_figure_block(figures[spec["figure"]], entities, loc, loc_name))
        parts.append("</section>")
        out.append("".join(parts))
    return "".join(out)


def _table_html(recon: dict, loc: dict) -> str:
    head = "".join(
        f"<th>{_e(_ui(loc, key))}</th>"
        for key in ("col_component", "col_kind", "col_status", "col_detected",
                    "col_evidence", "col_source")
    )
    rows = []
    for row in recon["entities"]:
        verdict = row["verdict"]
        badge = _ui(loc, VERDICT_LABEL.get(verdict, "status_current"))
        avail = _ui(loc, AVAIL_LABEL.get(row["status_detected"], "avail_ga"))
        name = _e(row["name"])
        if row.get("article_name"):
            name += (f'<br><small class="alt">{_e(_ui(loc, "article_called_it"))}: '
                     f'{_e(row["article_name"])}</small>')
        kind_label = _ui(loc, "kind_" + row["kind"])
        rows.append(
            f'<tr data-verdict="{_e(verdict)}">'
            f"<td>{name}</td>"
            f"<td>{_e(kind_label)}</td>"
            f'<td><span class="badge b-{_e(verdict.lower())}">{_e(badge)}</span></td>'
            f"<td>{_e(avail)}</td>"
            f'<td class="ev">{_e(row["evidence"][0] if row["evidence"] else "")}</td>'
            f'<td><a href="{_e(row["source_urls"].get("en", row["final_url"]))}" '
            f'rel="noopener" target="_blank">Learn</a></td></tr>'
        )
    return (f'<div class="tablewrap"><table class="recon"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


CSS = """
*{box-sizing:border-box}
:root{
 --bg:#f7f9fc;--panel:#fff;--ink:#14203a;--muted:#4a5876;--line:#d8e0ee;
 --accent:#2a5bd7;--accent-ink:#fff;
 --ok:#1a7f4b;--ok-bg:#e6f6ed;--warn:#8a5a00;--warn-bg:#fdf3e0;
 --info:#1f5fa8;--info-bg:#e7f1fb;--dep:#8c3a2e;--dep-bg:#fbeae7;
 --link:#1c4fd8;
 --shadow:0 1px 3px rgba(16,32,64,.08),0 8px 24px rgba(16,32,64,.06);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --bg:#0d111a;--panel:#151b28;--ink:#e9eefb;--muted:#a2b0cc;--line:#2a3550;
 --accent:#8fb0ff;--accent-ink:#0d111a;
 --ok:#7fd7a6;--ok-bg:#123024;--warn:#e5bf78;--warn-bg:#33280f;
 --link:#eef2fb;
 --info:#9cc4f2;--info-bg:#12263c;--dep:#f0a89b;--dep-bg:#3a1f1a;
 --shadow:0 1px 3px rgba(0,0,0,.5),0 8px 24px rgba(0,0,0,.4);
}}
:root[data-theme="dark"]{
 --bg:#0d111a;--panel:#151b28;--ink:#e9eefb;--muted:#a2b0cc;--line:#2a3550;
 --accent:#8fb0ff;--accent-ink:#0d111a;
 --ok:#7fd7a6;--ok-bg:#123024;--warn:#e5bf78;--warn-bg:#33280f;
 --link:#eef2fb;
 --info:#9cc4f2;--info-bg:#12263c;--dep:#f0a89b;--dep-bg:#3a1f1a;
}
/* Anchors must never fall through to the UA default (#0000EE), which is
   unreadable on the dark palette. Underlines carry the affordance so the
   colour can sit close to the body text. */
a{color:var(--link);text-decoration:underline;text-underline-offset:3px}
a:hover,a:focus-visible{text-decoration-thickness:2px}
body{margin:0;background:var(--bg);color:var(--ink);
 font:16px/1.65 'Segoe UI',system-ui,-apple-system,'Helvetica Neue',sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 80px}
header.top{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start;
 justify-content:space-between;margin-bottom:8px}
h1{font-size:clamp(26px,4vw,38px);line-height:1.15;margin:0 0 6px}
.sub{color:var(--muted);font-size:17px;margin:0 0 14px;max-width:62ch}
.prov{background:var(--panel);border:1px solid var(--line);border-radius:12px;
 padding:14px 16px;font-size:14px;color:var(--muted);box-shadow:var(--shadow);margin-bottom:22px}
.prov b{color:var(--ink)}
.controls{display:flex;gap:8px;align-items:center}
.controls button,.exports a,.fig-tools a,.fig-tools button{
 font:inherit;font-size:13px;border:1px solid var(--line);background:var(--panel);
 color:var(--ink);border-radius:999px;padding:7px 14px;cursor:pointer;text-decoration:none}
.controls button[aria-pressed="true"]{background:var(--accent);color:var(--accent-ink);
 border-color:var(--accent)}
.exports{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 26px}
h2{font-size:clamp(20px,2.6vw,26px);margin:34px 0 10px;scroll-margin-top:20px}
p{max-width:74ch}
ul{max-width:74ch}
section{border-top:1px solid var(--line);padding-top:6px}
section:first-of-type{border-top:0}
.fig{margin:20px 0 8px;background:var(--panel);border:1px solid var(--line);
 border-radius:14px;padding:14px;box-shadow:var(--shadow)}
.fig-canvas{overflow-x:auto}
.fig svg{width:100%;height:auto;min-width:640px;display:block}
.fig-tools{display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;
 align-items:center;margin-top:10px;font-size:13px;color:var(--muted)}
.fig-dl{display:flex;gap:8px;flex-wrap:wrap}
.tablewrap{overflow-x:auto;background:var(--panel);border:1px solid var(--line);
 border-radius:14px;box-shadow:var(--shadow)}
table.recon{border-collapse:collapse;width:100%;font-size:14px;min-width:780px}
.recon th,.recon td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);
 vertical-align:top}
.recon th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.recon tr:last-child td{border-bottom:0}
.recon .ev{color:var(--muted);max-width:38ch}
.refs{margin:10px 0}
.alt{color:var(--muted)}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;
 font-weight:600;white-space:nowrap}
.b-current{background:var(--ok-bg);color:var(--ok)}
.b-changed{background:var(--info-bg);color:var(--info)}
.b-renamed{background:var(--warn-bg);color:var(--warn)}
.b-deprecated{background:var(--dep-bg);color:var(--dep)}
.node:hover .card,.node:focus-visible .card{stroke:var(--accent);stroke-width:2}
a.ent{color:var(--link);cursor:pointer;text-decoration:underline;
 text-decoration-style:dotted;text-underline-offset:3px}
a.ent:hover,a.ent:focus-visible{text-decoration-style:solid}
dialog.lb{border:1px solid var(--line);border-radius:16px;padding:0;max-width:min(680px,92vw);
 background:var(--panel);color:var(--ink);box-shadow:var(--shadow)}
dialog.lb.wide{max-width:none;width:100vw;height:100vh;max-height:100vh;
 border-radius:0;border:0}
dialog.lb::backdrop{background:rgba(8,12,22,.62)}
.lb-in{padding:20px 22px 22px}
.lb-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}
.lb h3{margin:0 0 2px;font-size:21px}
.lb .kind{color:var(--muted);font-size:13px}
.lb .row{margin-top:14px;font-size:14px}
.lb .ev{color:var(--muted);font-size:13px;border-left:3px solid var(--line);
 padding-left:12px;margin-top:12px}
.lb .warn{color:var(--warn);font-size:13px;margin-top:8px}
.lb .x{border:1px solid var(--line);background:transparent;color:var(--ink);
 border-radius:999px;width:34px;height:34px;font-size:18px;cursor:pointer;flex:none}
/* The figure is a flex item, so flex-shrink pulls it back to the container
   width whatever width is set -- flex:none is what makes zoom actually zoom.
   The SVG viewBox handles letterboxing, so width+height 100% fits without
   distortion. */
.lb-fig{padding:8px;height:calc(100vh - 66px);display:flex;align-items:center;
 justify-content:center;overflow:auto;cursor:zoom-in}
.lb-fig svg{width:100%;height:100%;flex:none}
.lb-fig.zoom{align-items:flex-start;justify-content:flex-start;cursor:zoom-out}
.lb-fig.zoom svg{width:220%;height:auto;flex:none}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);
 color:var(--muted);font-size:13px}
[data-langroot]{display:none}
[data-langroot].on{display:block}
@media print{
 .controls,.exports,.fig-tools,.lb{display:none!important}
 body{background:#fff;color:#000}
 .wrap{max-width:none;padding:0}
 section{break-inside:avoid}
 .fig{break-inside:avoid;box-shadow:none;border:1px solid #999}
 .fig svg{min-width:0}
 .tablewrap{overflow:visible;box-shadow:none}
 table.recon{min-width:0;font-size:10pt}
 a[href^="http"]::after{content:" (" attr(href) ")";font-size:8pt;color:#555;word-break:break-all}
}
"""

JS = """
(function(){
 var DATA=JSON.parse(document.getElementById('entity-data').textContent);
 var UI=JSON.parse(document.getElementById('ui-data').textContent);
 var lang=new URLSearchParams(location.search).get('lang')
   ||localStorage.getItem('sasb-lang')||'en';
 if(!DATA.__locales.includes(lang)){lang='en';}
 function applyLang(next){
  lang=next;localStorage.setItem('sasb-lang',next);
  document.documentElement.lang=next;
  document.querySelectorAll('[data-langroot]').forEach(function(el){
   el.classList.toggle('on',el.getAttribute('data-langroot')===next);});
  document.querySelectorAll('[data-setlang]').forEach(function(b){
   b.setAttribute('aria-pressed',String(b.getAttribute('data-setlang')===next));});
 }
 document.querySelectorAll('[data-setlang]').forEach(function(b){
  b.addEventListener('click',function(){applyLang(b.getAttribute('data-setlang'));});});
 applyLang(lang);

 var dlg=document.getElementById('lb'),body=document.getElementById('lb-body');
 function open(htmlStr,wide){
  body.innerHTML=htmlStr;dlg.classList.toggle('wide',!!wide);
  if(!dlg.open){dlg.showModal();}
 }
 function esc(s){var d=document.createElement('div');d.textContent=s==null?'':s;
  return d.innerHTML;}
 function detail(id){
  var rec=DATA[id];if(!rec)return;var d=rec[lang]||rec.en;var t=UI[lang];
  var alt=d.articleName?'<div class="row"><b>'+esc(t.article_called_it)+':</b> '
    +esc(d.articleName)+'</div>':'';
  var note=d.urlIsLocalized?'':'<div class="warn">'+esc(t.english_only)+'</div>';
  open('<div class="lb-in"><div class="lb-head"><div>'
   +'<h3>'+esc(d.name)+'</h3><div class="kind">'+esc(d.kind)+' &middot; '
   +'<span class="badge b-'+esc(d.verdict.toLowerCase())+'">'+esc(d.status)+'</span> &middot; '
   +esc(d.avail)+'</div></div>'
   +'<button class="x" type="button" data-close aria-label="'+esc(t.close)+'">&times;</button>'
   +'</div><p>'+esc(d.summary)+'</p>'+alt
   +'<div class="ev">'+esc(d.evidence)+'</div>'
   +'<div class="row"><a href="'+esc(d.url)+'" target="_blank" rel="noopener">'
   +esc(t.open_in_learn)+'</a></div>'+note
   +'<div class="row kind">'+esc(t.verified_on)+' '+esc(d.checkedAt)+'</div></div>');
 }
 document.addEventListener('click',function(ev){
  if(ev.target.closest('[data-close]')){dlg.close();return;}
  var big=ev.target.closest('.enlarge');
  if(big){var fig=big.closest('.fig');var t=UI[lang];
   open('<div class="lb-in"><div class="lb-head"><div></div>'
    +'<button class="x" type="button" data-close aria-label="'+esc(t.close)
    +'">&times;</button></div><div class="lb-fig">'
    +fig.querySelector('.fig-canvas').innerHTML+'</div></div>',true);return;}
  var zoomable=ev.target.closest('.lb-fig');
  if(zoomable){zoomable.classList.toggle('zoom');return;}
  var node=ev.target.closest('[data-entity]');
  if(node){detail(node.getAttribute('data-entity'));}
 });
 document.addEventListener('keydown',function(ev){
  if(ev.key!=='Enter'&&ev.key!==' ')return;
  var node=ev.target.closest&&ev.target.closest('[data-entity]');
  if(node){ev.preventDefault();detail(node.getAttribute('data-entity'));}
 });
 dlg.addEventListener('click',function(ev){if(ev.target===dlg){dlg.close();}});
})();
"""


def assert_tokens_resolve(locales: dict[str, dict], entities: dict[str, Entity]) -> None:
    """Every {entity-id} in prose must name a real entity.

    An unresolved token would print literal braces on the page, and worse, would
    mean a product reference that no longer tracks the model.
    """
    unknown = set()
    for name, loc in sorted(locales.items()):
        for sid, section in sorted((loc.get("sections") or {}).items()):
            for text in section.get("body", []) + section.get("bullets", []):
                unknown |= {
                    f"{name}/{sid}:{tok}" for tok in _TOKEN_RE.findall(text)
                    if tok not in entities
                }
    if unknown:
        raise ValueError(f"unresolvable entity tokens in prose: {sorted(unknown)}")


def render_html(content: dict, entities: dict[str, Entity], figures: list[Figure],
                recon: dict, locales: dict[str, dict]) -> str:
    assert_publishable([Verdict(r["verdict"]) for r in recon["entities"]])
    assert_tokens_resolve(locales, entities)
    # "unknown" is a state, not a value to render. If a row carries one, the
    # sweep failed to measure something and the page must not claim otherwise.
    unmeasured = sorted(r["id"] for r in recon["entities"]
                        if r.get("status_detected") in (None, "", "unknown"))
    if unmeasured:
        raise ValueError(f"refusing to publish unmeasured availability for: {unmeasured}")
    fig_map = {f.id: f for f in figures}
    art = recon["article"]

    payload = _entity_payload(entities, recon, locales)
    payload["__locales"] = list(LOCALES)
    ui_payload = {
        name: {
            key: _ui(loc, key)
            for key in ("close", "open_in_learn", "verified_on", "article_called_it",
                        "english_only")
        }
        for name, loc in sorted(locales.items())
    }

    roots = []
    for loc_name in LOCALES:
        loc = locales[loc_name]
        on = " on" if loc_name == DEFAULT_LOCALE else ""
        roots.append(
            f'<div data-langroot="{loc_name}" class="langroot{on}">'
            f"<h1>{_e(_ui(loc, 'brief_title'))}</h1>"
            f'<p class="sub">{_e(_ui(loc, "brief_subtitle"))}</p>'
            f'<div class="prov">{_e(_ui(loc, "origin_note"))}<br><br>'
            f'{_e(_ui(loc, "derived_from"))} '
            f'<a href="{_e(art["source_url"])}" target="_blank" rel="noopener">'
            f'<b>{_e(art["subject"])}</b></a> {_e(_ui(loc, "by_author"))} '
            f'<b>{_e(art["author"])}</b>, {_e(art["post_time"][:10])}.<br>'
            f'{_e(_ui(loc, "reconciled_prefix"))} <b>{_e(recon["checked_at"])}</b>.</div>'
            f'<nav class="exports" aria-label="{_e(_ui(loc, "exports_heading"))}">'
            f'<a href="brief.{loc_name}.pdf" download>{_e(_ui(loc, "download_pdf"))}</a>'
            f'<a href="brief.{loc_name}.pptx" download>{_e(_ui(loc, "download_pptx"))}</a>'
            f"</nav>"
            f"{_sections_html(content, entities, fig_map, loc, loc_name)}"
            f'<section><h2>{_e(_ui(loc, "section_reconciliation"))}</h2>'
            f'<p>{_e(_ui(loc, "section_reconciliation_intro"))}</p>'
            f"{_table_html(recon, loc)}</section>"
            f"</div>"
        )

    switch = "".join(
        f'<button type="button" data-setlang="{name}" aria-pressed="false">'
        f'{_e(_ui(locales[name], "lang_name"))}</button>'
        for name in LOCALES
    )
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    ui_blob = json.dumps(ui_payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")

    return (
        "<!doctype html>\n"
        f'<html lang="{DEFAULT_LOCALE}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(_ui(locales[DEFAULT_LOCALE], 'brief_title'))}</title>"
        f'<meta name="description" content="{_e(_ui(locales[DEFAULT_LOCALE], "brief_subtitle"))}">'
        f"<style>{CSS}</style></head><body><div class=\"wrap\">"
        f'<header class="top"><div></div><div class="controls" role="group" '
        f'aria-label="Language">{switch}</div></header>'
        + "".join(roots)
        + f'<footer>Reconciled automatically against Microsoft Learn. '
          f'Article body hash <code>{_e(art["body_hash"][:12])}</code>, '
          f'last edited {_e(art["last_edit_time"][:10])}.</footer>'
        + '</div><dialog class="lb" id="lb"><div id="lb-body"></div></dialog>'
        + f'<script type="application/json" id="entity-data">{blob}</script>'
        + f'<script type="application/json" id="ui-data">{ui_blob}</script>'
        + f"<script>{JS}</script></body></html>"
    )


def main(argv: list[str] | None = None) -> int:
    entities = {e.id: e for e in load_entities(ROOT / "model" / "entities.yaml")}
    figures = load_diagrams(ROOT / "model" / "diagram.yaml")
    content = load_content(ROOT / "model" / "content.yaml")
    locales = {name: load_locale(name) for name in LOCALES}
    recon = json.loads((ROOT / "state" / "reconciliation.json").read_text(encoding="utf-8"))

    dist = ROOT / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text(
        render_html(content, entities, figures, recon, locales), encoding="utf-8")
    for name in LOCALES:
        loc = locales[name]
        for fig in figures:
            (dist / f"{fig.id}.{name}.svg").write_text(
                render_svg(fig, entities, loc), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
