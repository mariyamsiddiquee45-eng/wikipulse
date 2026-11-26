# Verified data sources

Checked against the live APIs on 2026-11-26. Every response used by the pipeline must match
these shapes or fail loudly; fixtures are recorded from these exact URLs.

## Pageviews: top articles per day

```
GET https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/2024/01/15
```

- Earliest day with data: 2015-07-01. A request for 2015-06-30 returns 404 with a
  "no data for those date(s)" detail.
- Returns up to 1000 articles; observed 999 on 2024-01-15.
- Date path is `YYYY/MM/DD`, not the compact `YYYYMMDD` used by per-article requests.
- Response:

```json
{"items":[{"project":"en.wikipedia","access":"all-access","year":"2024","month":"01","day":"15",
  "articles":[{"article":"Main_Page","views":5046651,"rank":1}]}]}
```

- `article` is the raw wiki title with underscores. It can include namespaces
  (`Special:Search`, `Wikipedia:Featured_pictures`, `File:...`, `User:...`) and
  percent-encoded or non-ASCII titles.
- Data for yesterday was available when checked. Today's file is partial and is never used
  as a completed day.
- License: CC0 1.0. Credit Wikimedia in the footer regardless.

## Pageviews: per-article history

```
GET https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Albert_Einstein/daily/20240101/20240115
```

- `agent` is `user` (excludes spiders and automated agents), `access` is `all-access`.
- A five-year range in one request works (checked 2021-11-26 to 2026-11-25, 279 KB).
- Timestamps are `YYYYMMDD00`; there is one item per day, no zero-view filler rows.
- Missing days are absent, not zero. The pipeline records gaps and never imputes.
- Response:

```json
{"items":[{"project":"en.wikipedia","article":"Albert_Einstein","granularity":"daily",
  "timestamp":"2024010100","access":"all-access","agent":"user","views":26079}]}
```

- Titles with spaces or non-ASCII characters must be percent-encoded in the path.

## Most-edited pages per day

```
GET https://wikimedia.org/api/rest_v1/metrics/edited-pages/top-by-edits/en.wikipedia/all-editor-types/content/2024/01/15
```

- Daily granularity exists and works back to at least 2015-08-01, so the edit-surge signal
  is kept.
- The response is the top 100 content pages only; it is not a per-article edit count.
- There is no daily per-page edit endpoint. The per-page route
  `/metrics/edits/per-page/...` returns 404, and the documented per-page edit metrics are
  monthly only. Edit surge can therefore mean membership and rank in the daily top 100,
  nothing finer.
- Response:

```json
{"items":[{"project":"en.wikipedia","editor-type":"all-editor-types","page-type":"content",
  "granularity":"daily","results":[{"timestamp":"2024-01-15T00:00:00.000Z",
  "top":[{"page_title":"2023–24_NFL_playoffs","edits":167,"rank":1}]}]}]}
```

- Monthly form uses `all-days` as the day segment. Not needed by the daily pipeline.
- License: CC0 1.0.

## Article summaries

```
GET https://en.wikipedia.org/api/rest_v1/page/summary/Albert_Einstein
```

- Returns `type`, `title`, `displaytitle` (HTML), `pageid`, `wikibase_item`, `titles`,
  `description`, `extract` (plain text), `extract_html`, `content_urls`, and optional
  `thumbnail` or `originalimage`.
- `displaytitle` and `extract_html` contain HTML and are never rendered. Only `title`,
  `description`, `extract`, and `content_urls.desktop.page` are used.
- A missing page returns HTTP 404 with `{"status":404,"type":"Internal error"}`, which does
  not follow the usual problem JSON shape. The client must treat it by status code.
- Text is CC BY-SA. The site attributes it and links to the source article.

## Access rules

- Wikimedia requires a descriptive User-Agent with contact information. Requests without
  one can be blocked without notice.
- The Analytics API documents a 25 req/s limit; the pageviews API documents a higher one.
  The client stays sequential with a 0.5 s default delay, well below both.
- Raw responses are cached by request key; completed past days are immutable.

## Hosting constraints

- Cloudflare Pages Free allows 20,000 files per site (100,000 on paid plans) and 25 MiB per
  file. Five years of day files plus search shards leaves room for roughly 16,000 article
  files. The export phase must cap or pool article files to stay under the limit; this is
  an open design decision for Phase 7.
- `_headers` supports up to 100 rules and 2,000 characters per header.
- Direct upload uses `wrangler pages deploy <dist> --project-name <name>`; a project
  created with Direct Upload cannot switch to Git integration later.

## Licensing and attribution

- Pageview and edit analytics: CC0 1.0, no attribution required, credited anyway.
- Wikipedia article text: CC BY-SA. Attribute with a link to the source article.
- Wikipedia logos, marks, and article images are never used.
