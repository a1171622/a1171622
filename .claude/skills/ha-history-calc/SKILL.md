---
name: ha-history-calc
description: Pull Home Assistant history or long-term statistics (energy, temperatures, battery, aircon) and turn them into an engineering calc with numbers and stated assumptions. Use for any "how much / why / is it working" question about Wing's house.
---

# Engineering calcs from Home Assistant history

Wing is a structural engineer. Answers carry numbers from HA history, the period and sensors used, the assumptions,
and an honest error band, the way an engineering calc would.

## 1. Pick the source

| Need | Source | Limit |
|---|---|---|
| Last 7 days, minute detail | raw history: websocket `history/history_during_period` | recorder purges raw after **7 days** |
| Older, or hourly totals | websocket `recorder/statistics_during_period`, `period: "hour"` (or `"5minute"`, `"day"`) | counters give `sum`/`change`; measurements give `mean`/`min`/`max` |
| What an automation did | `logbook/get_events`, automation traces | raw window only |

Lost data: 8 Oct 08:00 -> 9 Oct 10:05 2026; flat (frozen) values 7 Oct 23:00Z -> 8 Oct 22:00Z in some series. The recorder excludes battery power, per-string PV and grid import/export
power on purpose; use the plant sensors below. Only data from **1 Aug 2026** describes the renovated house.

Example (websocket batch):
```json
{"type": "recorder/statistics_during_period", "start_time": "2026-10-27T00:00:00+11:00",
 "end_time": "2026-11-03T00:00:00+11:00", "statistic_ids": ["sensor.sigen_plant_total_imported_energy"],
 "period": "hour", "types": ["change"]}
```
Big results are saved to a tool-results JSON file: load and analyse them in Python (pandas), never by eye.

## 2. Sensors that matter (confirm ids live before use)

- Grid: `sensor.sigen_plant_total_imported_energy`, `_total_exported_energy` (counters); `sensor.sigen_plant_grid_active_power`.
- Battery: `sensor.sigen_plant_battery_state_of_charge` (40.3 kWh; 1 % = 0.40 kWh); floor `sensor.home_battery_needed`.
- Solar / load: `sensor.sigen_plant_pv_power`, `sensor.sigen_plant_total_load_power` (reads ~115-176 W low).
- Aircon: cumulative meter `sensor.living_room_aircon_measured_cumulative_power_consumption` (all Mitsubishi heads,
  0.1 kWh steps), `sensor.mitsubishi_outdoor_unit_power`, LG `sensor.bedroom_2_air_conditioner_energy_today`.
- Temperatures: hallway `sensor.bedroom_temperature`, outdoor `sensor.melbourne_home_temp`. Head room temps read
  1.8-2.4 C low at night.
- Car: `sensor.car_charging_power` (SoC-rate estimate; the BYD cloud reports 0 kW while AC charging).
- Forecast vs actual heating: `sensor.aircon_forecast_accuracy` attributes.

## 3. Conventions

- Times are Melbourne (`Australia/Sydney` in HA, UTC+11 in summer). Convert before splitting by hour.
- Tariff (GloBird): free 11:00-13:58, peak 39.6c 16:00-23:00, otherwise 31.9c; Super Export 10c for the first 15 kWh
  18:00-21:00. "Paid import" = import outside 11:00-14:00. The Sigen trickle is ~0.25 kWh/day and unavoidable.
- House constants (Oct 2026 calibration): H ~390 W/K (+-25), heat storage ~11.3 kWh/K, time constant ~29 h,
  heating COP ~2.65, cooling COP ~4.5 (rough), empty-house load ~10.9 kWh/day.
- Raw data needed beyond 7 days: export it to CSV under `/mnt/project-files/plan/<topic>/data/` and keep the scripts
  in `/mnt/project-files/plan/<topic>/scripts/` so the calc can be re-run.

## 4. Write it up

- Lead with the answer and its size ("0.25 kWh/day paid, about 8c a day").
- A small table per day or per case, with units.
- State assumptions and which sensors were used; say what is a guess.
- Separate measured facts from interpretation. A model change needs a backtest on days it was not tuned on.
- Longer than ~15 lines: write `/mnt/project-files/plan/<topic>/REPORT.md` and point to it.
