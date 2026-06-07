# Sonic NSPanel — Custom UI (`sonic/` namespace)

Brand-customization layer for our fork of `joBr99/nspanel-lovelace-ui`.
Everything Sonic lives **here** so `git pull upstream` stays clean — no upstream file is modified
by the Phase 1 scaffold.

> Full rationale and architecture: [`docs/sonic-custom-ui-plan.md`](../docs/sonic-custom-ui-plan.md)

## What this is

A **dark blue/black/gray "studio control surface"** skin for the NSPanel, delivered through
**config + theme data only** — no device flashing, no firmware edits, no live-infra changes.

The NSPanel display is a dumb renderer: the backend streams colors (as RGB565 integers), icons,
labels, and card content over MQTT at runtime. So the entire Phase 1 look is achieved by *what we
send*, not by re-flashing the panel.

## Hard boundaries (Phase 1)

- ❌ Do **not** edit `HMI/nspanel.HMI`, `HMI/nspanel.tft`, or any generated firmware.
- ❌ Do **not** flash any device.
- ❌ Do **not** modify live Home Assistant, MQTT, Tasmota, ESPHome, or AppDaemon runtime config.
- ✅ All Sonic changes are additive, under `sonic/`, and reversible by deleting the folder.

## Contents

```
sonic/
├── README.md                          ← you are here
├── theme/
│   ├── palette.md                     ← canonical Sonic palette (RGB + RGB565 + intended use)
│   └── sonic-screensaver-theme.yaml   ← screensaver colors (dark blue/black/gray)
├── config/
│   └── apps.sonic.example.yaml        ← sample panel config wiring the theme + cards
└── backend/
    └── PATCH-NOTES.md                 ← OPTIONAL, quarantined Tier-2 palette patch (not applied)
```

## How it's intended to be used

These files are **reference/sample artifacts in the repo**. They are *not* wired into any running
backend yet — wiring that into live HA/AppDaemon is a later, Atlas-approved step.

When we do deploy (later, with approval), the flow is:

1. Copy `sonic/config/apps.sonic.example.yaml` into the AppDaemon `apps.yaml` (or merge the
   relevant panel block), adjusting MQTT topics and entity IDs for the real panel.
2. Point its `screensaver.theme` include at `sonic/theme/sonic-screensaver-theme.yaml`
   (or copy that file next to `apps.yaml` per your AppDaemon layout).
3. Restart the AppDaemon app / rebuild the add-on. **No flashing.** The panel re-renders on the
   next push.
4. To revert: restore the previous `apps.yaml`. Nothing on the device changed.

### Color-only ceiling

This scaffold re-skins **colors, background, icons, labels, and card composition**. It does **not**
change pixel layout, fonts, widget geometry, or add a Sonic logo — those live inside the compiled
`.tft` and require Nextion Editor + a device flash, which is gated behind Atlas approval (see the
plan doc, §9–§10).

## Backends

The repo ships two backends (legacy AppDaemon `apps/.../luibackend/` and the newer standalone
add-on `nspanel-lovelace-ui/rootfs/.../mqtt-manager/`). The palette in `theme/palette.md` is
**backend-agnostic** — the `[r,g,b]` values work in either. The sample config targets the
AppDaemon format because that's the documented config surface today; choosing the canonical
backend for Sonic is an open decision for Atlas.
