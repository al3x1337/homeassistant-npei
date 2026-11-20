"""Sensor platform for Niagara Peninsula Energy Inc. (NPEI)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CURRENCY_DOLLAR,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NPEIDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NPEI sensors based on a config entry."""
    coordinator: NPEIDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        # Energy & Cost
        NPEIDailyConsumptionSensor(coordinator, entry),
        NPEIDailyCostSensor(coordinator, entry),
        NPEIPricePlanSensor(coordinator, entry),
        # TOU Bucket Sensors
        NPEITOUBucketSensor(coordinator, entry, "Off-Peak", "off_peak_consumption"),
        NPEITOUBucketSensor(coordinator, entry, "Mid-Peak", "mid_peak_consumption"),
        NPEITOUBucketSensor(coordinator, entry, "On-Peak", "on_peak_consumption"),
        # Tiered Sensors (if applicable)
        NPEITOUBucketSensor(coordinator, entry, "Tier 1", "tier_1_consumption"),
        NPEITOUBucketSensor(coordinator, entry, "Tier 2", "tier_2_consumption"),
        # Weather
        NPEIWeatherSensor(coordinator, entry, "temperature", "outside_temperature"),
        NPEIWeatherSensor(coordinator, entry, "maxTemperature", "outside_max_temperature"),
        NPEIWeatherSensor(coordinator, entry, "minTemperature", "outside_min_temperature"),
        # Season Sensors (Option B)
        NPEICurrentSeasonSensor(coordinator, entry),
        NPEINextSeasonSensor(coordinator, entry),
        NPEINextSeasonStartDateSensor(coordinator, entry),
        NPEIDaysUntilNextSeasonSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class NPEIBaseSensor(CoordinatorEntity[NPEIDataUpdateCoordinator], SensorEntity):
    """Base sensor for NPEI."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NPEIDataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._key = key
        account_id = coordinator.account_id
        self._attr_unique_id = f"npei_{account_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_id)},
            name=f"NPEI Electricity Meter ({account_id})",
            manufacturer="Niagara Peninsula Energy Inc.",
            model="Smart Meter Account",
        )


class NPEIDailyConsumptionSensor(NPEIBaseSensor):
    """Sensor for latest daily electricity consumption."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt-circle"

    def __init__(self, coordinator: NPEIDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "daily_consumption")
        self._attr_name = "Daily Consumption"

    @property
    def native_value(self) -> Optional[float]:
        latest = self.coordinator.data.get("latest_usage")
        if latest:
            return latest.get("value")
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        latest = self.coordinator.data.get("latest_usage") or {}
        return {
            "start_time": latest.get("startTime"),
            "reading_quality": latest.get("readingQuality"),
            "buckets": self.coordinator.data.get("buckets", {}),
        }


class NPEIDailyCostSensor(NPEIBaseSensor):
    """Sensor for latest daily cost."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: NPEIDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "daily_cost")
        self._attr_name = "Daily Cost"

    @property
    def native_value(self) -> Optional[float]:
        latest = self.coordinator.data.get("latest_usage")
        if latest:
            cost = latest.get("cost")
            return round(cost, 2) if cost is not None else None
        return None


class NPEIPricePlanSensor(NPEIBaseSensor):
    """Sensor for active electricity price plan (TOU, Tiered, ULO)."""

    _attr_icon = "mdi:clock-time-four-outline"

    def __init__(self, coordinator: NPEIDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "price_plan")
        self._attr_name = "Price Plan"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.get("price_plan", "TOU")


class NPEITOUBucketSensor(NPEIBaseSensor):
    """Sensor for specific rate periods (Off-Peak, Mid-Peak, On-Peak, Tier 1, etc.)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        coordinator: NPEIDataUpdateCoordinator,
        entry: ConfigEntry,
        bucket_name: str,
        key: str,
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._bucket_name = bucket_name
        self._attr_name = f"{bucket_name} Consumption"

    @property
    def native_value(self) -> Optional[float]:
        buckets = self.coordinator.data.get("buckets", {})
        if self._bucket_name in buckets:
            return round(buckets[self._bucket_name], 2)
        # If account is on another plan (e.g. Tiered vs TOU), return 0.0
        return 0.0


class NPEIWeatherSensor(NPEIBaseSensor):
    """Sensor for outside temperature from NPEI/London Hydro weather."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: NPEIDataUpdateCoordinator,
        entry: ConfigEntry,
        weather_key: str,
        key: str,
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._weather_key = weather_key
        name_map = {
            "temperature": "Outside Temperature",
            "maxTemperature": "Outside Max Temperature",
            "minTemperature": "Outside Min Temperature",
        }
        self._attr_name = name_map.get(weather_key, weather_key)

    @property
    def native_value(self) -> Optional[float]:
        weather = self.coordinator.data.get("weather", {})
        val = weather.get(self._weather_key)
        return round(val, 1) if val is not None else None


class NPEICurrentSeasonSensor(NPEIBaseSensor):
    """Sensor for current Ontario electricity season."""

    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator: NPEIDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "current_season")
        self._attr_name = "Current Season"

    @property
    def native_value(self) -> str:
        season = self.coordinator.data.get("season", {})
        return season.get("current_season", "winter")

    @property
    def icon(self) -> str:
        return "mdi:weather-sunny" if self.native_value == "summer" else "mdi:snowflake"


class NPEINextSeasonSensor(NPEIBaseSensor):
    """Sensor for next Ontario electricity season."""

    def __init__(self, coordinator: NPEIDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "next_season")
        self._attr_name = "Next Season"

    @property
    def native_value(self) -> str:
        season = self.coordinator.data.get("season", {})
        return season.get("next_season", "summer")


class NPEINextSeasonStartDateSensor(NPEIBaseSensor):
    """Sensor for when the next Ontario electricity season begins (YYYY-MM-DD)."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, coordinator: NPEIDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "next_season_start_date")
        self._attr_name = "Next Season Start Date"

    @property
    def native_value(self) -> Optional[str]:
        season = self.coordinator.data.get("season", {})
        return season.get("next_season_start_date")


class NPEIDaysUntilNextSeasonSensor(NPEIBaseSensor):
    """Sensor for countdown days until next Ontario electricity season."""

    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: NPEIDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "days_until_next_season")
        self._attr_name = "Days Until Next Season"

    @property
    def native_value(self) -> Optional[int]:
        season = self.coordinator.data.get("season", {})
        return season.get("days_until_next_season")
