from __future__ import annotations

import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = SKILL_ROOT / "assets" / "pyside6-serial-console"
sys.path.insert(0, str(APP_ROOT))

from protocol_core import (  # noqa: E402
    decode_response,
    encode_frame,
    find_matching_command,
    load_protocol,
    modbus_crc16,
)


class ProtocolCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_path = APP_ROOT / "sample_protocol.json"
        self.protocol = load_protocol(self.sample_path)

    def test_sample_protocol_loads(self) -> None:
        self.assertEqual(self.protocol["schema_version"], "serial_protocol.v1")
        self.assertEqual(len(self.protocol["commands"]), 3)

    def test_modbus_crc_and_frame_append(self) -> None:
        request = self.protocol["commands"][0]["request"]
        encoded = encode_frame(request)
        self.assertEqual(encoded.hex(" ").upper(), "01 03 00 00 00 01 84 0A")
        self.assertEqual(modbus_crc16(encoded[:-2]), 0x0A84)

    def test_masked_command_matching(self) -> None:
        received = bytes.fromhex("01 06 00 10 00 02 08 0E")
        command = find_matching_command(received, self.protocol["commands"])
        self.assertIsNotNone(command)
        self.assertEqual(command["id"], "set_run_state")

    def test_scaled_response_decode(self) -> None:
        command = self.protocol["commands"][0]
        response = encode_frame(command["response"])
        fields = decode_response(response, command["response"])
        self.assertEqual(fields[0]["display"], "25 °C")


if __name__ == "__main__":
    unittest.main()
