# Week 3 — Stock Momentum MCP Server

A local **Model Context Protocol** server (STDIO transport) that fuses two
independent signals into a single momentum verdict for a stock:

1. **Price technicals** — current price vs. self-computed SMA-20/50/200 (Yahoo
   Finance via `yfinance`, no API key).
2. **Crowd attention** — Reddit/social mention volume and a derived sentiment
   proxy (ApeWisdom, no auth).

The interesting tool is `get_momentum_signal`, which combines the two and flags
**divergences** — e.g. price rising while the crowd sours. `get_quote` and
`get_sentiment` exist mainly to feed it, but are exposed as standalone tools.

---

## Prerequisites

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** for dependency management
- **Node 18+** (only for the MCP Inspector: `npx @modelcontextprotocol/inspector`)
- Network access (Yahoo Finance + `apewisdom.io`). No API keys are required.

## Setup

```bash
cd week3/server
uv sync          # creates .venv and installs mcp[cli], yfinance, httpx
```

## Run standalone (STDIO)

```bash
cd week3/server
uv run stock_momentum.py
```

The process will sit waiting for JSON-RPC on stdin — that is correct for a
STDIO MCP server. Drive it from an MCP client (below) rather than typing into it.

## Exercise with the MCP Inspector

Interactive UI (opens a browser):

```bash
cd week3/server
npx @modelcontextprotocol/inspector uv run stock_momentum.py
```

Headless CLI (what was used to verify this server):

```bash
cd week3/server
# list tools — should show exactly 3
npx @modelcontextprotocol/inspector --cli uv run stock_momentum.py \
  --method tools/list

# call a tool
npx @modelcontextprotocol/inspector --cli uv run stock_momentum.py \
  --method tools/call --tool-name get_momentum_signal --tool-arg symbol=NVDA
```

## Claude Desktop configuration

