"""MCP server wrapping the US National Weather Service (NWS) API.

Mirrors the official MCP weather quickstart
(https://modelcontextprotocol.io/docs/develop/build-server) so it can be read
side-by-side with the docs, with added resilience (timeouts, HTTP error
handling, empty-result handling) and stderr-only logging.

Transport: STDIO. Nothing is ever written to stdout except the MCP protocol
framing itself — see the logging note below.
"""

import logging
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# --- Logging -----------------------------------------------------------------
# STDIO transport uses stdout to exchange JSON-RPC messages with the client.
# Any stray write to stdout (a stray print, a library banner) corrupts that
# framing and the client drops the connection. So we log to stderr ONLY, which
# the client treats as a side channel and ignores.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("weather")

# Initialize the FastMCP server. The name shows up in client tool listings.
mcp = FastMCP("weather")

# --- Constants ---------------------------------------------------------------
NWS_API_BASE = "https://api.weather.gov"
# NWS requires a User-Agent identifying the application; requests without one
# may be rejected. No API key is needed.
USER_AGENT = "weather-app/1.0 (week3-mcp-study; contact: student@example.com)"


# --- Helpers -----------------------------------------------------------------
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a GET request to the NWS API and return parsed JSON.

    Returns None on any failure (HTTP error, timeout, malformed body) and logs
    the cause to stderr. Callers turn None into a user-facing message rather
    than raising, so a flaky upstream never crashes the server.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.warning("NWS request timed out: %s", url)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "NWS returned %s for %s", exc.response.status_code, url
            )
        except httpx.HTTPError as exc:
            logger.warning("NWS request failed for %s: %s", url, exc)
        except ValueError as exc:  # JSON decode error
            logger.warning("NWS returned non-JSON for %s: %s", url, exc)
        return None


def format_alert(feature: dict[str, Any]) -> str:
    """Format a single alert feature into a readable string."""
    props = feature["properties"]
    return (
        f"Event: {props.get('event', 'Unknown')}\n"
        f"Area: {props.get('areaDesc', 'Unknown')}\n"
        f"Severity: {props.get('severity', 'Unknown')}\n"
        f"Description: {props.get('description', 'No description available')}\n"
        f"Instructions: {props.get('instruction') or 'No specific instructions provided'}"
    )


# --- Tools -------------------------------------------------------------------
@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get active weather alerts for a US state.

    Args:
        state: Two-letter US state or territory code (e.g. CA, NY, TX).
    """
    code = state.strip().upper()
    if len(code) != 2 or not code.isalpha():
        return (
            f"'{state}' is not a valid state code. "
            "Use a two-letter code like CA, NY, or TX."
        )

    url = f"{NWS_API_BASE}/alerts/active/area/{code}"
    data = await make_nws_request(url)

    if data is None:
        return "Unable to fetch alerts right now. The weather service may be unavailable; please try again."

    features = data.get("features", [])
    if not features:
        return f"No active weather alerts for {code}."

    alerts = [format_alert(feature) for feature in features]
    return "\n\n---\n\n".join(alerts)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get the weather forecast for a location.

    Args:
        latitude: Latitude of the location (e.g. 38.5816).
        longitude: Longitude of the location (e.g. -121.4944).
    """
    if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
        return (
            f"Coordinates ({latitude}, {longitude}) are out of range. "
            "Latitude must be -90..90 and longitude -180..180."
        )

    # First resolve the coordinates to an NWS grid/forecast endpoint.
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if points_data is None:
        return (
            "Unable to fetch forecast for this location. NWS only covers the "
            "United States and its territories; double-check the coordinates."
        )

    forecast_url = points_data.get("properties", {}).get("forecast")
    if not forecast_url:
        return "No forecast is available for this location."

    forecast_data = await make_nws_request(forecast_url)
    if forecast_data is None:
        return "Unable to fetch the detailed forecast right now; please try again."

    periods = forecast_data.get("properties", {}).get("periods", [])
    if not periods:
        return "No forecast periods were returned for this location."

    # Show the next five forecast periods (roughly 2-3 days).
    forecasts = []
    for period in periods[:5]:
        forecasts.append(
            f"{period.get('name', 'Unknown')}:\n"
            f"Temperature: {period.get('temperature', '?')}°{period.get('temperatureUnit', '')}\n"
            f"Wind: {period.get('windSpeed', '?')} {period.get('windDirection', '')}\n"
            f"Forecast: {period.get('detailedForecast', 'No details available')}"
        )
    return "\n\n---\n\n".join(forecasts)


if __name__ == "__main__":
    logger.info("Starting weather MCP server (STDIO transport)")
    mcp.run(transport="stdio")
