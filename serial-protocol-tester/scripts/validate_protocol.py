#!/usr/bin/env python3
"""Validate a serial_protocol.v1 JSON script."""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "serial_protocol.v1"
MODES = {"hex", "text", "utf8", "ascii", "base64"}
PARITY = {"N", "E", "O", "M", "S"}
ROLES = {"host", "device", "both"}
DECODE_TYPES = {
    "uint8",
    "int8",
    "uint16",
    "int16",
    "uint32",
    "int32",
    "float32",
    "bytes",
    "hex",
    "ascii",
    "utf8",
}
ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
HEX_RE = re.compile(r"^[0-9a-fA-F\s:,-]*$")


class ValidationError(Exception):
    pass


def fail(path: str, message: str) -> None:
    raise ValidationError(f"{path}: {message}")


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(path, "must be an object")
    return value


def require_array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        fail(path, "must be an array")
    return value


def require_string(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        fail(path, "must be a string")
    if not allow_empty and not value.strip():
        fail(path, "must not be empty")
    return value


def validate_payload(payload: Any, path: str) -> None:
    payload = require_object(payload, path)
    mode = require_string(payload.get("mode"), f"{path}.mode")
    if mode not in MODES:
        fail(f"{path}.mode", f"must be one of {sorted(MODES)}")

    data = require_string(payload.get("data"), f"{path}.data", allow_empty=True)
    if mode == "hex":
        normalized = data.replace("0x", "").replace("0X", "").replace(",", " ").replace(":", " ")
        if not HEX_RE.match(normalized):
            fail(f"{path}.data", "contains non-hex characters")
        digits = "".join(normalized.split())
        if len(digits) % 2:
            fail(f"{path}.data", "hex payload must contain an even number of digits")
    elif mode == "base64":
        try:
            base64.b64decode(data.encode("ascii"), validate=True)
        except Exception as exc:  # noqa: BLE001
            fail(f"{path}.data", f"invalid base64 payload: {exc}")

    if "terminator" in payload and not isinstance(payload["terminator"], str):
        fail(f"{path}.terminator", "must be a string")
    if "original" in payload and not isinstance(payload["original"], str):
        fail(f"{path}.original", "must be a string")


def validate_decode_rule(rule: Any, path: str) -> None:
    rule = require_object(rule, path)
    require_string(rule.get("name"), f"{path}.name")
    dtype = require_string(rule.get("type"), f"{path}.type")
    if dtype not in DECODE_TYPES:
        fail(f"{path}.type", f"must be one of {sorted(DECODE_TYPES)}")

    for key in ("offset", "length"):
        if key in rule and (not isinstance(rule[key], int) or rule[key] < 0):
            fail(f"{path}.{key}", "must be a non-negative integer")
    if dtype not in {"bytes", "hex", "ascii", "utf8"} and "offset" not in rule:
        fail(f"{path}.offset", "is required for numeric decode rules")
    if "endian" in rule and rule["endian"] not in {"big", "little"}:
        fail(f"{path}.endian", "must be big or little")
    if "scale" in rule and not isinstance(rule["scale"], (int, float)):
        fail(f"{path}.scale", "must be numeric")
    if "offset_value" in rule and not isinstance(rule["offset_value"], (int, float)):
        fail(f"{path}.offset_value", "must be numeric")


def validate_command(command: Any, path: str) -> None:
    command = require_object(command, path)
    command_id = require_string(command.get("id"), f"{path}.id")
    if not ID_RE.match(command_id):
        fail(f"{path}.id", "must use only letters, digits, underscore, or hyphen")
    require_string(command.get("name"), f"{path}.name")

    if "role" in command and command["role"] not in ROLES:
        fail(f"{path}.role", f"must be one of {sorted(ROLES)}")
    if "baudrate" in command:
        baudrate = command["baudrate"]
        if not isinstance(baudrate, int) or baudrate <= 0:
            fail(f"{path}.baudrate", "must be a positive integer")

    validate_payload(command.get("request"), f"{path}.request")

    if "response" in command:
        response = require_object(command["response"], f"{path}.response")
        if "mode" in response and response["mode"] not in MODES:
            fail(f"{path}.response.mode", f"must be one of {sorted(MODES)}")
        if "example" in response:
            mode = response.get("mode", command["request"].get("mode"))
            validate_payload({"mode": mode, "data": response["example"]}, f"{path}.response.example")
        if "timeout_ms" in response and (not isinstance(response["timeout_ms"], int) or response["timeout_ms"] < 0):
            fail(f"{path}.response.timeout_ms", "must be a non-negative integer")
        if "decode" in response:
            for index, rule in enumerate(require_array(response["decode"], f"{path}.response.decode")):
                validate_decode_rule(rule, f"{path}.response.decode[{index}]")

    if "auto_reply" in command:
        auto_reply = require_object(command["auto_reply"], f"{path}.auto_reply")
        if "enabled" in auto_reply and not isinstance(auto_reply["enabled"], bool):
            fail(f"{path}.auto_reply.enabled", "must be a boolean")
        if auto_reply.get("enabled", True):
            data = require_string(auto_reply.get("data"), f"{path}.auto_reply.data", allow_empty=True)
            mode = command.get("response", {}).get("mode", command["request"].get("mode"))
            validate_payload({"mode": mode, "data": data}, f"{path}.auto_reply.data")


def validate(data: Any) -> None:
    root = require_object(data, "$")
    if root.get("schema") != SCHEMA:
        fail("$.schema", f"must be {SCHEMA!r}")

    metadata = require_object(root.get("metadata"), "$.metadata")
    if "default_baudrate" in metadata:
        baudrate = metadata["default_baudrate"]
        if not isinstance(baudrate, int) or baudrate <= 0:
            fail("$.metadata.default_baudrate", "must be a positive integer")

    if "serial" in metadata:
        serial_settings = require_object(metadata["serial"], "$.metadata.serial")
        if "bytesize" in serial_settings and serial_settings["bytesize"] not in {5, 6, 7, 8}:
            fail("$.metadata.serial.bytesize", "must be 5, 6, 7, or 8")
        if "parity" in serial_settings and serial_settings["parity"] not in PARITY:
            fail("$.metadata.serial.parity", f"must be one of {sorted(PARITY)}")
        if "stopbits" in serial_settings and serial_settings["stopbits"] not in {1, 1.5, 2}:
            fail("$.metadata.serial.stopbits", "must be 1, 1.5, or 2")
        if "timeout_ms" in serial_settings:
            timeout = serial_settings["timeout_ms"]
            if not isinstance(timeout, int) or timeout < 0:
                fail("$.metadata.serial.timeout_ms", "must be a non-negative integer")

    commands = require_array(root.get("commands"), "$.commands")
    if not commands:
        fail("$.commands", "must contain at least one command")

    seen: set[str] = set()
    for index, command in enumerate(commands):
        validate_command(command, f"$.commands[{index}]")
        command_id = command["id"]
        if command_id in seen:
            fail(f"$.commands[{index}].id", "must be unique")
        seen.add(command_id)

    if root.get("status") == "needs_confirmation":
        questions = require_array(root.get("questions", []), "$.questions")
        if not questions:
            fail("$.questions", "must list unresolved questions when status is needs_confirmation")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", type=Path, help="Path to a serial_protocol.v1 JSON file")
    args = parser.parse_args(argv)

    try:
        data = json.loads(args.script.read_text(encoding="utf-8"))
        validate(data)
    except FileNotFoundError:
        print(f"ERROR: file not found: {args.script}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}", file=sys.stderr)
        return 2
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"OK: {args.script} is a valid {SCHEMA} script")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
