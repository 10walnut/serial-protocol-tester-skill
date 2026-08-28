# `serial_protocol.v1` format

The protocol script is UTF-8 JSON. It describes fixed request/response commands that can be sent or simulated from the bundled console.

## Top-level object

```json
{
  "schema_version": "serial_protocol.v1",
  "name": "Protocol name",
  "description": "Optional protocol summary",
  "serial": {
    "defaults": {
      "baudrate": 9600,
      "bytesize": 8,
      "parity": "N",
      "stopbits": 1,
      "timeout_ms": 200
    }
  },
  "commands": []
}
```

Allowed parity values are `N`, `E`, `O`, `M`, and `S`. `bytesize` is 5 through 8. `stopbits` is `1`, `1.5`, or `2`.

## Command object

```json
{
  "id": "read_temperature",
  "name": "Read temperature / 读取温度",
  "description": "Read one holding register at address 0x0000",
  "baudrate": 9600,
  "request": {
    "encoding": "hex",
    "data": "01 03 00 00 00 01",
    "checksum": {
      "algorithm": "modbus_crc16",
      "append": true,
      "start": 0,
      "end": null,
      "byte_order": "little"
    }
  },
  "response": {
    "encoding": "hex",
    "data": "01 03 02 00 FA",
    "checksum": {
      "algorithm": "modbus_crc16",
      "append": true,
      "byte_order": "little"
    },
    "decode": []
  },
  "auto_reply": true
}
```

`baudrate` is optional and overrides the default for that command. `request` is required. `response` may be omitted for one-way commands.

Frame `encoding` is one of:

- `hex`: pairs of hexadecimal digits; spaces, tabs, colons, commas, dashes, and `0x` prefixes are accepted.
- `ascii`: ASCII text.
- `utf8`: UTF-8 text.

If `checksum.append` is true, `data` contains the frame without the checksum. The console computes the checksum over the byte slice `[start:end]` and appends it. `start` defaults to zero and `end` defaults to the current frame length.

Supported checksum algorithms:

- `sum8`: sum of covered bytes modulo 256.
- `xor8`: XOR of covered bytes.
- `modbus_crc16`: CRC-16/Modbus, polynomial `0xA001`, initial value `0xFFFF`.

`byte_order` applies to multi-byte checksums and defaults to `little` for Modbus CRC.

## Response decoding

Each item in `response.decode` extracts one value from the received frame.

```json
{
  "name": "temperature",
  "label": "Temperature / 温度",
  "offset": 3,
  "length": 2,
  "type": "uint16",
  "byte_order": "big",
  "scale": 0.1,
  "offset_value": 0,
  "unit": "°C",
  "enum": {
    "0": "Stopped / 停止",
    "1": "Running / 运行"
  }
}
```

Supported types are `hex`, `ascii`, `utf8`, `uint8`, `int8`, `uint16`, `int16`, `uint32`, `int32`, and `float32`. Numeric types require an exact compatible `length`. `byte_order` is `big` or `little`. `scale`, `offset_value`, `unit`, and `enum` are optional.

## Matching requests in device mode

The simulator matches an incoming frame against each fully encoded request. To ignore changing bytes, add `match_mask` to the request. It is a hex byte string of the same length; bits set to 1 must match.

```json
"request": {
  "encoding": "hex",
  "data": "01 06 00 10 00 00",
  "match_mask": "FF FF FF FF 00 00"
}
```

When no mask is present, every byte must match. If multiple entries match, the first command in `commands` is used.
