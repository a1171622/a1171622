---
name: hub-dashboard-edit
description: Change Wing's custom Home Assistant hub dashboard (www/hub JS tabs) with before/after screenshots at phone, tablet and desktop sizes in light and dark, shown to Wing before going live. Use for any visible hub change.
---

# Hub dashboard edit with before/after screenshots

The main UI is a custom JS hub in HA at `www/hub/` (dashboard `home-hub-new` -> `/local/hub/index.html`). Files:
`core.js` (HUB.* helpers), `index.html` (layout tokens), `tab-*.js` per tab, `heat-outlook.js` (Climate > Heat & cost).
Wing is visual and detail-minded: fewer, clearer charts; one consistent look across tabs; explanations behind `?`
(`HUB.help`), not on the page.

## Steps

1. **Read live** each file you will change (keep the sha256) and `www/hub/build.txt`. Back up each file to
   `claude/archive/<file>.bak-YYYY-MM-DD-<topic>` (see `ha-safe-edit`).
2. **Set up the harness locally.** Copy the hub files (`www/hub/`: index.html, core.js, tab-*.js, heat-outlook.js,
   build.txt, img/) and `claude/tools/hub-harness.html` into `<dir>/hub/`, and `shot_hub.py` + `srv.sh` next to it.
   Run `bash srv.sh <dir>` (serves on port 8765; read srv.sh first). The Weather tab uses `wx-harness.html` /
   `shot_wx.py` instead. Mock live data in JS:
   `HUB.hass().states[id] = {state: ..., attributes: {...}}; HUB.render(true)`. Use real values pulled from HA so the
   shots look like the house.
3. **Before shots**: `TZ=Australia/Sydney TAB=<tab> SW=1280 SH=800 python3 shot_hub.py before-1280-light.png "<js>"`,
   and the same at 1080x690 and 390 wide, light and dark. shot_hub.py needs Python Playwright (`pip install playwright`).
   In Claude cloud sessions Chromium is already at `/opt/pw-browsers/chromium`: point Playwright there rather than
   downloading another browser.
4. **Edit** the local copy. Syntax-check every JS file:
   `node -e "require('vm').createScript(require('fs').readFileSync('tab-x.js','utf8'))"`.
5. **After shots** at the same sizes and themes. Check: nothing overflows or overlaps, text >= `--fs-cap` (.95rem,
   SVG included), touch targets >= `--tap` 4.4rem, contrast in dark mode, chart labels clear of footers.
6. **Independent review** of the diff and the shots (`independent-review` skill).
7. **Show Wing** the before/after pair (save PNGs under `/mnt/project-files/plan/<topic>/` and attach them) and wait
   for OK on anything they would notice.
8. **Deploy**: patch the live files with `expected_sha256`, read patched lines back, then bump `www/hub/build.txt`
   (format `YYYY-MM-DD` + letter, e.g. `2026-11-04a`); index.html reloads itself once when build.txt moves on.
9. **Record** in `claude/PROGRESS_LOG.md` (files, sha before -> after, build) and HANDOFF §10.

## Rules learnt the hard way

- Use `/* */` comments, not `//`, mid-line. In tab-home `flow()` `N` is node positions: use `NS()`.
- Never set inline margin-top/bottom on `input.rng`. Elements with `data-keep` are never touched by `HUB.morph`.
- Tokens: `--fs-cap` .95rem, `--fs-sub` 1rem, `--fs-val-s` 1.3rem, `--fs-val` 1.7rem, `--tap` 4.4rem, `--tap-gap` .5rem,
  `.chart` min-height 8rem, compact tile `.tile.sm` with `.k/.v/.s`.
- The hub hard-codes heat loss H: `tab-climate.js` `FB.model` = 390 and `heat-outlook.js` `SC` = 390/318.4.
- `www/` is public without login: harnesses, mocks and screenshots stay out of it.
- Vendored libs only (`www/vendor/`); no CDNs.
