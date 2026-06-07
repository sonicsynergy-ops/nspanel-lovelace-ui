# Sonic NSPanel — Target Hardware & V1 Stack Plan

> Companion to [`docs/sonic-custom-ui-plan.md`](sonic-custom-ui-plan.md) (architecture) and the
> `sonic/` scaffold (config/theme/preview).
> Status: **planning only** — no code, HA, MQTT, firmware, HMI/TFT, backend, or preview changes.
> Date: 2026-06-07

---

## TL;DR

Atlas is targeting the **standard SONOFF NSPanel** (the Smart Scene Wall Switch), **portrait
orientation** — **not** the NSPanel Pro. For V1 the recommended stack is **Tasmota → MQTT → Home
Assistant → AppDaemon (`nspanel-lovelace-ui` backend)**, because that is exactly what this fork and
our `sonic/` scaffold are built around. The stock display firmware (the NSPanel Lovelace `.tft`)
is reused **as-is**; we get the Sonic look first through **colors/config** (no flash), and only
touch the HMI/TFT later, with explicit approval.

Before any of that, we need a short inventory from Atlas (model, current firmware, MQTT/AppDaemon
status, HA entities, relay wiring) so we know what each Sonic screen can actually show.

---

## 1. Hardware Target

| Attribute | Target | Notes |
|-----------|--------|-------|
| Device | **SONOFF NSPanel** (Smart Scene Wall Switch) | The standard model. ESP32 + Nextion-class display + 2 relays. |
| **Not** | NSPanel **Pro** | Pro is an Android-based device — different stack entirely (no Tasmota, no `nspanel-lovelace-ui` `.tft`). This plan does **not** apply to Pro. |
| Orientation | **Portrait** | Matches the standard NSPanel and our Preview v2/v3 (320×480 portrait). The fork ships portrait + landscape; we use portrait. |
| Display | 3.5" 320×480 Nextion-style TFT, resistive touch | Driven over serial by the ESP32; "dumb" renderer (see architecture doc). |
| Relays | 2 × mains relays | Physically switch wall load(s). Their HA exposure depends on firmware + config (see relay checklist). |
| Current firmware | **Unknown** | Could be stock eWeLink, Tasmota, ESPHome, or never-configured. Must be confirmed before any flashing decision (Risk Gate). |

### EU / 86 vs 120 form factor

- The **EU model** is the relevant one for our build (the fork's default `model: "eu"`; US model is a
  separate `.tft`). Confirm EU vs US, since the wrong `model` value / `.tft` mismatches the layout.
