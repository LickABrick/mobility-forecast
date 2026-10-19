"""Integration constants; statistical tuning is deliberately not configurable."""

DOMAIN = "mobility_forecast"
VERSION = "1.0.0"
FORECAST_KEYS = ("today", "tomorrow", "next_7_days", "next_30_days", "annual")
# Retention is time-based with <=2 physical observations per hour, not latest-N.
MAX_READINGS = 2 * 24 * 1096
HISTORY_DAYS = 1095
