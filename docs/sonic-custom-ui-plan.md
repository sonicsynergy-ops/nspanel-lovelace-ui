# Sonic NSPanel — Custom UI Implementation Plan

> Fork: `sonicsynergy-ops/nspanel-lovelace-ui` (branch `sonic/custom-ui`)
> Upstream: `joBr99/nspanel-lovelace-ui` (push DISABLED — we only pull from it)
> Goal: a dark, precise, blue/black/gray "studio control surface" UI for a Sonoff NSPanel that still works with Home Assistant.
> Date: 2026-06-07

---

## Phase 1 Scaffold Created (2026-06-07)

Phase 1 is scaffolded — **additive, config-only, no firmware/runtime touched, not committed.**
All files live under `sonic/` (plus this doc) so `git pull upstream` stays clean.

| File | Purpose |
|------|---------|
| [sonic/README.md](../sonic/README.md) | Explains the `sonic/` namespace, hard boundaries, and how the scaffold is intended to be used (copy config → restart backend → no flash). |
| [sonic/theme/palette.md](../sonic/theme/palette.md) | Canonical Sonic palette — every token as `[R,G,B]` + precomputed RGB565 + intended use. Single source of truth, backend-agnostic. |
| [sonic/theme/sonic-screensaver-theme.yaml](../sonic/theme/sonic-screensaver-theme.yaml) | Screensaver colors (dark blue/black/gray) using upstream's exact theme keys; `autoWeather` block included but commented. |
| [sonic/config/apps.sonic.example.yaml](../sonic/config/apps.sonic.example.yaml) | Sample AppDaemon panel config wiring `defaultBackgroundColor`, the screensaver theme include, and utility-first cards with accent-blue/idle-gray per-entity overrides. Topics/entities are placeholders. |
| [sonic/backend/PATCH-NOTES.md](../sonic/backend/PATCH-NOTES.md) | **Optional, NOT applied.** Documents the 2-line Tier-2 swap of the backend default on/off palette (HA yellow/blue → Sonic blue/gray), with revert markers and constraints. |

**No existing/upstream files were modified.** The only change to a pre-existing file is this
section appended to `docs/sonic-custom-ui-plan.md`.

What this scaffold delivers when deployed (later, with approval): black canvas, blue identity
accent, gray idle state, re-themed screensaver, clutter-reduced card layout — all without flashing.
What it does **not** touch: pixel layout, fonts, widget geometry, logos, new page types (Tier 3 —
needs Nextion Editor + flash + Atlas approval).

---

## TL;DR

The NSPanel firmware is a **dumb display**: the Nextion screen (`.tft`) only renders what the
backend tells it to over MQTT. **Navigation, content, colors, icons, and labels are all decided
by the backend at runtime** and pushed as text commands. This means **~80% of the "Sonic feel"
(palette, dark background, accent logic, icons, labels, card composition) can be achieved with
ZERO device flashing** — purely through YAML config and small Python edits in our fork.

The remaining ~20% (pixel layout, widget geometry, custom fonts, logos, removing HA-style card
chrome, new page types) lives inside the compiled `.tft` and **requires Nextion Editor + a device
flash**, which is explicitly out of scope until Atlas approves hardware changes.

**Recommendation:** do **color/theme/config theming first** (no flash, fully reversible, keeps
upstream pullable). Do **not** fork the `.HMI` yet — only branch a parallel `HMI/sonic/` variant
once we hit the ceiling of color-only theming AND Atlas signs off on flashing.

---

## 1. Repo Architecture Summary

The repo is the upstream multi-backend monorepo. Four layers matter:

```
┌──────────────────────────────────────────────────────────────────────┐
│  HOME ASSISTANT  (entity states, weather, services)                     │
└───────────────┬────────────────────────────────────────────────────────┘
                │ HA API / events
┌───────────────▼────────────────────────────────────────────────────────┐
│  BACKEND  (Python — translates HA state → panel protocol strings)        │
│                                                                          │
│   A) apps/nspanel-lovelace-ui/luibackend/   ← legacy AppDaemon app       │
│   B) nspanel-lovelace-ui/rootfs/.../mqtt-manager/ ← newer HA add-on      │
│      (standalone rewrite, v4.7.91 — the direction upstream is heading)   │
└───────────────┬────────────────────────────────────────────────────────┘
                │ MQTT:  cmnd/<topic>/CustomSend   (HA → panel)
                │        tele/<topic>/RESULT       (panel → HA)
┌───────────────▼────────────────────────────────────────────────────────┐
│  TASMOTA + Berry driver  (on the NSPanel ESP32)                          │
│  Receives CustomSend, forwards raw serial to the Nextion chip            │
└───────────────┬────────────────────────────────────────────────────────┘
                │ serial
┌───────────────▼────────────────────────────────────────────────────────┐
│  NEXTION DISPLAY  (HMI/nspanel.tft — compiled firmware)                  │
│  "Dumb" renderer. Holds page templates, fonts, widget slots.            │
│  Source: HMI/nspanel.HMI  (edited in Nextion Editor → compiles to .tft) │
└──────────────────────────────────────────────────────────────────────────┘
```

