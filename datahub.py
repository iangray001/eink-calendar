"""
datahub - Met Office Weather DataHub site-specific API client

Replacement for the retired DataPoint API. Requires a free API key from
https://datahub.metoffice.gov.uk (site-specific forecast, 360 calls/day).
"""

import json
import urllib.error
import urllib.request
from datetime import datetime

BASE_URL = "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/"


def _fetch(endpoint, apikey, lat, lon):
    url = (
        f"{BASE_URL}{endpoint}"
        f"?latitude={lat}&longitude={lon}"
        f"&includeLocationName=true&excludeParameterMetadata=false"
    )
    req = urllib.request.Request(url, headers={"apikey": apikey})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise RuntimeError(
                "DataHub API key is invalid or expired. "
                "Check weather.json and https://datahub.metoffice.gov.uk"
            ) from e
        if e.code == 429:
            raise RuntimeError(
                "DataHub rate limit exceeded (360 requests/day). Try again later."
            ) from e
        raise


def fetch_three_hourly(apikey, lat, lon):
    """Fetch three-hourly forecast. Returns list of dicts with keys:
    timestamp (datetime), weather_code (int), feels_like_temp (float).
    """
    data = _fetch("three-hourly", apikey, lat, lon)
    series = data["features"][0]["properties"]["timeSeries"]
    results = []
    for entry in series:
        results.append({
            "timestamp": datetime.fromisoformat(entry["time"].replace("Z", "+00:00")).replace(tzinfo=None),
            "weather_code": int(entry["significantWeatherCode"]),
            "feels_like_temp": float(entry["feelsLikeTemp"]),
        })
    return results


def fetch_daily(apikey, lat, lon):
    """Fetch daily forecast. Returns list of dicts with keys:
    timestamp (datetime), weather_code (int),
    max_feels_like_temp (float), min_feels_like_temp (float).
    """
    data = _fetch("daily", apikey, lat, lon)
    series = data["features"][0]["properties"]["timeSeries"]
    results = []
    for entry in series:
        if "daySignificantWeatherCode" not in entry:
            continue  # partial day (e.g. today after daytime has passed)
        results.append({
            "timestamp": datetime.fromisoformat(entry["time"].replace("Z", "+00:00")).replace(tzinfo=None),
            "weather_code": int(entry["daySignificantWeatherCode"]),
            "max_feels_like_temp": float(entry["dayMaxFeelsLikeTemp"]),
            "min_feels_like_temp": float(entry["nightMinFeelsLikeTemp"]),
        })
    return results


