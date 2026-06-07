# Sonic backend palette patch — NOTES ONLY (NOT APPLIED)

> Status: **not applied.** No Python file in this repo has been modified. This document describes
> an *optional* Tier-2 change for later, so the diff is small, reviewed, and easy to revert.

## Why this exists

Phase 1 re-skins the panel through **config only** (`sonic/config/` + `sonic/theme/`). That covers
the background, screensaver, and any entity with an explicit `color:` override.

But entities **without** a per-entity override fall back to the backend's built-in defaults — which
are the generic HA palette:

- on / active  → `[253, 216, 53]` (HA yellow)
- off / idle   → `[68, 115, 158]` (HA blue-gray)

Defined in:
- add-on backend: `nspanel-lovelace-ui/rootfs/usr/bin/mqtt-manager/ha_colors.py` → `get_entity_color()`
- legacy backend: `apps/nspanel-lovelace-ui/luibackend/` (color logic in `pages.py` / `icons.py`)

To make *every* entity Sonic without annotating each one in YAML, we'd swap those two defaults to
the Sonic tokens. **This is optional and deferred** — config-level overrides already work today.

## Proposed change (when approved)

In `ha_colors.py`, replace only the two default constants:

```python
# BEFORE (upstream)
default_color_on  = rgb_dec565([253, 216, 53])   # HA yellow
default_color_off = rgb_dec565([68, 115, 158])    # HA blue-gray

# AFTER (Sonic)  — palette source: sonic/theme/palette.md
default_color_on  = rgb_dec565([56, 139, 222])   # accent-blue   -> 15451
default_color_off = rgb_dec565([110, 120, 132])  # inactive-gray -> 27600
```

Leave the per-domain logic (climate/alarm/weather) intact for now; revisit per `palette.md` status
colors in a later pass.

## Constraints when applying

- This edits an **upstream-tracked file**, so it slightly complicates `git pull upstream`. Keep the
  diff to the two lines above and mark them, e.g.:
  ```python
  # >>> SONIC PALETTE (see sonic/backend/PATCH-NOTES.md) — revert these 2 lines to restore upstream
  ...
  # <<< SONIC PALETTE
  ```
- Decide **which backend** is canonical before applying (don't patch both). See plan §9.
- Requires a backend restart / add-on rebuild to take effect. **No device flash.**
- Reversible: delete the two marked lines / restore upstream constants.

## Not in scope here

Layout, fonts, widget geometry, logos, new page types → those need Nextion Editor + a flash and
are gated behind Atlas approval (plan §9–§10). This patch only changes color *data*.