### Key directories

| Path | Role | Touch for Sonic UI? |
|------|------|----------------------|
| [HMI/nspanel.HMI](../HMI/nspanel.HMI) | Nextion Editor **source** (15.9 MB) — page layouts, fonts, widget geometry | Only Tier 3 (needs flash + Atlas) |
| [HMI/nspanel.tft](../HMI/nspanel.tft) | **Compiled** display firmware (8.4 MB) — what actually runs on the chip | Generated output, never hand-edit |
| [HMI/US/](../HMI/US/) | US model `.HMI`/`.tft` (portrait + landscape) | Same as above, per-model |
| [HMI/code_gen/](../HMI/code_gen/) | Python that **generates Nextion instruction blocks** for pages/icons/fonts | Reference only for now |
| [HMI/fonts/](../HMI/fonts/) | `.zi` font assets (NotoSans 24/32) baked into the `.tft` | Tier 3 |
| [HMI/README.md](../HMI/README.md) | **The protocol spec** (49 KB) — every `CustomSend`/`CustomRecv` command | Read this — it's the contract |
| [apps/nspanel-lovelace-ui/luibackend/](../apps/nspanel-lovelace-ui/luibackend/) | Legacy AppDaemon backend | Tier 2 edits |
| [nspanel-lovelace-ui/rootfs/usr/bin/mqtt-manager/](../nspanel-lovelace-ui/rootfs/usr/bin/mqtt-manager/) | Newer standalone add-on backend | Tier 2 edits (preferred long-term) |
| [appdaemon/](../appdaemon/) | Example `apps.yaml` / theme configs | Tier 1 (our config lives here) |

### How the display protocol works (the important part)

The HMI doc opens with the key fact:

> *"The HMI Project of this project is only used to display stuff, navigation is mostly up to the
> backend. This allows to be way more flexible."*

- Panel boots → emits `event,startup,<version>,<model>` on `tele/<topic>/RESULT`.
- Backend replies with setup (`timeout~`, `dimmode~`, `pageType~screensaver`) then streams content.
- Content is one big delimited string, e.g. an entities page:
  ```
  entityUpd~<heading>~<nav>~light~light.desk~X~17299~Desk Lamp~0~...~switch~switch.bath~D~63142~Bath~1
  ```
  Each field is `type~entity_id~icon~**color**~name~state`. **The `color` is an RGB565 integer
  computed by the backend** — `17299`, `63142`, `65535`, etc.
- Touches come back as `event,buttonPress2,<page>,<component>,<value>`; the backend decides what
  happens next and pushes the next screen.

**Implication:** colors, icons, labels, which card shows, and what's on it are all *backend
decisions sent as data*. They are not baked into the firmware.

---

## 2. How the Backend Sends HA Data to the Panel

Walking the legacy `luibackend` path (the add-on `mqtt-manager` mirrors this structure):

| File | Responsibility |
|------|----------------|
| [mqtt.py](../apps/nspanel-lovelace-ui/luibackend/mqtt.py) | Subscribes to `RESULT`, parses `CustomRecv`, routes events (startup/sleep/button) |
| [controller.py](../apps/nspanel-lovelace-ui/luibackend/controller.py) | Orchestrates page lifecycle; sets global `defaultBackgroundColor`, brightness, timeout |
| [pages.py](../apps/nspanel-lovelace-ui/luibackend/pages.py) | **Renders** each card type into `entityUpd~...` protocol strings (1100 lines) |
| [theme.py](../apps/nspanel-lovelace-ui/luibackend/theme.py) | Screensaver color mapping → `color~...` command |
| [icons.py](../apps/nspanel-lovelace-ui/luibackend/icons.py) / [icon_mapping.py](../apps/nspanel-lovelace-ui/luibackend/icon_mapping.py) | mdi-name → Nextion codepoint |
| [config.py](../apps/nspanel-lovelace-ui/luibackend/config.py) | Parses `apps.yaml`; holds all defaults incl. `defaultBackgroundColor: "ha-dark"` |
| [helper.py](../apps/nspanel-lovelace-ui/luibackend/helper.py) | `rgb_dec565()` (RGB→565), `rgb_brightness()`, color math |