Edit `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Use **absolute paths** (Claude Desktop does not inherit your shell):

```json
{
  "mcpServers": {
    "stock-momentum": {
      "command": "/Users/davidlai/.local/bin/uv",
      "args": [
        "--directory",
        "/Users/davidlai/projects/modern-software-dev-assignments/week3/server",
        "run",
        "stock_momentum.py"
      ]
    }
  }
}
```

Find your `uv` path with `which uv`. Restart Claude Desktop, then ask:

> "What's the momentum on NVDA?" · "Show me the quote for AAPL." ·
> "Is the crowd bullish on GME?"

No API key needs to be configured anywhere — both data sources are public.

---

## Tool reference

| Tool | Parameters | What it does | Example prompt |
|------|------------|--------------|----------------|
| `get_quote` | `symbol: str` | Last close, previous close, % change, and **self-computed** SMA-20/50/200 from ~1y of daily history. | "Show me the quote for AAPL" |
| `get_sentiment` | `symbol: str` | ApeWisdom 24h mentions, mention change %, rank, and a `[-1, +1]` sentiment proxy. Paginates ApeWisdom's full ~1,000-symbol list; thinly-discussed or absent symbols return a `note`, not an error. | "Is the crowd talking about GME?" |
| `get_momentum_signal` | `symbol: str` | Calls the two above, scores each `-3..+3`, returns a composite verdict and any divergence. | "What's the momentum on NVDA?" |

All three take a single `symbol` string, are fully type-annotated (the SDK
derives the JSON schema from the annotations), and **never raise** — failures
come back as a dict with an `error` field.

### `get_quote(symbol)` example output

```json
{
  "symbol": "NVDA",
  "price": 224.36,
  "previous_close": 211.14,
  "change_pct": 6.2612,
  "sma_20": 216.7535,
  "sma_50": 200.2648,
  "sma_200": 187.8671,
  "pct_above_sma_200": 19.4248,
  "as_of": "2026-06-01"
}
```

Unknown symbol → `{"error": "no price history found (unknown or delisted symbol?)", "symbol": "BOGUSXYZ"}`.
SMAs are `null` until enough history exists to fill the window (e.g. a stock
with <200 trading days has `sma_200: null`).

### `get_sentiment(symbol)` example output

Tracked symbol:

```json
{
  "symbol": "NVDA",
  "mentions_24h": 329,
  "mentions_change_pct": 422.22,
  "sentiment_score": 0.3476,
  "rank": 4,
  "as_of": "2026-06-01T22:29:14+00:00"
}
```

Tracked but too thinly discussed to score (not an error). ApeWisdom carries the
symbol deep in its list with only a mention or two, so the real count and rank
are returned but `sentiment_score` is `null`:

```json
{
  "symbol": "GWRE",
  "mentions_24h": 1,
  "mentions_change_pct": null,
  "sentiment_score": null,
  "rank": 602,
  "as_of": "2026-06-02T00:16:20+00:00",
  "note": "only 1 mention(s) in the last 24h (rank 602); too thinly discussed for a reliable sentiment score"
}
```

Symbol not in ApeWisdom's list at all (also not an error):

```json
{
  "symbol": "ZZZZ",
  "mentions_24h": 0,
  "mentions_change_pct": null,
  "sentiment_score": null,
  "rank": null,
  "as_of": "2026-06-02T00:15:32+00:00",
  "note": "symbol not found in ApeWisdom's tracked list (the ~1,000 most-discussed stocks); no crowd data available"
}
```

### `get_momentum_signal(symbol)` example output

```json
{
  "symbol": "NVDA",
  "verdict": "CONFIRMED_BULLISH",
  "composite_score": 5,
  "crowd_data_available": true,
  "price_momentum": {
    "score": 3,
    "interpretation": "Golden stack: price > SMA20 > SMA50 > SMA200",
    "price": 224.36,
    "sma_20": 216.7535,
    "sma_50": 200.2648,
    "sma_200": 187.8671,
    "pct_above_sma_200": 19.4248
  },
  "crowd_momentum": {
    "score": 2,
    "interpretation": "Positive sentiment with growing attention",
    "sentiment_score": 0.3476,
    "mentions_24h": 329,
    "mentions_change_pct": 422.22
  },
  "divergence": null,
  "caveat": "24h sentiment snapshot. Not investment advice."
}
```

---

## Methodology

The verdict is built from two independent sub-scores, each clamped to `-3..+3`.

### Price sub-score (moving-average stack)

```
score = 0
if price > sma_20:   score += 1     # short-term uptrend
if sma_20 > sma_50:  score += 1     # medium-term uptrend
if sma_50 > sma_200: score += 1     # long-term uptrend
# mirrored for the downside (price < sma_20, etc.) → score -= 1 each
```

`+3` is a "**golden stack**" (`price > SMA20 > SMA50 > SMA200`), the classic
bullish alignment; `-3` is the inverse "**death stack**." The `interpretation`
string is generated from the actual comparisons, so "Golden stack" only appears
when all three tests pass.

### Crowd sub-score

```
score = 0
if sentiment_score >  0.2: score += 1
if sentiment_score >  0.5: score += 1
if sentiment_score < -0.2: score -= 1
if sentiment_score < -0.5: score -= 1
if mentions_change_pct >  50: score += 1     # attention surging
if mentions_change_pct < -50: score -= 1     # attention fading
score = max(-3, min(3, score))
```

**Sentiment proxy.** ApeWisdom's *free* API does **not** expose a sentiment
score (only `mentions` and `upvotes`). We therefore derive one from the
**upvotes-per-mention ratio**, squashed onto `[-1, +1]` with `tanh`:

```
sentiment_score = tanh((upvotes / mentions − 6.0) / 6.0)
```

A ratio near the empirical baseline (~6) maps to ~0; heavily up-voted tickers
(ratio ~12) approach +1; low-engagement tickers can read mildly negative. This
is an **engagement-positivity proxy, not true NLP sentiment** — see Limitations.

**Coverage & a minimum-mentions guard.** ApeWisdom serves its tracked stocks
~100 per page across ~11 pages (~1,000 symbols total). `get_sentiment` walks the
pages and stops at the first match, so popular tickers cost a single request and
deep-list names cost a few. Because a symbol can appear with just one or two
mentions — far too little for the proxy to mean anything — any symbol below
`MIN_MENTIONS_TO_SCORE` (5) returns its real mention count and rank but
`sentiment_score: null` with a `note`, rather than a confident-looking score
derived from a single Reddit post. Those symbols therefore route to the
price-only fallback below.

### Verdict

| Condition | Verdict |
|-----------|---------|
| `price ≥ 2` and `crowd ≥ 2` | `CONFIRMED_BULLISH` |
| `price ≤ -2` and `crowd ≤ -2` | `CONFIRMED_BEARISH` |
| `price ≥ 2` and `crowd ≤ -1` | `BEARISH_DIVERGENCE` (price up, crowd souring) |
| `price ≤ -2` and `crowd ≥ 1` | `BULLISH_DIVERGENCE` (price down, crowd accumulating) |
| otherwise | `MIXED` |

**Divergences are the point.** Agreement between price and crowd is easy to
read off a chart; the value here is surfacing when the two disagree — a price
breakout the crowd isn't buying, or a sell-off the crowd is leaning into.

**Price-only fallback.** When ApeWisdom returns no sentiment for the symbol
(`sentiment_score: null`), there is no crowd sub-score, so the verdict collapses
to `PRICE_BULLISH` / `PRICE_BEARISH` / `PRICE_MIXED` and the output carries
`"crowd_data_available": false`.

---

## Sample runs

Captured live through the MCP Inspector CLI on 2026-06-01
(`npx @modelcontextprotocol/inspector --cli uv run stock_momentum.py ...`).

**`tools/list`** → exactly 3 tools registered: `get_quote`, `get_sentiment`,
`get_momentum_signal`.

**`get_quote NVDA`**

```json
{
  "symbol": "NVDA", "price": 224.36, "previous_close": 211.14,
  "change_pct": 6.2612, "sma_20": 216.7535, "sma_50": 200.2648,
  "sma_200": 187.8671, "pct_above_sma_200": 19.4248, "as_of": "2026-06-01"
}
```

**`get_sentiment NVDA`** (tracked)

```json
{
  "symbol": "NVDA", "mentions_24h": 329, "mentions_change_pct": 422.22,
  "sentiment_score": 0.3476, "rank": 4, "as_of": "2026-06-01T22:29:14+00:00"
}
```

**`get_sentiment GWRE`** (found deep in the list, but too thin to score)

```json
{
  "symbol": "GWRE", "mentions_24h": 1, "mentions_change_pct": null,
  "sentiment_score": null, "rank": 602, "as_of": "2026-06-02T00:16:20+00:00",
  "note": "only 1 mention(s) in the last 24h (rank 602); too thinly discussed for a reliable sentiment score"
}
```

**`get_sentiment ZZZZ`** (not in ApeWisdom's list at all)

```json
{
  "symbol": "ZZZZ", "mentions_24h": 0, "mentions_change_pct": null,
  "sentiment_score": null, "rank": null, "as_of": "2026-06-02T00:15:32+00:00",
  "note": "symbol not found in ApeWisdom's tracked list (the ~1,000 most-discussed stocks); no crowd data available"
}
```

**`get_momentum_signal NVDA`**

```json
{
  "symbol": "NVDA", "verdict": "CONFIRMED_BULLISH", "composite_score": 5,
  "crowd_data_available": true,
  "price_momentum": { "score": 3, "interpretation": "Golden stack: price > SMA20 > SMA50 > SMA200",
    "price": 224.36, "sma_20": 216.7535, "sma_50": 200.2648, "sma_200": 187.8671, "pct_above_sma_200": 19.4248 },
  "crowd_momentum": { "score": 2, "interpretation": "Positive sentiment with growing attention",
    "sentiment_score": 0.3476, "mentions_24h": 329, "mentions_change_pct": 422.22 },
  "divergence": null, "caveat": "24h sentiment snapshot. Not investment advice."
}
```

Manual sanity check: `224.36 > 216.75 > 200.26 > 187.87` → all three stack
tests pass → price score `3` (golden stack). Sentiment `0.35 > 0.2` (+1) and
mentions `+422% > 50` (+1) → crowd score `2`. Both `≥ 2` → `CONFIRMED_BULLISH`,
composite `5`. ✓

**`get_momentum_signal GWRE`** (thinly tracked → price-only fallback)

```json
{
  "symbol": "GWRE", "verdict": "PRICE_MIXED", "composite_score": -1,
  "crowd_data_available": false,
  "price_momentum": { "score": -1, "interpretation": "Downtrend leaning (price below shorter-term averages)",
    "price": 171.42, "sma_20": 138.376, "sma_50": 140.0062, "sma_200": 184.4042, "pct_above_sma_200": -7.0412 },
  "crowd_momentum": { "score": 0, "interpretation": "unavailable: only 1 mention(s) in the last 24h (rank 602); too thinly discussed ..." },
  "divergence": null, "caveat": "Price-only verdict; no crowd data. Not investment advice."
}
```

---

## STDIO logging rule (why `print()` breaks the server)

Under STDIO transport the client and server speak JSON-RPC over the process's
**stdout/stdin**. Any stray bytes on stdout — a `print()`, a debug banner, a
library that logs to stdout — land in the middle of a JSON-RPC frame and
corrupt the stream, and the client disconnects with a parse error.

This server therefore:

- **never calls `print()`**;
- configures the `logging` module to write to **stderr only**
  (`logging.basicConfig(stream=sys.stderr, ...)`), which the MCP client ignores;
- logs each tool call's key result to stderr for debugging.

When developing, watch stderr (the Inspector shows it in a side panel) for the
`INFO` lines; stdout stays clean for the protocol.

---

## Limitations

- **ApeWisdom coverage is finite and long-tailed.** It tracks ~1,000 of the
  most-discussed stocks (paginated). Names beyond that return the "not found"
  fallback; names deep in the list often have only one or two mentions, which
  the minimum-mentions guard treats as unscoreable. Either way the verdict drops
  to price-only. Walking to the deepest pages also costs up to ~11 HTTP requests
  for a symbol that turns out to be absent.
- **No true sentiment.** The free ApeWisdom API exposes only mention counts and
  upvotes, so `sentiment_score` is an *upvotes-per-mention proxy*, not NLP
  sentiment. It captures crowd enthusiasm/engagement, not polarity of opinion.
- **`yfinance` is an unofficial Yahoo scraper.** It has no SLA and can break
  without notice when Yahoo changes its endpoints; treat outages as expected.
- **24h window is short.** Both the mention-change signal and the sentiment
  snapshot are single-day; a trustworthy signal would need a multi-day trend.
- **Not investment advice.** This is a study artifact.

## Future work

- **Volume confirmation** — weight the price score by whether moves come on
  above-average volume.
- **RSI / momentum oscillators** — add an overbought/oversold dimension
  alongside the moving-average stack.
- **Multi-day sentiment trend** — persist daily ApeWisdom snapshots and score
  the *trajectory* of mentions and sentiment instead of a single 24h reading.
