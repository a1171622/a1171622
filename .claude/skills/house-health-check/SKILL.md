---
name: house-health-check
description: Weekly or on-demand check of how Wing's house ran - paid grid import, battery low points, car charging, Hold, bathroom warm-up, fan memory, heating forecast, errors - written as a short report. Use when Wing asks "how did the house run" or something looks off.
---

# House health check

Goal being checked: the house and the car run on solar plus the free grid window (11:00-13:58) alone.
Report only unless Wing asks for fixes; fixes then follow `ha-safe-edit` and `independent-review`.
The last full report is a good template: `/mnt/project-files/plan/health-check-2026-11-02/REPORT.md`.

## Steps

1. Read `claude/HANDOFF.md` §4-§5 for what is live and what is being watched.
2. Pull the period's data (see `ha-history-calc`): hourly `change` of `sensor.sigen_plant_total_imported_energy` and
   `_total_exported_energy`; 5-minute or raw battery SoC, grid power, `sensor.car_charging_power`, aircon meter,
   `binary_sensor.ev_charge_wanted`, `input_text.whole_house_comfort_state`; the logbook for automations and people.
3. Build a per-day table: paid kWh (import outside 11:00-14:00), free kWh, exported (and Super Export 18-21), aircon kWh,
   lowest battery % and when.
4. For every day with paid import above the ~0.25 kWh/day trickle, find the cause from the 5-minute data and logbook:
   battery empty before 11:00 (car overnight? Hold heating? cloudy free window?), or the Sigen charging from the grid
   on its own (HA has no Sigen control except the DC charger switch).
5. Check each live feature did what HANDOFF says: Hold start/pauses (incl. the "battery" pause), Bedrooms off at start,
   bathroom warm-up runs/skips, free-hours heat soak and its end, fan memory save/restore, car floor and below-minimum
   rule, export cut-off. Quote the times.
6. Heating forecast vs actual from `sensor.aircon_forecast_accuracy` attributes; explain big single-day misses.
7. Errors: `system_log/list`, `sensor.house_problems` items, offline devices, failed logins.
8. Write `/mnt/project-files/plan/health-check-YYYY-MM-DD/REPORT.md`: bottom line first (goal met on N of M days,
   paid kWh and $), then one section per finding with numbers, then suggested fixes, each marked "not done".
9. Message Wing in under 15 lines with the bottom line and the decisions they need to make, attach the report, and
   add the open items to HANDOFF §5 and `/mnt/project-files/plan/PLAN.md`.

## Remember

- The car follows Wing's BYD-app schedule. Never suggest stopping the car for the house; Hold gives way.
- Sigen app settings are Wing's to change; say what to check in the app instead.
- Times in Melbourne. Battery 1 % = 0.40 kWh.
