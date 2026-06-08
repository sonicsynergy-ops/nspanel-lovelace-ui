# Sonic NSPanel — MQTT Emulator Plan

> Companion to [`docs/sonic-custom-ui-plan.md`](sonic-custom-ui-plan.md) (architecture),
> [`docs/sonic-nspanel-target-plan.md`](sonic-nspanel-target-plan.md) (V1 stack), and the
> `sonic/preview/` screen mockups.
> Status: **planning only** — nothing implemented. No HA, MQTT broker config, Tasmota, ESPHome,
> AppDaemon runtime config, HMI, TFT, or backend Python is touched by this document.
> Date: 2026-06-07

---

## TL;DR

Build a small **software stand-in for a physical NSPanel** that speaks the same MQTT protocol the
real panel does. It **subscribes** to the backend's `CustomSend` topic, **logs/decodes** every
command (`pageType~`, `entityUpd~`, `entityUpdateDetail~`), and **publishes** scripted fake panel
events (startup, taps, sleep) on the `RESULT` topic. This lets us develop and test the Sonic UI
**without flashing or wiring any hardware** — satisfying the project's "no flash until approved"
gate. A later, optional browser renderer can feed the decoded commands into `sonic/preview/` to
*visually* show what the real panel would draw.

Target topics (test-only, deliberately distinct from any real panel):
- Subscribe: `cmnd/sonic_nspanel_test/CustomSend`  (backend → emulator)
- Publish:   `tele/sonic_nspanel_test/RESULT`       (emulator → backend)
- Startup payload: `{"CustomRecv":"event,startup,39,eu"}`

---

## 1. Why an emulator

- **Closes the hardware loop in software.** The real NSPanel is a "dumb" renderer driven entirely
  by MQTT strings (see architecture doc). That means a faithful emulator only needs to talk the
  protocol — no display hardware required.
- **Zero-risk iteration.** We can exercise the AppDaemon `nspanel-lovelace-ui` backend + our Sonic
  `apps.yaml`/theme against a fake panel, observe the exact `entityUpd~` strings, and confirm
  colors/layout decisions **before** any flashing or wall install.
- **Reproducible test input.** Scripted event scenarios (tap scene, next/prev, sleep) make backend
  behavior testable and repeatable, unlike poking a physical touchscreen.

---

## 2. Protocol Recap (what the emulator must speak)

From [`HMI/README.md`](../HMI/README.md) (the protocol spec) — **reference only, do not modify**:

**Backend → Panel** (we receive on `cmnd/.../CustomSend`):
- `time~HH:MM`, `date~…` — clock/date pushes
- `timeout~20`, `dimmode~…` — setup after startup
- `pageType~screensaver` / `pageType~cardEntities` / `pageType~cardGrid` / … — navigation
- `entityUpd~…` — full page content (delimited fields: type, entity_id, icon, **color (RGB565 int)**, name, state)
- `entityUpdateDetail~…` — detail popups (e.g. light brightness/temperature/color, cover position)
- `color~…` — screensaver color theme

**Panel → Backend** (we publish on `tele/.../RESULT`, JSON-wrapped):
- Startup (repeated until navigated away): `{"CustomRecv":"event,startup,39,eu"}`
  - fields: `event, startup, <HMI version=39>, <model=eu|us>`
- Button/touch: `{"CustomRecv":"event,buttonPress2,<page>,<component>,<value>"}`
  - e.g. screensaver exit → `event,buttonPress2,screensaver,bExit,1`
- Sleep reached → `event,sleepReached,<entity_id>` (panel idle timeout)
- Optional: `{"nlui_driver_version": <int>}` (driver version handshake)

> The emulator does **not** need to render anything to be useful — logging/decoding the inbound
> commands and emitting correct outbound events is enough to drive and validate the backend.

---

## 3. Architecture

```
                         test MQTT broker (e.g. local Mosquitto)
                          ▲                         │
        publish RESULT    │                         │  CustomSend
   {"CustomRecv":"..."}   │                         ▼
   ┌──────────────────────┴─────────────────────────────────────┐
   │                    SONIC NSPANEL EMULATOR                    │
   │                                                             │
   │  MQTT client (paho)                                         │
   │    ├─ subscribe cmnd/sonic_nspanel_test/CustomSend          │
   │    └─ publish    tele/sonic_nspanel_test/RESULT             │
   │                                                             │
   │  Decoder        — split "~" / "," ; classify command type   │
   │  Logger         — pretty-print pageType / entityUpd / detail │
   │  State model    — current page, last entities, dim/sleep     │
   │  Scenario engine— scripted fake inputs (startup/tap/sleep)   │
   │  (optional) Bridge — forward decoded JSON to a browser UI    │
   └─────────────────────────────────────────────────────────────┘
                          ▲                         │
              CustomSend  │                         │  RESULT
                          │                         ▼
                 AppDaemon nspanel-lovelace-ui backend (later)
                          │
                 Home Assistant (later, with placeholders or test entities)
```

