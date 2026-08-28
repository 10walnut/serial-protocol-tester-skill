---
name: serial-protocol-tester
description: Convert serial communication protocol documents into validated protocol scripts for a PySide6 host/device serial test console, especially for upper/lower computer debugging.
---

# Serial Protocol Tester

Use this skill when the user needs to turn a serial communication protocol into a runnable test script, or when they need help debugging communication between an upper computer (host/controller) and a lower computer (device/target).

## Outcome

Produce a `serial_protocol.v1` JSON script that can be loaded by the bundled PySide6 serial console. The script should preserve the original command bytes/text, command comments, serial settings, expected response examples, auto-reply behavior, and response decoding rules.

When the user uploads or pastes a protocol document:

- Extract serial settings: baud rate, byte size, parity, stop bits, timeout, byte order, and framing.
- Extract every command with a stable `id`, display `name`, original request data, comment, expected response, and response decoding fields.
- Capture checksum/CRC information when it is defined, including algorithm, covered byte range, initial value, polynomial, xor-out, reflection, and output byte order.
- Mark unresolved protocol details with `status: "needs_confirmation"` and a concise `questions` array instead of silently inventing bytes or formulas.
- Validate the finished JSON with `scripts/validate_protocol.py` before presenting it as ready for the console.

Ask the user before finalizing when missing information changes on-wire bytes or parsing behavior. Important examples are checksum algorithms, byte order, variable-length framing, escape rules, command IDs, required terminators, default baud rate, and how returned bytes map to values. If the missing information is only a label or a display note, use a conservative placeholder and flag it in the script.

## Protocol Script Format

Read `references/protocol-script-format.md` before generating or editing a script. Follow the documented schema rather than creating an ad hoc format.

The core shape is:

```json
{
  "schema": "serial_protocol.v1",
  "metadata": {
    "name": "Device protocol",
    "default_baudrate": 115200,
    "serial": {
      "bytesize": 8,
      "parity": "N",
      "stopbits": 1,
      "timeout_ms": 1000
    }
  },
  "commands": []
}
```

## PySide6 Console

The bundled app in `assets/pyside6-serial-console/` loads the generated JSON and provides:

- Host mode for sending protocol commands to a device or device simulator.
- Device mode for listening on a serial port and auto-replying to matched requests.
- `loop://` self-test mode through pyserial.
- Serial/virtual COM port opening with the configured baud rate.
- Command table columns for original command data, comments, baud rate, and response conversion.
- TX/RX log with decoded response fields.

The app cannot create kernel-level COM ports by itself. For testing another independent Windows application through two COM ports, the user needs a paired virtual serial driver such as com0com, a USB serial loopback, or vendor-provided virtual ports. The console can then open one side of the pair while the user's application opens the other.

## Delivery Style

Default user-facing explanations and command comments to Chinese when the user works in Chinese. Include English labels or bilingual summaries when the user asks for public documentation, GitHub publishing, or mixed-language handoff.
