"""Unit tests for the Phase A offline decoder (stdlib unittest, no pytest)."""
import os
import sys
import unittest

# Make the repo root importable so `sonic.emulator.decoder` resolves regardless
# of the current working directory used to launch the tests.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sonic.emulator.decoder import (  # noqa: E402
    DIRECTION_BACKEND_TO_PANEL,
    DIRECTION_PANEL_TO_BACKEND,
    decode,
    decode_command,
    decode_event,
)


class JsonSerializableMixin:
    def assertJsonSerializable(self, obj):
        import json
        try:
            json.dumps(obj)
        except (TypeError, ValueError) as exc:  # pragma: no cover - failure path
            self.fail(f"result is not JSON-serializable: {exc}")


class TestCommands(unittest.TestCase, JsonSerializableMixin):
    def test_page_type_screensaver(self):
        r = decode_command("pageType~screensaver")
        self.assertEqual(r["direction"], DIRECTION_BACKEND_TO_PANEL)
        self.assertEqual(r["cmd"], "pageType")
        self.assertEqual(r["page"], "screensaver")
        self.assertEqual(r["raw"], "pageType~screensaver")
        self.assertJsonSerializable(r)

    def test_page_type_card_entities(self):
        r = decode_command("pageType~cardEntities")
        self.assertEqual(r["cmd"], "pageType")
        self.assertEqual(r["page"], "cardEntities")

    def test_entity_upd(self):
        msg = ("entityUpd~Lights~button~navigate.prev~<~65535~~~"
               "light~light.desk~X~17299~Desk~0~switch~switch.bath~D~63142~Bath~1")
        r = decode_command(msg)
        self.assertEqual(r["cmd"], "entityUpd")
        self.assertEqual(r["heading"], "Lights")
        # fields preserve everything after the keyword, in order.
        self.assertEqual(r["fields"][0], "Lights")
        self.assertIn("light.desk", r["fields"])
        self.assertEqual(r["raw"], msg)
        self.assertJsonSerializable(r)

    def test_entity_update_detail(self):
        msg = "entityUpdateDetail~1~17299~1~100~78~enable"
        r = decode_command(msg)
        self.assertEqual(r["cmd"], "entityUpdateDetail")
        self.assertEqual(r["entity"], "1")
        self.assertEqual(r["fields"], ["1", "17299", "1", "100", "78", "enable"])
        self.assertJsonSerializable(r)

    def test_color(self):
        msg = "color~0~65535~65535~38066~0"
        r = decode_command(msg)
        self.assertEqual(r["cmd"], "color")
        self.assertEqual(r["values"], [0, 65535, 65535, 38066, 0])
        self.assertTrue(all(isinstance(v, int) for v in r["values"]))
        self.assertJsonSerializable(r)

    def test_unknown_command(self):
        r = decode_command("totallyMadeUp~a~b")
        self.assertEqual(r["cmd"], "unknown")
        self.assertEqual(r["command"], "totallyMadeUp")
        self.assertEqual(r["fields"], ["a", "b"])
        self.assertEqual(r["raw"], "totallyMadeUp~a~b")
        self.assertJsonSerializable(r)

    def test_command_without_args(self):
        r = decode_command("pageType")
        self.assertEqual(r["cmd"], "pageType")
        self.assertIsNone(r["page"])


class TestEvents(unittest.TestCase, JsonSerializableMixin):
    def test_startup(self):
        r = decode_event('{"CustomRecv":"event,startup,39,eu"}')
        self.assertEqual(r["direction"], DIRECTION_PANEL_TO_BACKEND)
        self.assertEqual(r["type"], "startup")
        self.assertEqual(r["hmi_version"], 39)
        self.assertEqual(r["model"], "eu")
        self.assertEqual(r["recv"], "event,startup,39,eu")
        self.assertJsonSerializable(r)

    def test_button_press2(self):
        r = decode_event('{"CustomRecv":"event,buttonPress2,screensaver,bExit,1"}')
        self.assertEqual(r["type"], "buttonPress2")
        self.assertEqual(r["page"], "screensaver")
        self.assertEqual(r["component"], "bExit")
        self.assertEqual(r["value"], 1)
        self.assertJsonSerializable(r)

    def test_button_press2_without_value(self):
        r = decode_event('{"CustomRecv":"event,buttonPress2,pageName,bNext"}')
        self.assertEqual(r["type"], "buttonPress2")
        self.assertEqual(r["component"], "bNext")
        self.assertIsNone(r["value"])

    def test_button_press2_non_numeric_value(self):
        # colorWheel sends a pipe-delimited payload; it must survive as a string.
        r = decode_event('{"CustomRecv":"event,buttonPress2,nameEntity,colorWheel,12|34|160"}')
        self.assertEqual(r["component"], "colorWheel")
        self.assertEqual(r["value"], "12|34|160")

    def test_sleep_reached(self):
        r = decode_event('{"CustomRecv":"event,sleepReached,sensor.foo"}')
        self.assertEqual(r["type"], "sleepReached")
        self.assertEqual(r["entity"], "sensor.foo")
        self.assertJsonSerializable(r)

    def test_malformed_json(self):
        r = decode_event('{"CustomRecv": not valid json')
        self.assertEqual(r["type"], "error")
        self.assertEqual(r["error"], "invalid_json")
        self.assertEqual(r["raw"], '{"CustomRecv": not valid json')
        self.assertJsonSerializable(r)

    def test_missing_customrecv(self):
        r = decode_event('{"somethingElse":1}')
        self.assertEqual(r["type"], "error")
        self.assertEqual(r["error"], "missing_customrecv")

    def test_driver_version_handshake(self):
        r = decode_event('{"nlui_driver_version":39}')
        self.assertEqual(r["type"], "driver_version")
        self.assertEqual(r["version"], 39)


class TestAutoDetect(unittest.TestCase):
    def test_decode_routes_json_to_event(self):
        r = decode('{"CustomRecv":"event,startup,39,eu"}')
        self.assertEqual(r["type"], "startup")

    def test_decode_routes_tilde_to_command(self):
        r = decode("pageType~screensaver")
        self.assertEqual(r["cmd"], "pageType")

    def test_decode_handles_leading_whitespace_json(self):
        r = decode('   {"CustomRecv":"event,sleepReached,sensor.foo"}')
        self.assertEqual(r["type"], "sleepReached")

    def test_decode_non_string(self):
        r = decode(None)
        self.assertEqual(r["error"], "not_a_string")


if __name__ == "__main__":
    unittest.main()