- **86-type vs 120-type** refers to the wall box / faceplate size:
  - **86** = square ~86×86 mm box (common EU/Asia). The standard NSPanel is an **86-type**.
  - **120** = longer ~120 mm box (some regions / US-style gangs).
  - This is a **physical mounting** concern (does it fit Atlas's wall box), **not** a UI/firmware
    concern. Flag it only so the faceplate/back-box is verified before wall install. Bench testing
    (below) sidesteps this entirely for V1.

---

## 2. Recommended V1 Stack

**Decision: adopt the Tasmota + AppDaemon path for V1.** Rationale: it is the documented,
first-class path for `nspanel-lovelace-ui`, it matches our `sonic/` scaffold
(`apps.sonic.example.yaml`, screensaver theme), and it keeps the Sonic look reachable through
**config/colors with no device flash**.

```
NSPanel (ESP32)            ── Tasmota firmware + berry driver (CustomSend/CustomRecv)
        │ MQTT
MQTT broker                ── e.g. Mosquitto (HA add-on or external)
        │
Home Assistant             ── entity states, services, scenes
        │
AppDaemon                  ── nspanel-lovelace-ui backend (apps/.../luibackend)
        │                     renders HA state → panel protocol strings
NSPanel display (.tft)     ── existing NSPanel Lovelace TFT/HMI, reused as-is
```

| Layer | V1 choice | Sonic customization route |
|-------|-----------|---------------------------|
| Panel firmware | **Tasmota** (+ nlui berry driver) | None in V1 (reuse). Flash only if/when approved. |
| Transport | **MQTT** | None — plumbing only. |
| Brain | **Home Assistant** | Entities/scenes the screens read. |
| Backend | **AppDaemon** `nspanel-lovelace-ui` | **Primary Sonic surface**: `apps.yaml` cards + theme colors + per-entity `color` overrides (config-only, no flash). |
| Display firmware | **Existing NSPanel Lovelace `.tft`/HMI** | Reuse as-is. Custom HMI/TFT is a **later** phase, gated (Risk Gate). |

> Backend note: the repo also ships a newer standalone **add-on** backend (`mqtt-manager`). For V1
> we stay on **AppDaemon** to match the scaffold; revisiting the canonical backend is an open item
> tracked in the architecture doc, not a V1 blocker.

---

## 3. What We Need From Atlas / HA Inventory

Checklist to fill in **before** building V1 config. Nothing here changes hardware — it's discovery.

### Device & firmware
- [ ] Exact NSPanel model + region (standard NSPanel, **EU** vs US; confirm it is **not** Pro).
- [ ] Form factor / wall box: **86** vs **120** (mounting fit only).
- [ ] Current firmware state — pick one:
  - [ ] Stock **eWeLink** (factory)
  - [ ] **Tasmota** already flashed (note version + whether nlui berry driver present)
  - [ ] **ESPHome**
  - [ ] **Unknown / never set up**
- [ ] Will the panel be **bench-tested** (powered on a desk, not wired to mains) before wall install? *(strongly recommended — see Next Action)*

### Infrastructure
- [ ] MQTT broker: exists? (Mosquitto add-on / external). Host, and whether HA is already connected.
- [ ] AppDaemon: installed? (HA add-on or standalone). Version.
- [ ] HA backup/export taken and stored off-device? *(Risk Gate prerequisite for any HA change.)*

### HA entities available (per domain — list entity_ids, or mark "none yet")
- [ ] **Lights** — which rooms/groups exist (Main Room, Booth, Lounge, Hallway, Bathroom, Accent…)?
- [ ] **Climate** — `climate.*` thermostat? or separate temp/humidity sensors only?
- [ ] **Doors / contacts** — `binary_sensor.*` for Main/Booth/Lounge doors; locks; motion (PIR).
- [ ] **Power** — `sensor.*` for total draw / per-device watts; UPS; rack temperature.
- [ ] **Scenes / modes** — `scene.*` or `input_select.*` for Tracking/Mixing/Vocal/Podcast/Cleanup/Away.
- [ ] **Weather/SPL** — any noise-floor/SPL sensor (likely a placeholder for V1).

### Relays (critical for a wall switch)
- [ ] What does **Relay 1** physically control? (e.g. main room lights)
- [ ] What does **Relay 2** physically control?
- [ ] Are the relays in **decoupled** mode (button → MQTT, not directly to load) or hard-wired to load?
- [ ] Is there a load on each relay, or should one/both be unused (blanked)?

---

## 4. Screen → Entity Map

For each Sonic screen (from Preview v3). "Required" = screen is meaningful only with these;
"Optional" = enriches it; "Placeholder" = safe to fake/static in V1; "Blocked until inventory" =
cannot be real until the entities above are confirmed.

> Convention: until an entity exists, the screen shows a **placeholder/static value** (as in the
> preview) rather than a broken/unknown state.

### Screensaver / Idle
- **Required:** time/date (panel/HA native — always available).
- **Optional:** climate temp, humidity, power draw, noise/SPL.
- **Placeholder:** noise floor `38 dB`, status word `STUDIO READY`.
- **Blocked until inventory:** any live tele value (falls back to placeholder otherwise).

### Home / Main Menu
- **Required:** none (pure navigation).
- **Optional:** per-zone status summaries (lights "4/6 on", climate "21.0°", security "Armed", power "0.42 kW").
- **Placeholder:** all summary sub-lines.
- **Blocked until inventory:** accurate summaries (need the underlying domain entities).

### Scenes
- **Required:** `scene.*` or `input_select.*` for the six studio modes.
- **Optional:** an "active scene" indicator (`input_select` current option).
- **Placeholder:** the 6 preset tiles + which one is active.
- **Blocked until inventory:** actually recalling a scene (needs the scene/automation entities).

### Lights
- **Required:** `light.*` (or relay-backed `switch.*`) for the groups present.
- **Optional:** brightness attribute → dim % meter; color.
- **Placeholder:** dim levels for groups that don't exist yet.
- **Blocked until inventory:** real on/off + dim (need each `light.*`). Relay-controlled groups depend on relay mapping.

### Climate
- **Required:** `climate.*` (mode + current/target temp) **or** temp sensor + a mode `input_select`.
- **Optional:** humidity, fan mode, airflow, coil temp, filter status.
- **Placeholder:** target, fan speed, airflow, coil, filter.
- **Blocked until inventory:** mode/fan control (needs a real `climate.*` or HVAC integration).

### Session
- **Required:** none hard — it's a studio telemetry dashboard.
- **Optional:** session/room mode `input_select`, SPL/noise sensor, power, climate, door.
- **Placeholder:** SPL meter (`38 dB`), session mode `TRACKING`, room mode `LIVE`.
- **Blocked until inventory:** real SPL (needs a sound-level sensor — likely a V2 add).

### Security / Doors
- **Required:** door/contact `binary_sensor.*`; ideally `alarm_control_panel.*` for armed state.
- **Optional:** locks, motion (PIR), per-zone labels.
- **Placeholder:** armed banner, secure/open/locked/clear states.
- **Blocked until inventory:** real status + amber/red warnings (need the contact/alarm entities). **Color semantics (green/amber/red) must reflect real states — no faking once live.**

### Power / Rack
- **Required:** at least one power `sensor.*` (total draw).
- **Optional:** per-device watts, UPS state/%, rack temperature, network/interface online status.
- **Placeholder:** total `412 W`, per-subsystem watts, UPS 100%, rack temp.
- **Blocked until inventory:** real metering (needs smart plugs / energy sensors / UPS integration).

### Settings / System
- **Required:** panel brightness + sleep timeout (Tasmota/backend config — available once on the stack).
- **Optional:** Wi-Fi RSSI, MQTT connected, backend status/version.
- **Placeholder:** Wi-Fi `-52 dBm`, MQTT `Connected`, backend `AppDaemon`.
- **Blocked until inventory:** Reboot/Update actions stay **visual-only/disabled** until explicitly approved (Risk Gate).

---

## 5. Risk Gates

Hard stops — do not cross without the stated condition.

| Gate | Rule | Condition to proceed |
|------|------|----------------------|
| ⚡ Mains wiring | No mains wiring/wall install without proper electrical care (power off at breaker, competent person). | Atlas confirms safe install or uses bench power. |
| 🔧 Flashing | **No flashing** (Tasmota, ESPHome, or `.tft`) until Atlas explicitly approves. | Written go-ahead + current firmware backed up. |
| 🗄️ Live HA config | **No live HA config mutation** until a backup/export exists and is stored off-device. | Verified HA backup taken. |
| 🎨 Custom HMI/TFT | **No custom HMI/TFT firmware** until the color/config route has been built and tested on the existing `.tft`. | Config-only Sonic theme validated on hardware first. |

---

## 6. Next Recommended Action (lowest risk)

**Run the Section 3 inventory with Atlas — purely read-only discovery, zero device/HA changes.**
Specifically, the single highest-value first step:

> **Confirm the panel's current firmware state and whether it can be bench-tested.**

Why this first:
- It decides the entire V1 path. If it's **already Tasmota + connected to MQTT/HA**, we can reach
  the Sonic look through **config/colors with no flash at all** — the safest possible start.
- If it's **stock eWeLink** or **unknown**, the next gate is a flashing decision (which stays
  closed until Atlas approves and a firmware backup exists).
- **Bench testing** (panel on a desk, USB/bench power, not wired to mains) lets us validate the
  Tasmota → MQTT → HA → AppDaemon → Sonic-theme chain with **no mains-wiring and no wall-install
  risk**, satisfying the ⚡ and 🔧 gates while we iterate.

After inventory + bench decision, the first build step is config-only: wire
`sonic/config/apps.sonic.example.yaml` + `sonic/theme/sonic-screensaver-theme.yaml` into a **test**
AppDaemon against real (or placeholder) entities — no flashing, fully revertible.
