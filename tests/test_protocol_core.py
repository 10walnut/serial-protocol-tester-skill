from __future__ import annotations

import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

from protocol_core import (  # noqa: E402
    ProtocolError,
    decode_frame_details,
    decode_response,
    encode_frame,
    find_matching_command,
    find_matching_frame,
    load_protocol,
    localized_value,
    modbus_crc16,
    split_framed_bytes,
)


class ProtocolCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_path = SKILL_ROOT / "examples" / "sample_protocol.json"
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
        temperature = next(field for field in fields if field["name"] == "temperature")
        self.assertEqual(temperature["display"], "25 °C")

    def test_single_language_protocol_text(self) -> None:
        command = self.protocol["commands"][0]
        self.assertEqual(localized_value(command, "name", "zh"), "读取温度")
        self.assertNotIn(" / ", localized_value(command, "description", "en"))

    def test_formula_variables_build_frame_and_explain_calculation(self) -> None:
        command = self.protocol["commands"][1]
        runtime = {"run_state": 0}
        encoded = encode_frame(command["request"], runtime)
        self.assertEqual(encoded[:6], bytes.fromhex("01 06 00 10 00 00"))
        spec = dict(command["request"])
        spec["_runtime_values"] = runtime
        details = decode_frame_details(encoded, spec, language="zh")
        state = next(row for row in details if row["field"] == "运行状态")
        self.assertIn("公式 run_state = 0", state["calculation"])
        self.assertTrue(any(row["field"] == "校验和" and row["result"] == "通过" for row in details))

    def test_formula_rejects_code_execution(self) -> None:
        frame = {
            "encoding": "hex",
            "data": "00",
            "variables": [{"name": "value", "default": 1}],
            "encode": [{"name": "value", "offset": 0, "length": 1, "type": "uint8", "formula": "__import__('os')"}],
        }
        with self.assertRaises(ProtocolError):
            encode_frame(frame)

    def test_length_framing_splits_sticky_and_partial_frames(self) -> None:
        framing = {
            "header": "AA 55",
            "length_offset": 3,
            "payload_offset": 4,
            "checksum_length": 1,
        }
        first = bytes.fromhex("AA 55 81 01 00 82")
        second = bytes.fromhex("AA 55 11 00 11")
        third = bytes.fromhex("AA 55 82 01 00 83")
        frames, remainder = split_framed_bytes(b"noise" + first + second + third[:4], framing)
        self.assertEqual(frames, [first, second])
        self.assertEqual(remainder, third[:4])

    def test_passive_frame_matching(self) -> None:
        frame = bytes.fromhex("AA 55 10 00 10")
        match = find_matching_frame(frame, [{"id": "data", "match": {"offset": 2, "data": "10"}}])
        self.assertEqual(match["id"], "data")


if __name__ == "__main__":
    unittest.main()
