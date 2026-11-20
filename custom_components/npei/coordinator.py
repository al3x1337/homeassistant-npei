"""DataUpdateCoordinator for Niagara Peninsula Energy Inc. (NPEI)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any, Dict, Optional

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NPEIClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NPEIDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching NPEI data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NPEIClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self.client = client
        self.entry = entry
        self.account_id = entry.data.get("account_id")
        self.service_id = entry.data.get("service_id")
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via NPEI API."""
        try:
            today = date.today()
            # Fetch past 30 days of daily usage
            start_date = (today - timedelta(days=35)).isoformat()
            end_date = today.isoformat()

            usage_data = await self.client.get_usage(
                start_date=start_date,
                end_date=end_date,
                view="DAILY",
            )

            # Fetch weather for Niagara Falls
            weather_data = await self.client.get_weather(
                from_date=(today - timedelta(days=7)).isoformat(),
                to_date=today.isoformat(),
                time_type="daily",
            )

            # Compute Ontario season info (Option B)
            season_info = self.client.get_season_info(today)

            # Process latest daily record
            latest_usage = None
            price_plan = "TOU"
            buckets: Dict[str, float] = {}

            if usage_data:
                # Find the most recent day with valid consumption
                latest_usage = usage_data[-1]
                price_plan = latest_usage.get("pricePlan", "TOU")
                for bucket in latest_usage.get("usageBucket", []):
                    period = bucket.get("pricePeriod")
                    if period:
                        buckets[period] = bucket.get("value", 0.0)

            # Extract latest weather
            latest_weather = {}
            if weather_data and "weather" in weather_data and weather_data["weather"]:
                latest_weather = weather_data["weather"][-1]

            data = {
                "account_id": self.account_id,
                "service_id": self.service_id,
                "price_plan": price_plan,
                "latest_usage": latest_usage,
                "buckets": buckets,
                "season": season_info,
                "weather": latest_weather,
                "history": usage_data or [],
            }

            # Ingest into Home Assistant Long-Term Statistics for native Energy Dashboard
            await self._async_sync_energy_statistics(usage_data)

            return data

        except Exception as err:
            _LOGGER.exception("Error updating NPEI data: %s", err)
            raise UpdateFailed(f"Error communicating with NPEI: {err}") from err

    async def _async_sync_energy_statistics(
        self, usage_data: Optional[list[dict[str, Any]]]
    ) -> None:
        """Inject daily interval usage into Home Assistant's recorder statistics."""
        if not usage_data:
            return

        statistic_id = f"npei:{self.account_id}_consumption"
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=f"NPEI Electricity Consumption ({self.account_id})",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

        try:
            # Check last cumulative sum in HA database
            last_stats = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
            )
            cumulative_sum = 0.0
            if last_stats and statistic_id in last_stats and last_stats[statistic_id]:
                cumulative_sum = last_stats[statistic_id][0].get("sum") or 0.0

            stats_to_insert: list[StatisticData] = []
            for record in usage_data:
                start_str = record.get("startTime")
                val = record.get("value", 0.0)
                if not start_str or val is None:
                    continue

                try:
                    dt = datetime.fromisoformat(start_str)
                    cumulative_sum += float(val)
                    stats_to_insert.append(
                        StatisticData(
                            start=dt,
                            state=val,
                            sum=cumulative_sum,
                        )
                    )
                except ValueError:
                    continue

            if stats_to_insert:
                async_add_external_statistics(self.hass, metadata, stats_to_insert)
                _LOGGER.debug(
                    "Injected %d historical usage statistics for %s",
                    len(stats_to_insert),
                    statistic_id,
                )

        except Exception as err:
            _LOGGER.warning("Could not sync NPEI energy statistics to recorder: %s", err)
