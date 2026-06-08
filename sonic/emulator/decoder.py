"""Offline decoder for the Sonic NSPanel MQTT emulator (Phase A).

Pure Python stdlib. No MQTT, no network, no hardware. This module only parses
strings: it translates the ``nspanel-lovelace-ui`` wire protocol (documented in
``HMI/README.md``) into JSON-serializable dicts, in both directions:

  backend -> panel : tilde-delimited command strings
                     e.g. ``pageType~screensaver``, ``entityUpd~...``, ``color~...``
  panel -> backend : JSON payloads wrapping a CustomRecv string
                     e.g. ``{"CustomRecv": "event,startup,39,eu"}``

Design intent for Phase A:
  * Be faithful where the layout is stable (pageType, color, startup,
    buttonPress2, sleepReached).
  * Be lossless and crash-free where the layout is variant-heavy
    (entityUpd / entityUpdateDetail item structure is card- and entity-type
    dependent) by preserving the raw tilde fields rather than guessing.
  * Always preserve the original message under ``raw``.
  * Never raise on unexpected/malformed input -- return a structured result.

See ``docs/sonic-nspanel-emulator-plan.md`` for the wider plan. This module does
not touch HA, MQTT broker config, Tasmota, ESPHome, AppDaemon, HMI, TFT, or the
backend -- it is a pure parser.
"""
from __future__ import annotations

import json
import sys

DELIM = "~"

DIRECTION_BACKEND_TO_PANEL = "backend_to_panel"
DIRECTION_PANEL_TO_BACKEND = "panel_to_backend"

# Backend->panel command keywords this decoder understands explicitly.
KNOWN_COMMANDS = ("pageType", "entityUpd", "entityUpdateDetail", "color")


def _maybe_int(value):
    """Return ``int(value)`` when value is a clean integer string, else value unchanged.

    Used for fields that are *usually* numeric (RGB565 colors, tap counts, HMI
    version) but may legitimately be non-numeric (e.g. a colorWheel ``x|y|wh``
    payload). Keeps output JSON-serializable either way.
    """
    if isinstance(value, bool):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def decode_command(message):
    """Decode a backend->panel command string (tilde-delimited).

    Returns a JSON-serializable dict. Unknown command keywords yield a
    structured ``cmd == "unknown"`` result rather than raising.
    """
    raw = message
    if not isinstance(message, str):
        return {
            "direction": DIRECTION_BACKEND_TO_PANEL,
            "cmd": "error",
            "error": "not_a_string",
            "raw": message,
        }

    parts = message.split(DELIM)
    keyword = parts[0] if parts else ""
    args = parts[1:]

    result = {
        "direction": DIRECTION_BACKEND_TO_PANEL,
        "cmd": keyword,
        "raw": raw,
    }

    if keyword == "pageType":
        result["page"] = args[0] if args else None

    elif keyword == "entityUpd":
        # Structure: entityUpd~title~[navigation]~[entity_information]
        # Entity-information grouping depends on the card type, so we expose the
        # heading plus the raw tilde fields rather than guessing the grouping.
        result["heading"] = args[0] if args else None
        result["fields"] = args

    elif keyword == "entityUpdateDetail":
        # Detail-popup layout is entity-type dependent (light / cover / thermo /
        # selection / timer ...). Preserve entity name + raw fields.
        result["entity"] = args[0] if args else None
        result["fields"] = args

    elif keyword == "color":
        # Screensaver theme: a list of RGB565 integers.
        result["values"] = [_maybe_int(a) for a in args]

    else:
        result["cmd"] = "unknown"
        result["command"] = keyword
        result["fields"] = args

    return result


def decode_event(message):
    """Decode a panel->backend JSON payload string.

    Expects a JSON object string, typically ``{"CustomRecv": "event,..."}`` or a
    ``{"nlui_driver_version": N}`` handshake. Malformed JSON or unexpected shapes
    return a structured ``type == "error"`` result rather than raising.
    """
    raw = message
    result = {"direction": DIRECTION_PANEL_TO_BACKEND, "raw": raw}

    try:
        data = json.loads(message)
    except (ValueError, TypeError):
        result["type"] = "error"
        result["error"] = "invalid_json"
        return result

    if not isinstance(data, dict):
        result["type"] = "error"
        result["error"] = "unexpected_payload"
        return result

    if "nlui_driver_version" in data:
        result["type"] = "driver_version"
        result["version"] = _maybe_int(data["nlui_driver_version"])
        return result

    if "CustomRecv" not in data:
        result["type"] = "error"
        result["error"] = "missing_customrecv"
        return result

    recv = data["CustomRecv"]
    result["recv"] = recv

    if not isinstance(recv, str):
        result["type"] = "error"
        result["error"] = "customrecv_not_a_string"
        return result

    tokens = recv.split(",")
    kind = tokens[0] if tokens else ""

    if kind != "event":
        result["type"] = "unknown"
        result["tokens"] = tokens
        return result

    sub = tokens[1] if len(tokens) > 1 else None
    rest = tokens[2:]

    if sub == "startup":
        # event,startup,<hmi_version>,<model>
        result["type"] = "startup"
        result["hmi_version"] = _maybe_int(rest[0]) if len(rest) > 0 else None
        result["model"] = rest[1] if len(rest) > 1 else None

    elif sub == "buttonPress2":
        # event,buttonPress2,<page>,<component>[,<value>]
        # value varies: tap count, slider int, "x|y|wh" colorWheel, action
        # string, or absent. Parsed as the next token; int only when clean.
        result["type"] = "buttonPress2"
        result["page"] = rest[0] if len(rest) > 0 else None
        result["component"] = rest[1] if len(rest) > 1 else None
        result["value"] = _maybe_int(rest[2]) if len(rest) > 2 else None

    elif sub == "sleepReached":
        # event,sleepReached,<entity_id>
        result["type"] = "sleepReached"
        result["entity"] = rest[0] if len(rest) > 0 else None

    else:
        result["type"] = "event"
        result["event"] = sub
        result["args"] = rest

    return result


def decode(message):
    """Auto-detect direction and decode.

    JSON object payloads (panel->backend events) are routed to
    :func:`decode_event`; everything else is treated as a backend->panel command
    and routed to :func:`decode_command`.
    """
    if not isinstance(message, str):
        return {"direction": None, "type": "error", "error": "not_a_string", "raw": message}

    stripped = message.strip()
    if stripped.startswith("{"):
        return decode_event(message)
    return decode_command(message)


def _main(argv):
    if not argv:
        print(json.dumps({"type": "error", "error": "no_input"}, indent=2))
        return 1
    print(json.dumps(decode(argv[0]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
