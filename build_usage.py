#!/usr/bin/env python3
"""Build the "how to use it" page into ./site/use.html.

  python3 build_usage.py          # writes ./site/use.html

Separate from build_site.py because it answers a different question — that page says what
exists, this one says how to point a client at it — but it imports `STYLE` and `GATEWAY` from
there so the palette and the endpoint have exactly one definition between them.

THE SAMPLE RESULTS ON THIS PAGE ARE REAL. Every corpus title quoted below came back from
gateway.morficflux.com on 2026-08-03 and is reproducible by running the query shown. Inventing
a plausible-looking transcript would be the single most damaging thing this page could do: it
is a page about a platform whose entire value proposition is that its answers are traceable to
sources, aimed at readers deciding whether to trust it.

Stdlib only, same rule as build_site.py — no build-time dependency the deploy has to carry.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from build_site import GATEWAY, ORG_URL, SITE, STYLE, esc

# Captured 2026-08-03 against gateway.morficflux.com. Re-run the queries to refresh; do not
# edit the titles by hand.
SAMPLES_CAPTURED = "2026-08-03"

WILDFIRE_HITS = [
    ("executive-regulatory-frameworks",
     "Adoption of wildfire hazard mitigation code standards for new buildings"),
    ("oregon-legislature",
     "SB 84 (2025R1): Exempts local governments that adopted and continue to…"),
    ("oregon-budget",
     "Appropriations in 2021 Regular Session House Bill 2795"),
    ("oregon-audits",
     "Advisory Report: ODOT Worked Quickly to Oversee the Largest Wildfire D…"),
    ("oregon-kpm",
     "Department of Forestry — Annual Performance Progress Report"),
]

FORESTRY_HITS = [
    ("oregon-budget", "Forestry, Dept of — FY2022 expenditures"),
    ("oregon-kpm", "Forestry, Department of — Annual Performance Progress Report"),
    ("oregon-budget", "Forestry, Dept of — FY2019 expenditures"),
]

CITATION_PATHS = [
    ("executive-regulatory-frameworks", "direct"),
    ("oregon-audits", "sibling:executive-regulatory-frameworks"),
    ("oregon-kpm", "sibling:executive-regulatory-frameworks"),
    ("oregon-counties", "sibling:executive-regulatory-frameworks"),
    ("oregon-collective-bargaining", "sibling:executive-regulatory-frameworks"),
]


def rows(pairs) -> str:
    return "\n".join(
        f'<tr><td class="c">{esc(a)}</td><td>{esc(b)}</td></tr>' for a, b in pairs
    )


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How to use the OregonAI corpora — connect the MCP endpoint</title>
<meta name="description" content="Connect Claude, or any MCP client, to public non-authoritative knowledge bases of Oregon government: statutes, rules, budgets, audits, performance measures, county code and collective bargaining agreements.">
<style>__STYLE__
  pre{background:var(--panel);border:1px solid var(--line);border-radius:10px;
    padding:14px 16px;overflow-x:auto;font-size:13.5px;line-height:1.5;margin:12px 0 0}
  pre code{background:transparent;border:0;padding:0;font-size:inherit}
  .steps{counter-reset:s;list-style:none;padding:0;margin:14px 0 0}
  .steps li{counter-increment:s;position:relative;padding:0 0 14px 34px;max-width:70ch}
  .steps li::before{content:counter(s);position:absolute;left:0;top:-1px;width:23px;height:23px;
    border:1px solid var(--line);border-radius:999px;display:grid;place-items:center;
    font-size:12.5px;color:var(--muted);background:var(--bg)}
  table{border-collapse:collapse;width:100%;margin:12px 0 0;font-size:14.5px}
  th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
  th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
  td.c{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:var(--muted);white-space:nowrap}
  .ask{border-left:3px solid var(--line);padding:2px 0 2px 14px;margin:0 0 10px;font-size:15.5px}
  .warn{border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:8px;
    padding:14px 16px;background:var(--panel);max-width:72ch}
  .warn p{margin:0 0 8px}
  .warn p:last-child{margin:0}
  @media (max-width:640px){td.c{white-space:normal}}
</style>
</head>
<body>
<main class="wrap">

  <header>
    <div class="eyebrow"><a href="./">OregonAI</a> · using the platform</div>
    <h1>Point an AI client at Oregon government</h1>
    <p class="lede">
      One endpoint gives a model searchable access to Oregon statutes and rules, legislative
      measures, budgets and expenditures, Secretary of State audits, agency performance
      measures, county code, collective bargaining agreements, and the federal instruments
      Oregon must comply with. It is free, public, and requires no account or key.
    </p>
    <div class="cta">
      <button class="endpoint" type="button" data-endpoint="__MCP__"
              title="Copy this endpoint into an MCP client — it does not open in a browser"><code>MCP</code>__MCP__</button>
    </div>
  </header>

  <section>
    <h2>Add it to Claude</h2>
    <p>Custom connectors are available on Free, Pro, Max, Team and Enterprise plans. Free
       accounts can hold one connector.</p>
    <ol class="steps">
      <li>Open <b>Settings → Connectors</b> in Claude.</li>
      <li>Click <b>+ Add custom connector</b>.</li>
      <li>Paste the endpoint above as the remote MCP server URL.</li>
      <li>Click <b>Add</b>. There is nothing to configure under Advanced settings — this
          server takes no authentication.</li>
    </ol>
    <p style="margin-top:14px">On Team and Enterprise plans an owner adds it once under
       <b>Organization settings → Connectors → Add → Custom → Web</b>, and members then
       connect it individually from their own Connectors page.</p>
    <p>For a client that reads a config file, such as Claude Desktop:</p>
    <pre><code>{
  "mcpServers": {
    "oregonai": { "url": "__MCP__" }
  }
}</code></pre>
  </section>

  <section>
    <h2>What to ask</h2>
    <p>Ask in plain language. The model decides which corpora to search; you do not have to
       know which one holds the answer. Start with <em>“what Oregon corpora can you see?”</em>
       to confirm the connection.</p>

    <p class="ask">“What does Oregon require for wildfire hazard mitigation in new
       construction, and what has it spent on it?”</p>
    <p>One question, one search, five corpora answering — the building-code standard, the bill
       that changed it, the appropriation, the audit, and the agency's own performance report:</p>
    <table>
      <tr><th>corpus</th><th>top result</th></tr>
      __WILDFIRE__
    </table>

    <p class="ask" style="margin-top:26px">“Resolve ORS 401.204 and tell me which corpora
       reference it.”</p>
    <p>One statute, reached five ways. Four corpora resolve it through their sibling index into
       the corpus that actually holds it, so the answer is one document with its provenance
       intact rather than five near-duplicates:</p>
    <table>
      <tr><th>corpus</th><th>resolved via</th></tr>
      __CITATION__
    </table>
    <p style="margin-top:12px;color:var(--muted);font-size:14px">
      Three further corpora reported that they recognised no citation of that form — which the
      answer states, rather than leaving it as silence.</p>

    <p class="ask" style="margin-top:26px">“Compare what the Department of Forestry reported
       achieving against what it was appropriated.”</p>
    <p>Spending and self-reported outcomes for one agency, side by side. Answers of this shape
       are the reason the platform exists:</p>
    <table>
      <tr><th>corpus</th><th>top results</th></tr>
      __FORESTRY__
    </table>
    <p style="margin-top:12px;color:var(--muted);font-size:14px">
      Performance figures are each agency's own report on itself — not an independent finding.
      The audits corpus is what disputes them.</p>
  </section>

  <section>
    <h2>Reading the answers</h2>
    <div class="warn">
      <p><b>These are non-authoritative mirrors, never the official text.</b> Every document
         carries a <code>source_url</code>; anything that matters should be checked against it.
         Ask the model to cite them — the servers instruct it to.</p>
      <p><b>Search always returns something.</b> Matching is partly semantic, so a corpus with
         nothing relevant still returns its nearest documents. A result is a candidate to check,
         not confirmation that the subject is covered.</p>
      <p><b>Every response says which corpora answered.</b> If one was slow or unreachable it is
         named, and the answer is marked partial. Not finding something is never the same as it
         not existing — ask what was actually searched.</p>
    </div>
  </section>

  <section>
    <h2>Connecting one corpus at a time</h2>
    <p>The endpoint above fronts every corpus and is the simplest way in. Each corpus also
       serves its own MCP endpoint, listed on the <a href="./">main page</a> — useful to pin a
       client to a single subject area, and unaffected by the gateway.</p>
    <p>Everything is open source. The corpora, the shared toolkit they are built on, and the
       contract they all answer are at <a href="__ORG_URL__">github.com/OregonAI</a>.</p>
  </section>

  <footer>
    <p>Sample results captured __CAPTURED__ against the live endpoint and reproducible by
       running the queries shown. Built __BUILT__.</p>
    <p>© __YEAR__ OregonAI · non-authoritative mirrors of public records · not legal advice</p>
  </footer>
</main>
<script>
  document.querySelectorAll('.endpoint').forEach(function(el){
    el.addEventListener('click', function(){
      var v = el.getAttribute('data-endpoint');
      navigator.clipboard && navigator.clipboard.writeText(v).then(function(){
        el.classList.add('copied');
        var c = el.querySelector('code'), was = c.textContent;
        c.textContent = 'copied';
        setTimeout(function(){ c.textContent = was; el.classList.remove('copied'); }, 1200);
      });
    });
  });
</script>
</body>
</html>
"""


def build() -> str:
    out = TEMPLATE
    for token, value in (
        ("__STYLE__", STYLE),
        ("__MCP__", GATEWAY["mcp"]),
        ("__WILDFIRE__", rows(WILDFIRE_HITS)),
        ("__CITATION__", rows(CITATION_PATHS)),
        ("__FORESTRY__", rows(FORESTRY_HITS)),
        ("__CAPTURED__", SAMPLES_CAPTURED),
        ("__ORG_URL__", ORG_URL),
        ("__BUILT__", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
        ("__YEAR__", str(date.today().year)),
    ):
        out = out.replace(token, value)
    return out


def main() -> None:
    SITE.mkdir(parents=True, exist_ok=True)
    path = Path(SITE) / "use.html"
    html = build()
    path.write_text(html, encoding="utf-8")
    print(f"wrote {path} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
