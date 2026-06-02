# Week 3 — Weather MCP Server

A local [Model Context Protocol](https://modelcontextprotocol.io) server
(STDIO transport) that wraps the **US National Weather Service (NWS) API**
(<https://api.weather.gov>) and exposes two tools:

| Tool | Purpose |
| --- | --- |
| `get_alerts` | Active weather alerts for a US state |
| `get_forecast` | Forecast for a latitude/longitude |

The NWS API requires **no authentication** — only a `User-Agent` header — so
this server runs without any API key. It mirrors the official MCP weather
quickstart (<https://modelcontextprotocol.io/docs/develop/build-server>) so it
can be studied side-by-side with the docs.

## Prerequisites

- **Python 3.10+**
- **[`uv`](https://docs.astral.sh/uv/)** for dependency and environment management
- **Node.js ≥ 18** (only for the MCP Inspector verification step; `npx` ships with Node)

## Setup

```bash
cd week3/server
uv sync          # creates .venv and installs mcp[cli] + httpx from pyproject.toml
```

That's all — there are no environment variables to set and no API key to
obtain.

## Running the server

### Standalone (STDIO)

```bash
cd week3/server
uv run weather.py
```

The process speaks JSON-RPC over stdin/stdout and waits for an MCP client. It
prints nothing to stdout (see [STDIO logging rule](#stdio-logging-rule)); a
startup line is logged to **stderr**. On its own this is not interactive —
drive it with the Inspector or Claude Desktop below.

### Exercise it with the MCP Inspector

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is the
official, no-API-key debugging tool. Launch the browser UI:

```bash
cd week3/server
npx @modelcontextprotocol/inspector uv run weather.py
```

Then open the printed URL, click **Connect**, open the **Tools** tab, and call
`get_alerts` / `get_forecast`.

The Inspector also has a non-interactive **CLI mode**, which is what was used to
produce the [Sample runs](#sample-runs) below:

```bash
# List registered tools
npx @modelcontextprotocol/inspector --cli uv run weather.py --method tools/list

# Call a tool
npx @modelcontextprotocol/inspector --cli uv run weather.py \
  --method tools/call --tool-name get_alerts --tool-arg state=CA
```

> No Node? The `mcp[cli]` package ships an equivalent dev runner that also works
> without an API key: `uv run mcp dev weather.py`.

### Use it from Claude Desktop

Claude Desktop drives the server with your Claude.ai subscription, so this is a
no-API-key way to use the tools with an actual LLM. Edit
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) and add:

```json
{
  "mcpServers": {
    "weather": {
      "command": "/Users/davidlai/.local/bin/uv",
      "args": [
        "--directory",
        "/Users/davidlai/projects/modern-software-dev-assignments-master/week3/server",
        "run",
        "weather.py"
      ]
    }
  }
}
```

Use **absolute paths** — Claude Desktop does not inherit your shell `PATH`, so
both the `uv` binary and the `--directory` must be fully qualified. (Find your
`uv` path with `which uv`.) Restart Claude Desktop, then ask: *"What's the
weather in Sacramento?"* or *"Active alerts in CA?"* — it will call these tools.

## Tool reference

| Tool | Parameters | Example invocation | Returns |
| --- | --- | --- | --- |
| `get_alerts` | `state: str` — two-letter US state/territory code (e.g. `CA`) | "Active alerts in CA?" | Newline-separated active alerts (event, area, severity, description, instructions), or a "no active alerts" message |
| `get_forecast` | `latitude: float`, `longitude: float` | "What's the weather in Sacramento?" (38.5816, -121.4944) | The next five forecast periods (name, temperature, wind, detailed forecast) |

**Expected behavior & error handling**

- `get_alerts` validates that `state` is a two-letter alphabetic code before
  calling the API; otherwise it returns a guidance message.
- `get_forecast` validates the coordinate ranges (lat -90..90, lon -180..180).
  NWS only covers the US and its territories; out-of-coverage coordinates yield
  a friendly explanation rather than an error.
- All upstream calls have a 30s timeout. HTTP errors, timeouts, malformed JSON,
  and empty result sets are caught and turned into plain-language messages — the
  server never crashes on a flaky upstream, and the cause is logged to stderr.

## Sample runs

Captured from a live MCP Inspector CLI session (real NWS data). Values change
over time since the upstream data is live.

**`tools/list`** — exactly two tools register:

```json
{
  "tools": [
    { "name": "get_alerts",   "inputSchema": { "type": "object", "properties": { "state": { "type": "string" } }, "required": ["state"] } },
    { "name": "get_forecast", "inputSchema": { "type": "object", "properties": { "latitude": { "type": "number" }, "longitude": { "type": "number" } }, "required": ["latitude", "longitude"] } }
  ]
}
```

**`get_alerts` with `state=CA`:**

```
Event: Beach Hazards Statement
Area: San Francisco; Coastal North Bay Including Point Reyes National Seashore; San Francisco Peninsula Coast; Northern Monterey Bay; Southern Monterey Bay and Big Sur Coast
Severity: Moderate
Description: * WHAT...Increased risk of sneaker waves and strong rip currents
due to long period SW swell.

* WHERE...Beaches along the Pacific Coast.

* WHEN...Now through 5 AM Tuesday.

* IMPACTS...Dangerous swimming and surfing conditions and
localized beach erosion can be expected. Sneaker waves can
sweep across the shoreline without warning, pulling people
into the sea from rocks, jetties and beaches.
Instructions: Stay off of jetties, piers, rocks, and other waterside
infrastructure. Remain out of the water to avoid hazardous surf
and NEVER turn your back on the ocean. Monitor local weather,
surf and tide forecasts at www.weather.gov/mtr.
```

**`get_forecast` with `latitude=38.5816, longitude=-121.4944` (Sacramento):**

```
This Afternoon:
Temperature: 93°F
Wind: 3 mph W
Forecast: Sunny, with a high near 93. West wind around 3 mph.

---

Tonight:
Temperature: 58°F
Wind: 3 to 9 mph SSW
Forecast: Clear, with a low around 58. South southwest wind 3 to 9 mph.

---

Tuesday:
Temperature: 93°F
Wind: 1 to 9 mph SSW
Forecast: Sunny, with a high near 93. South southwest wind 1 to 9 mph.

---

Tuesday Night:
Temperature: 57°F
Wind: 5 to 9 mph SSW
Forecast: Mostly cloudy, with a low around 57. South southwest wind 5 to 9 mph.

---

Wednesday:
Temperature: 93°F
Wind: 2 to 7 mph SSW
Forecast: Sunny, with a high near 93. South southwest wind 2 to 7 mph.
```

## STDIO logging rule

With STDIO transport, **stdout is the wire**: the client and server exchange
JSON-RPC messages over stdin/stdout. Any stray write to stdout — a `print()`, a
library banner, a debug dump — is injected into that byte stream, corrupts the
JSON-RPC framing, and the client drops the connection (often with a confusing
parse error).

So this server:

- Uses no `print()` anywhere.
- Configures the `logging` module to write to **stderr** (`stream=sys.stderr`).
  The client treats stderr as a side channel and ignores it, so logs are safe.

This is why the standalone run looks "silent" on stdout — that silence is
correct.

## API endpoints used

Only the documented NWS endpoints, no invented ones:

- `GET /alerts/active/area/{state}` — active alerts for a state
- `GET /points/{lat},{lon}` — resolves coordinates to a forecast URL
- The `properties.forecast` URL returned by `/points` — the actual forecast
