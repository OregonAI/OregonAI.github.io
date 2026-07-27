# Backlog — OregonAI.github.io

Follow-ups for the organization landing page. This repo holds no corpus data; everything
here is about how the page stays truthful about corpora it does not own.

## Done

- **Weekly rebuild.** `.github/workflows/pages.yml` runs on `schedule: cron "17 8 * * 1"`
  (Mondays, 08:17 UTC) in addition to push and `workflow_dispatch`. The page reads each
  corpus's `corpus-index.json` at build time, so it goes stale when a *sibling* changes and
  nothing here does — the cron is what picks that up. Force one immediately with:

  ```bash
  gh workflow run pages -R OregonAI/OregonAI.github.io
  ```

## Open

- **A failed probe is indistinguishable from "no index published" — and it silently
  understates the platform.** `probe()` in `build_site.py` returns `None` for every failure
  mode: a corpus that has not shipped an index yet, a network timeout, a Pages outage, a
  ratelimit. The renderer treats them identically — the corpus loses its document count,
  and because the "documents" tile sums only successful probes, a transient blip on
  `executive-regulatory-frameworks` would publish a page claiming the platform has **no
  documents at all**, with the build still green.

  This is the failure mode most likely to actually bite, precisely because the weekly cron
  makes it unattended: nobody is watching the run that breaks it, and the page looks
  intentional rather than broken. Fix by separating the cases — `None` for "no index
  published" vs. an error for "could not reach a corpus that is supposed to be Active" —
  and then either fail the build (so the last good deploy stays up) or carry forward the
  last known count with an "as of" date. Failing the build is probably right: an unattended
  weekly job should not be able to quietly replace a good page with a worse one.

- **Event-driven refresh instead of waiting up to a week.** The cron closes the staleness
  hole but with up to 7 days of lag, so a corpus going live is invisible until the next
  Monday. Have each corpus's own `pages.yml` fire a `repository_dispatch` at this repo
  after a successful deploy, and keep the weekly run as the safety net for anything that
  misses. Needs a token with `contents: write` on this repo available to the sibling repos —
  the reason this wasn't done up front.

- **Decide what the org profile README is for now.** `OregonAI/.github` renders a corpus
  registry table on github.com/OregonAI that this page now covers in more detail and keeps
  current automatically. Two sources of the same list will drift, and the README is the one
  that drifts silently. Either trim it to a short pointer at <https://oregonai.github.io/>,
  or generate it from the same registry.

- **The MCP link returns 406 to a browser.** Correct behavior — MCP servers want a POST with
  specific `Accept` headers, not a navigation — but it is rendered as an ordinary link, so
  clicking it looks broken to a human. Present it as a copyable endpoint rather than an
  `<a href>`, or point it at setup docs. (`executive-regulatory-frameworks`'s own site has
  the same issue; worth fixing in both.)

- **No link checking in CI.** Both problems found at launch were bad links: a card pointing
  at a repo that did not exist, and Pages defaulting to the legacy Jekyll builder. The
  corpus repos already run a `check-links.yml`; this repo does not. Cheap to add, and it
  guards exactly the class of regression that the live-probing design can introduce.
