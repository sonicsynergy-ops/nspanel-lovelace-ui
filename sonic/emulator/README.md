# Sonic NSPanel — Emulator (Phase A: offline decoder)

A software stand-in for a physical NSPanel that speaks its MQTT wire protocol, so
we can develop and test the Sonic UI **without flashing or wiring any hardware**.

> Plan: [`docs/sonic-nspanel-emulator-plan.md`](../../docs/sonic-nspanel-emulator-plan.md)
> Protocol source of truth: [`HMI/README.md`](../../HMI/README.md) (reference only — never modified)

## What's here now (Phase A)

Only the **offline decoder** — pure Python stdlib, no MQTT, no network, no
hardware. It parses the `nspanel-lovelace-ui` protocol into JSON-serializable
dicts, in both directions.

```
sonic/emulator/
├── README.md            # this file
├── __init__.py
├── decoder.py           # pure parser (backend->panel commands + panel->backend events)
└── tests/
    └── test_decoder.py  # stdlib unittest
```

MQTT client, scenario engine, and the optional browser renderer are **later
phases** (see the plan) and are intentionally **not** present yet.

## Decoder

Two directions, plus an auto-detecting entry point:

- `decode_command(str)` — backend → panel tilde-delimited commands
  (`pageType~`, `entityUpd~`, `entityUpdateDetail~`, `color~`; unknown keywords
  return a structured `cmd == "unknown"`).
- `decode_event(str)` — panel → backend JSON payloads
  (`{"CustomRecv":"event,..."}` for `startup` / `buttonPress2` / `sleepReached`,
  plus the `{"nlui_driver_version":N}` handshake; malformed JSON returns a
  structured `type == "error"`).
- `decode(str)` — routes JSON to `decode_event`, tilde strings to
  `decode_command`.

Every result preserves the original message under `raw` and is JSON-serializable.

Where the protocol layout is variant-heavy (the per-card `entityUpd` item
grouping and the per-entity-type `entityUpdateDetail` fields), the decoder keeps
the raw tilde `fields` rather than guessing — faithful and crash-free.

## CLI

```sh
# from the repo root
python -m sonic.emulator.decoder 'pageType~screensaver'
python -m sonic.emulator.decoder '{"CustomRecv":"event,startup,39,eu"}'
```

Prints the decoded JSON.

## Tests

```sh
# from the repo root
python -m unittest discover -s sonic/emulator/tests
```

## Safety boundaries

- Pure parser: touches **no** HA, MQTT broker config, Tasmota, ESPHome,
  AppDaemon runtime config, HMI, TFT, backend Python, or live preview.
- No network and no broker connection in Phase A.
- When MQTT lands (later phase) it will use a **test-only** topic base
  (`sonic_nspanel_test`) against a **local/test** broker — never a production
  broker or a real panel's topics.