### Components

| Component | Responsibility |
|-----------|----------------|
| **MQTT client** | Connect to the test broker; sub `CustomSend`, pub `RESULT`. Reconnect-safe. |
| **Decoder** | Parse incoming payloads (`{"CustomSend":"…"}` or raw), tokenize on `~`, identify `pageType` / `entityUpd` / `entityUpdateDetail` / `time` / `dimmode` / `color`. |
| **Logger** | Human-readable, colorized console output; optional structured JSONL log to `sonic/emulator/logs/`. |
| **State model** | Track current page, entity slots, brightness/sleep, last startup ack — so scripted inputs are context-aware (e.g. "tap scene 2" knows which page is showing). |
| **Scenario engine** | Replay a sequence of fake panel events with delays (startup → wake → tap → sleep). Driven by a YAML/JSON scenario file. |
| **Bridge (optional, later)** | Push decoded commands to the browser renderer over WebSocket (or write a JSON file the page polls). |

---

## 4. Files To Create Later

All under a new `sonic/emulator/` namespace (additive; nothing else touched). **Not created yet.**

```
sonic/emulator/
├── README.md                  # how to run the emulator + safety notes
├── emulator.py                # main: MQTT client + decoder + logger + scenario runner
├── decoder.py                 # pure functions: parse CustomSend strings → structured dict
├── scenarios/
│   ├── startup.yaml           # startup → setup ack
│   ├── tap-scene.yaml         # startup → wake → tap a scene button
│   ├── navigate.yaml          # next/prev page taps
│   ├── relay.yaml             # relay/button press events
│   └── sleep.yaml             # idle → sleepReached
├── config.example.yaml        # broker host/port, topic base, client id, log options
├── requirements.txt           # paho-mqtt, pyyaml  (stdlib otherwise)
└── logs/                      # .gitignored runtime output (JSONL/console capture)
```

Optional future (Section 8):
```
sonic/emulator/
├── bridge.py                  # decoded-command → WebSocket/JSON bridge for the renderer
└── (reuses sonic/preview/ for the visual layer)
```

### Decoder output shape (illustrative target)
A decoded `entityUpd~…` becomes something like:
```json
{ "cmd": "entityUpd", "heading": "CONTROL", "nav": {...},
  "items": [ { "type": "light", "entity": "light.desk", "icon": "X",
               "color565": 17299, "name": "Desk", "state": "0" }, ... ] }
```
`color565` is preserved as the raw RGB565 int (optionally expanded to `#rrggbb` for the renderer).

---

## 5. Scripted Fake Input Events

Each scenario is an ordered list of steps the emulator publishes to `RESULT` (with optional waits).
Names map to real panel behaviors:

| Input | Emitted payload (CustomRecv) | Notes |
|-------|------------------------------|-------|
| **startup** | `event,startup,39,eu` | Repeated every few seconds until backend navigates away (mirrors real panel). |
| **wake** | `event,buttonPress2,screensaver,bExit,1` | Touch on screensaver → leave idle. |
| **tap scene** | `event,buttonPress2,<page>,<scene_component>,1` | Recall a studio mode (Tracking/Mixing/…); component id depends on current page. |
| **tap next / prev** | `event,buttonPress2,<page>,navRight,1` / `navLeft,1` | Page navigation (component ids per protocol spec). |
| **tap relay / button** | `event,buttonPress2,<page>,<button_component>,<value>` | Generic control press (e.g. light/switch toggle). |
| **sleep** | `event,sleepReached,<entity_id>` | Idle timeout reached. |

> Exact component identifiers (`bExit`, nav names, button slots) will be transcribed from
> `HMI/README.md` during implementation — the plan does not hardcode them.

Scenario file sketch (`scenarios/tap-scene.yaml`):
```yaml
name: tap-scene
steps:
  - emit: startup
  - wait: 1.0
  - emit: wake
  - wait: 0.5
  - emit: tap
    page: cardGrid
    component: scene01
    value: 1
  - wait: 1.0
  - emit: sleep
    entity: screensaver
```

---

## 6. Dependencies

