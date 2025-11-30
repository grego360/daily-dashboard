"""Weather panel component for displaying weather information."""

from textual.app import ComposeResult
from textual.widgets import Label, Static

from ..models.weather import WeatherData


class WeatherPanel(Static):
    """Panel displaying weather information."""

    DEFAULT_CSS = """
    WeatherPanel {
        height: auto;
        border: solid $primary;
        padding: 0 1;
    }

    WeatherPanel #weather-error {
        color: $error;
        display: none;
    }

    WeatherPanel #weather-error.visible {
        display: block;
    }

    WeatherPanel #weather-empty {
        color: $text-muted;
        display: none;
    }

    WeatherPanel #weather-empty.visible {
        display: block;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._loading = True
        self._weather: WeatherData | None = None

    def compose(self) -> ComposeResult:
        yield Static("Loading...", id="weather-header")
        yield Label("", id="weather-error")
        yield Label("", id="weather-empty")
        yield Static("", id="weather-forecast")

    def set_loading(self, loading: bool) -> None:
        """Set loading state."""
        self._loading = loading
        if loading:
            self.query_one("#weather-header", Static).update("[dim]Loading...[/dim]")
            self.query_one("#weather-error", Label).update("")
            self.query_one("#weather-empty", Label).update("")
            self.query_one("#weather-forecast", Static).update("")

    def set_error(self, error: str) -> None:
        """Display an error message."""
        self._loading = False
        self.query_one("#weather-header", Static).update("[bold]Weather[/bold]")
        error_label = self.query_one("#weather-error", Label)
        error_label.update(f"[red]{error}[/red]")
        error_label.add_class("visible")
        self.query_one("#weather-empty", Label).remove_class("visible")
        self.query_one("#weather-forecast", Static).update("")

    def set_empty(self, message: str = "Weather disabled") -> None:
        """Display empty state message."""
        self._loading = False
        self.query_one("#weather-header", Static).update("[bold]Weather[/bold]")
        self.query_one("#weather-error", Label).remove_class("visible")
        empty_label = self.query_one("#weather-empty", Label)
        empty_label.update(f"[dim]{message}[/dim]")
        empty_label.add_class("visible")
        self.query_one("#weather-forecast", Static).update("")

    def _temp_color(self, temp: float) -> str:
        """Get color for temperature value."""
        if temp <= 0:
            return "blue"
        elif temp <= 10:
            return "cyan"
        elif temp <= 20:
            return "green"
        elif temp <= 30:
            return "yellow"
        return "red"

    def update_weather(self, weather: WeatherData) -> None:
        """Update panel with weather data."""
        self._weather = weather
        self._loading = False

        header_widget = self.query_one("#weather-header", Static)
        error_label = self.query_one("#weather-error", Label)
        empty_label = self.query_one("#weather-empty", Label)
        forecast_widget = self.query_one("#weather-forecast", Static)

        if weather.error:
            header_widget.update("[bold]Weather[/bold]")
            error_label.update(f"[red]{weather.error}[/red]")
            error_label.add_class("visible")
            empty_label.remove_class("visible")
            forecast_widget.update("")
            return

        error_label.remove_class("visible")
        empty_label.remove_class("visible")

        # Build header: "Location  5.0°C → 8km/h 💧"
        if weather.current:
            temp = weather.current.temperature
            wind = weather.current.wind_speed
            trend = weather.temperature_trend
            tc = self._temp_color(temp)

            # Check today's rain from daily forecast
            rain = ""
            if weather.daily:
                today = weather.daily[0]
                if today.precipitation_sum > 0 or today.precipitation_probability > 30:
                    rain = f" 💧{today.precipitation_probability}%"

            header_widget.update(
                f"[bold]{weather.location_name}[/bold]  "
                f"[{tc}]{temp:.1f}°C[/{tc}] {trend} {wind:.0f}km/h{rain}"
            )
        else:
            header_widget.update(f"[bold]{weather.location_name}[/bold]")

        # Build forecast: "Sun 2/6°  Mon 5/12°💧  ..."
        if weather.daily:
            parts = []
            for day in weather.daily[:5]:
                d = day.date.strftime("%a")
                mc, xc = self._temp_color(day.temp_min), self._temp_color(day.temp_max)
                rain = (
                    "💧" if day.precipitation_sum > 0 or day.precipitation_probability > 30 else ""
                )
                parts.append(
                    f"{d} [{mc}]{day.temp_min:.0f}[/{mc}]/[{xc}]{day.temp_max:.0f}°[/{xc}]{rain}"
                )
            forecast_widget.update("  ".join(parts))
        else:
            forecast_widget.update("[dim]No forecast[/dim]")

    def clear(self) -> None:
        """Clear all data."""
        self._weather = None
        self.query_one("#weather-header", Static).update("[bold]Weather[/bold]")
        self.query_one("#weather-error", Label).update("")
        self.query_one("#weather-empty", Label).update("")
        self.query_one("#weather-forecast", Static).update("")
