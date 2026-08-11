# Wiring the frontend to relevance scoring

Handoff doc for a session picking up the frontend work. Everything below was verified
against the running stack and the code on `main` as of 2026-08-10.

## The situation

The Aug 8 work added **facet relevance scoring** to the backend: every scanned listing
gets scored on whether it is actually the thing you searched for, not just cheap. The
API serves those scores today. **The frontend has never been touched** — `frontend/` is
unchanged since the initial commit (`827e7bf`), so the feature is invisible in the UI.

Concretely: a listing for a *PS5 vertical stand* can still rank above a real console,
because the UI sorts client-side on raw discount and ignores the relevance score
entirely. Server-side the gate works and suppresses the notification — the user just
can't see any of it.

## Stack and dev loop

React 19 · Vite 8 · Tailwind 4 (via `@tailwindcss/vite`) · react-router-dom 7 · TypeScript 5.9.

```bash
docker compose up -d          # backend on :8000
cd frontend && npm install && npm run dev    # UI on :5173
```

`frontend/vite.config.ts` proxies `/api` → `http://localhost:8000`, so the dev server
talks to the containerized backend with no CORS setup. Use this loop — do **not**
iterate by rebuilding the Docker image, since the Dockerfile bakes the frontend in at
build time (`npm ci && npm run build` in stage 1) and a rebuild is several minutes.

Typecheck with `npm run build` (`tsc -b && vite build`). There is **no frontend test
runner** — `test_ui.py` at the repo root is Playwright-based but `pytest-playwright` was
never added as a dependency, so all 21 of its tests error out on a missing `page`
fixture. Assume manual verification unless you add the dep.

## Backend contract (verified against the live API)

`GET /api/listings` — `backend/routers/listings.py:11`

| Param | Type | Default |
|---|---|---|
| `item_name` | string | — |
| `deal_quality` | string | — |
| `limit` | int | 100 |
| `offset` | int | 0 |
| **`sort`** | `final` \| `relevance` \| `deal` \| `price` \| `recent` | `recent` |

`sort` is the new one. It is a `Literal` in FastAPI and a whitelist dict in
`backend/db.py:202` (`SORT_CLAUSES`), so an unknown value is a 422 — it never reaches
SQL. All scored sorts push NULLs last so pre-migration rows don't squat the top.

Three new fields on every listing (`backend/models.py:67-69`):

```
relevance_score: float | null   # [0,1] — is this actually the item?
final_score:     float | null   # [0,1] — relevance × price attractiveness
match_details:   string | null  # JSON-ENCODED STRING, not an object
```

### What the numbers mean

- `relevance_score` — facet match from `score_listing()`. `0.0` means disqualified
  (an exclusion term like "for parts" or "broken" fired).
- `price_score` = `1 - price/fair_price`, clamped to `[0,1]`. Not persisted; derivable.
- `final_score = relevance × price_score` (`backend/relevance.py:203`). They **multiply**
  deliberately: a great price on the wrong item must collapse to ~0, not average out to
  "decent". This is the field to sort by for "best actual deals".
- `settings.notify_min_relevance` (default `0.5`) is the email cutoff. Below it the
  listing is still stored and shown — only the notification is skipped. A UI hint at
  this threshold would explain to the user why a cheap item never emailed them.

`match_details` parses to (`backend/relevance.py:81`):

```json
{"score": 0.83, "matched": ["model", "storage"], "missed": ["color"], "excluded_by": null}
```

`excluded_by` is the exclusion term that disqualified the listing, or `null`. When it is
set, `score` is `0.0` and that string is the single most useful thing to show the user —
it is the literal reason the listing was rejected.

## The four gaps

1. **`frontend/src/api.ts:32-45`** — the `Listing` interface stops at `first_seen`.
   The three new fields aren't declared, so they're dropped on arrival. Add them as
   nullable.
2. **`frontend/src/api.ts:102-115`** — `getListings` builds its query string from
   `item_name`/`deal_quality`/`limit`/`offset` only. No `sort`. Add it.
3. **`frontend/src/pages/Listings.tsx:6,83-101`** — `SortKey` is
   `newest|price-low|price-high|discount`, sorted client-side in a `useMemo`. It has no
   relevance option and never calls the backend's `sort`.
4. **`frontend/src/components/ListingsTable.tsx`** — renders item tag, deal badge,
   title, location, date, price, fair price, discount. Nothing about relevance.

## Traps

**`match_details` is a string.** It is stored via `json.dumps` and typed `str` in the
Pydantic model, so it arrives as an encoded string, not a nested object. You must
`JSON.parse` it, in a `try/catch` — a malformed value should degrade to "no details",
never blank the row.

