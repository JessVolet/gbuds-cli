# Release guide

This guide prepares a release; it does not publish automatically. The project currently has no configured PyPI publisher or release automation.

For pre-1.0 releases, use a Python-compatible pre-release identifier such as `0.1.0b1` for public testing. Use `0.1.0` only when intentionally declaring the first stable release; subsequent bug fixes should increment the patch component.

## Before cutting a release

- [ ] Choose a version and make sure it is available on the intended distribution channel.
- [ ] Update `project.version` in `pyproject.toml` and move the relevant `CHANGELOG.md` entries under that version with the release date.
- [ ] Review README, device matrix, installation requirements, and known limitations for accurate claims.
- [ ] Ensure the working tree contains only intended changes, then commit them.
- [ ] Confirm the GitHub Actions workflow passes on all supported Python versions.
- [ ] Run the offline checks in [Development](DEVELOPMENT.md).
- [ ] If feasible, perform hardware smoke checks and state the exact models/firmware tested in the release notes.

## Build and inspect artifacts

From a clean checkout at the release commit:

```bash
python3 -m venv .release-venv
. .release-venv/bin/activate
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

This produces a wheel and source archive in `dist/`. The PyPI source archive intentionally excludes the test suite and GPLv3 fixture data; these remain in the GitHub source repository with separate attribution and licensing. Verify installation in a fresh virtual environment and run `gbuds --help`. Keep generated artifacts out of Git unless the repository adopts a deliberate release-artifact policy.

## GitHub Release

1. Create an annotated tag matching the version, for example `v0.1.0b1` for the first beta.
2. Push the commit and tag.
3. Create a GitHub Release from that tag.
4. Add the matching changelog section and attach the wheel/source archive if desired.
5. State the validation scope, especially that only Buds FE and Buds3 have physical tests and that the legacy SM-R170 framing is unsupported.

## Optional PyPI publication

Publish to PyPI only after confirming the package name is available and the project account is configured. Prefer PyPI Trusted Publishing with a reviewed workflow and least-privilege permissions. No publishing workflow is enabled here, so an explicit manual upload would use:

```bash
python -m twine upload dist/*
```

Provide credentials through Twine's secure prompt or a protected CI secret; never commit an API token or paste it into shell history. Test the release by installing the published version in a clean environment before announcing it.

## Rollback

For a GitHub-only release, mark the release as pre-release/yanked or replace it with a corrected release and clearly document the affected version. PyPI releases cannot be deleted or replaced with the same version; publish a new patch version and, if the release is defective, yank the old version through the PyPI project settings.
