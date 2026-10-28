# Protocol notes

Gbuds communicates with Galaxy Buds over Samsung's Bluetooth Serial Port Profile (SPP) service using RFCOMM. This document describes the implemented modern framing and marks protocol families that are not supported; it is not a complete Samsung protocol specification.

## Modern SPP packet framing

```text
+------+-----------------------+-------+-------------+---------------+------+
| SOM  | 16-bit header (LE)     | MsgId | Payload     | CRC16 (LE)    | EOM  |
+------+-----------------------+-------+-------------+---------------+------+
| 0xFD | size/type/fragment    | 1 B   | variable    | 2 B           | 0xDD |
+------+-----------------------+-------+-------------+---------------+------+
```

- The low 10 bits of the header contain the body size: message ID + payload + two CRC bytes.
- Header bit 12 indicates a response; bit 13 indicates a fragment.
- CRC16-CCITT is calculated over the message ID followed by payload, with polynomial `0x1021` and initial value `0x0000`.
- The two CRC bytes are stored little-endian.
- A packet is discarded if its delimiters, declared length, or checksum are invalid.

The default modern frame uses `0xFD` / `0xDD`. The constants for SMEP framing exist for reference, but the CLI does not negotiate SMEP mode.

## Legacy first-generation header

The first-generation Galaxy Buds (SM-R170) uses a different frame:

```text
0xFE | message type (1 B) | size (1 B) | MsgId | payload | CRC16 (2 B) | 0xEE
```

Gbuds currently parses and emits only the modern two-byte-header format. The presence of legacy constants or a model-name mapping does not provide SM-R170 protocol support.

## Session behavior

After opening RFCOMM, Gbuds sends `MANAGER_INFO` (`0x88`) to establish the manager session. The earbuds then emit status messages; `EXTENDED_STATUS_UPDATED` (`0x61`) is the primary status event. `STATUS_UPDATED` (`0x60`) is also decoded when received, but is an event and is not sent as a polling request.

The `watch` command listens for spontaneous device events after the handshake. It prints the initial cached status and then emits updates when the decoded state changes. A closed RFCOMM socket ends the stream cleanly.

## Model-specific payloads

Status payload layouts vary by model and firmware revision. Gbuds uses the detected model code for fields whose offsets or bit meanings differ, and uses fixtures from GalaxyBudsClient for six model families. Unknown or missing fields should remain unavailable instead of being inferred from another model's payload layout.

The fixtures validate selected status fields only. They do not prove full message coverage, support for every firmware revision, or correctness of mutating commands. See the [device support matrix](DEVICE_SUPPORT.md).

## Reference

Protocol behavior and fixture expectations are cross-checked against [GalaxyBudsClient](https://github.com/timschneeb/GalaxyBudsClient). The fixture files, license, and source paths are documented in the [Gbuds fixture notice](https://github.com/JessVolet/gbuds-cli/blob/main/tests/fixtures/README.md).
