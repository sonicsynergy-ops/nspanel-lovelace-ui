# Sonic NSPanel Palette

Canonical color source of truth for the Sonic NSPanel UI. Every color is listed as a name, an
`[R,G,B]` triplet (0–255, the format YAML config expects), and the **RGB565 integer** the panel
actually receives over MQTT.

> The backend converts `[R,G,B]` → RGB565 via `rgb_dec565()`
> (`((r>>3)<<11) | ((g>>2)<<5) | (b>>3)`). The 565 values below are precomputed so you can verify
> what the panel renders and spot quantization (dark blues collapse toward black — see notes).

## Core

| Token | Use | `[R,G,B]` | RGB565 |
|-------|-----|-----------|--------|
| `sonic-bg` | Default background (near-black blue) | `[6,10,16]` | `66` |
| `sonic-bg-true-black` | Alt background (true black, max contrast) | `[0,0,0]` | `0` |
| `sonic-surface` | Panel/card surface gray | `[20,26,34]` | `4292` |
| `accent-blue` | **Active / on** state — primary accent | `[56,139,222]` | `15451` |
| `accent-cyan` | Highlight / focus / live data | `[64,196,255]` | `17983` |
| `inactive-gray` | **Off / idle** state | `[110,120,132]` | `27600` |
| `text-primary` | Primary text (off-white) | `[224,228,234]` | `59197` |
| `text-secondary` | Secondary/label text | `[150,160,172]` | `38165` |

## Status (use sparingly — alerts should earn their color)

| Token | Use | `[R,G,B]` | RGB565 |
|-------|-----|-----------|--------|
| `warn-amber` | Warning | `[245,180,60]` | `62887` |
| `critical-red` | Critical / triggered | `[223,76,30]` | `55907` |
| `ok-green` | OK / disarmed / safe | `[46,160,110]` | `11533` |

## Design intent

- **Studio control surface, not smart-home toy.** Black/near-black canvas, blue as the single
  identity accent, gray for everything dormant. No HA yellow.
- **Active = `accent-blue`, idle = `inactive-gray`.** This replaces upstream's default
  on=`[253,216,53]` (yellow) / off=`[68,115,158]` (blue-gray).
- **Restraint:** status colors (amber/red/green) appear only for genuine state changes, so they
  read as signal, not decoration.

## Quantization notes

- RGB565 has 5 bits red, 6 green, 5 blue. Very dark blues lose precision: `[6,10,16]` packs to
  `66`, which is nearly black with a faint blue cast — intended. If it reads as flat black on the
  real panel and we want more blue, nudge toward `[8,14,24]`.
- Test every chosen color on the actual hardware before locking it; the panel's gamma differs from
  a monitor. (Hardware testing is gated behind Atlas approval.)
