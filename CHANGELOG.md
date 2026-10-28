# Changelog

All notable user-facing changes are documented here. This project follows the Keep a Changelog format; versions follow Semantic Versioning where practical.

## [Unreleased]

### Added

- `gbuds capabilities` (also `gbuds specifications`) to report model-specific declared hardware features and Gbuds command coverage in text or JSON without opening an RFCOMM connection.
- `gbuds update` to check published GitHub releases and install a digest-verified wheel into an active virtual environment on explicit request.
- Uninstallation instructions for pipx and virtual-environment installs.

## [0.1.0b1] - 2026-10-28

### Added

- Offline status regression fixtures for Galaxy Buds+, Buds Live, Buds Pro, Buds2, Buds2 Pro, and Buds FE.
- Explicit ambiguity handling when multiple Galaxy Buds are available, consistent global options, and model-specific ambient-volume validation.
- Recognition and declared capability metadata for Galaxy Buds3 FE, Buds4, and Buds4 Pro.
- Automatic selection now ignores disconnected devices that are not paired.
- Release-focused documentation for requirements, installation, usage, device coverage, architecture, protocol boundaries, troubleshooting, development, and security.
- A least-privilege CI workflow, package metadata, and public bug-report form.

### Changed

- Corrected Galaxy Buds3 capability metadata against GalaxyBudsClient: Ambient Sound is declared with maximum level 2; Adaptive mode and Blade Lights are Pro-only.
- Normalized unavailable zero case readings in `watch` output to match `battery` output.
- Hardened SDP parsing against truncated lengths, invalid UUID/boolean sizes, and excessive nesting.

### Fixed

- `watch` now handles RFCOMM EOF without a busy loop and treats status event messages as passive inbound telemetry.

[Unreleased]: https://github.com/JessVolet/gbuds-cli/compare/v0.1.0b1...HEAD
[0.1.0b1]: https://github.com/JessVolet/gbuds-cli/releases/tag/v0.1.0b1