The color pipeline (the lever we pull for Sonic):
- `helper.rgb_dec565([r,g,b])` packs an 8-8-8 RGB into a 5-6-5 integer the panel understands.
- In the add-on, [ha_colors.py](../nspanel-lovelace-ui/rootfs/usr/bin/mqtt-manager/ha_colors.py)
  centralizes per-entity color: default **on = `[253,216,53]` (HA yellow)**, **off = `[68,115,158]`
  (HA blue)**, plus per-domain logic for climate/alarm/weather. This is where the generic
  smart-home palette comes from — and exactly what we re-skin.
- Per-entity YAML key `color` (`config.py:19 self.colorOverride`) lets a single entity override its
  color with no code change.
- Global background: `controller.py:80` — `"ha-dark"` → `6371`, `"black"` → `0`, or a literal
  `[r,g,b]` list → `rgb_dec565`.

---

## 3. Customization Points: Safe (YAML) vs Risky (firmware)

### Tier 1 — Pure YAML config (NO flash, NO code, fully reversible)
- **Global background**: `defaultBackgroundColor: black` or `[6,10,16]` (near-black blue).
- **Screensaver theme**: every element color (time/date/forecast/bar) via
  [screensaver-theme.yaml](../appdaemon/screensaver-theme-include/screensaver-theme.yaml) as `[r,g,b]`.
- **Per-entity color override**: `color: [50,130,200]` on any card entity.
- **Card composition**: which cards exist, order, which entities, titles, icons (`mdi:*`), labels.
- **Per-entity font** slot selection (`font:` — chooses among fonts already baked in the `.tft`).
- Brightness, sleep timeout, locale, time/date format.

### Tier 2 — Backend Python edits in our fork (NO flash; restart AppDaemon / rebuild add-on)
- Change the **default palette** (replace HA yellow/blue in `ha_colors.py` / `theme.py`) so *every*
  panel gets the Sonic look without per-entity YAML.
- Adjust color **logic** (active/inactive, per-domain accents, brightness scaling).
- Tweak how existing card types compose their `entityUpd` strings (labels, formatting, units).
- All constrained to **what the existing HMI page types already support** — we're changing data,
  not the renderer.

### Tier 3 — HMI / `.tft` firmware edits (REQUIRES Nextion Editor + DEVICE FLASH + Atlas approval)
- Pixel layout, widget geometry/positioning, card chrome (the rounded HA-card look).
- Custom fonts (e.g. a monospace/technical typeface), font sizes beyond baked set.
- Custom backgrounds, Sonic logo/wordmark, splash screen.
- Brand-new page types or control-surface widgets that don't exist upstream.
- Changing display resolution behavior, gauges, sliders geometry.

---

## 4. Build / Export Path for the Panel UI

**Config + backend changes (Tiers 1–2):**
1. Edit YAML / Python in the repo.
2. Deploy: restart the AppDaemon app **or** rebuild/restart the HA add-on.
3. Panel re-renders on next push — **no flashing, instantly reversible by reverting the file.**

**Firmware changes (Tier 3 — gated):**
1. Open `HMI/nspanel.HMI` (or `HMI/US/...`) in **Nextion Editor** (Windows GUI; runs in a VM/Wine).
2. (Optional) regenerate page instruction blocks with the `HMI/code_gen/` Python helpers.
3. Compile in Nextion Editor → produces a new `.tft`.
4. Upload `.tft` to the panel via Tasmota (web UI "Upload TFT" / `FlashNextion` URL or MQTT).
5. **This is the flash step — explicitly off-limits until Atlas approves.**

> The `.HMI`/`.tft` files are large binaries. Treat them as build artifacts: never hand-edit,
> never delete upstream copies, and keep any Sonic variant in a *separate* path so `git pull
> upstream` stays clean.

---

## 5. Recommended MVP

**"Sonic Skin v0" — a dark blue/black/gray re-palette delivered entirely through config + a fork
backend palette, no device flashing.**

