from __future__ import annotations

import json
import re
import struct
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "serial_protocol.v1"
FRAME_ENCODINGS = {"hex", "ascii", "utf8"}
CHECKSUM_ALGORITHMS = {"sum8", "xor8", "modbus_crc16"}
FIELD_TYPES = {
    "hex",
    "ascii",
    "utf8",
    "uint8",
    "int8",
    "uint16",
    "int16",
    "uint32",
    "int32",
    "float32",
}
NUMERIC_LENGTHS = {
    "uint8": 1,
    "int8": 1,
    "uint16": 2,
    "int16": 2,
    "uint32": 4,
    "int32": 4,
    "float32": 4,
}


class ProtocolError(ValueError):
    pass


def format_hex(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def parse_hex(value: str) -> bytes:
    cleaned = re.sub(r"0[xX]", "", value)
    cleaned = re.sub(r"[\s,:;_\-]", "", cleaned)
    if not cleaned:
        return b""
    if len(cleaned) % 2:
        raise ProtocolError("hex data must contain complete byte pairs")
    if re.search(r"[^0-9a-fA-F]", cleaned):
        raise ProtocolError("hex data contains a non-hexadecimal character")
    return bytes.fromhex(cleaned)


def encode_text(value: str, encoding: str) -> bytes:
    if encoding == "hex":
        return parse_hex(value)
    if encoding == "ascii":
        try:
            return value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ProtocolError("ASCII frame contains a non-ASCII character") from exc
    if encoding == "utf8":
        return value.encode("utf-8")
    raise ProtocolError(f"unsupported frame encoding: {encoding}")


def modbus_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def checksum_bytes(data: bytes, checksum: dict[str, Any]) -> bytes:
    algorithm = checksum.get("algorithm")
    start = checksum.get("start", 0)
    end = checksum.get("end")
    end = len(data) if end is None else end
    if not isinstance(start, int) or not isinstance(end, int):
        raise ProtocolError("checksum start and end must be integers or null")
    if start < 0 or end < start or end > len(data):
        raise ProtocolError("checksum coverage is outside the frame")
    covered = data[start:end]
    if algorithm == "sum8":
        return bytes((sum(covered) & 0xFF,))
    if algorithm == "xor8":
        value = 0
        for byte in covered:
            value ^= byte
        return bytes((value,))
    if algorithm == "modbus_crc16":
        byte_order = checksum.get("byte_order", "little")
        if byte_order not in {"little", "big"}:
            raise ProtocolError("checksum byte_order must be 'little' or 'big'")
        return modbus_crc16(covered).to_bytes(2, byte_order)
    raise ProtocolError(f"unsupported checksum algorithm: {algorithm}")


def encode_frame(frame: dict[str, Any]) -> bytes:
    if not isinstance(frame, dict):
        raise ProtocolError("frame must be an object")
    data = frame.get("data")
    encoding = frame.get("encoding", "hex")
    if not isinstance(data, str):
        raise ProtocolError("frame data must be a string")
    encoded = encode_text(data, encoding)
    checksum = frame.get("checksum")
    if checksum is not None:
        if not isinstance(checksum, dict):
            raise ProtocolError("checksum must be an object")
        if checksum.get("algorithm") not in CHECKSUM_ALGORITHMS:
            raise ProtocolError("checksum algorithm is not supported")
        if checksum.get("append", True):
            encoded += checksum_bytes(encoded, checksum)
    return encoded


def frame_matches(received: bytes, frame: dict[str, Any]) -> bool:
    expected = encode_frame(frame)
    if len(received) != len(expected):
        return False
    mask_value = frame.get("match_mask")
    if mask_value is None:
        return received == expected
    if not isinstance(mask_value, str):
        raise ProtocolError("match_mask must be a hex string")
    mask = parse_hex(mask_value)
    if len(mask) != len(expected):
        raise ProtocolError("match_mask length must equal the encoded frame length")
    return all((actual & bitmask) == (wanted & bitmask) for actual, wanted, bitmask in zip(received, expected, mask))


def find_matching_command(received: bytes, commands: list[dict[str, Any]]) -> dict[str, Any] | None:
    for command in commands:
        request = command.get("request")
        if isinstance(request, dict) and frame_matches(received, request):
            return command
    return None


def _decode_numeric(chunk: bytes, field_type: str, byte_order: str) -> int | float:
    if field_type == "float32":
        prefix = "<" if byte_order == "little" else ">"
        return struct.unpack(f"{prefix}f", chunk)[0]
    signed = field_type.startswith("int")
    return int.from_bytes(chunk, byte_order, signed=signed)


def decode_response(data: bytes, response: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not response:
        return []
    decoded: list[dict[str, Any]] = []
    for field in response.get("decode", []):
        name = field.get("name", "field")
        label = field.get("label", name)
        offset = field.get("offset", 0)
        length = field.get("length", 1)
        field_type = field.get("type", "hex")
        end = offset + length
        if end > len(data):
            decoded.append(
                {
                    "name": name,
                    "label": label,
                    "raw": "",
                    "value": None,
                    "display": f"frame too short: need bytes {offset}:{end}",
                }
            )
            continue
        chunk = data[offset:end]
        if field_type == "hex":
            value: Any = format_hex(chunk)
        elif field_type in {"ascii", "utf8"}:
            codec = "ascii" if field_type == "ascii" else "utf-8"
            value = chunk.decode(codec, errors="replace").rstrip("\x00")
        else:
            value = _decode_numeric(chunk, field_type, field.get("byte_order", "big"))

        raw_value = value
        enum_map = field.get("enum", {})
        enum_value = enum_map.get(str(value)) if isinstance(enum_map, dict) else None
        if enum_value is not None:
            display = str(enum_value)
        elif isinstance(value, (int, float)):
            value = value * field.get("scale", 1) + field.get("offset_value", 0)
            display = f"{value:g}" if isinstance(value, float) else str(value)
        else:
            display = str(value)
        unit = field.get("unit", "")
        if unit:
            display = f"{display} {unit}"
        decoded.append(
            {
                "name": name,
                "label": label,
                "raw": format_hex(chunk),
                "value": raw_value,
                "display": display,
            }
        )
    return decoded


def _validate_serial(defaults: Any, errors: list[str]) -> None:
    if not isinstance(defaults, dict):
        errors.append("serial.defaults must be an object")
        return
    baudrate = defaults.get("baudrate")
    if not isinstance(baudrate, int) or baudrate <= 0:
        errors.append("serial.defaults.baudrate must be a positive integer")
    if defaults.get("bytesize", 8) not in {5, 6, 7, 8}:
        errors.append("serial.defaults.bytesize must be 5, 6, 7, or 8")
    if defaults.get("parity", "N") not in {"N", "E", "O", "M", "S"}:
        errors.append("serial.defaults.parity must be N, E, O, M, or S")
    if defaults.get("stopbits", 1) not in {1, 1.5, 2}:
        errors.append("serial.defaults.stopbits must be 1, 1.5, or 2")
    timeout_ms = defaults.get("timeout_ms", 200)
    if not isinstance(timeout_ms, int) or timeout_ms < 0:
        errors.append("serial.defaults.timeout_ms must be a non-negative integer")


def _validate_frame(frame: Any, path: str, errors: list[str]) -> bytes | None:
    if not isinstance(frame, dict):
        errors.append(f"{path} must be an object")
        return None
    if frame.get("encoding", "hex") not in FRAME_ENCODINGS:
        errors.append(f"{path}.encoding must be hex, ascii, or utf8")
    try:
        encoded = encode_frame(frame)
    except (ProtocolError, TypeError, ValueError) as exc:
        errors.append(f"{path}: {exc}")
        return None
    mask = frame.get("match_mask")
    if mask is not None:
        try:
            mask_bytes = parse_hex(mask) if isinstance(mask, str) else b""
            if not isinstance(mask, str) or len(mask_bytes) != len(encoded):
                errors.append(f"{path}.match_mask must encode exactly {len(encoded)} bytes")
        except ProtocolError as exc:
            errors.append(f"{path}.match_mask: {exc}")
    return encoded


def _validate_decode(fields: Any, response_length: int | None, path: str, errors: list[str]) -> None:
    if fields is None:
        return
    if not isinstance(fields, list):
        errors.append(f"{path} must be an array")
        return
    names: set[str] = set()
    for index, field in enumerate(fields):
        item_path = f"{path}[{index}]"
        if not isinstance(field, dict):
            errors.append(f"{item_path} must be an object")
            continue
        name = field.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"{item_path}.name must be a non-empty string")
        elif name in names:
            errors.append(f"{item_path}.name is duplicated: {name}")
        else:
            names.add(name)
        field_type = field.get("type", "hex")
        if field_type not in FIELD_TYPES:
            errors.append(f"{item_path}.type is not supported: {field_type}")
        offset = field.get("offset")
        length = field.get("length")
        if not isinstance(offset, int) or offset < 0:
            errors.append(f"{item_path}.offset must be a non-negative integer")
        if not isinstance(length, int) or length <= 0:
            errors.append(f"{item_path}.length must be a positive integer")
        if field_type in NUMERIC_LENGTHS and length != NUMERIC_LENGTHS[field_type]:
            errors.append(f"{item_path}.length must be {NUMERIC_LENGTHS[field_type]} for {field_type}")
        if field_type in NUMERIC_LENGTHS and field.get("byte_order", "big") not in {"big", "little"}:
            errors.append(f"{item_path}.byte_order must be big or little")
        if response_length is not None and isinstance(offset, int) and isinstance(length, int):
            if offset + length > response_length:
                errors.append(f"{item_path} extends past the fixed response length {response_length}")


def validate_protocol_data(protocol: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(protocol, dict):
        return ["protocol root must be an object"]
    if protocol.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(protocol.get("name"), str) or not protocol.get("name", "").strip():
        errors.append("name must be a non-empty string")
    serial = protocol.get("serial")
    if not isinstance(serial, dict):
        errors.append("serial must be an object")
    else:
        _validate_serial(serial.get("defaults"), errors)
    commands = protocol.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("commands must be a non-empty array")
        return errors
    ids: set[str] = set()
    for index, command in enumerate(commands):
        path = f"commands[{index}]"
        if not isinstance(command, dict):
            errors.append(f"{path} must be an object")
            continue
        command_id = command.get("id")
        if not isinstance(command_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", command_id):
            errors.append(f"{path}.id must use lowercase letters, digits, underscores, or hyphens")
        elif command_id in ids:
            errors.append(f"{path}.id is duplicated: {command_id}")
        else:
            ids.add(command_id)
        if not isinstance(command.get("name"), str) or not command.get("name", "").strip():
            errors.append(f"{path}.name must be a non-empty string")
        if "baudrate" in command and (not isinstance(command["baudrate"], int) or command["baudrate"] <= 0):
            errors.append(f"{path}.baudrate must be a positive integer")
        _validate_frame(command.get("request"), f"{path}.request", errors)
        response = command.get("response")
        response_bytes = None
        if response is not None:
            response_bytes = _validate_frame(response, f"{path}.response", errors)
            if isinstance(response, dict):
                _validate_decode(
                    response.get("decode"),
                    len(response_bytes) if response_bytes is not None else None,
                    f"{path}.response.decode",
                    errors,
                )
        if command.get("auto_reply", False) and response is None:
            errors.append(f"{path}.auto_reply requires a response")
    return errors


def load_protocol(path: str | Path) -> dict[str, Any]:
    protocol_path = Path(path)
    try:
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProtocolError(f"cannot read protocol file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    errors = validate_protocol_data(protocol)
    if errors:
        raise ProtocolError("protocol validation failed:\n- " + "\n- ".join(errors))
    return protocol
