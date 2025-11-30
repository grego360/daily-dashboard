"""Weather data models."""

from datetime import datetime

from pydantic import BaseModel, Field


class CurrentWeather(BaseModel):
    """Current weather conditions."""

    temperature: float
    wind_speed: float
    time: datetime
    temperature_unit: str = "°C"
    wind_speed_unit: str = "km/h"


class HourlyForecast(BaseModel):
    """Hourly weather forecast for a single hour."""

    time: datetime
    temperature: float
    humidity: int
    wind_speed: float


class DailyForecast(BaseModel):
    """Daily weather forecast."""

    date: datetime
    temp_min: float
    temp_max: float
    precipitation_sum: float = 0.0
    precipitation_probability: int = 0


class WeatherData(BaseModel):
    """Complete weather data from API."""

    location_name: str
    latitude: float
    longitude: float
    timezone: str = "GMT"
    current: CurrentWeather | None = None
    hourly: list[HourlyForecast] = Field(default_factory=list)
    daily: list[DailyForecast] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.now)
    error: str | None = None

    @property
    def next_hours(self) -> list[HourlyForecast]:
        """Get forecast for next 12 hours from now."""
        now = datetime.now()
        return [h for h in self.hourly if h.time >= now][:12]

    @property
    def today_forecast(self) -> list[HourlyForecast]:
        """Get today's remaining forecast."""
        now = datetime.now()
        today = now.date()
        return [h for h in self.hourly if h.time.date() == today and h.time >= now]

    @property
    def temperature_trend(self) -> str:
        """Get temperature trend for next few hours."""
        next_hours = self.next_hours[:6]
        if len(next_hours) < 2:
            return "→"

        first_temp = next_hours[0].temperature
        last_temp = next_hours[-1].temperature
        diff = last_temp - first_temp

        if diff > 1:
            return "↑"
        elif diff < -1:
            return "↓"
        return "→"
