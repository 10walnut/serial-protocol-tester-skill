# `serial_protocol.v1` format

The protocol script is UTF-8 JSON. Human-readable protocol content must use the language requested by the user. Do not combine Chinese and English in one value and do not emit duplicate language fields unless the user explicitly requests a bilingual protocol file.

## Top-level object

```json
{
  "schema_version": "serial_protocol.v1",
  "name": "设备串口协议",
  "description": "协议说明",
  "serial": {
    "defaults": {
      "baudrate": 115200,
      "bytesize": 8,
      "parity": "N",
      "stopbits": 1,
      "timeout_ms": 200
    }
  },
  "framing": {},
  "frames": [],
  "commands": []
}
```

Allowed parity values are `N`, `E`, `O`, `M`, and `S`. `bytesize` is 5 through 8. `stopbits` is `1`, `1.5`, or `2`.

## Command and fixed frame

`request` is required. `response` may be omitted for one-way commands or when the source gives a response layout but no safe concrete mock response.

```json
{
  "id": "read_temperature",
  "name": "读取温度",
  "description": "读取当前温度。",
  "baudrate": 9600,
  "request": {
    "encoding": "hex",
    "data": "01 03 00 00 00 01",
    "purpose": "读取温度寄存器",
    "checksum": {
      "algorithm": "modbus_crc16",
      "append": true,
      "start": 0,
      "end": null,
      "byte_order": "little"
    },
    "decode": []
  },
  "response": {
    "encoding": "hex",
    "data": "01 03 02 00 FA",
    "checksum": {"algorithm": "modbus_crc16", "append": true, "byte_order": "little"},
    "decode": []
  },
  "auto_reply": true
}
```

Frame `encoding` is `hex`, `ascii`, or `utf8`. If `checksum.append` is true, `data` excludes the checksum. The console computes it over `[start:end]` and appends it. Supported algorithms are `sum8`, `xor8`, and `modbus_crc16`.

## Variable input and formulas

Use variables whenever the protocol does not prescribe one fixed transmitted value. The console opens an input form before sending, writes each formula result into the frame template, then recalculates the checksum.

```json
"request": {
  "encoding": "hex",
  "data": "AA 55 07 06 00 00 00 00 00 00",
  "variables": [
    {
      "name": "channel",
      "label": "通道",
      "purpose": "选择要标定的重量通道",
      "type": "integer",
      "default": 0,
      "choices": {"0": "A 通道", "1": "B 通道"}
    },
    {
      "name": "reference_weight_g",
      "label": "实际砝码重量",
      "purpose": "放置在目标通道上的砝码重量",
      "type": "number",
      "default": 500.0,
      "min": 0.1,
      "max": 100000.0,
      "decimals": 1,
      "unit": "g"
    }
  ],
  "encode": [
    {
      "name": "channel",
      "label": "通道",
      "purpose": "0 和 1 分别表示 A、B 通道",
      "offset": 4,
      "length": 1,
      "type": "uint8",
      "formula": "channel"
    },
    {
      "name": "reference_weight",
      "label": "协议标准重量",
      "purpose": "把克换算为 0.1g 计数",
      "offset": 5,
      "length": 4,
      "type": "int32",
      "byte_order": "little",
      "formula": "round(reference_weight_g * 10)",
      "scale": 0.1,
      "unit": "g"
    }
  ],
  "checksum": {"algorithm": "sum8", "append": true, "start": 2}
}
```

Variable types are `integer` and `number`. Optional keys are `min`, `max`, `decimals`, `unit`, and `choices`. Date/time variables may use these dynamic defaults:

- `system.year`, `system.month`, `system.day`
- `system.hour`, `system.minute`, `system.second`, `system.millisecond`

Formula results are raw values encoded into the specified numeric type. Formulas may contain declared variables, numeric constants, parentheses, `+ - * / // % **`, and `round`, `int`, `abs`, `min`, or `max`. Arbitrary Python, attributes, imports, and file or network access are rejected.

## Field definitions

Both `decode` and `encode` use absolute, zero-based byte offsets in the full frame. Add a source-faithful `purpose` for every meaningful field.

```json
{
  "name": "temperature",
  "label": "温度",
  "purpose": "设备测得的当前温度",
  "offset": 3,
  "length": 2,
  "type": "int16",
  "byte_order": "little",
  "scale": 0.1,
  "offset_value": 0,
  "unit": "°C",
  "enum": {"-1": "传感器故障"}
}
```

Supported field types are `hex`, `ascii`, `utf8`, `uint8`, `int8`, `uint16`, `int16`, `uint32`, `int32`, and `float32`. The detail table shows direction, byte positions, purpose, raw bytes, byte order, arithmetic, scaled result, and checksum validation.

## Length-based stream framing

Use top-level `framing` when serial reads can contain partial or concatenated frames.

```json
"framing": {
  "header": "AA 55",
  "command_offset": 2,
  "length_offset": 3,
  "length_size": 1,
  "length_byte_order": "big",
  "payload_offset": 4,
  "checksum_length": 1,
  "length_adjustment": 0,
  "max_frame_length": 260,
  "checksum": {"algorithm": "sum8", "start": 2}
}
```

The total frame size is `payload_offset + payload_length + checksum_length + length_adjustment`. The console searches for the header, preserves partial data, and repeatedly extracts complete frames. It does not use an idle-time gap when this definition exists.

## Unsolicited and repeated frames

Use `frames` for device-originated data that is not a fixed response to one command.

```json
"frames": [
  {
    "id": "measurement",
    "name": "实时或历史采样数据",
    "description": "实时和历史记录共用一种结构。",
    "purpose": "传输采样时间和传感器数据",
    "repeat_group": "measurement",
    "match": {"offset": 2, "data": "10", "mask": "FF"},
    "decode": []
  }
]
```

The first matching definition is used. `repeat_group` documents that repeated records share one structure; the application keeps every raw frame in the traffic log but replaces the lower detail view with the latest values instead of repeating explanations.

## Matching variable requests in device mode

`match_mask` has the same length as the fully encoded request. Bits set to 1 must match; zero bits ignore variable and checksum bytes.

```json
"match_mask": "FF FF FF FF 00 00 00"
```

Without a mask, every encoded byte must match. When several commands match, the first command is used.
