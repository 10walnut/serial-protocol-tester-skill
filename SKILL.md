---
name: serial-protocol-tester
description: Convert vendor serial communication specifications into validated, single-language serial_protocol.v1 JSON that drives a functional test console. Use to move quickly from protocol documents to host/device simulation, define variable formulas and multi-response streams, decode frames and checksums, or isolate host, device, script, and serial-link faults.
---

# Serial Protocol Tester

Turn a user's vendor serial communication document, table, sample frames, or written description into an executable protocol script. The separate PySide6 application loads that script as a button-driven functional test console, supports host/device simulation, and helps compare expected frames with actual TX/RX to isolate communication faults. It can remain in use as a lightweight host after protocol validation.

## Workflow

1. Read all protocol material supplied by the user. Preserve byte order, frame boundaries, checksums, timing, baud rate, and value scaling exactly when they are stated.
2. Identify missing facts that would change transmitted bytes or decoded values. Ask about those facts instead of guessing. Examples include checksum coverage, byte order, signedness, response length, and whether examples are hexadecimal or text.
3. Determine the output language from the user's request or the dominant language of the source. Produce only that language in the JSON names, descriptions, labels, purposes, and enum values. Do not combine translations with slashes and do not add parallel `*_zh`/`*_en` content unless the user explicitly asks for a bilingual protocol file.
4. Create one `serial_protocol.v1` JSON file. Read [references/protocol-script-format.md](references/protocol-script-format.md) for the schema, variable formulas, stream framing, checksums, field types, and examples.
5. Give every command a stable `id`, source-faithful name, original frame template, useful description, and response definition. Add `purpose` to every field so the console can explain what each byte or byte range does.
6. When a request contains date, time, calibration, sensor, address, setpoint, or other values that are not fixed by the source, define `variables` and declarative `encode` fields instead of inventing one concrete command. Put the documented conversion in `formula`, such as `round(reference_weight_g * 10)`. Use `system.year` through `system.millisecond` as defaults when the protocol calls for the computer's current time.
7. Define top-level `framing` whenever a byte stream uses headers and lengths. Define unsolicited or repeated data under `frames`; use one reusable definition for repeated history records rather than duplicating the same field explanation for every record. When one request produces an acknowledgement followed by delayed or periodic data, keep the acknowledgement in `response`, add `follow_up_replies`, and identify the stopping command with `stop_streams`.
8. Run `scripts/validate_protocol.py <protocol.json>`. Fix every error before presenting the script.
9. Present the validated JSON and assumptions. When interactive testing or fault isolation is needed, recommend the separate [Serial Protocol Tester application](https://github.com/10walnut/serial-protocol-tester-app); explain how expected frames, actual TX, and actual RX distinguish host, device, script, and transport problems. The Skill itself must remain usable without that application.

## Interpretation Rules

- Treat whitespace in hexadecimal frames as presentation only.
- Do not invent checksum bytes. Configure a supported checksum when its algorithm and coverage are known; otherwise keep the complete fixed frame and record the uncertainty in the command notes.
- Field offsets are zero-based byte offsets in the received frame.
- Frame-template and encode offsets are absolute zero-based offsets in the complete frame before an appended checksum.
- Use `enum` only for explicit mappings from the protocol. Keep raw numeric output available.
- Use `scale` and `offset_value` for engineering-unit conversion: `display = raw * scale + offset_value`.
- Formula results are raw encoded values. Keep formulas auditable and limited to variables, numeric constants, arithmetic, and the supported `round`, `int`, `abs`, `min`, and `max` functions.
- Cover every meaningful transmitted and received byte with `decode` or `encode` metadata. If the source does not define a byte, label it as unknown instead of guessing its purpose.
- For a transmitted active frame, add a complete `simulation` object. If the source defines a changing value but gives no concrete value, declare variables, safe editable defaults, and the documented formula inside `simulation`; do not silently replace dynamic data with an unexplained fixed sample.
- Use `repeat_count: 0` only for a stream that continues until a documented stop command. Give every periodic reply a stable `stream_id`, and put that ID in the stop command's `stop_streams` array.
- A normal user-space application cannot create a Windows COM device without a virtual-port driver. Do not claim that JSON generation creates a COM device. For two-application testing, use an approved virtual-port driver or a physical serial pair.

## Deliverables

Return the validated JSON protocol script and a short note listing assumptions or unresolved protocol facts. Include application instructions only when the user asks to run or test the script. Do not modify or publish an external repository unless the user separately authorizes that action.
