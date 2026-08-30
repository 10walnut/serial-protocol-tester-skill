---
name: serial-protocol-tester
description: Convert uploaded serial communication specifications into validated, single-language serial_protocol.v1 JSON scripts and test them with the bundled PySide6 host/device simulator. Use for serial protocol extraction, variable frame formulas, command/response scripting, stream framing, field decoding, checksums, and upper/lower computer communication testing.
---

# Serial Protocol Tester

Turn a user's serial communication document, table, sample frames, or written description into an executable protocol script for the bundled tester.

## Workflow

1. Read all protocol material supplied by the user. Preserve byte order, frame boundaries, checksums, timing, baud rate, and value scaling exactly when they are stated.
2. Identify missing facts that would change transmitted bytes or decoded values. Ask about those facts instead of guessing. Examples include checksum coverage, byte order, signedness, response length, and whether examples are hexadecimal or text.
3. Determine the output language from the user's request or the dominant language of the source. Produce only that language in the JSON names, descriptions, labels, purposes, and enum values. Do not combine translations with slashes and do not add parallel `*_zh`/`*_en` content unless the user explicitly asks for a bilingual protocol file.
4. Create one `serial_protocol.v1` JSON file. Read [references/protocol-script-format.md](references/protocol-script-format.md) for the schema, variable formulas, stream framing, checksums, field types, and examples.
5. Give every command a stable `id`, source-faithful name, original frame template, useful description, and response definition. Add `purpose` to every field so the console can explain what each byte or byte range does.
6. When a request contains date, time, calibration, sensor, address, setpoint, or other values that are not fixed by the source, define `variables` and declarative `encode` fields instead of inventing one concrete command. Put the documented conversion in `formula`, such as `round(reference_weight_g * 10)`. Use `system.year` through `system.millisecond` as defaults when the protocol calls for the computer's current time.
7. Define top-level `framing` whenever a byte stream uses headers and lengths. Define unsolicited or repeated data under `frames`; use one reusable definition for repeated history records rather than duplicating the same field explanation for every record.
8. Run `scripts/validate_protocol.py <protocol.json>`. Fix every error before presenting the script.
9. Tell the user to load the resulting JSON into the bundled PySide6 console in `assets/pyside6-serial-console/`. Use internal simulation for a no-hardware check, or a COM port/serial URL for real or externally paired communication.

## Interpretation Rules

- Treat whitespace in hexadecimal frames as presentation only.
- Do not invent checksum bytes. Configure a supported checksum when its algorithm and coverage are known; otherwise keep the complete fixed frame and record the uncertainty in the command notes.
- Field offsets are zero-based byte offsets in the received frame.
- Frame-template and encode offsets are absolute zero-based offsets in the complete frame before an appended checksum.
- Use `enum` only for explicit mappings from the protocol. Keep raw numeric output available.
- Use `scale` and `offset_value` for engineering-unit conversion: `display = raw * scale + offset_value`.
- Formula results are raw encoded values. Keep formulas auditable and limited to variables, numeric constants, arithmetic, and the supported `round`, `int`, `abs`, `min`, and `max` functions.
- Cover every meaningful transmitted and received byte with `decode` or `encode` metadata. If the source does not define a byte, label it as unknown instead of guessing its purpose.
- A normal user-space application cannot create a Windows COM device without a virtual-port driver. The bundled internal transport is process-local. The console can invoke an already installed com0com `setupc.exe` through UAC to create a pair; it must not silently download or install a kernel driver. For testing another application, connect the two applications through that pair or a physical serial pair.

## Deliverables

Return the validated JSON protocol script, a short note listing any assumptions, and the relevant launch command. Do not modify or publish an external repository unless the user separately authorizes that action.
