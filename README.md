# OregonAI.github.io

The organization landing page for the **Civic Corpus Platform**, served at
<https://oregonai.github.io/>.

This repository contains no corpus data. It renders one page describing the platform and
the corpora, and it reads every corpus fact live rather than storing it.

## How the corpus data gets here

Each corpus publishes `corpus-index.json` to its own GitHub Pages site as part of its
deploy. `build_site.py` reads the header of that file for each corpus in its registry:

- **index found** → the corpus renders as `Active` with its live document count and
  contract version, and links to its site.
- **no index** → the corpus renders with the `status` declared in the registry
  (`In progress` / `Planned`) and **no counts**. The page degrades to the registry rather
  than showing a stale or invented number.

The build prints exactly which corpora were probed live and which fell back, so a corpus
silently dropping off the page is visible in the Actions log rather than inferred from a
missing card.

`corpus-index.json` is ~8 MB, and only three scalars at the front of it are needed, so the
probe issues a `Range: bytes=0-2047` request. A full fetch is the fallback for a host that
ignores `Range`.

## Adding a corpus

Add an entry to `CORPORA` in `build_site.py`. Only the descriptive fields are
hand-maintained — `repo`, `name`, `scope`, `archetype`, a fallback `status`, an optional
`mcp` URL, and the blurb. Counts and live/active state come from the corpus itself.

## Building

```bash
python3 build_site.py            # probes each corpus, writes site/index.html
python3 build_site.py --offline  # registry-only render, no network (for local dev)
```

Stdlib only — no dependencies to install.

`site/` is generated and gitignored; it is built in CI on every push to `main`, weekly
(so a sibling corpus going live appears without a commit here), and on manual dispatch.

---

Unofficial and non-authoritative. Not affiliated with the State of Oregon. Every document
in every corpus links to its authoritative source; always verify there.
