# Build log — undirected decisions

Every decision below was made by my judgment, NOT dictated by the prompt.

## Dependency versions
- Pinned `mcp[cli]>=1.2` (as directed); `uv sync` resolved it to `mcp==1.27.2`.
- Added `httpx>=0.27` — the prompt named `httpx` but not a version; `>=0.27` is
  a recent stable baseline with the async API used here.
- Set `requires-python = ">=3.10"` to match the prompt's "Python 3.10+"
  requirement, even though the local machine runs 3.14. `uv init` had defaulted
  to `>=3.13`; I lowered it. Also set `server/.python-version` to `3.10`.

## Project layout
- Used `uv init server` then renamed the package to `weather` in
  `pyproject.toml` and used `weather.py` (per prompt) as the entrypoint instead
  of the generated `main.py`, which I deleted.
- Kept a minimal `server/README.md` stub because `pyproject.toml`'s
  `readme` field points at it; the real docs live in `week3/README.md`.

## Server name / metadata
- Named the FastMCP server `"weather"` (matches the official example and the
  Claude Desktop config key).
- `User-Agent` string: `weather-app/1.0 (week3-mcp-study; contact:
  student@example.com)` — NWS requires *a* User-Agent but the contents are my
  choice; used a placeholder contact.

## Error-handling shape
- `make_nws_request` returns `None` on any failure and logs the cause to
  stderr; each tool converts `None` into a distinct, plain-language message.
  Chose return-None-over-raise so a flaky upstream never crashes the server.
- Catch granularity: separate branches for `TimeoutException`,
  `HTTPStatusError`, generic `HTTPError`, and `ValueError` (JSON decode), each
  with a tailored log line.
- HTTP timeout set to **30.0s** (prompt said "handle timeouts" but gave no
  value).
- Added input validation beyond the prompt: `get_alerts` rejects non-2-letter
  codes; `get_forecast` range-checks lat/lon. These short-circuit before any
  network call.

## Output formatting
- `get_forecast` returns the **next 5 periods** (matches the official example's
  slice of `[:5]`).
- Used `\n\n---\n\n` as the separator between multiple alerts / forecast
  periods for readability. Arbitrary choice.
- Alert `instruction` field falls back to "No specific instructions provided"
  when null (NWS often omits it).

## Verification approach
- The prompt said to verify with the MCP Inspector. The Inspector's interactive
  browser UI can't be driven from a headless session, so I used the Inspector's
  **`--cli` mode** (`npx @modelcontextprotocol/inspector --cli ...`) — the same
  official tool, scriptable — to run `tools/list`, `get_alerts state=CA`, and
  `get_forecast` for Sacramento. All three returned real NWS data, pasted into
  the README "Sample runs" section.

## Deviations from the linked docs
- Effectively none in structure — this intentionally mirrors the official
  weather quickstart. Additions on top of it: stderr logging via the `logging`
  module (the doc example is silent), explicit input validation, and broader
  exception branches with logging.
