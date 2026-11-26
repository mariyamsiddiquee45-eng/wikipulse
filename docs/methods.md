# Methods and limitations

This page describes what the code does. The website reads the same numbers from
`data/export/methods.json`; it does not invent metrics.

## Sources

- English Wikipedia, all-access, top 1000 articles per day. Data starts 2015-07-01.
- Per-article daily views for the user agent only, used for candidate history.
- Daily top-100 edited content pages. Publication lags pageviews by roughly one to two
  months, so edit surge is missing for recent days.
- Article summaries from the Wikipedia REST API, rendered as plain text and attributed
  CC BY-SA 4.0.

Pageview and edit data are CC0. Missing days are recorded and excluded from baselines.

## Filtering and candidates

Main page and non-main namespaces are removed, plus a configurable denylist. Titles that
merely contain a colon are kept. The candidate pool is new entrants to the top 1000 absent
for 28 days, articles whose rank improved by at least 100 places, and articles that spiked
in the previous 14 days. Each day is capped to keep history fetches inside the machine
budget.

## Features

- Robust z-score: median and MAD over the previous 28 days, with a weekday factor derived
  from the same weekday in that window.
- STL residual z-score when at least 365 days of history exist (period 7, robust).
- Same-day-last-year ratio, rise days, time to peak, half-life, peak-to-baseline ratio,
  rank jump, days since the last spike, weekly ratio, minimum-views flag and edit surge.
- Half-life is unknown when a spike is detected on its peak day; no future data is used.
- A zero MAD falls back to unit scale so the score is always finite.
- Scale invariance holds when the baseline has non-zero dispersion; this is tested with
  Hypothesis.

## Detection

Baseline A, the shipped detector, fires when the robust z-score is at least 3 and the day
has at least 1000 views. Baselines for comparison are:

- B: raw rank in the top 1000 (rank at most 100).
- C: the day's views at least twice the previous seven-day median.

Synthetic tests plant spikes of known magnitude over article-days. The gate is event recall
of at least 0.85 in the 5x and 10x bands and a false-positive rate at or below 3 percent.
The two-million article-day performance test is marked `slow` and excluded from the default
run.

## Classifier

Labels are human judgments in `labels/labels.csv`, with classes `event`, `noise` and
`recurring`. The target is 300 labels across the archive. Logistic regression and LightGBM
are trained inside scikit-learn pipelines with class weights and fixed seeds. Evaluation
uses expanding-window time-series splits only, never random splits, and reports per-class
precision, recall and F1, a confusion matrix, calibration, precision at k, a Brier score,
permutation importance and LightGBM gain importance against baselines A to C.

An initial 331-label pilot (282 event, 42 recurring, 7 noise) trained LightGBM with event
F1 0.878, macro F1 0.329 and Brier 0.18. It does not beat baseline A (0.937) and it cannot
recognize noise (F1 0). It is therefore not applied: `WIKIPULSE_APPLY_CLASSIFIER` stays false
until a retrained model beats the rule baseline. More non-event labels and a broader archive
are required.

## Events and spike types

Article title plus summary is embedded with all-MiniLM-L6-v2 on CPU and cached per article.
Each day's spikes are clustered with HDBSCAN on L2-normalized vectors, minimum cluster size
2. Noise points become single-article events. Very small days use a deterministic
cosine-similarity fallback because HDBSCAN is unstable on ties. Event labels come from the
highest-scoring member. Spike types use documented rules:

- Always-on: high baseline and peak ratio below 2.
- Recurring: a spike within the previous 30 days.
- Slow burn: rise time at least 3 days.
- Flash: half-life at most 2 days, otherwise peak ratio at least 2.

## Limitations

- Human labels exist but are imbalanced; the pilot classifier is not good enough to ship.
- Edit surge is unavailable for recent days and only covers the daily top 100 edited pages.
- Events are grouped by title and summary embeddings; there is no link-graph signal yet.
- Single-article events are not independently confirmed as real-world events.
- The local archive is a 28-day window; the pipeline supports the full five-year window.
- Cloudflare Pages Free allows 20,000 files. The export caps article files at 12,000, so an
  article that was capped falls back to its Wikipedia source.
