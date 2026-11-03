---
name: ha-safe-edit
description: Change Wing's Home Assistant config (packages, automations, templates, helpers, hub files) safely - read live, back up, patch with a hash guard, review, check_config, reload, verify, log. Use for any HA file or automation edit.
---

# Safe Home Assistant edit

Wing's house runs on Home Assistant, reached through the Home_Assistant MCP connector. Earlier sessions keep the
current state in `claude/HANDOFF.md` (read it first, every session) and a change log with file hashes in
`claude/PROGRESS_LOG.md`. A bad write can stop HA starting, so every edit follows these steps in order.

## Before you start

1. Read `claude/HANDOFF.md` §1 (permissions and standing constraints) and the §4 section for the feature.
2. Search `claude/PROGRESS_LOG.md` for the feature name: other threads edit the same files.
3. Decide whether Wing must OK it first. Ask first for: an HA/host/add-on restart, deleting anything that can't be
   put back, weakening safety (heater, lawn valve, leak, outage, backups, locks, cameras), anything costing money or
   changing a Sigen/tariff/account setting, physical actions people would notice, or anything Wing would see change.
   Reloads, new helpers, template edits and faked test states don't need asking.
4. Never discover entity ids by guessing. Confirm every id with `home_assistant_eval_template`
   (`{{ states('x') }}`, `{{ states.sensor | selectattr('entity_id','search','...') | map(attribute='entity_id') | list }}`).
   The aircon entity names are misleading (e.g. `climate.main_bedroom_aircon` is the Living room); HANDOFF §2 maps them.

## Steps

1. **Read live.** `home_assistant_read_text_file` on the file; keep the full `sha256`. Results over ~25k tokens land in
   a tool-results JSON file: load it with Python (`json.load(...)['text']`) instead of retyping.
2. **Back up.** `home_assistant_move_or_copy_file` copy:true to `claude/archive/<file>.bak-YYYY-MM-DD-<topic>`. For a UI
   automation edit, back up `automations.yaml` too.
3. **Test logic first.** Render any new template with `home_assistant_eval_template` against live state.
4. **Edit.**
   - Existing file: `home_assistant_patch_file` with `expected_sha256` and a unified diff. Hunk header counts must be
     exact; `read_text_file start_line` is 0-based, hunk headers are 1-based. Keep at least one context line each side,
     never end a hunk on a blank context line.
     A zero-context `@@ -N,0 +N,k @@` hunk inserts BEFORE 1-based line N; an insert hunk with context on one side only
     is anchored to end-of-file and fails. Generate the diff with Python `difflib.unified_diff` (or
     `claude/tools/mkdiff.py`) from the live text, rather than writing it by hand.
   - New file: `home_assistant_write_file` with `override_existing_file: false`.
   - UI automation: GET `/api/config/automation/config/<id>`, change it, POST the whole config back.
5. **Independent review** (see the `independent-review` skill) before anything goes live, unless it is a trivial fix.
6. **Check config.** `POST /api/config/core/check_config` must return `valid`. If not, copy the backup back and stop.
7. **Reload only what changed:** `automation/reload`, `template/reload`, `script/reload`,
   `homeassistant/reload_custom_templates`, `input_boolean/reload` etc., or `reload_config_entry`. A new integration
   (e.g. `shell_command`) needs a restart: ask Wing. A script that calls a not-yet-loaded service aborts, so don't
   reload scripts before that restart.
8. **Verify live.** Read states/attributes, the automation trace or logbook, and `system_log/list` for new errors.
   Prefer tests without physical effects: `POST /api/states/<id>` fakes a state, `POST /api/events/<type>` fires an
   event; switch `automation.house_problems_phone_alerts` off while faking problems; undo every fake. Never POST
   `sensor.aircon_forecast_accuracy` (its log lives in its attributes).
9. **Record.** Append to `claude/PROGRESS_LOG.md`: date/time (Melbourne), thread, files with sha before -> after,
   backups, what was verified and what wasn't. Fold the new behaviour into the right HANDOFF §2-§6 section and add one
   line to §10. Update "Last updated".

## Known pitfalls

- YAML `on:` / `off:` keys are booleans: quote them.
- Trigger-template `variables` are parsed as Python literals: pass macro JSON through `| from_json`.
- `this` is undefined in a trigger template's actions/variables.
- A restart resets `last_changed` and cancels running automations: store start times in `input_datetime` helpers.
- A change from the hub or HA app has a user context; wall-remote and maker-app changes look like the device itself.
- `www/` is public without login: never put harnesses, secrets, photos or logs there.
- Never deploy by restoring a backup (a "homeassistant" restore wipes /config first).

## Tell Wing

One short message: what changed in plain words, whether it needed a restart, that a backup exists, and what was
verified live versus what will only show on the next real event.
