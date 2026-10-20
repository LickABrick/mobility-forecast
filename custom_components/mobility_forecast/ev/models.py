"""Immutable battery-side energy, timed travel and opportunity contracts."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EVConfig:
    usable_capacity_kwh: float
    consumption_kwh_per_100km: float
    max_ac_charge_power_kw: float
    minimum_soc: float = 15
    preferred_max_soc: float = 80
    absolute_max_soc: float = 100
    allow_above_preferred_soc: bool = False
    charging_mode: str = "home_only"
    minimum_appointment_minutes: float = 90
    max_charger_distance_m: float = 300
    session_overhead_minutes: float = 15
    minimum_useful_charge_kwh: float = 5
    prefer_long_sessions: bool = True
    home_window_start: str = "18:00"
    home_window_end: str = "07:00"

    @classmethod
    def from_options(cls, options):
        return cls(
            **{k: v for k, v in options.items() if k in cls.__dataclass_fields__}
        )


@dataclass(frozen=True)
class VehicleTelemetry:
    current_soc_percent: float | None
    soc_observed_at: datetime | None
    freshness: str = "unavailable"
    charging_state: str = "unknown"
    plugged_in: bool | None = None
    charging_power_kw: float | None = None
    vehicle_charge_limit_percent: float | None = None
    reported_range_km: float | None = None
    remaining_charge_minutes: float | None = None
    location_state: str | None = None
    consumption_kwh_per_100km: float | None = None


@dataclass(frozen=True)
class JourneyLeg:
    departure: datetime
    arrival: datetime
    distance_km: float
    duration_minutes: float
    origin_identity: str
    destination_identity: str
    quality: str = "timed_home_chain_assumed"


@dataclass(frozen=True)
class Stop:
    arrival: datetime
    departure: datetime
    destination_identity: str
    query: str  # Ephemeral only; never serialized in API or diagnostics.
    coordinates: tuple[float, float] | None = None


@dataclass(frozen=True)
class ChargePoint:
    provider_id: str
    latitude: float
    longitude: float
    ac_power_kw: float
    distance_m: float
    status: str = "unknown"
    provider: str = "NDW DOT-NL"
    connector: str = "IEC_62196_T2"
    updated_at: str | None = None


@dataclass(frozen=True)
class ChargingOpportunity:
    source: str
    start: datetime
    end: datetime
    effective_power_kw: float
    potential_battery_kwh: float
    stop_identity: str = "home"
    charger: ChargePoint | None = None
    quality: str = "assumed_home_availability"


@dataclass(frozen=True)
class ChargingRecommendation:
    status: str
    reason: str
    confidence: str = "insufficient_data"
    start: datetime | None = None
    end: datetime | None = None
    location_type: str | None = None
    pre_charge_soc: float | None = None
    target_soc: float | None = None
    battery_energy_kwh: float | None = None
    grid_energy_kwh: float | None = None
    duration_minutes: float | None = None
    deadline: datetime | None = None
    charger_distance_m: float | None = None
