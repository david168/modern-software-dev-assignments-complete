# BUILD_LOG — undirected decisions

Every decision below was a judgment call *not* pinned down by the prompt. One
bullet per decision. This is the diff between the spec and what shipped.

## Data source / API reality

- **ApeWisdom has no sentiment field.** The prompt's `get_sentiment` shape
  assumes ApeWisdom returns a sentiment value to "normalize to [-1, +1]." It
  does not. The live free API (`/api/v1.0/filter/all-stocks`) returns only
  `rank, ticker, name, mentions, upvotes, rank_24h_ago, mentions_24h_ago` —
  confirmed against both the live endpoint and their API docs page. So there
  was no scale to normalize; I had to *derive* sentiment.
- **Sentiment proxy = `tanh((upvotes/mentions − 6.0) / 6.0)`.** Chosen because
  upvotes-per-mention is the only positivity-ish signal available. Baseline 6.0
  and scale 6.0 were picked from observed live ratios (~3.5 for SPY up to ~11.6
  for SPCE), so the baseline maps to ~0 and high-engagement names approach +1.
  Documented openly as a proxy, not true sentiment, in README Limitations.
- **No ticker-specific ApeWisdom endpoint.** Their docs only document
  `/filter/{filter}`; there is no per-ticker lookup. So `get_sentiment` scans
  the all-stocks list for the symbol. The "ticker-specific endpoint if it
  exists" branch in the prompt resolved to "doesn't exist."
- **`as_of` for sentiment is the fetch time (UTC ISO-8601).** ApeWisdom returns
  no timestamp in the payload, so I stamp the moment of the request rather than
  inventing a data freshness claim.

## Library versions (pinned in pyproject.toml)

- `mcp[cli]>=1.2` (as directed), `yfinance>=0.2.40`, `httpx>=0.27`. Resolved
  lockfile installed `yfinance==1.4.1`, `httpx==0.28.x`, `mcp 1.x`.
- `requires-python = ">=3.10"` to match the README prerequisite.
- `[tool.uv] package = false` so `uv run stock_momentum.py` runs the script
  directly without building/installing the project as a package.

## File layout

- `week3/server/` holds `stock_momentum.py` + `pyproject.toml` (a self-contained
  uv project), separate from the repo-root poetry project, so `uv sync` here
  doesn't touch the rest of the course repo.
- Added a `[project.scripts] stock-momentum` entry point as a convenience; the
  graded run command remains `uv run stock_momentum.py`.

## yfinance specifics

- **`history(period="1y", auto_adjust=False)`.** Passed `auto_adjust=False`
  explicitly so "price" is the raw close (matching what users see quoted) rather
  than a dividend/split-adjusted series, and to silence yfinance's default-change
  warning.
- **SMA NaN handling.** Instead of letting early rows be NaN, `_sma` returns
  `None` when there are fewer closes than the window. So a stock with <200
  trading days reports `sma_200: null` rather than a misleading partial average.
- **`previous_close` = second-to-last close** from the same history series, not a
  separate field, to keep one source of truth for `change_pct`.
- **Rounding to 4 decimals** on all computed floats for readable output.
- yfinance logs its own `ERROR` line to stderr for unknown tickers (404). That's
  harmless (stderr, not stdout) and the tool still catches the empty history and
  returns a clean `error` dict.

## Error-return structure

- Errors are a dict with an `"error"` string plus the echoed `"symbol"`; tools
  never raise (verified against `BOGUSXYZ`, timeouts, and HTTP errors).
- **429 is special-cased** with a distinct rate-limit message before
  `raise_for_status`, separate from generic HTTP errors and timeouts.
- **Untracked symbol is NOT an error** (per spec): returns `mentions_24h: 0`,
  `sentiment_score: null`, and a `note`.
- **`mentions_change_pct` is `null` when the 24h-ago baseline is 0** (avoids a
  divide-by-zero and avoids reporting a fake "+∞%" surge).

## Scoring / interpretation details

- **Price sub-score uses explicit `elif` for the downside** so each of the three
  comparisons contributes exactly one of {+1, 0, −1}; equal values contribute 0.
- **Interpretation strings are generated, not hardcoded:** "Golden stack" only
  when score == 3, "Death stack" only when score == −3, otherwise a phrase built
  from which tests passed / the sentiment & attention words.
- **`composite_score`** is `price_score + crowd_score` for the full path, and
  just `price_score` for the price-only fallback.
- **Divergence text** is populated only for the two divergence verdicts and is
  `null` otherwise.
- For the price-only fallback I still emit a `crowd_momentum` block (score 0 +
  an "unavailable: <reason>" interpretation) so the output shape stays stable
  for clients.

## Logging

- `logging.basicConfig(stream=sys.stderr, level=INFO)` with a named logger; one
  INFO line per tool call summarizing the key result. No `print()` anywhere.

## Verification

- Verified through the actual MCP Inspector **CLI** (`--cli`), not just direct
  imports: `tools/list` shows exactly 3 tools; `tools/call` exercised
  `get_quote`/`get_sentiment`/`get_momentum_signal` for NVDA and the
  not-tracked path for CALM. Output pasted into README "Sample runs".
- Chose `CALM` (Cal-Maine Foods) as the obscure ticker for the initial build: a
  real, liquid stock that yfinance knows — used to exercise the price-only
  fallback with real SMAs rather than erroring on the price side too.

## Post-build revision — ApeWisdom coverage (added after a coverage question)

- **Corrected a wrong assumption: ApeWisdom is NOT limited to the top ~100.**
  The initial build read only `/filter/all-stocks` (page 1 = 100 rows) and
  reported everything past rank 100 as "not tracked." The API actually paginates
  to ~1,000 symbols across ~11 pages. The original README/BUILD_LOG "top ~100"
  wording was therefore inaccurate and has been fixed.
- **`get_sentiment` now paginates `/all-stocks/page/{n}` and stops at the first
  match.** Popular tickers (page 1) still cost one request; deep-list names cost
  a few; a genuinely absent symbol walks all pages (~11 requests). Capped at
  `MAX_PAGES = 15` as a safety net against the page count drifting upward.
- **Added a minimum-mentions guard (`MIN_MENTIONS_TO_SCORE = 5`).** Symbols deep
  in the list can appear with a single mention (e.g. GWRE, CALM each showed 1).
  A `tanh` proxy off one mention is noise, so below the threshold the tool now
  returns the real mention count and rank but `sentiment_score: null` + a `note`,
  which routes the verdict to the price-only fallback. The threshold value (5)
  is a judgment call, not from any spec.
- **Two distinct "no score" notes** now exist: "not found in the list" (truly
  untracked) vs. "too thinly discussed" (found but under the mention threshold).
  Both are non-error returns, consistent with the original spec's intent.
- **Re-verified through the Inspector CLI** after the change: still exactly 3
  tools; NVDA scores normally (1 request), GWRE returns rank 602 / 1 mention via
  the thin-data guard, ZZZZ exercises the full-pagination not-found path. README
  "Sample runs" updated to GWRE (thin) + ZZZZ (absent) accordingly.
- **Known unaddressed (flagged, not fixed):** the price-score `interpretation`
  string for a negative score reads "price below shorter-term averages," which
  is misleading when the −1 comes from SMA *ordering* while price sits above the
  short MAs (exactly GWRE's case). Left as-is per scope; noted here as the next
  code-quality fix.
