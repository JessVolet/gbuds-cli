# Troubleshooting

## No Galaxy Buds device was detected

Confirm that BlueZ is running, the adapter is powered, and the earbuds are paired. Automatic discovery needs Python D-Bus bindings. If those are absent, specify the address:

```bash
gbuds --mac AA:BB:CC:DD:EE:FF battery
```

See [Installation](INSTALLATION.md) for optional D-Bus dependencies.

## More than one pair is connected

Gbuds intentionally refuses to pick a device arbitrarily. Select the target by address:

```bash
gbuds --mac AA:BB:CC:DD:EE:FF battery
```

When only one pair is connected, it is selected automatically.

## Device or resource busy / an SPP channel is occupied

Another process (for example GalaxyBudsClient or a vendor control daemon) may hold an RFCOMM channel. The direct transport tries discovered channels and can use an alternate one. A notice such as `External daemon detected on channel [27]; active via channel 20` means the selected Gbuds session connected on channel 20 while channel 27 was already busy.

Avoid running two applications that send control commands to the same earbuds at the same time. If connection still fails, close the other controller and retry. Do not kill unrelated processes based only on a busy-channel notice.

## No battery update received

- Ensure the device is connected and try again.
- Check that another application is not holding the only available SPP channel.
- Try a specific device address with `--mac`.
- Try `--transport bluez` only if Python D-Bus and GLib bindings are installed.
- Capture the exact error and firmware/model information. Redact addresses and serial numbers before sharing.

## A command is rejected as unsupported

Capabilities vary by model. `ambient`, `adaptive`, `voice-detect`, Blade Lights, and ambient-volume limits are checked against the detected model. A recognized model may still have incomplete protocol support. Review the [support matrix](DEVICE_SUPPORT.md) before retrying; do not bypass the capability guard by sending raw packets.

## `watch` exits or stops printing

`watch` is passive after its handshake: it prints the initial snapshot and then waits for spontaneous changes from the earbuds. No new line is expected while the reported state stays unchanged. If the device closes RFCOMM, Gbuds exits the stream cleanly. Run it again after reconnecting the earbuds.

## Quickshell, DMS, or a status bar crashes on Bluetooth reconnect

Gbuds is a short-lived CLI process for one-shot commands; it does not own or manage Quickshell/DMS. If `gbuds battery` succeeds while the desktop shell crashes, inspect the shell's user journal and crash report separately. For a DMS setup using OrbitBluetooth, temporarily disabling that plugin is a useful isolation step. A correlation with a Bluetooth/audio reconnect does not by itself prove the plugin is the cause.

## Bluetooth permission errors

Run Gbuds as the normal logged-in user. Pair through the desktop Bluetooth settings or `bluetoothctl`, and check the distribution's BlueZ/policy configuration. Do not use `sudo` as the default workaround: it can create root-owned caches and still may not address the actual socket or D-Bus policy.
