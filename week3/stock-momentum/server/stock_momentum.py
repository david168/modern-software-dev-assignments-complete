"""Stock Momentum MCP server.

Combines price-based technical signals (from yfinance) with social-media crowd
attention (from ApeWisdom) to produce a composite momentum verdict for a stock.

Transport: STDIO. Per the MCP STDIO contract, stdout is reserved for protocol
framing, so all logging goes to stderr and the code never calls print().
"""

from __future__ import annotations

import logging
import math
import sys
from datetime import datetime, timezone
from typing import Any

import httpx
import yfinance as yf
from mcp.server.fastmcp import FastMCP

# --- Logging -----------------------------------------------------------------
# STDIO transport uses stdout for JSON-RPC framing. Writing anything else there
# corrupts the stream, so we attach our handler to stderr explicitly.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("stock_momentum")

mcp = FastMCP("stock-momentum")

APEWISDOM_BASE = "https://apewisdom.io/api/v1.0/filter/all-stocks"
HTTP_TIMEOUT = 15.0

# ApeWisdom paginates its tracked stocks (~100 per page, ~1,000 total). We walk
# pages until the symbol is found, capping requests as a safety net.
MAX_PAGES = 15

# A symbol can technically appear with only a mention or two (deep in the long
# tail). A sentiment proxy off so little data is noise, so below this threshold
# we report the mention count but return sentiment_score=None with a note.
MIN_MENTIONS_TO_SCORE = 5

# Baseline / scale for mapping ApeWisdom's upvotes-per-mention ratio onto a
# [-1, +1] sentiment proxy. See README "Methodology" and BUILD_LOG.
SENTIMENT_RATIO_BASELINE = 6.0
SENTIMENT_RATIO_SCALE = 6.0


class _RateLimited(Exception):
    """Raised internally when ApeWisdom returns HTTP 429."""


# --- Helpers -----------------------------------------------------------------
def _sma(closes: list[float], window: int) -> float | None:
    """Simple moving average of the last `window` closes.

    Returns None when there is not enough history to fill the window, which
    keeps the first NaN-equivalent rows out of the output instead of emitting
    a misleading partial average.
    """
    if len(closes) < window:
        return None
    return round(sum(closes[-window:]) / window, 4)


def _proxy_sentiment(mentions: int, upvotes: int) -> float | None:
    """Derive a [-1, +1] sentiment proxy from upvotes-per-mention.

    ApeWisdom's free API does not expose a true sentiment score (only mentions
    and upvotes). We use the upvotes/mention ratio as an engagement-positivity
    proxy and squash it with tanh around an empirically chosen baseline so that
    low-engagement tickers can read mildly negative and high-engagement ones
    read strongly positive.
    """
    if mentions <= 0:
        return None
    ratio = upvotes / mentions
    score = math.tanh((ratio - SENTIMENT_RATIO_BASELINE) / SENTIMENT_RATIO_SCALE)
    return round(score, 4)


def _get_apewisdom_page(client: httpx.Client, page: int) -> dict[str, Any]:
    """Fetch one ApeWisdom page; raise on rate limit / HTTP error."""
    resp = client.get(f"{APEWISDOM_BASE}/page/{page}")
    if resp.status_code == 429:
        raise _RateLimited()
    resp.raise_for_status()
    return resp.json()


