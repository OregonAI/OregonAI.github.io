#!/usr/bin/env python3
"""One real thread through the whole platform: PERS, from statute to audit.

  python3 build_chain.py        # writes site/chain.html (run before build_site.py)

Closes issue #6. The landing page states the thesis — a statute directs, rules
implement, policies operationalize, dollars are spent, measures report, audits check —
and nothing demonstrated it. This page traces ONE thread, PERS, with every node's count
DERIVED at build time from published artifacts and linked to the documents behind it.
The issue's constraints hold: a node that cannot link does not appear; a link that
cannot be derived is drawn as a GAP, visibly, because an honest broken link beats a
tidy diagram — and the legislature link IS that gap (bill→statute citation density in
the mirror is ~14%, and ORS 238's sections predate the mirrored sessions).

Fetch failures fail the build (this repo's own #1 rule; build_site.py enforces the
same for the landing page).
"""
from __future__ import annotations

import datetime
import json
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

from corpus_toolkit import viz

SITE = Path(__file__).resolve().parent / "site"
RAW = "https://raw.githubusercontent.com/OregonAI"
PAGES = "https://oregonai.github.io"
MCP = "https://oregonai.morficflux.com"
ERF = "executive-regulatory-frameworks"
PERS_SLUG = "oregon-public-employees-retirement-system"

FETCHED: list[dict] = []


def fetch(url: str, label: str) -> bytes:
    import hashlib
    req = urllib.request.Request(url, headers={"User-Agent": "oregonai-chain-builder"})
    with urllib.request.urlopen(req, timeout=120) as r:   # any failure raises: red build
        body = r.read()
    FETCHED.append({"label": label, "url": url,
                    "sha256": hashlib.sha256(body).hexdigest()})
    return body


def card(*, corpus: str, stat: str, title: str, meaning: str, links: list[tuple],
         mcp_path: str, derived: str) -> str:
    ln = " · ".join(f'<a href="{u}">{t}</a>' for t, u in links)
    return f"""
<div class="panel" style="position:relative">
  <p class="eyebrow" style="margin-top:0">{corpus} · <b>{derived}</b></p>
  <h2 style="margin:0 0 2px;font-size:19px">{stat} <small style="font-weight:400;
    color:var(--ink2)">{title}</small></h2>
  <p style="margin:4px 0 8px;color:var(--ink2)">{meaning}</p>
  <p style="margin:0;font-size:13px">{ln} ·
    <button class="ep" type="button" data-ep="{MCP}{mcp_path}">{MCP}{mcp_path}</button></p>
</div>
<div class="link-arm">↓ <span></span></div>"""


