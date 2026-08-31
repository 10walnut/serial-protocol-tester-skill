from __future__ import annotations

import ast
import json
import math
import re
import struct
from datetime import datetime
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


def localized_value(item: dict[str, Any], key: str, language: str | None = None, default: str = "") -> str:
    if language:
        localized = item.get(f"{key}_{language}")
        if isinstance(localized, str) and localized:
            return localized
    value = item.get(key, default)
    if isinstance(value, dict):
        candidate = value.get(language or "") or value.get("zh") or value.get("en")
        return str(candidate) if candidate is not None else default
    text = str(value) if value is not None else default
    if language and " / " in text:
        english, chinese = text.split(" / ", 1)
        return chinese if language == "zh" else english
    return text


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


def default_variable_values(frame: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now()
    system_values = {
        "system.year": current.year,
        "system.month": current.month,
        "system.day": current.day,
        "system.hour": current.hour,
        "system.minute": current.minute,
        "system.second": current.second,
        "system.millisecond": current.microsecond // 1000,
    }
    values: dict[str, Any] = {}
    for variable in frame.get("variables", []):
        if not isinstance(variable, dict) or not isinstance(variable.get("name"), str):
            continue
        default = variable.get("default", 0)
        values[variable["name"]] = system_values.get(default, default) if isinstance(default, str) else default
    return values


def evaluate_formula(expression: str, variables: dict[str, Any]) -> int | float:
    functions = {"round": round, "int": int, "abs": abs, "min": min, "max": max}
    binary = {
        ast.Add: lambda left, right: left + right,
        ast.Sub: lambda left, right: left - right,
        ast.Mult: lambda left, right: left * right,
        ast.Div: lambda left, right: left / right,
        ast.FloorDiv: lambda left, right: left // right,
        ast.Mod: lambda left, right: left % right,
        ast.Pow: lambda left, right: left**right,
    }

    def visit(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id in variables:
            value = variables[node.id]
            if not isinstance(value, (int, float)):
                raise ProtocolError(f"formula variable '{node.id}' is not numeric")
            return value
        if isinstance(node, ast.BinOp) and type(node.op) in binary:
            left = visit(node.left)
            right = visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 16:
                raise ProtocolError("formula exponent must be between -16 and 16")
            return binary[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions:
            if node.keywords:
                raise ProtocolError("formula function keyword arguments are not supported")
            return functions[node.func.id](*(visit(argument) for argument in node.args))
        raise ProtocolError(f"unsupported formula element: {ast.dump(node, include_attributes=False)}")

    try:
        parsed = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(parsed)) > 64:
            raise ProtocolError("formula is too complex")
        value = visit(parsed)
    except (SyntaxError, ArithmeticError, TypeError, ValueError) as exc:
        raise ProtocolError(f"invalid formula '{expression}': {exc}") from exc
    if not isinstance(value, (int, float)):
        raise ProtocolError(f"formula '{expression}' did not produce a number")
    if not math.isfinite(value):
        raise ProtocolError(f"formula '{expression}' did not produce a finite number")
    return value


def _encode_formula_field(value: int | float, field: dict[str, Any]) -> bytes:
    field_type = field.get("type", "uint8")
    length = field.get("length", NUMERIC_LENGTHS.get(field_type, 1))
    byte_order = field.get("byte_order", "big")
    if field_type == "float32":
        prefix = "<" if byte_order == "little" else ">"
        return struct.pack(f"{prefix}f", float(value))
    if field_type not in NUMERIC_LENGTHS:
        raise ProtocolError(f"formula encoding requires a numeric field type, got {field_type}")
    integer = int(round(value))
    try:
        return integer.to_bytes(length, byte_order, signed=field_type.startswith("int"))
    except OverflowError as exc:
        raise ProtocolError(f"formula result {integer} does not fit {field_type}") from exc


def encode_frame(frame: dict[str, Any], variables: dict[str, Any] | None = None) -> bytes:
    if not isinstance(frame, dict):
        raise ProtocolError("frame must be an object")
    data = frame.get("data")
    encoding = frame.get("encoding", "hex")
    if not isinstance(data, str):
        raise ProtocolError("frame data must be a string")
    encoded = bytearray(encode_text(data, encoding))
    encode_fields = frame.get("encode", [])
    if encode_fields:
        values = default_variable_values(frame)
        if variables:
            values.update(variables)
        for field in encode_fields:
            expression = field.get("formula")
            if not isinstance(expression, str) or not expression.strip():
                raise ProtocolError("encode field formula must be a non-empty string")
            offset = field.get("offset")
            length = field.get("length")
            if not isinstance(offset, int) or not isinstance(length, int) or offset < 0 or length <= 0:
                raise ProtocolError("encode field offset and length are invalid")
            end = offset + length
            if end > len(encoded):
                raise ProtocolError(f"encode field extends past template length {len(encoded)}")
            result = evaluate_formula(expression, values)
            chunk = _encode_formula_field(result, field)
            if len(chunk) != length:
                raise ProtocolError("encoded formula result length does not match field length")
            encoded[offset:end] = chunk
    checksum = frame.get("checksum")
    if checksum is not None:
        if not isinstance(checksum, dict):
            raise ProtocolError("checksum must be an object")
        if checksum.get("algorithm") not in CHECKSUM_ALGORITHMS:
            raise ProtocolError("checksum algorithm is not supported")
        if checksum.get("append", True):
            encoded += checksum_bytes(bytes(encoded), checksum)
    return bytes(encoded)


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


def find_matching_frame(received: bytes, frames: list[dict[str, Any]]) -> dict[str, Any] | None:
    for frame in frames:
        match = frame.get("match", {})
        if not isinstance(match, dict):
            continue
        offset = match.get("offset", 0)
        data_value = match.get("data")
        if not isinstance(offset, int) or offset < 0 or not isinstance(data_value, str):
            continue
        expected = parse_hex(data_value)
        actual = received[offset : offset + len(expected)]
        if len(actual) != len(expected):
            continue
        mask_value = match.get("mask")
        if mask_value is None:
            if actual == expected:
                return frame
            continue
        mask = parse_hex(mask_value)
        if len(mask) != len(expected):
            raise ProtocolError("frame match mask length must equal match data length")
        if all((value & bitmask) == (wanted & bitmask) for value, wanted, bitmask in zip(actual, expected, mask)):
            return frame
    return None


def split_framed_bytes(data: bytes, framing: dict[str, Any]) -> tuple[list[bytes], bytes]:
    header = parse_hex(str(framing.get("header", "")))
    if not header:
        raise ProtocolError("framing.header must contain at least one byte")
    length_offset = framing.get("length_offset")
    length_size = framing.get("length_size", 1)
    payload_offset = framing.get("payload_offset")
    checksum_length = framing.get("checksum_length", 0)
    length_adjustment = framing.get("length_adjustment", 0)
    byte_order = framing.get("length_byte_order", "big")
    if not isinstance(length_offset, int) or length_offset < 0:
        raise ProtocolError("framing.length_offset must be a non-negative integer")
    if not isinstance(length_size, int) or length_size <= 0:
        raise ProtocolError("framing.length_size must be a positive integer")
    if not isinstance(payload_offset, int) or payload_offset <= length_offset:
        raise ProtocolError("framing.payload_offset must follow the length field")
    if not isinstance(checksum_length, int) or checksum_length < 0:
        raise ProtocolError("framing.checksum_length must be a non-negative integer")
    if not isinstance(length_adjustment, int):
        raise ProtocolError("framing.length_adjustment must be an integer")
    if byte_order not in {"big", "little"}:
        raise ProtocolError("framing.length_byte_order must be big or little")

    maximum = framing.get("max_frame_length", 65535)
    if not isinstance(maximum, int) or maximum <= 0:
        raise ProtocolError("framing.max_frame_length must be a positive integer")

    buffer = bytearray(data)
    frames: list[bytes] = []
    while buffer:
        header_index = buffer.find(header)
        if header_index < 0:
            keep = 0
            for size in range(1, min(len(header), len(buffer)) + 1):
                if bytes(buffer[-size:]) == header[:size]:
                    keep = size
            return frames, bytes(buffer[-keep:]) if keep else b""
        if header_index:
            del buffer[:header_index]
        length_end = length_offset + length_size
        if len(buffer) < length_end:
            break
        payload_length = int.from_bytes(buffer[length_offset:length_end], byte_order)
        frame_length = payload_offset + payload_length + checksum_length + length_adjustment
        if frame_length < payload_offset + checksum_length or frame_length > maximum:
            del buffer[0]
            continue
        if len(buffer) < frame_length:
            break
        frames.append(bytes(buffer[:frame_length]))
        del buffer[:frame_length]
    return frames, bytes(buffer)


def _decode_numeric(chunk: bytes, field_type: str, byte_order: str) -> int | float:
    if field_type == "float32":
        prefix = "<" if byte_order == "little" else ">"
        return struct.unpack(f"{prefix}f", chunk)[0]
    signed = field_type.startswith("int")
    return int.from_bytes(chunk, byte_order, signed=signed)


def _numeric_calculation(
    chunk: bytes,
    field: dict[str, Any],
    raw_value: int | float,
    converted_value: int | float,
    language: str | None,
) -> str:
    byte_order = field.get("byte_order", "big")
    order_name = {"zh": {"little": "小端", "big": "大端"}, "en": {"little": "little-endian", "big": "big-endian"}}
    order = order_name.get(language or "en", order_name["en"])[byte_order]
    if field.get("type") == "float32":
        formula = f"{order}: {format_hex(chunk)} -> {raw_value:g}"
    else:
        base_offset = field.get("offset", 0)
        terms = []
        for index, value in enumerate(chunk):
            power = index if byte_order == "little" else len(chunk) - index - 1
            byte_label = "字节" if language == "zh" else "byte"
            terms.append(f"{byte_label}{base_offset + index}=0x{value:02X}({value})×256^{power}")
        unsigned = int.from_bytes(chunk, byte_order, signed=False)
        formula = f"{order}: {' + '.join(terms)} = {unsigned}"
        if field.get("type", "").startswith("int") and raw_value != unsigned:
            bits = len(chunk) * 8
            formula += f"; {bits}位补码 {unsigned} - 2^{bits} = {raw_value}" if language == "zh" else f"; {bits}-bit two's complement {unsigned} - 2^{bits} = {raw_value}"
    scale = field.get("scale", 1)
    offset_value = field.get("offset_value", 0)
    if scale != 1 or offset_value != 0:
        formula += f"; {raw_value} × {scale:g} + {offset_value:g} = {converted_value:g}"
    return formula


def decode_response(
    data: bytes,
    response: dict[str, Any] | None,
    language: str | None = None,
) -> list[dict[str, Any]]:
    if not response:
        return []
    decoded: list[dict[str, Any]] = []
    for field in response.get("decode", []):
        name = field.get("name", "field")
        label = localized_value(field, "label", language, name)
        offset = field.get("offset", 0)
        length = field.get("length", 1)
        field_type = field.get("type", "hex")
        end = offset + length
        if end > len(data):
            too_short = (
                f"帧长度不足：需要字节 {offset}:{end}"
                if language == "zh"
                else f"frame too short: need bytes {offset}:{end}"
            )
            decoded.append(
                {
                    "name": name,
                    "label": label,
                    "raw": "",
                    "value": None,
                    "display": too_short,
                    "offset": offset,
                    "length": length,
                    "type": field_type,
                    "calculation": "",
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
        enum_map = field.get(f"enum_{language}", field.get("enum", {})) if language else field.get("enum", {})
        enum_value = enum_map.get(str(value)) if isinstance(enum_map, dict) else None
        if enum_value is not None:
            display = str(enum_value)
            if language and " / " in display:
                english, chinese = display.split(" / ", 1)
                display = chinese if language == "zh" else english
            byte_label = "字节" if language == "zh" else "byte"
            calculation = f"{byte_label}{offset}={format_hex(chunk)} -> {value} -> {display}"
        elif isinstance(value, (int, float)):
            value = value * field.get("scale", 1) + field.get("offset_value", 0)
            display = f"{value:g}" if isinstance(value, float) else str(value)
            calculation = _numeric_calculation(chunk, field, raw_value, value, language)
        else:
            display = str(value)
            if len(chunk) <= 16:
                characters = []
                for index, byte in enumerate(chunk):
                    char = chr(byte) if 32 <= byte <= 126 else "."
                    byte_label = "字节" if language == "zh" else "byte"
                    suffix = f"('{char}')" if field_type in {"ascii", "utf8"} else ""
                    characters.append(f"{byte_label}{offset + index}=0x{byte:02X}{suffix}")
                calculation = f"{field_type}: {'; '.join(characters)} -> {display}"
            else:
                count_label = "字节" if language == "zh" else "bytes"
                calculation = f"{field_type}: {len(chunk)} {count_label} -> {display}"
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
                "offset": offset,
                "length": length,
                "type": field_type,
                "byte_order": field.get("byte_order", ""),
                "calculation": calculation,
            }
        )
    return decoded


def _byte_range(offset: int, length: int) -> str:
    return str(offset) if length == 1 else f"{offset}-{offset + length - 1}"


def _field_rule(field: dict[str, Any], language: str) -> str:
    field_type = field.get("type", "hex")
    parts = [str(field_type)]
    if field_type in NUMERIC_LENGTHS:
        byte_order = field.get("byte_order", "big")
        if language == "zh":
            parts.append("小端" if byte_order == "little" else "大端")
        else:
            parts.append("little-endian" if byte_order == "little" else "big-endian")
    scale = field.get("scale", 1)
    offset_value = field.get("offset_value", 0)
    if scale != 1 or offset_value != 0:
        parts.append(
            f"比例={scale:g}, 偏移={offset_value:g}"
            if language == "zh"
            else f"scale={scale:g}, offset={offset_value:g}"
        )
    return ", ".join(parts)


def _detail_row(
    byte_range: str,
    field: str,
    purpose: str,
    raw: str,
    rule: str,
    calculation: str,
    result: str,
) -> dict[str, str]:
    return {
        "byte_range": byte_range,
        "field": field,
        "purpose": purpose,
        "raw": raw,
        "rule": rule,
        "calculation": calculation,
        "result": result,
    }


def _checksum_length(checksum: dict[str, Any] | None) -> int:
    if not checksum:
        return 0
    return 2 if checksum.get("algorithm") == "modbus_crc16" else 1


def _checksum_detail(
    data: bytes,
    checksum: dict[str, Any],
    length: int,
    language: str,
) -> dict[str, str] | None:
    if length <= 0 or len(data) < length:
        return None
    body = data[:-length]
    actual = data[-length:]
    calculation_spec = dict(checksum)
    calculation_spec["end"] = min(calculation_spec.get("end", len(body)) or len(body), len(body))
    try:
        expected = checksum_bytes(body, calculation_spec)
    except ProtocolError:
        return None
    algorithm = str(checksum.get("algorithm", "checksum")).upper()
    start = calculation_spec.get("start", 0)
    end = calculation_spec.get("end", len(body))
    covered_count = max(0, end - start)
    valid = actual == expected
    covered = body[start:end]
    if language == "zh":
        field = "校验和"
        rule = f"{algorithm}，覆盖字节 {start}-{max(start, end - 1)}"
        if algorithm in {"SUM8", "XOR8"} and covered_count <= 16:
            operator = " + " if algorithm == "SUM8" else " XOR "
            terms = operator.join(f"0x{value:02X}" for value in covered)
            suffix = " & 0xFF" if algorithm == "SUM8" else ""
            calculation = f"({terms}){suffix} = {format_hex(expected)}；收到 {format_hex(actual)}"
        else:
            calculation = f"{algorithm}(字节 {start}-{max(start, end - 1)}，共 {covered_count} 字节) = {format_hex(expected)}；收到 {format_hex(actual)}"
        result = "通过" if valid else "失败"
    else:
        field = "Checksum"
        rule = f"{algorithm}, bytes {start}-{max(start, end - 1)}"
        if algorithm in {"SUM8", "XOR8"} and covered_count <= 16:
            operator = " + " if algorithm == "SUM8" else " XOR "
            terms = operator.join(f"0x{value:02X}" for value in covered)
            suffix = " & 0xFF" if algorithm == "SUM8" else ""
            calculation = f"({terms}){suffix} = {format_hex(expected)}; received {format_hex(actual)}"
        else:
            calculation = f"{algorithm}(bytes {start}-{max(start, end - 1)}, {covered_count} bytes) = {format_hex(expected)}; received {format_hex(actual)}"
        result = "Valid" if valid else "Invalid"
    return _detail_row(
        _byte_range(len(data) - length, length),
        field,
        "验证传输过程中数据是否完整" if language == "zh" else "Verifies frame integrity during transmission",
        format_hex(actual),
        rule,
        calculation,
        result,
    )


def decode_frame_details(
    data: bytes,
    frame_spec: dict[str, Any] | None,
    framing: dict[str, Any] | None = None,
    language: str = "zh",
) -> list[dict[str, str]]:
    spec = frame_spec or {}
    rows: list[dict[str, str]] = []
    covered: set[int] = set()

    if framing:
        header = parse_hex(str(framing.get("header", "")))
        if header and len(data) >= len(header):
            rows.append(
                _detail_row(
                    _byte_range(0, len(header)),
                    "帧头" if language == "zh" else "Header",
                    "标记一帧数据的起始位置" if language == "zh" else "Marks the start of a frame",
                    format_hex(data[: len(header)]),
                    "固定标识" if language == "zh" else "Fixed marker",
                    (
                        "；".join(f"字节 {index}=0x{value:02X}" for index, value in enumerate(data[: len(header)]))
                        + f"；期望 {format_hex(header)}"
                        if language == "zh"
                        else "; ".join(f"byte {index}=0x{value:02X}" for index, value in enumerate(data[: len(header)]))
                        + f"; expected {format_hex(header)}"
                    ),
                    "匹配" if data[: len(header)] == header and language == "zh" else
                    "Match" if data[: len(header)] == header else
                    "不匹配" if language == "zh" else "Mismatch",
                )
            )
            covered.update(range(len(header)))
        command_offset = framing.get("command_offset")
        if isinstance(command_offset, int) and command_offset < len(data):
            value = data[command_offset]
            rows.append(
                _detail_row(
                    str(command_offset),
                    "命令字" if language == "zh" else "Command",
                    localized_value(spec, "purpose", language, localized_value(spec, "description", language)) or (
                        "标识请求、应答或数据类型" if language == "zh" else "Identifies the request, response, or data type"
                    ),
                    f"{value:02X}",
                    "uint8",
                    f"0x{value:02X} = {value}",
                    f"0x{value:02X}",
                )
            )
            covered.add(command_offset)
        length_offset = framing.get("length_offset")
        length_size = framing.get("length_size", 1)
        if isinstance(length_offset, int) and isinstance(length_size, int) and length_offset + length_size <= len(data):
            chunk = data[length_offset : length_offset + length_size]
            byte_order = framing.get("length_byte_order", "big")
            value = int.from_bytes(chunk, byte_order)
            rows.append(
                _detail_row(
                    _byte_range(length_offset, length_size),
                    "数据长度" if language == "zh" else "Payload length",
                    "确定数据域长度并用于连续拆帧" if language == "zh" else "Defines payload size for stream framing",
                    format_hex(chunk),
                    f"uint{length_size * 8}, " + (
                        "小端" if language == "zh" and byte_order == "little" else
                        "大端" if language == "zh" else
                        "little-endian" if byte_order == "little" else "big-endian"
                    ),
                    f"{format_hex(chunk)} -> {value}",
                    f"{value} " + ("字节" if language == "zh" else "bytes"),
                )
            )
            covered.update(range(length_offset, length_offset + length_size))

    definitions = list(spec.get("decode", []))
    known_fields = {(field.get("offset"), field.get("length")) for field in definitions if isinstance(field, dict)}
    for field in spec.get("encode", []):
        if isinstance(field, dict) and (field.get("offset"), field.get("length")) not in known_fields:
            definitions.append(field)
    decoded = decode_response(data, {"decode": definitions}, language)
    for field, definition in zip(decoded, definitions):
        offset = field["offset"]
        length = field["length"]
        if offset + length <= len(data):
            covered.update(range(offset, offset + length))
        calculation = field["calculation"]
        formula = definition.get("formula")
        if isinstance(formula, str):
            runtime_values = spec.get("_runtime_values", {})
            inputs = ", ".join(f"{name}={value:g}" for name, value in runtime_values.items() if isinstance(value, (int, float)))
            try:
                formula_result = evaluate_formula(formula, runtime_values) if runtime_values else None
            except ProtocolError:
                formula_result = None
            if language == "zh":
                prefix = f"输入 {inputs}；" if inputs else ""
                prefix += f"公式 {formula}"
                prefix += f" = {formula_result:g}；" if formula_result is not None else "；"
            else:
                prefix = f"Inputs {inputs}; " if inputs else ""
                prefix += f"Formula {formula}"
                prefix += f" = {formula_result:g}; " if formula_result is not None else "; "
            calculation = prefix + calculation
        rows.append(
            _detail_row(
                _byte_range(offset, length),
                field["label"],
                localized_value(definition, "purpose", language, localized_value(definition, "description", language)),
                field["raw"],
                _field_rule(definition, language),
                calculation,
                field["display"],
            )
        )

    checksum = spec.get("checksum") if isinstance(spec.get("checksum"), dict) else None
    checksum_length = _checksum_length(checksum)
    if framing:
        framing_checksum = framing.get("checksum")
        if isinstance(framing_checksum, dict):
            checksum = framing_checksum
        checksum_length = framing.get("checksum_length", checksum_length)
    if not isinstance(checksum_length, int):
        checksum_length = 0
    payload_start = framing.get("payload_offset", 0) if framing else 0
    payload_end = max(payload_start, len(data) - checksum_length)
    index = payload_start
    while index < payload_end:
        if index in covered:
            index += 1
            continue
        start = index
        while index < payload_end and index not in covered:
            index += 1
        chunk = data[start:index]
        rows.append(
            _detail_row(
                _byte_range(start, len(chunk)),
                "未定义数据" if language == "zh" else "Undefined data",
                "协议未说明这些字节的作用" if language == "zh" else "The protocol does not define these bytes",
                format_hex(chunk),
                "原始字节" if language == "zh" else "Raw bytes",
                ("协议未给出这些字节的计算规则" if language == "zh" else "No calculation rule is defined for these bytes"),
                format_hex(chunk),
            )
        )
    if checksum and checksum_length:
        detail = _checksum_detail(data, checksum, checksum_length, language)
        if detail:
            rows.append(detail)
    return rows


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
    variable_names = _validate_variables(frame.get("variables"), f"{path}.variables", errors)
    _validate_encode(frame.get("encode"), variable_names, f"{path}.encode", errors)
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
    _validate_decode(frame.get("decode"), len(encoded), f"{path}.decode", errors)
    return encoded


def _validate_variables(variables: Any, path: str, errors: list[str]) -> set[str]:
    if variables is None:
        return set()
    if not isinstance(variables, list):
        errors.append(f"{path} must be an array")
        return set()
    names: set[str] = set()
    for index, variable in enumerate(variables):
        item_path = f"{path}[{index}]"
        if not isinstance(variable, dict):
            errors.append(f"{item_path} must be an object")
            continue
        name = variable.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            errors.append(f"{item_path}.name must use lowercase letters, digits, or underscores")
        elif name in names:
            errors.append(f"{item_path}.name is duplicated: {name}")
        else:
            names.add(name)
        if variable.get("type", "integer") not in {"integer", "number"}:
            errors.append(f"{item_path}.type must be integer or number")
        default = variable.get("default", 0)
        if isinstance(default, str) and default not in {
            "system.year", "system.month", "system.day", "system.hour", "system.minute",
            "system.second", "system.millisecond",
        }:
            errors.append(f"{item_path}.default system value is not supported: {default}")
        elif not isinstance(default, (str, int, float)):
            errors.append(f"{item_path}.default must be numeric or a supported system value")
        minimum = variable.get("min")
        maximum = variable.get("max")
        if minimum is not None and not isinstance(minimum, (int, float)):
            errors.append(f"{item_path}.min must be numeric")
        if maximum is not None and not isinstance(maximum, (int, float)):
            errors.append(f"{item_path}.max must be numeric")
    return names


def _validate_encode(fields: Any, variable_names: set[str], path: str, errors: list[str]) -> None:
    if fields is None:
        return
    _validate_decode(fields, None, path, errors)
    if not isinstance(fields, list):
        return
    functions = {"round", "int", "abs", "min", "max"}
    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            continue
        expression = field.get("formula")
        if not isinstance(expression, str) or not expression.strip():
            errors.append(f"{path}[{index}].formula must be a non-empty string")
            continue
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            errors.append(f"{path}[{index}].formula is invalid: {exc.msg}")
            continue
        referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} - functions
        unknown = sorted(referenced - variable_names)
        if unknown:
            errors.append(f"{path}[{index}].formula uses unknown variables: {', '.join(unknown)}")


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


def _validate_framing(framing: Any, errors: list[str]) -> None:
    if framing is None:
        return
    if not isinstance(framing, dict):
        errors.append("framing must be an object")
        return
    try:
        split_framed_bytes(b"", framing)
    except (ProtocolError, TypeError, ValueError) as exc:
        errors.append(f"framing: {exc}")
    command_offset = framing.get("command_offset")
    if command_offset is not None and (not isinstance(command_offset, int) or command_offset < 0):
        errors.append("framing.command_offset must be a non-negative integer")
    checksum = framing.get("checksum")
    if checksum is not None:
        if not isinstance(checksum, dict):
            errors.append("framing.checksum must be an object")
        elif checksum.get("algorithm") not in CHECKSUM_ALGORITHMS:
            errors.append("framing.checksum.algorithm is not supported")


def _validate_passive_frames(frames: Any, errors: list[str]) -> None:
    if frames is None:
        return
    if not isinstance(frames, list):
        errors.append("frames must be an array")
        return
    ids: set[str] = set()
    for index, frame in enumerate(frames):
        path = f"frames[{index}]"
        if not isinstance(frame, dict):
            errors.append(f"{path} must be an object")
            continue
        frame_id = frame.get("id")
        if not isinstance(frame_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", frame_id):
            errors.append(f"{path}.id must use lowercase letters, digits, underscores, or hyphens")
        elif frame_id in ids:
            errors.append(f"{path}.id is duplicated: {frame_id}")
        else:
            ids.add(frame_id)
        if not isinstance(frame.get("name"), str) or not frame.get("name", "").strip():
            errors.append(f"{path}.name must be a non-empty string")
        match = frame.get("match")
        if not isinstance(match, dict):
            errors.append(f"{path}.match must be an object")
        else:
            offset = match.get("offset", 0)
            if not isinstance(offset, int) or offset < 0:
                errors.append(f"{path}.match.offset must be a non-negative integer")
            try:
                match_data = parse_hex(match.get("data", "")) if isinstance(match.get("data"), str) else b""
                if not match_data:
                    errors.append(f"{path}.match.data must contain at least one hex byte")
                mask = match.get("mask")
                if mask is not None:
                    mask_data = parse_hex(mask) if isinstance(mask, str) else b""
                    if not isinstance(mask, str) or len(mask_data) != len(match_data):
                        errors.append(f"{path}.match.mask must encode exactly {len(match_data)} bytes")
            except ProtocolError as exc:
                errors.append(f"{path}.match: {exc}")
        _validate_decode(frame.get("decode"), None, f"{path}.decode", errors)


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
    _validate_framing(protocol.get("framing"), errors)
    _validate_passive_frames(protocol.get("frames"), errors)
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
