# gbuds

`gbuds` is a Linux command-line client and Python library for reading status from and controlling Samsung Galaxy Buds over Bluetooth RFCOMM. It is designed for terminals, scripts, and desktop status bars; it does not require a graphical application.

> **Beta software.** Compatibility is model-specific and still being validated. Only Galaxy Buds FE (SM-R400N) and Galaxy Buds3 (SM-R530) have been physically tested by the maintainer. See the [device support matrix](https://github.com/JessVolet/gbuds-cli/blob/main/docs/DEVICE_SUPPORT.md) before relying on a feature.

## Quick start

Requirements and installation options are in the [installation guide](https://github.com/JessVolet/gbuds-cli/blob/main/docs/INSTALLATION.md).

```bash
gbuds info
gbuds battery
gbuds anc toggle
gbuds eq
gbuds watch --json
```

To uninstall, use `pipx uninstall gbuds` for a pipx install, or activate the virtual environment and run `python -m pip uninstall gbuds` for a pip install. See the [installation guide](https://github.com/JessVolet/gbuds-cli/blob/main/docs/INSTALLATION.md) for details.

Start with `info`, `battery`, and `eq` (without a preset) for read-only inspection. Commands such as `anc`, `eq PRESET`, `ambient-volume`, `touchpad`, and `find` send control messages to the earbuds.

When exactly one Galaxy Buds device is connected, it is selected automatically. If several are connected, select one explicitly:

```bash
gbuds --mac AA:BB:CC:DD:EE:FF battery
```

## What it supports

- Battery, placement, ANC/noise mode, equalizer, and selected device metadata.
- Model-gated controls for noise mode, ambient volume, voice detect, and Buds3 Pro Blade Lights.
- Passive telemetry streaming with `watch`.
- Direct Linux RFCOMM and BlueZ Profile transports.
- JSON output for scripts and widgets.

Recognized model names do not guarantee complete protocol support. The first-generation Galaxy Buds (SM-R170) is identified but its legacy packet framing is not implemented. Several newer models are recognized from GalaxyBudsClient specifications but do not yet have local packet fixtures or physical validation.

## Documentation

| Guide | Contents |
| --- | --- |
| [Installation and requirements](https://github.com/JessVolet/gbuds-cli/blob/main/docs/INSTALLATION.md) | Linux/BlueZ prerequisites, optional D-Bus packages, install from source or pipx |
| [Usage](https://github.com/JessVolet/gbuds-cli/blob/main/docs/USAGE.md) | Commands, device selection, JSON, widget integration, privacy notes |
| [Device support](https://github.com/JessVolet/gbuds-cli/blob/main/docs/DEVICE_SUPPORT.md) | Model capabilities and the difference between recognition, fixtures, and physical testing |
| [Architecture](https://github.com/JessVolet/gbuds-cli/blob/main/docs/ARCHITECTURE.md) | Module boundaries and Mermaid system/connection diagrams |
| [Protocol notes](https://github.com/JessVolet/gbuds-cli/blob/main/docs/PROTOCOL.md) | SPP framing, handshake, passive `watch` behavior, known protocol gaps |
| [Python API](https://github.com/JessVolet/gbuds-cli/blob/main/docs/API.md) | Public client and model API examples |
| [Troubleshooting](https://github.com/JessVolet/gbuds-cli/blob/main/docs/TROUBLESHOOTING.md) | Bluetooth, permissions, channel conflicts, and common errors |
| [Development](https://github.com/JessVolet/gbuds-cli/blob/main/docs/DEVELOPMENT.md) | Local setup, tests, fixtures, and contribution workflow |
| [Contributing](https://github.com/JessVolet/gbuds-cli/blob/main/CONTRIBUTING.md) | Contribution expectations and pull request checklist |
| [Release guide](https://github.com/JessVolet/gbuds-cli/blob/main/docs/RELEASE.md) | Versioning, artifact checks, GitHub Releases, and optional PyPI publication |
| [Changelog](https://github.com/JessVolet/gbuds-cli/blob/main/CHANGELOG.md) | User-visible changes |
| [Security policy](https://github.com/JessVolet/gbuds-cli/blob/main/SECURITY.md) | Reporting security issues and sensitive output |

## Project status

The CLI has offline regression fixtures for six model families and has been physically smoke-tested with Buds FE and Buds3. The current checks do not establish compatibility with every firmware revision or every command. No firmware update, pairing, or account modification is performed by this tool.

## License and acknowledgements

The Gbuds implementation is licensed under the [MIT License](https://github.com/JessVolet/gbuds-cli/blob/main/LICENSE). Protocol research and model specifications are cross-checked against [GalaxyBudsClient](https://github.com/timschneeb/GalaxyBudsClient). The copied protocol fixtures in the source repository have a separate GPLv3 license and attribution in the [fixture notice](https://github.com/JessVolet/gbuds-cli/blob/main/tests/fixtures/README.md).
