# serial_protocol.v1 Format

Use this JSON format for protocol scripts consumed by the PySide6 serial console.

## Top Level

```json
{
  "schema": "serial_protocol.v1",
  "metadata": {},
  "commands": []
}
```

Required fields:

- `schema`: must be `serial_protocol.v1`.
- `metadata`: object describing the protocol and default serial settings.
- `commands`: array of command definitions.

Optional top-level fields:

- `status`: `draft`, `ready`, or `needs_confirmation`.
- `questions`: array of questions that must be answered before the script is authoritative.
- `notes`: free-form implementation notes.

## Metadata

```json
{
  "name": "Example device",
  "version": "1.0",
  "language": "zh-CN",
  "default_baudrate": 115200,
  "serial": {
    "bytesize": 8,
    "parity": "N",
    "stopbits": 1,
    "timeout_ms": 1000
  },
  "encoding": "hex",
  "endianness": "big"
}
```

Recommended defaults only when the protocol does not specify them:

- `default_baudrate`: ask before finalizing if omitted by the source document.
- `bytesize`: 8.
- `parity`: `N`, `E`, `O`, `M`, or `S`.
- `stopbits`: 1, 1.5, or 2.
- `timeout_ms`: 1000.
- `encoding`: `hex` for byte-oriented protocols, `text` for line-oriented protocols.
- `endianness`: `big` unless the protocol states little-endian values.

## Command Object

```json
{
  "id": "read_status",
  "name": "读取状态",
  "role": "host",
  "comment": "查询设备当前工作状态",
  "baudrate": 115200,
  "request": {
    "mode": "hex",
    "data": "01 03 00 00 00 02 C4 0B",
    "terminator": "",
    "original": "01 03 00 00 00 02 C4 0B"
  },
  "response": {
    "mode": "hex",
    "example": "01 03 04 00 01 00 02 2A 32",
    "timeout_ms": 1000,
    "decode": [
      {
        "name": "state",
        "label": "状态",
        "type": "uint16",
        "offset": 3,
        "length": 2,
        "endian": "big",
        "scale": 1,
        "unit": ""
      }
    ]
  },
  "auto_reply": {
    "enabled": true,
    "data": "01 03 04 00 01 00 02 2A 32"
  },
  "checksum": {
    "type": "crc16_modbus",
    "range": "0:-2",
    "byte_order": "little"
  }
}
```

Required command fields:

- `id`: stable lowercase identifier using letters, digits, `_`, or `-`.
- `name`: human-readable button/table label.
- `request.mode`: `hex`, `text`, `utf8`, `ascii`, or `base64`.
- `request.data`: the on-wire payload before the optional terminator.

Recommended command fields:

- `role`: `host` for commands normally sent by the upper computer, `device` for commands normally sent by the lower computer, or `both`.
- `comment`: what the command does and any important constraints.
- `baudrate`: override when this command differs from `metadata.default_baudrate`.
- `request.original`: exact source text from the protocol document when it differs from normalized `data`.
- `response.example`: sample response bytes/text.
- `response.decode`: display conversion rules for returned data.
- `auto_reply`: response used by device-simulator mode when an incoming request matches.

## Decode Field Types

Supported scalar types in the bundled app:

- `uint8`, `int8`
- `uint16`, `int16`
- `uint32`, `int32`
- `float32`
- `bytes`
- `hex`
- `ascii`
- `utf8`

For numeric values:

- `offset` is zero-based byte offset in the full received frame.
- `length` is required unless implied by the type.
- `endian` is `big` or `little`.
- `scale` defaults to 1.
- `offset_value` defaults to 0 and is added after scaling.
- `unit` is appended for display only.

Formula:

```text
display_value = raw_value * scale + offset_value
```

## Checksums

Use `checksum` to document checksum behavior. The bundled app validates structure but does not recompute every possible custom checksum.

Common values:

- `crc16_modbus`
- `crc16_ccitt_false`
- `xor8`
- `sum8`
- `custom`

When the source protocol omits checksum details, set:

```json
{
  "status": "needs_confirmation",
  "questions": [
    "请确认校验算法、多项式、初始值、覆盖范围和输出字节序。"
  ]
}
```

## Matching Rules

Device simulator mode matches incoming request bytes against `request.data`.

- Whitespace in hex strings is ignored.
- `auto_reply.data` is used first when enabled.
- If no auto-reply is defined, `response.example` is used as the fallback reply.
- Commands with variable fields should include `match.prefix`, `match.length`, or `match.regex` notes; ask the user for exact rules before claiming the script is final.
