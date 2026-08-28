---
name: serial-protocol-tester
description: Convert uploaded serial communication specifications into validated serial_protocol.v1 JSON scripts and use them with the bundled PySide6 host/device simulator. Use for serial protocol extraction, command/response scripting, frame decoding, checksums, and upper/lower computer communication testing.
---

# Serial Protocol Tester

Turn a user's serial communication document, table, sample frames, or written description into an executable protocol script for the bundled tester.

## Workflow

1. Read all protocol material supplied by the user. Preserve byte order, frame boundaries, checksums, timing, baud rate, and value scaling exactly when they are stated.
2. Identify missing facts that would change transmitted bytes or decoded values. Ask about those facts instead of guessing. Examples include checksum coverage, byte order, signedness, response length, and whether examples are hexadecimal or text.
3. Create one `serial_protocol.v1` JSON file. Read [references/protocol-script-format.md](references/protocol-script-format.md) for the schema, supported checksums, field types, and examples.
4. Give every command a stable `id`, bilingual or source-faithful name, original request bytes, a useful annotation, and a response definition. Use command-specific serial settings only when they differ from `serial.defaults`.
5. Run `scripts/validate_protocol.py <protocol.json>`. Fix every error before presenting the script.
6. Tell the user to load the resulting JSON into the bundled PySide6 console in `assets/pyside6-serial-console/`. Use internal simulation for a no-hardware check, or a COM port/serial URL for real or externally paired communication.

## Interpretation Rules

- Treat whitespace in hexadecimal frames as presentation only.
- Do not invent checksum bytes. Configure a supported checksum when its algorithm and coverage are known; otherwise keep the complete fixed frame and record the uncertainty in the command notes.
- Field offsets are zero-based byte offsets in the received frame.
- Use `enum` only for explicit mappings from the protocol. Keep raw numeric output available.
- Use `scale` and `offset_value` for engineering-unit conversion: `display = raw * scale + offset_value`.
- A normal user-space application cannot create a Windows COM device without a virtual-port driver. The bundled internal transport is process-local. The console can invoke an already installed com0com `setupc.exe` through UAC to create a pair; it must not silently download or install a kernel driver. For testing another application, connect the two applications through that pair or a physical serial pair.

## Deliverables

Return the validated JSON protocol script, a short note listing any assumptions, and the relevant launch command. Do not modify or publish an external repository unless the user separately authorizes that action.
