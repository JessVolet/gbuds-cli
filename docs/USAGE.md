# Usage

## Device selection and global options

Every command accepts these options either before or after the subcommand:

| Option | Purpose |
| --- | --- |
| `--mac ADDRESS` | Select a specific paired device by Bluetooth address. |
| `--json` | Emit machine-readable JSON. `watch --json` emits one JSON object per line. |
| `--transport direct\|bluez` | Select the direct RFCOMM socket (default) or BlueZ Profile transport. |
| `--channel NUMBER` | Force an RFCOMM channel with the direct transport. Normally SDP discovery is used. |

Without `--mac`, Gbuds chooses a single connected Galaxy Buds device. If none is connected, it can choose a single paired device. If multiple candidates exist at the selected priority, it exits with an ambiguity error; it never silently chooses the first device. For seamless manual switching, keep only the desired pair connected or provide its address.

```bash
gbuds --mac AA:BB:CC:DD:EE:FF battery
gbuds battery --mac AA:BB:CC:DD:EE:FF --json
gbuds --json info
```

Automatic discovery depends on BlueZ D-Bus Python bindings. Use `--mac` when those bindings are unavailable; see [Installation](INSTALLATION.md).

## Commands

| Command | Syntax | Notes |
| --- | --- | --- |
| `update` | `gbuds update [--install] [--prerelease]` | Checks published GitHub releases. Installation is opt-in and requires an active virtual environment. |
| `capabilities` | `gbuds capabilities` | Reports model-declared features and Gbuds command coverage from cached BlueZ metadata; does not connect to the earbuds. `specifications` is an alias. |
| `info` | `gbuds info` | Shows model, firmware, transport, capabilities, and telemetry when available. |
| `battery` | `gbuds battery` | Reads battery, placement, ANC, EQ, and touchpad status. `status` is an alias. |
| `anc` | `gbuds anc [on\|off\|ambient\|adaptive\|toggle]` | Changes noise control. Default action is `toggle`; supported modes depend on the model. |
| `eq` | `gbuds eq [normal\|bass\|soft\|dynamic\|clear\|treble]` | Reads the current preset if omitted; otherwise changes it. |
| `ambient-volume` | `gbuds ambient-volume LEVEL` | Sets ambient amplification from zero up to the model-specific maximum. |
| `voice-detect` | `gbuds voice-detect on\|off` | Toggles conversation detection on capable models. |
| `lights` | `gbuds lights off\|steady\|fade\|blink` | Controls Blade Lights on Galaxy Buds3 Pro only. |
| `find` | `gbuds find [left\|right\|both\|stop]` | Locates earbuds acoustically; default target is `both`. |
| `touchpad` | `gbuds touchpad lock\|unlock` | Locks or unlocks touch controls. |
| `watch` | `gbuds watch [--interval SECONDS]` | Keeps one RFCOMM session open and listens for device events. |
| `connect` / `disconnect` | `gbuds connect` / `gbuds disconnect` | Changes host-level Bluetooth connection state through BlueZ D-Bus. |

Hardware-dependent commands are rejected when the detected model declares the feature unsupported. A capability declaration is not a guarantee of physical validation; consult the [support matrix](DEVICE_SUPPORT.md).

`gbuds capabilities --json` returns the detected device, declared noise-control modes, per-feature device support, and Gbuds command coverage. A feature can be marked `unknown` when the model is unidentified or the model table does not classify it. This command uses cached Bluetooth metadata and does not require an active RFCOMM connection. Automatic model detection requires BlueZ D-Bus; otherwise, output may be unknown.

`gbuds update` checks the latest published stable GitHub release without changing the installation. Use `--prerelease` to include beta releases. Add `--install` to install a newer release; it downloads the official wheel, verifies its SHA-256 digest from GitHub's release metadata, and runs pip only inside the active virtual environment. System Python installs are refused. The check contacts GitHub and does not send Bluetooth addresses or earbud telemetry. `gbuds update --json` provides machine-readable check results.

## JSON and scripts

`--json` is useful for scripts. Battery output includes `success`, battery values, placement, noise-control mode, equalizer, and touchpad lock state:

```bash
gbuds battery --json | jq '.battery.left, .battery.right, .noise_control'
```

`watch --json` emits an initial status snapshot and then emits another line when new device telemetry changes the cached state. It is a passive event stream; the interval controls how long each receive waits, not how often a status request is sent.

```bash
gbuds watch --json --interval 1
```

Stop the stream with `Ctrl+C`. If the RFCOMM peer closes the socket, the command exits instead of spinning.

## Status-bar example

For a widget that consumes newline-delimited JSON, keep the process running and map the emitted fields in the widget configuration. A one-shot command is more appropriate for a polling widget:

```bash
gbuds battery --json
```

For Waybar's continuous custom-module behavior, use its documented `exec`/`return-type` streaming configuration and adapt the `text`/`tooltip` fields to the JSON schema supported by your installed Waybar version. Gbuds emits device data; it does not format a Waybar-specific `text` property.

## Sensitive output

`gbuds info --json` includes the device Bluetooth address and may include earbud and case serial numbers. Treat the output as identifying information and redact those fields before sharing logs or issue reports. `battery --json` does not include serial numbers.
