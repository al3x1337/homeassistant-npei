# Niagara Peninsula Energy Inc. (NPEI) Custom Integration for Home Assistant

Custom Home Assistant integration that connects directly to the NPEI customer portal APIs (`myaccount.npei.ca`) to pull granular interval electricity consumption, Time-of-Use / Tiered rate breakdowns, London Hydro weather observations (Niagara Falls), and Ontario electricity season transitions.

---

## Features

- **Direct Portal Connection:** Connects via authenticated REST APIs (`usageapi`, `myaccountapi`, and London Hydro Shared Services).
- **Native Energy Dashboard Integration:** Automatically pushes daily and hourly intervals into Home Assistant Long-Term Statistics (`recorder`).
- **Dynamic Rate Handling:**
  - Detects whether your account is on **Time-of-Use (TOU)**, **Tiered**, or **Ultra-Low Overnight (ULO)**.
  - Automatically maps usage to `Off-Peak`, `Mid-Peak`, `On-Peak`, or `Tier 1` / `Tier 2` without breaking entities.
- **Niagara Falls Weather Integration:**
  - Retrieves exact outside temperatures (average, daily max, daily min) used on NPEI's portal graphs.
- **Ontario Energy Season Tracking (Option B):**
  - `sensor.npei_current_season`: (`winter` / `summer`)
  - `sensor.npei_next_season`: (`summer` / `winter`)
  - `sensor.npei_next_season_start_date`: (`2027-05-01`)
  - `sensor.npei_days_until_next_season`: Countdown in days for easy automation triggers.

---

## Installation

### Manual Installation
1. Copy the `custom_components/npei` folder into your Home Assistant `/config/custom_components/` directory:
   ```bash
   cp -r custom_components/npei /path/to/homeassistant/config/custom_components/
   ```
2. Restart Home Assistant.
3. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
4. Search for **Niagara Peninsula Energy Inc. (NPEI)**.
5. Enter your NPEI MyAccount portal login email and password.
6. The integration will automatically discover your Account ID, Service ID, and rate class, then set up the sensors.

---

## Provided Entities

| Entity ID | Name | Unit / State |
| :--- | :--- | :--- |
| `sensor.npei_daily_consumption` | Daily Consumption | `kWh` |
| `sensor.npei_daily_cost` | Daily Cost | `$` |
| `sensor.npei_price_plan` | Price Plan | `TOU`, `TIERED`, or `ULO` |
| `sensor.npei_off_peak_consumption` | Off-Peak Consumption | `kWh` |
| `sensor.npei_mid_peak_consumption` | Mid-Peak Consumption | `kWh` |
| `sensor.npei_on_peak_consumption` | On-Peak Consumption | `kWh` |
| `sensor.npei_tier_1_consumption` | Tier 1 Consumption | `kWh` |
| `sensor.npei_tier_2_consumption` | Tier 2 Consumption | `kWh` |
| `sensor.npei_outside_temperature` | Outside Temperature | `°C` |
| `sensor.npei_outside_max_temperature` | Outside Max Temperature | `°C` |
| `sensor.npei_outside_min_temperature` | Outside Min Temperature | `°C` |
| `sensor.npei_current_season` | Current Season | `winter` / `summer` |
| `sensor.npei_next_season` | Next Season | `summer` / `winter` |
| `sensor.npei_next_season_start_date` | Next Season Start Date | `YYYY-MM-DD` |
| `sensor.npei_days_until_next_season` | Days Until Next Season | `d` |

---

## Reproducing the Exact NPEI Portal Graph (Lovelace YAML)

Add this card to your dashboard using `custom:apexcharts-card`:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: NPEI Monthly Electricity Usage & Temperature
  show_states: false
graph_span: 12month
span:
  end: month
stacked: true
apex_config:
  chart:
    type: bar
  stroke:
    curve: smooth
    width: [0, 0, 0, 3, 2, 2]
    dashArray: [0, 0, 0, 0, 4, 4]
  yaxis:
    - title:
        text: Usage (kWh)
      min: 0
    - title:
        text: Temperature (°C)
      opposite: true
series:
  - entity: sensor.npei_off_peak_consumption
    name: Off-Peak
    type: column
    color: '#4caf50'
    group_by:
      func: sum
      duration: 1month
  - entity: sensor.npei_mid_peak_consumption
    name: Mid-Peak
    type: column
    color: '#ff9800'
    group_by:
      func: sum
      duration: 1month
  - entity: sensor.npei_on_peak_consumption
    name: On-Peak
    type: column
    color: '#f44336'
    group_by:
      func: sum
      duration: 1month
  - entity: sensor.npei_outside_temperature
    name: Avg Temperature
    type: line
    color: '#e91e63'
    yaxis_id: 1
    group_by:
      func: mean
      duration: 1month
  - entity: sensor.npei_outside_max_temperature
    name: Max Temp
    type: line
    color: '#9c27b0'
    yaxis_id: 1
    opacity: 0.7
    group_by:
      func: max
      duration: 1month
  - entity: sensor.npei_outside_min_temperature
    name: Min Temp
    type: line
    color: '#2196f3'
    yaxis_id: 1
    opacity: 0.7
    group_by:
      func: min
      duration: 1month
```