- **Python 3** (matches the repo's backend ecosystem).
- **paho-mqtt** — MQTT client.
- **PyYAML** — scenario + config files.
- (stdlib: `json`, `logging`, `argparse`, `time`).
- **Test MQTT broker** — local **Mosquitto** (Docker container or a standalone install) **separate
  from any production broker**. Not configured by this repo.
- Optional renderer (later): a tiny WebSocket lib (e.g. `websockets`) **or** no dependency if we use
  a polled JSON file. Browser side reuses existing static `sonic/preview/` (no framework).

All emulator deps live in `sonic/emulator/requirements.txt` — isolated from backend requirements.

---

## 7. Safety Boundaries

| Boundary | Rule |
|----------|------|
| Topic isolation | Use **`sonic_nspanel_test`** topic base only. Never subscribe/publish to a real panel's `cmnd/*` or `tele/*` topics. |
| Broker isolation | Point at a **local/test broker**. Do **not** connect the emulator to a production MQTT broker that controls real devices. |
| No infra changes | Emulator never edits HA, MQTT broker config, Tasmota, ESPHome, AppDaemon runtime config, HMI, TFT, or backend Python. It only sends/receives MQTT messages. |
| No flashing | The emulator is the *alternative* to hardware; it never flashes anything. |
| Read-only toward backend | The emulator imitates a panel; it must not call HA services directly or mutate HA state. Any state change must flow through the normal backend, exactly as a real panel would. |
| Logs hygiene | `sonic/emulator/logs/` is git-ignored; no secrets in committed config (use `config.example.yaml`). |

---

## 8. Optional Future: Browser Renderer

Reuse `sonic/preview/` as the **visual layer** so we can *see* what the real panel would draw from
the decoded commands:

1. Emulator `bridge.py` decodes each `pageType` / `entityUpd` / `entityUpdateDetail` into JSON.
2. Bridge sends that JSON to the browser (WebSocket push, or write `state.json` the page polls).
3. A thin JS layer in a new `sonic/preview/live.html` (separate from the static mockups) maps the
   decoded fields onto the existing v3 screen components:
   - `pageType` → which screen template to show
   - `entityUpd` items → row/tile labels, icons, `color565`→`#rrggbb` accents, states
   - `entityUpdateDetail` → detail popups
4. Result: a **live, faithful preview** of backend output — the static Preview v3 becomes a real
   render target, driven by actual `CustomSend` traffic.

This stays **optional and additive**: the static `sonic/preview/index.html` is untouched; the live
renderer is a new sibling file. No backend or hardware dependency to view it.

---

## 9. Test Flow

**Phase A — standalone (no AppDaemon):**
1. Start a local Mosquitto test broker.
2. Run `emulator.py` with `scenarios/startup.yaml`; confirm it publishes the startup event and logs
   any commands echoed back.
3. Manually publish a sample `entityUpd~…` to `CustomSend` (from `HMI/README.md`'s example) and
   confirm the decoder logs it correctly. *(Validates the decoder in isolation.)*

**Phase B — with AppDaemon backend (later, opt-in):**
1. Point a **test** AppDaemon `nspanel-lovelace-ui` instance at topic base `sonic_nspanel_test`,
   loading `sonic/config/apps.sonic.example.yaml` + `sonic/theme/sonic-screensaver-theme.yaml`
   against placeholder/test entities.
2. Start emulator → it emits `startup`; backend should reply with `time~`, `dimmode~`,
   `pageType~screensaver`, then `color~…`. Emulator logs the full handshake.
3. Run `scenarios/tap-scene.yaml`; confirm the backend responds with the expected page change /
   `entityUpd`. *(Validates the full backend ↔ panel loop with the Sonic config.)*

**Phase C — visual (optional):**
1. Enable the bridge; open `sonic/preview/live.html`; replay scenarios and watch the Sonic screens
   update live from real backend traffic.

**Pass criteria:** startup handshake completes; decoder classifies every command; scripted inputs
produce the expected backend responses; (Phase C) the rendered screen matches the decoded state.

---

## 10. Next Implementation Step (lowest risk)

**Implement the pure decoder first — `sonic/emulator/decoder.py` plus a unit test — with no MQTT and
no broker.** Feed it the literal example strings from `HMI/README.md` and assert the parsed
structure (command type, entity items, `color565`). This is:
- completely offline (no broker, no network, no hardware),
- the foundation every other component depends on,
- trivially testable and revertible.

Only after the decoder is proven do we add the MQTT client + scenario engine (Phase A), then wire
to a test AppDaemon (Phase B). The browser renderer (Phase C) comes last and stays optional.
