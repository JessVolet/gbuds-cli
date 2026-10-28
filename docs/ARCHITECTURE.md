# Architecture

Gbuds is a small Python package with a CLI boundary, a protocol/client layer, and interchangeable Linux Bluetooth transports. The transport passes raw RFCOMM bytes; packet framing, message interpretation, and model capability checks live above it.

## Components

| Component | Responsibility |
| --- | --- |
| `src/gbuds/cli.py` | Parse commands/options, select a device, enforce model capability gates, and format text or JSON. |
| `src/gbuds/client.py` | Own an RFCOMM session, perform the manager handshake, process incoming messages, cache status, and expose control/query methods. |
| `src/gbuds/protocol.py` | Define message IDs/enums, build and parse modern SPP packets, validate CRC16-CCITT, decode status, and encode supported commands. |
| `src/gbuds/models.py` | Map Samsung device IDs/names to model codes and declared capabilities. |
| `src/gbuds/transport.py` | Implement direct kernel RFCOMM and optional BlueZ Profile1 transports. |
| `src/gbuds/sdp.py` | Encode/decode the subset of SDP needed to discover RFCOMM service channels. |

## System view

```mermaid
flowchart LR
    User[User / script / status bar] --> CLI[CLI]
    CLI --> Client[BudsClient]
    Client --> Codec[SPP codec and model metadata]
    Client --> Transport{Transport}
    Transport -->|direct| SDP[SDP over L2CAP]
    SDP --> Kernel[Linux Bluetooth RFCOMM socket]
    Transport -->|bluez| Profile[BlueZ Profile1 over D-Bus]
    Profile --> Kernel
    Kernel <--> Buds[Galaxy Buds firmware]
    Buds -->|SPP status/events| Kernel
    Codec --> CLI
```

## Connection and status flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant C as gbuds CLI
    participant B as BudsClient
    participant T as Transport
    participant D as Galaxy Buds

    U->>C: gbuds battery / watch
    C->>C: Select one connected/paired device or require --mac
    C->>B: Create client with detected model code
    B->>T: Connect
    T->>D: Open RFCOMM session
    B->>D: MANAGER_INFO (0x88)
    D-->>B: Status event (usually EXTENDED_STATUS_UPDATED, 0x61)
    B->>B: Parse frame, verify CRC, decode/cache status
    alt one-shot command
        B-->>C: Current battery/status
        C-->>U: Text or JSON result
        C->>T: Close session
    else watch
        loop until interrupted, peer closes, or another event arrives
            D-->>B: Spontaneous status event
            B-->>C: Updated status
            C-->>U: One text/JSON line per changed status
        end
    end
```

`watch` is passive after the initial manager handshake. It does not periodically send a status event ID as a poll request. See [Protocol notes](PROTOCOL.md) for framing and model coverage boundaries.

## Transport selection

- **`direct`** (default): uses Linux `AF_BLUETOOTH` RFCOMM sockets and queries SDP over L2CAP to find Samsung service channels. It can try alternate discovered/fallback channels when a channel is occupied.
- **`bluez`**: registers a client Profile1 service with BlueZ, requests the device profile connection, and reads/writes the RFCOMM file descriptor BlueZ supplies. It requires Python D-Bus and GLib bindings.

An external process may already hold one SPP channel. Gbuds can report the busy channel and use another discovered channel. This does not mean Gbuds controls or owns the external daemon.