Visual targets (Sonic Synergy studio control surface):
- Background: true black `[0,0,0]` or near-black blue `[6,10,16]`.
- Primary accent (active/on): a precise blue, e.g. `[56,139,222]` / cyan-blue `[64,196,255]`.
- Inactive/off: muted gray `[110,120,132]` (not HA's blue-gray).
- Text: high-contrast off-white `[224,228,234]`; secondary `[150,160,172]`.
- Alerts only where they earn it: amber `[245,180,60]` warn, red `[223,76,30]` critical.
- Remove "toy" warmth — no HA yellow as the default on-state.

Scope of MVP:
1. A reusable **Sonic theme palette** (one source of truth) referenced by config.
2. Screensaver re-themed (black bg, blue/gray accents).
3. Default entity on/off colors re-mapped to Sonic accent/gray.
4. A **sample `apps.yaml`** showing a clean, utility-first card layout (no clutter).

Explicitly **out** of MVP: any `.tft` edit, any flash, any HA/MQTT/Tasmota/ESPHome/AppDaemon
*runtime* reconfiguration on the actual hardware.

---

## 6. Proposed File Changes — Phase 1

All additive, reversible, and isolated under a `sonic/` namespace so upstream stays pristine.

1. **New:** `sonic/theme/sonic-screensaver-theme.yaml`
   Sonic palette for the screensaver (black bg, blue/gray accents), modeled on
   `appdaemon/screensaver-theme-include/screensaver-theme.yaml` but with real values uncommented.

2. **New:** `sonic/config/apps.sonic.example.yaml`
   A clean example panel config: `defaultBackgroundColor: [6,10,16]`, `screensaver.theme: !include
   sonic-screensaver-theme.yaml`, and a minimal utility-first set of cards with per-entity
   `color` overrides demonstrating the accent/gray system.

3. **New:** `sonic/theme/palette.md`
   The canonical Sonic palette: every color as name + `[r,g,b]` + RGB565 int + intended use.
   Single source of truth for both YAML and any future backend edits.

4. **(Tier 2, optional in Phase 1) New:** `sonic/backend/sonic_palette.py` + a *small, documented*
   patch point in the fork's `ha_colors.py` / `theme.py` to swap the default on/off palette.
   Keep this as a clearly-marked, easily-revertible diff so upstream merges stay manageable.

5. **Docs:** this file (`docs/sonic-custom-ui-plan.md`) + a short `sonic/README.md` explaining the
   namespace and the no-flash boundary.

> No existing upstream file is modified in the config-only portion of Phase 1. The only upstream
> Python touch (item 4) is optional and quarantined behind a documented patch marker.

---

## 7. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Accidental device flash | **High** (hardware boundary) | Phase 1 is config/backend only; flashing requires explicit Atlas sign-off |
| Editing the `.tft`/`.HMI` and bricking display geometry | High | Don't touch firmware in Phase 1; if ever needed, work on a copy under `HMI/sonic/` |
| Diverging from upstream so `git pull` conflicts | Medium | Keep Sonic work in a `sonic/` namespace; quarantine backend patches behind markers |
| Two backends (legacy AppDaemon vs add-on) — theming one, deploying the other | Medium | Decide canonical backend with Atlas (add-on is the future direction); palette.md is backend-agnostic |
| RGB565 quantization (dark blues collapse toward black) | Low | Verify chosen colors survive the 5-6-5 pack via `rgb_dec565`; tune in `palette.md` |
| Changing HA/MQTT/Tasmota runtime config prematurely | Medium | Out of scope per boundaries; only example YAML in-repo, never applied to live HA yet |

---

## 8. Required Tools

**Phase 1 (no hardware):**
- Git (fork already configured: `origin` = sonicsynergy-ops, `upstream` = joBr99 push-disabled).
- A text editor + YAML knowledge. Python 3 for any Tier-2 backend edits.
- (Optional) a local AppDaemon or the HA add-on in a test environment to preview — not required to author config.

**Phase 2+ (firmware — gated, Atlas approval first):**
- **Nextion Editor** (Windows-only GUI; VM or Wine) to open `.HMI` and compile `.tft`.
- A Tasmota-flashed NSPanel + MQTT broker to deploy/test `.tft` (the actual hardware step).
- Backup of the current working `.tft` before any flash.

---

## 9. What Needs Atlas Approval Before Touching Hardware

Per the project boundaries, **stop and get Atlas sign-off before any of these**:
- Flashing **any** `.tft` to a physical NSPanel.
- Opening/recompiling the `.HMI` for production use (creating a Sonic firmware variant).
- Changing **Home Assistant, MQTT, Tasmota, ESPHome, or AppDaemon runtime config** on live infra.
- Choosing the **canonical backend** (legacy AppDaemon vs standalone add-on) for Sonic going forward.
- Any change that would make `git pull upstream` non-trivial (e.g. forking the `.HMI`).

Phase 1 (config + quarantined backend palette) needs **no** hardware and **no** runtime changes,
so it can proceed now within the stated boundaries.

---

## 10. Decision: Fork the HMI, or start a parallel Sonic HMI variant?

**Neither, yet.** Recommended sequence:

1. **Now:** color/theme/config theming only (Tiers 1–2). Leaves `.HMI`/`.tft` untouched, keeps
   upstream pullable, gets most of the Sonic look with zero hardware risk.
2. **When color-only hits its ceiling** (we need different geometry, fonts, logo, or new widgets)
   **and Atlas approves flashing:** create a **parallel** `HMI/sonic/` variant copied from upstream
   — do **not** edit `HMI/nspanel.HMI` in place. A parallel variant preserves upstream as a clean
   merge base and lets us diff/restore.

Forking-in-place the upstream `.HMI` is the worst option: it's a huge binary, it makes upstream
merges painful, and it couples our brand work to their firmware release cadence.
