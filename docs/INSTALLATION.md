# Installation and requirements

## Platform requirements

- Linux with a kernel that provides Bluetooth RFCOMM sockets (`AF_BLUETOOTH` / `BTPROTO_RFCOMM`).
- BlueZ (`bluetoothd`) and a working Bluetooth adapter.
- Earbuds paired with the host before first use.
- Python 3.10 or newer.

The core package has **no mandatory third-party Python dependencies**. `pipx` is recommended to install the CLI in an isolated environment.

There is intentionally no `requirements.txt`: `pyproject.toml` is the source of truth for Python package requirements. Optional D-Bus/GLib integrations use distribution-provided system bindings described below.

There is intentionally no `requirements.txt`: `pyproject.toml` is the source of truth for Python package requirements. Optional D-Bus/GLib integrations use distribution-provided system bindings described below.

There is intentionally no `requirements.txt`: `pyproject.toml` is the source of truth for Python package requirements. Optional D-Bus/GLib integrations use distribution-provided system bindings described below.

If `pipx` is not installed, use your distribution package manager. For example:

```bash
# Fedora
sudo dnf install pipx

# Debian / Ubuntu
sudo apt install pipx
```

Then make sure its app directory is on `PATH`:

```bash
pipx ensurepath
```

Open a new shell if `gbuds` is not found after installation. See the [pipx installation guide](https://pipx.pypa.io/stable/how-to/install-pipx/) for current distribution-specific steps.

### Optional BlueZ D-Bus integration

The following features need the operating system's Python D-Bus bindings:

- Automatic device discovery and BlueZ-cached metadata.
- `connect` and `disconnect`.
- `--transport bluez`, which also needs GLib/PyGObject.

Install the bindings from your distribution and make them visible to the Python environment running Gbuds. Package names vary; common names are `python3-dbus` and `python3-gi` on Debian/Ubuntu, `python3-dbus` and `python3-gobject` on Fedora, and `python-dbus` and `python-gobject` on Arch Linux. BlueZ is commonly packaged as `bluez`.

With `pipx`, `--system-site-packages` lets its virtual environment see distribution-provided Python bindings, provided pipx uses the Python interpreter those bindings target:

```bash
pipx install --system-site-packages git+https://github.com/JessVolet/gbuds-cli.git
```

Without D-Bus Python bindings, pass `--mac` explicitly and use the default `direct` transport. BlueZ profile transport and host-level connect/disconnect commands will not be available, and the CLI cannot read BlueZ's cached model metadata. Model-specific decoding and capability checks may therefore be incomplete; install the bindings for reliable model-aware behavior.

## Install from a Git checkout

### pipx (recommended)

```bash
git clone https://github.com/JessVolet/gbuds-cli.git
cd gbuds-cli
pipx install --system-site-packages .
gbuds --help
```

Omit `--system-site-packages` if you do not need the optional D-Bus integration.

### Virtual environment

```bash
git clone https://github.com/JessVolet/gbuds-cli.git
cd gbuds-cli
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
gbuds --help
```

For a source checkout without installation, run `./gbuds --help` from the repository root.

## Bluetooth setup

1. Enable Bluetooth and pair the earbuds using the desktop Bluetooth settings or `bluetoothctl`.
2. Connect one Galaxy Buds model to the host.
3. Run `gbuds info` and `gbuds battery`.
4. If multiple Galaxy Buds are connected, pass `--mac ADDRESS` to choose the target.

Run Gbuds as your normal desktop user. Do not run it with `sudo` as a workaround for Bluetooth permission problems; see [Troubleshooting](TROUBLESHOOTING.md).

## Install a built wheel

Release artifacts are not published automatically by this repository. If a wheel is provided by a release, install it with:

```bash
python -m pip install ./gbuds-<version>-py3-none-any.whl
```

See the [release guide](RELEASE.md) for artifact generation and publication steps.
