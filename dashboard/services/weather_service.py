"""Weather service using Open-Meteo API."""

import asyncio
import logging
import random
from datetime import datetime

import httpx

from ..models.config import WeatherConfig
from ..models.weather import CurrentWeather, DailyForecast, HourlyForecast, WeatherData

logger = logging.getLogger(__name__)

# Open-Meteo API base URL (free, no API key required)
API_BASE_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 10.0
BACKOFF_MULTIPLIER = 2.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _calculate_backoff(attempt: int) -> float:
    """Calculate backoff time with jitter."""
    backoff = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER**attempt), MAX_BACKOFF)
    jitter = 0.5 + random.random()
    return backoff * jitter


class WeatherService:
    """Service to fetch weather data from Open-Meteo API."""

    def __init__(self, timeout: float = 30.0, max_retries: int = MAX_RETRIES):
        self.timeout = timeout
        self.max_retries = max_retries

    async def fetch_weather(self, config: WeatherConfig) -> WeatherData:
        """Fetch weather data for the configured location with retry logic."""
        if not config.enabled:
            return WeatherData(
                location_name=config.location_name,
                latitude=config.latitude,
                longitude=config.longitude,
                error="Weather disabled in config",
            )

        params = {
            "latitude": config.latitude,
            "longitude": config.longitude,
            "current": "temperature_2m,wind_speed_10m",
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum,precipitation_probability_max",
            "forecast_days": 5,
            "timezone": "auto",
        }

        last_error: str | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(API_BASE_URL, params=params)
                    response.raise_for_status()
                    data = response.json()

                return self._parse_response(data, config.location_name)

            except httpx.TimeoutException:
                last_error = "Request timeout"
                if attempt < self.max_retries:
                    backoff = _calculate_backoff(attempt)
                    logger.debug(f"Weather timeout, retry {attempt + 1} in {backoff:.1f}s")
                    await asyncio.sleep(backoff)
                    continue
                logger.warning(f"Timeout fetching weather for {config.location_name} after retries")

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                last_error = f"HTTP {status}"

                if status in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    backoff = _calculate_backoff(attempt)
                    logger.debug(f"Weather HTTP {status}, retry {attempt + 1} in {backoff:.1f}s")
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"HTTP error fetching weather: {status}")

            except httpx.ConnectError as e:
                last_error = "Connection error"
                if attempt < self.max_retries:
                    backoff = _calculate_backoff(attempt)
                    logger.debug(f"Weather connection error, retry {attempt + 1} in {backoff:.1f}s")
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"Connection error fetching weather: {e}")

            except Exception as e:
                logger.error(f"Error fetching weather: {e}")
                last_error = str(e)
                break

        return WeatherData(
            location_name=config.location_name,
            latitude=config.latitude,
            longitude=config.longitude,
            error=last_error or "Unknown error",
        )

    def _parse_response(self, data: dict, location_name: str) -> WeatherData:
        """Parse the Open-Meteo API response."""
        try:
            # Parse current weather
            current_data = data.get("current", {})
            current_units = data.get("current_units", {})

            current = None
            if current_data:
                current = CurrentWeather(
                    temperature=current_data.get("temperature_2m", 0),
                    wind_speed=current_data.get("wind_speed_10m", 0),
                    time=datetime.fromisoformat(
                        current_data.get("time", datetime.now().isoformat())
                    ),
                    temperature_unit=current_units.get("temperature_2m", "°C"),
                    wind_speed_unit=current_units.get("wind_speed_10m", "km/h"),
                )

            # Parse hourly forecast
            hourly_data = data.get("hourly", {})
            hourly = []

            times = hourly_data.get("time", [])
            temps = hourly_data.get("temperature_2m", [])
            humidity = hourly_data.get("relative_humidity_2m", [])
            wind = hourly_data.get("wind_speed_10m", [])

            for i, time_str in enumerate(times):
                if i < len(temps) and i < len(humidity) and i < len(wind):
                    hourly.append(
                        HourlyForecast(
                            time=datetime.fromisoformat(time_str),
                            temperature=temps[i],
                            humidity=humidity[i],
                            wind_speed=wind[i],
                        )
                    )

            # Parse daily forecast
            daily_data = data.get("daily", {})
            daily = []

            daily_times = daily_data.get("time", [])
            temp_mins = daily_data.get("temperature_2m_min", [])
            temp_maxs = daily_data.get("temperature_2m_max", [])
            precip_sums = daily_data.get("precipitation_sum", [])
            precip_probs = daily_data.get("precipitation_probability_max", [])

            for i, date_str in enumerate(daily_times):
                if i < len(temp_mins) and i < len(temp_maxs):
                    daily.append(
                        DailyForecast(
                            date=datetime.fromisoformat(date_str),
                            temp_min=temp_mins[i],
                            temp_max=temp_maxs[i],
                            precipitation_sum=precip_sums[i] if i < len(precip_sums) else 0.0,
                            precipitation_probability=precip_probs[i]
                            if i < len(precip_probs)
                            else 0,
                        )
                    )

            return WeatherData(
                location_name=location_name,
                latitude=data.get("latitude", 0),
                longitude=data.get("longitude", 0),
                timezone=data.get("timezone", "GMT"),
                current=current,
                hourly=hourly,
                daily=daily,
            )

        except Exception as e:
            logger.error(f"Error parsing weather response: {e}")
            return WeatherData(
                location_name=location_name,
                latitude=data.get("latitude", 0),
                longitude=data.get("longitude", 0),
                error=f"Parse error: {e}",
            )

    async def geocode(self, query: str) -> tuple[str, float, float] | None:
        """Look up location by name or postcode with retry logic.

        Returns tuple of (location_name, latitude, longitude) or None if not found.
        """
        params = {
            "name": query,
            "count": 1,
            "language": "en",
            "format": "json",
        }

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(GEOCODING_URL, params=params)
                    response.raise_for_status()
                    data = response.json()

                results = data.get("results", [])
                if not results:
                    return None

                result = results[0]
                name = result.get("name", query)
                admin = result.get("admin1", "")
                country = result.get("country", "")

                # Build a nice location name
                location_parts = [name]
                if admin and admin != name:
                    location_parts.append(admin)
                if country:
                    location_parts.append(country)
                location_name = ", ".join(location_parts[:2])  # Limit to avoid too long names

                return (
                    location_name,
                    result.get("latitude", 0),
                    result.get("longitude", 0),
                )

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < self.max_retries:
                    backoff = _calculate_backoff(attempt)
                    logger.debug(f"Geocode error, retry {attempt + 1} in {backoff:.1f}s")
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"Geocoding error after retries: {e}")
                return None

            except httpx.HTTPStatusError as e:
                if e.response.status_code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    backoff = _calculate_backoff(attempt)
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"Geocoding HTTP error: {e.response.status_code}")
                return None

            except Exception as e:
                logger.error(f"Geocoding error: {e}")
                return None

        return None