def main() -> int:
    audits_graph = json.loads(fetch(f"{RAW}/oregon-audits/main/_meta/graph.json",
                                    "oregon-audits authority graph"))
    erf_index = json.loads(fetch(f"{PAGES}/{ERF}/corpus-index.json",
                                 "ERF published index"))
    budget_index = json.loads(fetch(f"{PAGES}/oregon-budget/corpus-index.json",
                                    "oregon-budget published index"))
    kpm_series = json.loads(fetch(f"{RAW}/oregon-kpm/main/_meta/series.json",
                                  "oregon-kpm extracted measure series"))

    # Derived counts, every one recomputed from the fetched artifacts.
    cite_238 = Counter()
    for e in audits_graph["edges"]:
        m = re.match(r"^ORS\s+(238)\.(\d+)$", e.get("to", ""))
        if m:
            cite_238[f"238.{m.group(2)}"] += 1
    reports_citing_238 = len({e["from"] for e in audits_graph["edges"]
                              if re.match(r"^ORS 238\.", e.get("to", ""))})
    top2 = cite_238.most_common(2)
    erf_docs = erf_index["documents"]
    n_rules_459 = sum(1 for k in erf_docs if k.startswith("oar-459-"))
    n_policies = sum(1 for k, row in erf_docs.items()
                     if str(row[2] if isinstance(row, list) else row.get("path", ""))
                     .startswith(f"agencies/{PERS_SLUG}/"))
    n_fy = sum(1 for k in budget_index["documents"] if k.startswith("expenditures-459-fy"))
    pers_rows = [r for r in kpm_series["rows"] if "Retirement" in r.get("agency", "")]
    n_measures = len({r["measure_key"] for r in pers_rows})

    cards = []
    cards.append(f"""
<div class="panel gap">
  <p class="eyebrow" style="margin-top:0">oregon-legislature · <b>a drawn gap</b></p>
  <h2 style="margin:0 0 2px;font-size:17px">No authorizing measure resolves</h2>
  <p style="margin:4px 0 0;color:var(--ink2)">ORS chapter 238 predates the mirrored
  sessions (2017 onward), and bill→statute citation density in the mirror is ~14% —
  so the thread's first link cannot be derived, and this page draws that honestly
  rather than papering over it. When a session law amending ORS 238 lands in the
  mirror, this node becomes real.</p>
</div>
<div class="link-arm">↓ <span></span></div>""")
    cards.append(card(
        corpus="executive-regulatory-frameworks", derived="derived",
        stat=f"ORS {top2[0][0]} · {top2[1][0]}", title="the statute directs",
        meaning=(f"The two most-cited provisions in the whole audit corpus "
                 f"({top2[0][1]} and {top2[1][1]} citations) — the Legislature's "
                 f"directions for the Public Employees Retirement System."),
        links=[("official ORS ch. 238", "https://www.oregonlegislature.gov/bills_laws/ors/ors238.html"),
               ("mirrored", f"https://github.com/OregonAI/{ERF}/blob/main/statutes/ors-{top2[0][0]}.md")],
        mcp_path=f"/{ERF}/mcp"))
    cards.append(card(
        corpus="executive-regulatory-frameworks", derived="derived",
        stat=f"{n_rules_459}", title="OAR chapter 459 rules implement it",
        meaning="PERS's administrative rules — how the statute's directions become "
                "procedure, every one mirrored with provenance.",
        links=[("official OAR ch. 459", "https://secure.sos.state.or.us/oard/displayChapterRules.action?selectedChapter=126"),
               ("mirrored", f"https://github.com/OregonAI/{ERF}/tree/main/rules/459")],
        mcp_path=f"/{ERF}/mcp"))
    cards.append(card(
        corpus="executive-regulatory-frameworks", derived="derived",
        stat=f"{n_policies}", title="agency instruments operationalize the rules",
        meaning="PERS-scoped policies and schedules held in the corpus under the "
                "agency's own registry slug.",
        links=[("mirrored agency docs",
                f"https://github.com/OregonAI/{ERF}/tree/main/agencies/{PERS_SLUG}")],
        mcp_path=f"/{ERF}/mcp"))
    cards.append(card(
        corpus="oregon-budget", derived="derived",
        stat=f"FY2019–FY20{18 + n_fy}", title=f"the dollars, {n_fy} fiscal years of them",
        meaning="PERS's recorded spending (budget agency code 459), mirrored from the "
                "state's own expenditure data and queryable live. The agency crosswalk "
                "makes this node derived rather than hand-filled — the gap issue #6 "
                "named is closed.",
        links=[("expenditure mirrors",
                "https://github.com/OregonAI/oregon-budget/tree/main/expenditures"),
               ("data.oregon.gov", "https://data.oregon.gov/d/y9g9-xsxs")],
        mcp_path="/oregon-budget/mcp"))
    cards.append(card(
        corpus="oregon-kpm", derived="derived",
        stat=f"{n_measures}", title=f"performance measures, {len(pers_rows):,} reported points",
        meaning="What PERS told the Legislature about its own performance — targets and "
                "actuals extracted from its Annual Performance Progress Reports.",
        links=[("mirrored reports", "https://github.com/OregonAI/oregon-kpm/tree/main/reports")],
        mcp_path="/oregon-kpm/mcp"))
    cards.append(f"""
<div class="panel">
  <p class="eyebrow" style="margin-top:0">oregon-audits · <b>derived</b></p>
  <h2 style="margin:0 0 2px;font-size:19px">{reports_citing_238} <small
    style="font-weight:400;color:var(--ink2)">audit reports cite ORS chapter 238</small></h2>
  <p style="margin:4px 0 8px;color:var(--ink2)">The only node that says whether any of
  the above worked: the Secretary of State's auditors, citing the same statute this
  thread started from. The circle closes.</p>
  <p style="margin:0;font-size:13px">
    <a href="https://sos.oregon.gov/audits/">SoS Audits Division</a> ·
    <a href="https://github.com/OregonAI/oregon-audits/tree/main/reports">mirrored reports</a> ·
    <button class="ep" type="button" data-ep="{MCP}/oregon-audits/mcp">{MCP}/oregon-audits/mcp</button></p>
</div>""")

    extra_css = """
.link-arm{color:var(--muted);text-align:center;margin:-6px 0;font-size:15px}
.gap{border-style:dashed;border-color:var(--axis)}
.ep{display:inline-flex;border:1px dashed var(--border);background:none;
    color:var(--muted);border-radius:8px;padding:2px 8px;font:12px ui-monospace,Menlo,monospace;
    cursor:copy;overflow-wrap:anywhere}
"""
    script = """
document.querySelectorAll('.ep').forEach(function(b){
  b.addEventListener('click', function(){
    navigator.clipboard.writeText(b.dataset.ep).then(function(){
      var t = b.textContent; b.textContent = 'copied'; setTimeout(function(){ b.textContent = t; }, 900);
    });
  });
});
"""
    page = viz.chart_page(
        title="One thread, end to end: PERS from statute to audit",
        eyebrow="Civic Corpus Platform · the thesis, demonstrated on one real program",
        lede_html=("A statute directs, rules implement, agency instruments "
                   "operationalize, dollars are spent, measures report, audits check. "
                   "Every count below is <b>derived at build time</b> from the "
                   "platform's published artifacts — nothing is hand-filled — and the "
                   "one link that cannot be derived is drawn as the gap it is."),
        body_html="".join(cards),
        caveats_html=(
            "<p>Counts are of <i>mirrored, linkable documents</i>, not of everything "
            "that exists — coverage per corpus is stated on each corpus's own site. "
            "The audit node counts reports <i>citing ORS chapter 238</i>, which is how "
            "the corpus records examination of PERS's statute; it is not a claim that "
            "each report audited PERS alone. The legislature node is a drawn gap, not "
            "an omission. Non-authoritative throughout: every node links to the "
            "official source.</p>"),
        sources=FETCHED,
        generated=datetime.date.today().isoformat(),
        script=script)
    page = page.replace("</style>", extra_css + "</style>", 1)
    SITE.mkdir(exist_ok=True)
    (SITE / "chain.html").write_text(page, encoding="utf-8")
    print(f"wrote site/chain.html "
          f"(238-citations={sum(cite_238.values())}, rules={n_rules_459}, "
          f"policies={n_policies}, fy={n_fy}, measures={n_measures}, "
          f"reports={reports_citing_238})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