def _find_ticker(payload: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    """Return the result row matching `symbol`, or None."""
    for row in payload.get("results", []):
        if str(row.get("ticker", "")).upper() == symbol:
            return row
    return None


def _lookup_apewisdom(symbol: str) -> dict[str, Any] | None:
    """Walk ApeWisdom pages until `symbol` is found or pages are exhausted.

    Stops at the first match so popular tickers (page 1) cost a single request.
    Raises httpx / _RateLimited errors for the caller to translate.
    """
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        first = _get_apewisdom_page(client, 1)
        match = _find_ticker(first, symbol)
        if match is not None:
            return match
        total_pages = min(int(first.get("pages", 1) or 1), MAX_PAGES)
        for page in range(2, total_pages + 1):
            match = _find_ticker(_get_apewisdom_page(client, page), symbol)
            if match is not None:
                return match
    return None


# --- Tool 1: price quote -----------------------------------------------------
@mcp.tool()
def get_quote(symbol: str) -> dict[str, Any]:
    """Fetch a daily price quote with self-computed SMA-20/50/200 for a symbol.

    Pulls ~1y of daily history from Yahoo Finance and computes the moving
    averages directly from the close series. Never raises: any failure
    (unknown symbol, empty history, network error) returns a dict with an
    `error` field.
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {"error": "empty symbol", "symbol": symbol}

    try:
        hist = yf.Ticker(symbol).history(period="1y", auto_adjust=False)
    except Exception as exc:  # network / yfinance scrape failure
        logger.warning("get_quote(%s) history fetch failed: %s", symbol, exc)
        return {"error": f"failed to fetch history: {exc}", "symbol": symbol}

    if hist is None or hist.empty:
        logger.info("get_quote(%s): no history (likely unknown symbol)", symbol)
        return {"error": "no price history found (unknown or delisted symbol?)",
                "symbol": symbol}

    closes = [float(c) for c in hist["Close"].dropna().tolist()]
    if len(closes) < 2:
        return {"error": "insufficient price history", "symbol": symbol}

    price = round(closes[-1], 4)
    previous_close = round(closes[-2], 4)
    change_pct = round((price - previous_close) / previous_close * 100, 4)

    sma_20 = _sma(closes, 20)
    sma_50 = _sma(closes, 50)
    sma_200 = _sma(closes, 200)
    pct_above_sma_200 = (
        round((price - sma_200) / sma_200 * 100, 4) if sma_200 else None
    )

    as_of = hist.index[-1].strftime("%Y-%m-%d")
    logger.info("get_quote(%s): price=%s sma200=%s", symbol, price, sma_200)
    return {
        "symbol": symbol,
        "price": price,
        "previous_close": previous_close,
        "change_pct": change_pct,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "pct_above_sma_200": pct_above_sma_200,
        "as_of": as_of,
    }


# --- Tool 2: crowd sentiment -------------------------------------------------
@mcp.tool()
def get_sentiment(symbol: str) -> dict[str, Any]:
    """Fetch ApeWisdom social-mention stats and a derived sentiment proxy.

    Paginates ApeWisdom's tracked stock list (~1,000 most-discussed symbols)
    until the symbol is found. Behavior:
      * Not in the list  -> mentions_24h=0 / sentiment_score=null + `note`.
      * Found but barely discussed (< MIN_MENTIONS_TO_SCORE mentions) ->
        real mention count / rank but sentiment_score=null + `note`, since a
        proxy off one or two mentions is noise.
      * Found with enough mentions -> full payload with a sentiment score.
    Network/HTTP/timeout/rate-limit failures return an `error` field; never
    raises.
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {"error": "empty symbol", "symbol": symbol}

    try:
        match = _lookup_apewisdom(symbol)
    except _RateLimited:
        logger.warning("get_sentiment(%s): ApeWisdom rate limited (429)", symbol)
        return {"error": "ApeWisdom rate limit hit (429); retry later",
                "symbol": symbol}
    except httpx.TimeoutException:
        logger.warning("get_sentiment(%s): ApeWisdom request timed out", symbol)
        return {"error": "ApeWisdom request timed out", "symbol": symbol}
    except httpx.HTTPError as exc:
        logger.warning("get_sentiment(%s): HTTP error: %s", symbol, exc)
        return {"error": f"ApeWisdom HTTP error: {exc}", "symbol": symbol}
    except Exception as exc:
        logger.warning("get_sentiment(%s): unexpected error: %s", symbol, exc)
        return {"error": f"unexpected error: {exc}", "symbol": symbol}

    as_of = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if match is None:
        logger.info("get_sentiment(%s): not in ApeWisdom tracked list", symbol)
        return {
            "symbol": symbol,
            "mentions_24h": 0,
            "mentions_change_pct": None,
            "sentiment_score": None,
            "rank": None,
            "as_of": as_of,
            "note": ("symbol not found in ApeWisdom's tracked list (the ~1,000 "
                     "most-discussed stocks); no crowd data available"),
        }

    mentions = int(match.get("mentions", 0))
    upvotes = int(match.get("upvotes", 0))
    rank = match.get("rank")
    prev = match.get("mentions_24h_ago")
    if isinstance(prev, (int, float)) and prev > 0:
        mentions_change_pct = round((mentions - prev) / prev * 100, 2)
    else:
        mentions_change_pct = None  # cannot compute without a positive baseline

    # Too few mentions for the proxy to mean anything.
    if mentions < MIN_MENTIONS_TO_SCORE:
        logger.info("get_sentiment(%s): only %d mention(s); too thin to score",
                    symbol, mentions)
        return {
            "symbol": symbol,
            "mentions_24h": mentions,
            "mentions_change_pct": mentions_change_pct,
            "sentiment_score": None,
            "rank": rank,
            "as_of": as_of,
            "note": (f"only {mentions} mention(s) in the last 24h (rank {rank}); "
                     "too thinly discussed for a reliable sentiment score"),
        }

    logger.info("get_sentiment(%s): mentions=%d rank=%s", symbol, mentions, rank)
    return {
        "symbol": symbol,
        "mentions_24h": mentions,
        "mentions_change_pct": mentions_change_pct,
        "sentiment_score": _proxy_sentiment(mentions, upvotes),
        "rank": rank,
        "as_of": as_of,
    }


# --- Scoring helpers ---------------------------------------------------------
def _price_subscore(q: dict[str, Any]) -> tuple[int, str]:
    """Return (-3..+3 price score, interpretation) from a get_quote result."""
    price, s20, s50, s200 = q.get("price"), q.get("sma_20"), q.get("sma_50"), q.get("sma_200")
    score = 0
    up_stack = []
    if price is not None and s20 is not None:
        if price > s20:
            score += 1
            up_stack.append("price>SMA20")
        elif price < s20:
            score -= 1
    if s20 is not None and s50 is not None:
        if s20 > s50:
            score += 1
            up_stack.append("SMA20>SMA50")
        elif s20 < s50:
            score -= 1
    if s50 is not None and s200 is not None:
        if s50 > s200:
            score += 1
            up_stack.append("SMA50>SMA200")
        elif s50 < s200:
            score -= 1

    if score == 3:
        interp = "Golden stack: price > SMA20 > SMA50 > SMA200"
    elif score == -3:
        interp = "Death stack: price < SMA20 < SMA50 < SMA200"
    elif score > 0:
        interp = f"Uptrend leaning ({', '.join(up_stack)})"
    elif score < 0:
        interp = "Downtrend leaning (price below shorter-term averages)"
    else:
        interp = "Flat / no clear moving-average alignment"
    return score, interp


def _crowd_subscore(s: dict[str, Any]) -> tuple[int, str]:
    """Return (-3..+3 crowd score, interpretation) from a get_sentiment result."""
    sentiment = s.get("sentiment_score")
    change = s.get("mentions_change_pct")
    score = 0
    if sentiment is not None:
        if sentiment > 0.2:
            score += 1
        if sentiment > 0.5:
            score += 1
        if sentiment < -0.2:
            score -= 1
        if sentiment < -0.5:
            score -= 1
    if change is not None:
        if change > 50:
            score += 1
        if change < -50:
            score -= 1
    score = max(-3, min(3, score))

    sent_word = "neutral"
    if sentiment is not None:
        sent_word = "positive" if sentiment > 0.2 else "negative" if sentiment < -0.2 else "neutral"
    attn_word = "steady attention"
    if change is not None:
        attn_word = "growing attention" if change > 50 else "fading attention" if change < -50 else "steady attention"
    interp = f"{sent_word.capitalize()} sentiment with {attn_word}"
    return score, interp


# --- Tool 3: composite momentum signal --------------------------------------
@mcp.tool()
def get_momentum_signal(symbol: str) -> dict[str, Any]:
    """Combine price technicals and crowd attention into a momentum verdict.

    Internally calls get_quote and get_sentiment, derives a price sub-score and
    a crowd sub-score (each -3..+3), then classifies the result. When the
    symbol is not tracked by ApeWisdom, falls back to a price-only verdict and
    sets crowd_data_available=false. Never raises.
    """
    symbol = (symbol or "").strip().upper()
    quote = get_quote(symbol)
    if "error" in quote:
        return {"symbol": symbol, "error": f"quote unavailable: {quote['error']}"}

    sentiment = get_sentiment(symbol)

    price_score, price_interp = _price_subscore(quote)
    price_block = {
        "score": price_score,
        "interpretation": price_interp,
        "price": quote.get("price"),
        "sma_20": quote.get("sma_20"),
        "sma_50": quote.get("sma_50"),
        "sma_200": quote.get("sma_200"),
        "pct_above_sma_200": quote.get("pct_above_sma_200"),
    }

    crowd_available = (
        "error" not in sentiment and sentiment.get("sentiment_score") is not None
    )

    # Price-only fallback when ApeWisdom has no data for the symbol.
    if not crowd_available:
        if price_score >= 2:
            verdict = "PRICE_BULLISH"
        elif price_score <= -2:
            verdict = "PRICE_BEARISH"
        else:
            verdict = "PRICE_MIXED"
        reason = sentiment.get("note") or sentiment.get("error") or "no sentiment score"
        logger.info("get_momentum_signal(%s): price-only verdict=%s", symbol, verdict)
        return {
            "symbol": symbol,
            "verdict": verdict,
            "composite_score": price_score,
            "crowd_data_available": False,
            "price_momentum": price_block,
            "crowd_momentum": {"score": 0, "interpretation": f"unavailable: {reason}"},
            "divergence": None,
            "caveat": "Price-only verdict; no crowd data. Not investment advice.",
        }

    crowd_score, crowd_interp = _crowd_subscore(sentiment)
    crowd_block = {
        "score": crowd_score,
        "interpretation": crowd_interp,
        "sentiment_score": sentiment.get("sentiment_score"),
        "mentions_24h": sentiment.get("mentions_24h"),
        "mentions_change_pct": sentiment.get("mentions_change_pct"),
    }

    divergence = None
    if price_score >= 2 and crowd_score >= 2:
        verdict = "CONFIRMED_BULLISH"
    elif price_score <= -2 and crowd_score <= -2:
        verdict = "CONFIRMED_BEARISH"
    elif price_score >= 2 and crowd_score <= -1:
        verdict = "BEARISH_DIVERGENCE"
        divergence = "Price trending up but crowd attention/sentiment souring."
    elif price_score <= -2 and crowd_score >= 1:
        verdict = "BULLISH_DIVERGENCE"
        divergence = "Price trending down but crowd appears to be accumulating."
    else:
        verdict = "MIXED"

    logger.info("get_momentum_signal(%s): verdict=%s (p=%d c=%d)",
                symbol, verdict, price_score, crowd_score)
    return {
        "symbol": symbol,
        "verdict": verdict,
        "composite_score": price_score + crowd_score,
        "crowd_data_available": True,
        "price_momentum": price_block,
        "crowd_momentum": crowd_block,
        "divergence": divergence,
        "caveat": "24h sentiment snapshot. Not investment advice.",
    }


def main() -> None:
    """Console-script / module entrypoint: run the server over STDIO."""
    logger.info("starting stock-momentum MCP server (STDIO)")
    mcp.run()


if __name__ == "__main__":
    main()
