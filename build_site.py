#!/usr/bin/env python3
"""Build the OregonAI organization landing page into ./site/ (gitignored, built at deploy).

This is the platform-level page: what the Civic Corpus Platform is, which corpora exist,
and where each one's own site, repo, and MCP server live. It is NOT a corpus itself and
holds no documents — every fact about a corpus is read from that corpus at build time.

Live aggregation, not a hand-maintained table. Each corpus publishes
`corpus-index.json` to its own Pages site as part of its deploy (see a corpus's
src/build_site.py). We read the header of that file to learn the corpus id, its
contract version, and its live document count. A corpus that has not shipped one yet
simply renders with its declared status and no counts — so this page degrades to the
registry rather than inventing numbers.

Why a ranged request: corpus-index.json is ~8 MB (it maps every document id to a title
and path, for cross-corpus citation resolution). We need three scalars from the front of
it. `Range: bytes=0-2047` gets them in one packet; the full-fetch fallback covers a host
that ignores Range or a corpus whose key order differs.

  python3 build_site.py           # writes ./site/index.html
  python3 build_site.py --offline # skip network probes (registry-only render, for dev)

Wired into .github/workflows/pages.yml, which runs this and deploys ./site/ on push
to main and on a weekly schedule (so a sibling corpus going live refreshes this page
without a commit here).
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, timezone, datetime
from pathlib import Path

SITE = Path(__file__).resolve().parent / "site"
ORG = "OregonAI"
ORG_URL = f"https://github.com/{ORG}"
PAGES = "https://oregonai.github.io"
TIMEOUT = 20

# The registry. `status` is the FALLBACK shown when a corpus publishes no index yet;
# any corpus that does publish one is reported Active with its live count, whatever
# this says. Keep descriptions honest about what is actually ingested.
#
# `group` decides which section a corpus renders under. It exists because federal-reference
# is `jurisdiction: us` and every other corpus stops at the state border — dropping a federal
# corpus into a list on a page titled "knowledge bases of Oregon government", with every
# sibling labelled "Oregon · …", reads as a mistake rather than a deliberate boundary. The
# grouping lives in the DATA rather than in a second list so the tiles keep counting every
# corpus with no arithmetic of their own.
CORPORA = [
    dict(
        repo="executive-regulatory-frameworks",
        group="oregon",
        name="Executive Regulatory Frameworks",
        scope="Oregon · executive branch",
        archetype="document",
        status="Active",
        mcp="https://oregonai.morficflux.com/executive-regulatory-frameworks/mcp",
        blurb="ORS statutes, OAR rules, executive orders, and agency policies, procedures, "
              "standards, and the Oregon Accounting Manual — with a mechanically-derived "
              "authority graph linking statute → rule → policy.",
    ),
    dict(
        repo="oregon-records-retention",
        group="oregon",
        name="Records Retention Schedules",
        scope="Oregon · Secretary of State Archives",
        archetype="document",
        status="In progress",
        mcp="https://oregonai.morficflux.com/oregon-records-retention/mcp",
        blurb="Agency-specific (SPECIAL) records-retention schedules. The general schedules "
              "in OAR chapter 166 live in Executive Regulatory Frameworks and are "
              "referenced here, never copied.",
    ),
    dict(
        repo="oregon-legislature",
        group="oregon",
        name="Legislative Measures",
        scope="Oregon · legislature",
        # hybrid, not api. The seed spec called for a pure OData proxy; PHASE5-MCP-SPEC
        # overrode that after measuring OData's substringof() miss 84 of 121 relevant
        # bills, so measures are mirrored and only status is proxied. _meta/corpus.yml
        # in that repo is the authority and says hybrid.
        archetype="hybrid",
        status="In progress",
        mcp="https://oregonai.morficflux.com/oregon-legislature/mcp",
        blurb="Mirrored measure metadata and bill text, with live status proxied from the "
              "Legislature's OData feed — the bill end of the bill → statute → rule chain.",
    ),
    dict(
        repo="oregon-budget",
        group="oregon",
        name="Budget & Expenditure",
        scope="Oregon · statewide",
        archetype="hybrid",
        status="In progress",
        mcp="https://oregonai.morficflux.com/oregon-budget/mcp",
        blurb="Where the money authorized by statute actually goes — the dollars node of "
              "the graph. 544 agency-year expenditure summaries over a 668,906-row "
              "mirror of state spending, plus appropriation line items extracted from "
              "budget bills and referenced back to the Legislature corpus.",
    ),
    dict(
        repo="oregon-audits",
        group="oregon",
        name="Audits",
        scope="Oregon · Secretary of State Audits Division",
        archetype="document",
        status="In progress",
        mcp="https://oregonai.morficflux.com/oregon-audits/mcp",
        blurb="Secretary of State audit reports, 2020 to present — findings, "
              "recommendations, and the audited agency's response. The audit node of the "
              "graph, and the only one that reports on whether the rest of the chain "
              "actually worked: 71% of reports cite the statutes and rules they examined.",
    ),
    dict(
        repo="oregon-kpm",
        group="oregon",
        name="Key Performance Measures",
        scope="Oregon · Legislative Fiscal Office",
        archetype="document",
        status="Active",
        mcp="https://oregonai.morficflux.com/oregon-kpm/mcp",
        blurb="Annual Performance Progress Reports, 2016 to 2025 — the targets and actuals "
              "every agency reports to the Legislature, with the year-on-year series "
              "derived across 785 reports. The outcome side of Budget: that corpus answers "
              "what was appropriated and spent, this one what the agency then claimed it "
              "achieved. Every number is the agency's own account of itself.",
    ),
    dict(
        repo="federal-reference",
        group="federal",
        name="Federal Reference",
        # The first non-Oregon scope on this page, and the reason `group` exists.
        scope="United States · federal instruments",
        archetype="document",
        status="Active",
        mcp="https://oregonai.morficflux.com/federal-reference/mcp",
        blurb="The federal requirements Oregon agencies are audited against — 2 CFR 200 "
              "(the Uniform Guidance), the CJIS Security Policy, IRS Publication 1075, "
              "WIOA and Perkins V, plus the 38 sections of 2 CFR 200 Oregon actually "
              "cites, each individually addressable. Where the authority chain goes when "
              "it leaves the state.",
    ),
]

PLATFORM = [
    dict(repo="corpus-toolkit", name="corpus-toolkit",
         blurb="The versioned core: frontmatter schemas, provenance and citation validators, "
               "reusable CI workflows, and the MCP server framework every corpus speaks "
               "through. Corpora pin a tag."),
    dict(repo="corpus-template", name="corpus-template",
         blurb="Template repository. Every new corpus starts here and inherits the contract, "
               "the workflows, and the disclaimer discipline on day one."),
]


# ---------- live corpus probing ----------

def _get(url: str, byte_range: str | None = None) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": f"{ORG}-site-builder"})
    if byte_range:
        req.add_header("Range", byte_range)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def probe(repo: str) -> dict | None:
    """Live {corpus, contract_version, n_documents} for a corpus, or None if it publishes
    no index yet. Ranged read first; full fetch only if that comes back unparseable."""
    url = f"{PAGES}/{repo}/corpus-index.json"
    head = _get(url, "bytes=0-2047")
    if head:
        text = head.decode("utf-8", "ignore")
        m_id = re.search(r'"corpus"\s*:\s*"([^"]+)"', text)
        m_n = re.search(r'"n_documents"\s*:\s*(\d+)', text)
        m_v = re.search(r'"contract_version"\s*:\s*(\d+)', text)
        if m_id and m_n:
            return {"corpus": m_id.group(1), "n_documents": int(m_n.group(1)),
                    "contract_version": int(m_v.group(1)) if m_v else None}
    body = _get(url)          # Range ignored, or unusual key order — pay for the full file
    if not body:
        return None
    try:
        d = json.loads(body)
    except json.JSONDecodeError:
        return None
    if "n_documents" not in d:
        return None
    return {"corpus": d.get("corpus", repo), "n_documents": int(d["n_documents"]),
            "contract_version": d.get("contract_version")}


def site_live(repo: str) -> bool:
    return _get(f"{PAGES}/{repo}/", "bytes=0-64") is not None


def repo_live(repo: str) -> bool:
    """Does the repository exist yet? A planned corpus may have no repo, and linking one
    that 404s is worse than showing no link — so the link is earned, not assumed. Probed
    rather than declared in the registry so the link appears by itself once the repo is
    created."""
    return _get(f"{ORG_URL}/{repo}", "bytes=0-64") is not None


# ---------- rendering ----------

def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def commas(n) -> str:
    return f"{n:,}" if isinstance(n, int) else "—"


def build(offline: bool = False) -> str:
    live, notes = {}, []
    for c in CORPORA:
        if offline:
            c["has_repo"] = True
            continue
        c["has_repo"] = repo_live(c["repo"])
        if not c["has_repo"]:
            notes.append(f"  {c['repo']}: no repository yet — link suppressed")
        info = probe(c["repo"])
        if info:
            live[c["repo"]] = {**info, "site": site_live(c["repo"])}
            notes.append(f"  {c['repo']}: live, {info['n_documents']:,} documents")
        else:
            notes.append(f"  {c['repo']}: no published index — rendering as "
                         f"'{c['status']}' with no counts")
    print("corpus probe:" if not offline else "corpus probe: skipped (--offline)")
    for n in notes:
        print(n)

    total_docs = sum(v["n_documents"] for v in live.values())
    n_active = len(live)

    tiles = [
        (commas(total_docs) if live else "—", "documents",
         "mirrored verbatim with provenance, across every active corpus"),
        (str(n_active) if not offline else "—", "corpora live",
         f"of {len(CORPORA)} planned, each its own repository and MCP server"),
        ("1", "interface contract",
         "every corpus server answers the same tool signatures"),
    ]
    tile_html = "\n".join(
        f'<div class="tile"><div class="num">{v}</div><div class="lbl">{esc(l)}</div>'
        f'<div class="sub">{esc(s)}</div></div>' for v, l, s in tiles)

    # Cards are bucketed by `group` rather than emitted as one list, so a federal corpus does
    # not appear unexplained among five labelled "Oregon · …". Unknown groups fall back to
    # "oregon", so a new entry that forgets the key still renders somewhere visible instead of
    # vanishing into a section that is never printed.
    grouped: dict[str, list[str]] = {"oregon": [], "federal": []}
    for c in CORPORA:
        info = live.get(c["repo"])
        status = "Active" if info else c["status"]
        cls = {"Active": "ok", "In progress": "wip"}.get(status, "plan")
        bits = []
        if info:
            bits.append(f'{commas(info["n_documents"])} documents')
            if info.get("contract_version"):
                bits.append(f'contract v{info["contract_version"]}')
        bits.append(esc(c["archetype"]))
        links = []
        if info and info.get("site"):
            links.append(f'<a href="{PAGES}/{c["repo"]}/">Explore the corpus →</a>')
        if c.get("has_repo", True):
            links.append(f'<a href="{ORG_URL}/{c["repo"]}">Repository →</a>')
        else:
            links.append('<span class="meta">Repository not created yet</span>')
        if c["mcp"]:
            links.append(f'<a href="{c["mcp"]}"><code>MCP</code> →</a>')
        group = c.get("group", "oregon")
        if group not in grouped:      # unknown group -> visible, never silently dropped
            group = "oregon"
        grouped[group].append(
            f'''<div class="card">
          <div class="chip {cls}">{esc(status)}</div>
          <h3>{esc(c["name"])}</h3>
          <div class="meta">{esc(c["scope"])}</div>
          <p>{esc(c["blurb"])}</p>
          <div class="meta mono">{" · ".join(bits)}</div>
          <div class="links">{" ".join(links)}</div>
        </div>''')

    # The federal section renders ONLY when something is in it. An empty <section> with a
    # heading and a justification for corpora that are not there would be worse than no
    # section at all, and this file is the kind of thing that gets copied to a new platform.
    federal_html = ""
    if grouped["federal"]:
        federal_html = f'''
  <section>
    <h2>Federal requirements Oregon answers to</h2>
    <p class="lede">Oregon agencies are audited against federal rules, so the authority chain
    does not stop at the state border. These corpora are not Oregon government — they are what
    Oregon government must comply with.</p>
    <div class="cards">{"".join(grouped["federal"])}</div>
  </section>'''

    plat = "\n".join(
        f'''<div class="card">
          <h3><code>{esc(p["name"])}</code></h3>
          <p>{esc(p["blurb"])}</p>
          <div class="links"><a href="{ORG_URL}/{p["repo"]}">Repository →</a></div>
        </div>''' for p in PLATFORM)

    # Sentinel replacement rather than str.format: the template is mostly CSS and JS, both
    # of which are full of braces that .format() would try to interpret as fields.
    # Same approach as a corpus's build_topic_map.py.
    out = TEMPLATE
    for token, value in (
        ("<!--TILES-->", tile_html),
        ("<!--CORPORA-->", "\n".join(grouped["oregon"])),
        ("<!--FEDERAL-->", federal_html),
        ("<!--PLATFORM-->", plat),
        ("__ORG_URL__", ORG_URL),
        ("__BUILT__", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
        ("__YEAR__", str(date.today().year)),
    ):
        out = out.replace(token, value)
    return out


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OregonAI — public, agent-readable knowledge bases of Oregon government</title>
<meta name="description" content="The Civic Corpus Platform: public, non-authoritative, machine-readable knowledge bases of Oregon government rules, processes, and data — one repository per corpus, one MCP interface contract.">
<style>
  :root{
    --bg:#f6f7f9; --panel:#ffffff; --ink:#161a20; --muted:#5a6472; --line:#e4e8ee;
    --accent:#1f6feb; --accent-ink:#0b4bc0; --gold:#8a6d1f;
    --ok:#1a7f4b; --wip:#8a6d1f; --plan:#5a6472;
    --shadow:0 1px 2px rgba(20,25,40,.06),0 8px 30px rgba(20,25,40,.07);
  }
  @media (prefers-color-scheme:dark){
    :root{--bg:#0e1116; --panel:#161b22; --ink:#e8ecf2; --muted:#9aa4b2; --line:#232a33;
      --accent:#5a9bff; --accent-ink:#8fbaff; --gold:#d9b45a;
      --ok:#57cf92; --wip:#d9b45a; --plan:#9aa4b2;
      --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 34px rgba(0,0,0,.45);}
  }
  :root[data-theme="light"]{--bg:#f6f7f9;--panel:#fff;--ink:#161a20;--muted:#5a6472;--line:#e4e8ee;--accent:#1f6feb;--accent-ink:#0b4bc0;--gold:#8a6d1f;--ok:#1a7f4b;--wip:#8a6d1f;--plan:#5a6472;}
  :root[data-theme="dark"]{--bg:#0e1116;--panel:#161b22;--ink:#e8ecf2;--muted:#9aa4b2;--line:#232a33;--accent:#5a9bff;--accent-ink:#8fbaff;--gold:#d9b45a;--ok:#57cf92;--wip:#d9b45a;--plan:#9aa4b2;}
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased}
  a{color:var(--accent-ink);text-decoration:none} a:hover{text-decoration:underline}
  .wrap{max-width:960px;margin:0 auto;padding:0 22px}
  .disc{background:var(--gold);color:#1a1400;font-size:13px;text-align:center;padding:7px 14px;font-weight:600;letter-spacing:.01em}
  header{padding:64px 0 26px;border-bottom:1px solid var(--line)}
  .eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:12px;color:var(--muted);font-weight:700;margin-bottom:14px}
  h1{font-size:clamp(30px,5vw,46px);line-height:1.08;margin:0 0 16px;letter-spacing:-.02em;text-wrap:balance;font-weight:800}
  .lede{font-size:19px;color:var(--muted);max-width:64ch;margin:0}
  .cta{display:flex;flex-wrap:wrap;gap:12px;margin-top:26px}
  .btn{display:inline-flex;align-items:center;gap:8px;padding:11px 18px;border-radius:10px;font-weight:650;font-size:15px;border:1px solid var(--line);background:var(--panel);color:var(--ink);box-shadow:var(--shadow)}
  .btn.primary{background:var(--accent);color:#fff;border-color:transparent}
  .btn:hover{text-decoration:none;transform:translateY(-1px)}
  section{padding:44px 0}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
  .tile{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px 20px 18px;box-shadow:var(--shadow)}
  .tile .num{font-size:32px;font-weight:800;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
  .tile .lbl{font-weight:650;margin-top:2px}
  .tile .sub{color:var(--muted);font-size:13.5px;margin-top:5px;line-height:1.45}
  h2{font-size:14px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:0 0 18px;font-weight:700}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px;box-shadow:var(--shadow);display:flex;flex-direction:column}
  .card h3{margin:0 0 4px;font-size:18px;letter-spacing:-.01em}
  .card p{margin:10px 0 14px;color:var(--muted);font-size:14.5px;flex:1}
  .card .meta{color:var(--muted);font-size:13px}
  .card .meta.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;margin-bottom:14px}
  .card .links{display:flex;flex-wrap:wrap;gap:14px;font-weight:650;font-size:14.5px}
  .chip{align-self:flex-start;font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
    padding:3px 9px;border-radius:999px;border:1px solid currentColor;margin-bottom:10px}
  .chip.ok{color:var(--ok)} .chip.wip{color:var(--wip)} .chip.plan{color:var(--plan)}
  .chain{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px;box-shadow:var(--shadow)}
  .chain .flow{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14.5px;line-height:2;
    color:var(--ink);overflow-x:auto;white-space:nowrap;padding-bottom:6px}
  .chain .flow b{color:var(--accent-ink);font-weight:700}
  /* revision is emergent from git, not a corpus — styled apart so the chain does not
     read as eight bodies to build */
  .chain .flow .emergent{color:var(--muted);font-weight:700;font-style:italic}
  code{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:13px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  ul.plain{margin:0;padding-left:20px;color:var(--muted);font-size:14.5px}
  ul.plain li{margin:7px 0}
  footer{border-top:1px solid var(--line);padding:30px 0 60px;color:var(--muted);font-size:13.5px}
  footer p{margin:6px 0}
  #theme{position:fixed;top:14px;right:14px;width:36px;height:36px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer;box-shadow:var(--shadow);font-size:16px;z-index:5}
</style>
</head>
<body>
<button id="theme" title="Toggle light/dark" aria-label="Toggle theme">◑</button>
<div class="disc">NON-AUTHORITATIVE reference — not the official text of Oregon law. Always verify against each document's cited source.</div>
<div class="wrap">
  <header>
    <div class="eyebrow">Civic Corpus Platform · Oregon</div>
    <h1>Government rules, made readable by machines</h1>
    <p class="lede">Public knowledge bases of Oregon government rules, processes, and data.
      Each corpus is a Markdown-and-graph repository with strict provenance guardrails and
      an MCP server, so an AI agent can cite the law instead of recalling it.</p>
    <div class="cta">
      <a class="btn primary" href="__ORG_URL__">Browse the organization →</a>
      <a class="btn" href="__ORG_URL__/corpus-toolkit">The toolkit</a>
      <a class="btn" href="__ORG_URL__/corpus-template">Start a corpus</a>
    </div>
  </header>

  <section>
    <div class="grid"><!--TILES--></div>
  </section>

  <section>
    <h2>Corpora</h2>
    <div class="cards"><!--CORPORA--></div>
  </section>
<!--FEDERAL-->

  <section>
    <h2>Platform</h2>
    <div class="cards"><!--PLATFORM--></div>
  </section>

  <section>
    <h2>The graph we're building</h2>
    <div class="chain">
      <div class="flow">
        <b>bill</b> → <b>statute</b> → <b>rule</b> → <b>policy</b> → <b>standard</b> →
        <b>dollars</b> → <b>audit</b> → <b>federal requirement</b> →
        <span class="emergent">revision</span>
      </div>
      <p style="color:var(--muted);font-size:14.5px;margin:14px 0 0">
        Each corpus contributes nodes and edge types to one graph. Because every server
        implements the same <code>resolve_citation</code> contract, an agent can follow a
        citation out of one corpus and into another — from the bill that authorized a
        program to the rule that runs it. Corpora reference each other; they never copy.
      </p>
      <p style="color:var(--muted);font-size:13.5px;margin:12px 0 0">
        Every node except <span class="emergent">revision</span> is now
          populated by a live corpus. <b>federal requirement</b> is the newest and the
          only one outside Oregon: an audit finds an agency out of compliance with
          2 CFR 200.303, and that citation now resolves to the text it was measured
          against instead of stopping at the state border. <span class="emergent">revision</span> is the exception
        and will never be a corpus — every corpus is a git repository, so its revision
        history already <em>is</em> the diff trail, with no separate body to ingest.
      </p>
    </div>
  </section>

  <section>
    <h2>How these corpora are built</h2>
    <ul class="plain">
      <li><b>Verbatim or labeled.</b> Mirrored text is reproduced exactly and marked
        <code>[VERBATIM]</code>; anything condensed is marked <code>[SUMMARY]</code>.
        Nothing is paraphrased into the record silently.</li>
      <li><b>Provenance on every document.</b> Source URL, retrieval date, and effective
        date travel in frontmatter and are validated in CI — a document that cannot say
        where it came from does not merge.</li>
      <li><b>Generated, not curated by hand.</b> Authority graphs, indexes, and site pages
        are built from the corpus on every push, so they cannot quietly fall behind it.</li>
      <li><b>Non-authoritative by construction.</b> Every corpus carries the disclaimer
        above and links each document to the official text. These are research aids, not
        a substitute for the law.</li>
    </ul>
  </section>

  <footer>
    <p><b>OregonAI</b> — Civic Corpus Platform. Built __BUILT__; corpus counts are read live
      from each corpus at build time.</p>
    <p>Unofficial and non-authoritative. Not affiliated with the State of Oregon.
      © __YEAR__.</p>
  </footer>
</div>
<script>
(function(){
  var b=document.getElementById('theme'),r=document.documentElement;
  try{var s=localStorage.getItem('theme'); if(s) r.setAttribute('data-theme',s);}catch(e){}
  b.addEventListener('click',function(){
    var cur=r.getAttribute('data-theme')||
      (matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
    var next=cur==='dark'?'light':'dark';
    r.setAttribute('data-theme',next);
    try{localStorage.setItem('theme',next);}catch(e){}
  });
})();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true",
                    help="skip network probes; render from the registry only")
    args = ap.parse_args()
    SITE.mkdir(exist_ok=True)
    html = build(args.offline)
    (SITE / "index.html").write_text(html, encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {SITE / 'index.html'} ({len(html):,} bytes)")


if __name__ == "__main__":
    sys.exit(main())
