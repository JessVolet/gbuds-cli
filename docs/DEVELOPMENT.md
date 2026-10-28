# Development

## Requirements

- Linux and Python 3.10 or newer.
- Git.
- No third-party Python packages are required to run the unit tests.
- BlueZ hardware is only needed for physical Bluetooth checks; the unit suite uses offline fixtures.

## Set up a checkout

```bash
git clone https://github.com/JessVolet/gbuds-cli.git
cd gbuds-cli
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

If you also need automatic BlueZ discovery or the BlueZ Profile transport, install your distribution's D-Bus/PyGObject packages and create the environment with `--system-site-packages`; see [Installation](INSTALLATION.md).

## Checks

Run the offline suite and basic source checks from the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
```

Tests use only Python's standard `unittest` framework. They do not connect to earbuds. A physical check should state the exact model, model code, firmware, transport, commands exercised, and any known limits; never claim all-device support based on one model.

## Protocol fixtures

Fixtures in `tests/fixtures/` are copied from GalaxyBudsClient test data. Preserve their attribution and source path. Add an expected result only when it can be tied to a reference test/specification or a reproducible physical capture. Do not include Bluetooth addresses, device serials, or unrelated user data in fixtures.

## Contribution expectations

- Keep protocol changes model-aware and conservative when payload fields are missing.
- Add a regression case for behavior changes.
- Update the support matrix when recognition, fixture coverage, or physical validation changes.
- Update the changelog for user-visible changes.
- Document limitations instead of claiming unverified support.

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the pull request workflow.