**Right now 100% of rows are unscored.** 140 listings in the DB, **0** with a
`relevance_score` — all NULL from the migration. Null handling is not an edge case here,
it is the only case you'll see until fresh listings arrive. Every new UI element needs a
sensible unscored state (omit the badge rather than render "0%" or "NaN").

**Rescanning will not backfill.** `upsert_listing` uses
`INSERT ... ON CONFLICT(fb_id) DO NOTHING` (`backend/db.py:186`) and returns `None` for
an existing row. Already-seen listings are never updated, so those 140 rows stay NULL
permanently. Only genuinely new `fb_id`s get scored. Don't burn time running scans
expecting the existing data to light up.

**A live scan is probably blocked anyway.** `~/.config/marketswipe/fb_state.json` is dated
Apr 2 — a four-month-old session cookie that will likely fail auth. See below for
seeding instead.

**Client sort will silently override server sort.** `Listings.tsx` currently fetches
`{limit: 500}` and re-sorts everything locally. If you add `sort` to the request but
leave the `useMemo` switch in place, the local sort wins and nothing appears to change.
Pick one. Note they aren't equivalent: the backend sorts **before** `LIMIT`, so
server-side `sort=final` returns the globally best 500, whereas the client sorts only
whatever 500 came back. Server-side is the correct semantics for ranking; it does mean
changing the sort now requires a refetch.

**Blast radius.** `ListingsTable` is shared by `Listings.tsx:198` and
`Dashboard.tsx:173`, and `DashboardStats.recent_deals` is typed `Listing[]`. Editing the
card lights up both pages at once — check the `compact` variant, which the dashboard
uses and which has tighter space.

## Getting test data without Facebook

Seed a few rows directly so you can build against real shapes, including the
disqualified case:

```bash
docker compose exec backend python3 -c "
import sqlite3, json
c = sqlite3.connect('/app/data/marketswipe.db')
rows = [
    (0.95, 0.38, {'score':0.95,'matched':['model','storage'],'missed':[],'excluded_by':None}),
    (0.62, 0.10, {'score':0.62,'matched':['model'],'missed':['storage','color'],'excluded_by':None}),
    (0.00, 0.00, {'score':0.0,'matched':[],'missed':['model'],'excluded_by':'for parts'}),
]
ids = [r[0] for r in c.execute('SELECT id FROM listings ORDER BY id LIMIT 3')]
for lid, (rel, fin, det) in zip(ids, rows):
    c.execute('UPDATE listings SET relevance_score=?, final_score=?, match_details=? WHERE id=?',
              (rel, fin, json.dumps(det), lid))
c.commit()
print('seeded', ids)
"
```

Then `curl -s 'localhost:8000/api/listings?sort=final&limit=5' | python3 -m json.tool`
to confirm the seeded rows sort to the top and the rest fall below on NULLs-last.

This is local dev data only — it writes to the `app-data` volume, not to anything shared.

## Suggested order

1. `api.ts` — add the three fields to `Listing`, add `sort` to `getListings`. Cheap and
   unblocks everything else.
2. `ListingsTable` — surface relevance on the card. Highest value per line changed, and
   it hits both pages. Suggest: a match badge when `relevance_score != null`, and when
   `excluded_by` is set, a muted "Excluded: for parts" chip with the row dimmed. The
   existing `dealStyles` map at the top of the file is the natural place for the styling.
3. `Listings.tsx` — extend `SortKey` with `final` and `relevance`, map to the backend
   values, move the fetch into the sort dependency, and delete the client-side sort
   branches you've replaced. **Default the sort to `final`** (see the DECIDED section)
   and set `sort: "final"` on the `Dashboard.tsx` fetch at the same time, so both
   surfaces change together rather than disagreeing for a commit.
4. Optional: expose `matched`/`missed` in a hover or expandable detail. Genuinely useful
   for debugging why something scored badly, but it's polish — do it after the above.

## DECIDED: default sort is `final`

Confirmed by the owner on 2026-08-10. Both listing surfaces should load ranked by
`final_score` descending, not by recency. Two places to set it:

- `frontend/src/pages/Listings.tsx:20` — initial sort state becomes the `final` option
  (currently `useState<SortKey>("newest")`).
- `frontend/src/pages/Dashboard.tsx:20` — the fetch becomes
  `api.getListings({ limit: 200, sort: "final" })`.

**No backend change is needed.** The API default stays `recent` (`routers/listings.py:17`)
and the frontend asks for `final` explicitly. Leaving the API default alone keeps the
endpoint's behavior stable for any other consumer.

Two things that make this cleanly frontend-only:

- **`DashboardStats.recent_deals` is dead.** The server computes it
  (`routers/listings.py:25-27`, hardcoded to recency) and ships it over the wire, but
  `Dashboard.tsx` never reads it — it renders `groupedByItem`, derived from its own
  `getListings` call. So the one ordering you *couldn't* fix from the frontend is one
  nothing displays. Ignore the field; don't try to sort it.
- **`Dashboard.tsx:174` shows `group.deals.slice(0, 4)`** per watch item, in fetch order.
  Sorting the fetch by `final` directly upgrades which four deals surface — this is
  where the decision pays off most visibly.

### Read this before you flip the default

**With today's data, `sort=final` shows the OLDEST listings first, and it looks broken.**
Every row's `final_score` is NULL, so `ORDER BY final_score IS NULL, final_score DESC`
ties all 140 rows and SQLite falls back to insertion order. Measured against the live
API just now:

```
sort=final   -> id=1    2026-04-02  LIKE NEW M4 MAC MINI          <- oldest first
sort=recent  -> id=131  2026-04-16  antique Chinese export ...    <- newest first
```

So the moment you change the default, the dashboard and listings page flip from
newest-first to oldest-first with no scores visible anywhere. That is expected and is
*not* a bug in your wiring — it is the pre-migration NULL backfill gap showing through.

**Seed the DB first** (script in the section above), then build. Otherwise you will be
designing a relevance UI against 140 rows that have no relevance data, and the ordering
will actively mislead you about whether your changes work.

If it matters to the user that the UI stays sensible before real scored data arrives,
the cheap mitigation is a secondary sort key on the backend — `ORDER BY final_score IS
NULL, final_score DESC, first_seen DESC` in `SORT_CLAUSES` (`backend/db.py:203`) — so
unscored rows at least fall back to newest-first. That is a one-line backend change and
outside the frontend-only scope; raise it rather than assuming it.

One knock-on worth knowing: `groupedByItem` counts totals from the fetched page
(`Dashboard.tsx:44`), so the per-item count means "within the top 200 fetched", not "all
listings". That's already true today with `recent`; switching to `final` changes *which*
200, not whether the count is approximate. Not a regression, just don't be surprised when
counts shift after the change.

## Rebrand to MarketSwipe — frontend scope

The only brand string in the frontend is `frontend/src/components/Layout.tsx:25`
("Marketplace Sniper"). Also check `frontend/index.html` for a `<title>`.

**Changing it breaks a test assertion.** `test_ui.py:18` asserts
`"Marketplace Sniper" in nav_text`. That suite cannot currently run (missing
`pytest-playwright`, see above), so it will not fail in CI today — it will fail later
when someone installs the dep, with a confusing message. Update the assertion in the
same change even though you cannot execute it.

**The backend rebrand is already done** (2026-08-10) — FastAPI title, notification email
body, logs, celery app name, README, and package name all say MarketSwipe. The
load-bearing paths were migrated too, with the data moved rather than recreated:

| Was | Now |
|---|---|
| `sniper.db` | `marketswipe.db` |
| `~/.config/sniper/` | `~/.config/marketswipe/` |
| volume `fb-mktplace_app-data` | `marketswipe_app-data` (140 listings copied) |
| repo dir `fb-mktplace` | `marketswipe` |

`docker-compose.yml` now pins `name: marketswipe`, so the volume namespace no longer
depends on the directory name.

**One frontend fix the rename left for you.** `frontend/src/pages/Dashboard.tsx:85`
hardcodes the old absolute path in the FB-login onboarding instruction it shows the user:

```
cd /Users/mramasub/misc/fb-mktplace && VIRTUAL_ENV= uv run python -c "..."
```

Change `fb-mktplace` to `marketswipe`. It is not broken today — a
`fb-mktplace -> marketswipe` symlink was left in place precisely so in-flight sessions
and stale paths keep resolving — but the symlink is a transition aid, not permanent, and
the string is shown to the user. This was deliberately left for you rather than edited
underneath you, since you are already changing `Dashboard.tsx:20` for the sort default
and a concurrent edit to the same file would conflict.

## Verify when done

```bash
cd frontend && npm run build            # must typecheck clean
curl -s 'localhost:8000/api/listings?sort=final&limit=3' | python3 -m json.tool
curl -s -o /dev/null -w '%{http_code}\n' 'localhost:8000/api/listings?sort=bogus'   # expect 422
```

Then check the seeded rows render correctly — scored, unscored, and excluded — on both
`/listings` and the dashboard. To ship it into the container image, a full
`docker compose up -d --build` is required; the dev server does not update `dist/`.
